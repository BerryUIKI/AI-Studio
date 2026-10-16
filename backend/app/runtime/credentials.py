"""
Secure BYOK Credential Manager.

Manages API keys for external cloud providers (OpenAI, Fal.ai, SiliconFlow).
Ensures secrets are stored locally, never exposed in workflow files or logs,
and strictly redacted in all diagnostic and status APIs.
"""

import base64
import json
import logging
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional
import httpx

from app.schemas.cloud import (
    CloudProviderId,
    CloudProviderInfo,
    LLMConfig,
    TestKeyResult,
)
from app.storage.db import get_default_data_dir

logger = logging.getLogger(__name__)


def _is_windows() -> bool:
    return sys.platform == "win32"


def _protect_dpapi(data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    # 0x1 = CRYPTPROTECT_UI_FORBIDDEN
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        "BerryCredential",
        None,
        None,
        None,
        0x1,
        ctypes.byref(blob_out),
    ):
        raise OSError("CryptProtectData failed to encrypt credential payload")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _unprotect_dpapi(data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    # 0x1 = CRYPTPROTECT_UI_FORBIDDEN
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(blob_out),
    ):
        raise OSError("CryptUnprotectData failed to decrypt credential payload")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def redact_key(key: str) -> str:
    """Mask an API key for safe display, preserving prefix and last 4 characters."""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    prefix = key[:3]
    suffix = key[-4:]
    return f"{prefix}...{suffix}"


class CredentialManager:
    """Manages secure persistence and live validation of BYOK cloud API keys."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = data_dir or get_default_data_dir()
        self.creds_file = self.data_dir / "credentials.json"
        self._memory_creds: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.creds_file.is_file():
            try:
                content = self.creds_file.read_text(encoding="utf-8")
                data = json.loads(content)
                if isinstance(data, dict):
                    if data.get("encrypted") and data.get("format") == "dpapi" and "data" in data:
                        raw_bytes = base64.b64decode(data["data"])
                        decrypted = _unprotect_dpapi(raw_bytes).decode("utf-8")
                        unpacked = json.loads(decrypted)
                        if isinstance(unpacked, dict):
                            self._memory_creds = unpacked
                    else:
                        self._memory_creds = data
            except Exception as e:
                logger.warning(f"Error loading credentials from {self.creds_file}: {e}")

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        raw_text = json.dumps(self._memory_creds, indent=2)
        try:
            if _is_windows():
                encrypted_blob = _protect_dpapi(raw_text.encode("utf-8"))
                envelope = {
                    "encrypted": True,
                    "format": "dpapi",
                    "data": base64.b64encode(encrypted_blob).decode("ascii"),
                }
                self.creds_file.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
            else:
                self.creds_file.write_text(raw_text, encoding="utf-8")
                if hasattr(os, "chmod") and os.name != "nt":
                    try:
                        os.chmod(self.creds_file, 0o600)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
            raise OSError(f"Failed to persist credentials: {e}") from e

    def get_key(self, provider_id: CloudProviderId | str) -> Optional[str]:
        """Resolve API key from stored BYOK credentials or environment variable."""
        # 1. Check user-stored BYOK key
        identifier = provider_id.value if isinstance(provider_id, CloudProviderId) else provider_id
        stored = self._memory_creds.get(identifier)
        if stored:
            return stored

        # 2. Check environment variables
        if provider_id == CloudProviderId.OPENAI:
            return os.environ.get("OPENAI_API_KEY")
        elif provider_id == CloudProviderId.FAL:
            return os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")
        elif provider_id == CloudProviderId.SILICONFLOW:
            return os.environ.get("SILICONFLOW_API_KEY")

        return None

    def set_key(self, provider_id: CloudProviderId | str, api_key: str) -> None:
        """Store an API key for a cloud provider."""
        identifier = provider_id.value if isinstance(provider_id, CloudProviderId) else provider_id
        old = self._memory_creds.get(identifier)
        revision_key = f"_revision:{identifier}"
        old_revision = self._memory_creds.get(revision_key)
        revision = self.key_revision(provider_id)
        self._memory_creds[identifier] = api_key.strip()
        if old != api_key.strip():
            self._memory_creds[revision_key] = str(revision + 1)
        try:
            self._save()
        except Exception:
            if old is None:
                self._memory_creds.pop(identifier, None)
            else:
                self._memory_creds[identifier] = old
            if old_revision is None:
                self._memory_creds.pop(revision_key, None)
            else:
                self._memory_creds[revision_key] = old_revision
            raise

    def key_revision(self, provider_id: CloudProviderId | str) -> int:
        """Durable cache namespace for credential replacement without hashing secrets."""
        identifier = provider_id.value if isinstance(provider_id, CloudProviderId) else provider_id
        try:
            return int(self._memory_creds.get(f"_revision:{identifier}", "0"))
        except (ValueError, TypeError):
            return 0

    def delete_key(self, provider_id: CloudProviderId | str) -> None:
        """Remove stored API key."""
        identifier = provider_id.value if isinstance(provider_id, CloudProviderId) else provider_id
        if identifier in self._memory_creds:
            old = self._memory_creds.pop(identifier)
            try:
                self._save()
            except Exception:
                self._memory_creds[identifier] = old
                raise

    def list_providers(self) -> List[CloudProviderInfo]:
        """List cloud providers with capability matrices and redacted keys."""
        providers = [
            CloudProviderInfo(
                id=CloudProviderId.VOLCENGINE,
                name="Volcengine Ark (Beijing)",
                description="Seedream 4.0 single-image generation and reference editing.",
                is_configured=bool(self.get_key(CloudProviderId.VOLCENGINE)),
                redacted_key=redact_key(self.get_key(CloudProviderId.VOLCENGINE) or ""),
                supported_models=["doubao-seedream-4-0-250828"],
                action_models={action: ["doubao-seedream-4-0-250828"] for action in ("txt2img", "img2img")},
                capabilities=["txt2img", "img2img"],
                upload_disclosure="Prompts and reference images are sent to Volcengine Ark in Beijing. Image generation may incur charges. This model revision is scheduled for retirement; no automatic model substitution is performed.",
                website_url="https://ark.volcengine.com/region:cn-beijing/apikey",
                key_test_supported=False,
            ),
            CloudProviderInfo(
                id=CloudProviderId.OPENAI,
                name="OpenAI",
                description="Image generation through Berry's DALL-E 3 adapter.",
                is_configured=bool(self.get_key(CloudProviderId.OPENAI)),
                redacted_key=redact_key(self.get_key(CloudProviderId.OPENAI) or ""),
                supported_models=["dall-e-3"],
                action_models={"txt2img": ["dall-e-3"]},
                capabilities=["txt2img"],
                upload_disclosure="Prompts are sent to OpenAI servers. Zero local GPU required.",
                website_url="https://platform.openai.com/api-keys",
            ),
            CloudProviderInfo(
                id=CloudProviderId.FAL,
                name="Fal.ai",
                description="Ultra-fast FLUX.1 [schnell] and FLUX.1 [dev] inference on serverless GPUs.",
                is_configured=bool(self.get_key(CloudProviderId.FAL)),
                redacted_key=redact_key(self.get_key(CloudProviderId.FAL) or ""),
                supported_models=["flux-schnell", "flux-dev"],
                capabilities=["txt2img", "img2img", "inpaint", "upscale"],
                action_models={
                    "txt2img": ["flux-schnell", "flux-dev"],
                    "img2img": ["fal-ai/flux/dev/image-to-image"],
                    "inpaint": ["fal-ai/flux-general/inpainting"],
                    "upscale": ["fal-ai/clarity-upscaler"],
                },
                upload_disclosure="Prompts and reference images are processed on Fal.ai cloud infrastructure.",
                website_url="https://fal.ai/dashboard/keys",
            ),
            CloudProviderInfo(
                id=CloudProviderId.LLAMA_SERVER,
                name="llama.cpp (Embedded)",
                description="Local embedded high-performance LLM runtime with zero host pollution.",
                is_configured=True,
                redacted_key="(local)",
                supported_models=["qwen2.5-7b-instruct-q4_k_m.gguf", "deepseek-r1-distill-qwen-7b-q4_k_m.gguf", "qwen2.5-1.5b-instruct-q4_k_m.gguf"],
                capabilities=["chat", "agent", "workflow"],
                upload_disclosure="100% private offline inference on local CPU/GPU.",
                website_url="https://github.com/ggml-org/llama.cpp",
            ),
            CloudProviderInfo(
                id=CloudProviderId.SILICONFLOW,
                name="SiliconFlow",
                description="Hosted SDXL generation through Berry's SiliconFlow adapter.",
                is_configured=bool(self.get_key(CloudProviderId.SILICONFLOW)),
                redacted_key=redact_key(self.get_key(CloudProviderId.SILICONFLOW) or ""),
                supported_models=["stabilityai/stable-diffusion-xl-base-1.0"],
                action_models={"txt2img": ["stabilityai/stable-diffusion-xl-base-1.0"]},
                capabilities=["txt2img"],
                upload_disclosure="Requests are dispatched to SiliconFlow cloud API endpoints.",
                website_url="https://cloud.siliconflow.cn/account/ak",
            ),
        ]
        from app.runtime.custom_providers import CustomProviderRegistry
        for record in CustomProviderRegistry(self.data_dir).list():
            spec = record.spec
            available = spec.mode == "rest" or (record.execution_trusted and bool(spec.source.strip()))
            if spec.mode == "python_sdk":
                from app.runtime.sdk_environment import sdk_ready
                available = available and sdk_ready(spec, self.data_dir)
            providers.append(CloudProviderInfo(id=spec.id, name=spec.name, description=f"Custom platform ({spec.mode}).",
                is_configured=available and (spec.auth == "none" or bool(self.get_key(spec.id))),
                redacted_key=redact_key(self.get_key(spec.id) or ""), supported_models=spec.models,
                action_models={action: spec.models for action in spec.actions}, capabilities=spec.actions,
                upload_disclosure=spec.upload_disclosure, website_url=spec.endpoint, key_test_supported=False,
                provider_revision=spec.revision, credential_revision=self.key_revision(spec.id),
                setup_guidance="" if available else "Review and approve the current calling code; SDK mode also needs its isolated environment prepared."))
        return providers

    def get_llm_config(self) -> LLMConfig:
        """Get currently configured LLM provider and settings."""
        stored = self._memory_creds.get("llm_config")
        if stored and isinstance(stored, dict):
            try:
                return LLMConfig.model_validate(stored)
            except Exception:
                pass
        # Default to embedded llama.cpp server (Priority Local First)
        return LLMConfig(
            provider="llama_server",
            model="qwen2.5-7b-instruct-q4_k_m.gguf",
            base_url="http://127.0.0.1:8080/v1",
            api_key="",
            temperature=0.7,
            enabled=True,
        )

    def set_llm_config(self, config: LLMConfig) -> None:
        """Persist LLM configuration."""
        self._memory_creds["llm_config"] = config.model_dump()
        self._save()

    async def test_llm_connection(self, config: Optional[LLMConfig] = None) -> TestKeyResult:
        """Test connection to LLM provider endpoint (llama-server / OpenAI / SiliconFlow / DeepSeek)."""
        cfg = config or self.get_llm_config()
        if cfg.api_key and ("..." in cfg.api_key or cfg.api_key == "****"):
            stored = self.get_llm_config()
            cfg = LLMConfig(
                provider=cfg.provider,
                model=cfg.model,
                base_url=cfg.base_url,
                api_key=stored.api_key,
                temperature=cfg.temperature,
                enabled=cfg.enabled,
            )
        elif not cfg.api_key and config is not None:
            stored = self.get_llm_config()
            if stored.provider == cfg.provider and stored.api_key:
                cfg = LLMConfig(
                    provider=cfg.provider,
                    model=cfg.model,
                    base_url=cfg.base_url,
                    api_key=stored.api_key,
                    temperature=cfg.temperature,
                    enabled=cfg.enabled,
                )
        base_url = cfg.base_url.rstrip("/")
        # Target OpenAI-compatible /models endpoint
        models_url = f"{base_url}/models" if not base_url.endswith("/models") else base_url
        headers = {}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"

        async with httpx.AsyncClient(timeout=6.0, trust_env=False) as client:
            try:
                resp = await client.get(models_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    model_list = [m.get("id") for m in data.get("data", [])] if isinstance(data, dict) else []
                    model_summary = f" Found models: {', '.join(model_list[:3])}" if model_list else ""
                    return TestKeyResult(
                        provider_id=CloudProviderId.LLAMA_SERVER if cfg.provider == "llama_server" else CloudProviderId.OPENAI,
                        valid=True,
                        message=f"Connected successfully to {cfg.provider} ({cfg.model}).{model_summary}",
                        status_code=200,
                    )
                elif resp.status_code in (401, 403):
                    return TestKeyResult(
                        provider_id=CloudProviderId.OPENAI,
                        valid=False,
                        message=f"Authentication failed (HTTP {resp.status_code}). Please check your API key.",
                        status_code=resp.status_code,
                    )
                else:
                    return TestKeyResult(
                        provider_id=CloudProviderId.OPENAI,
                        valid=False,
                        message=f"Server returned HTTP {resp.status_code}",
                        status_code=resp.status_code,
                    )
            except Exception as e:
                err_hint = " Make sure local llama-server is running." if "8080" in base_url or cfg.provider == "llama_server" else ""
                return TestKeyResult(
                    provider_id=CloudProviderId.LLAMA_SERVER if cfg.provider == "llama_server" else CloudProviderId.OPENAI,
                    valid=False,
                    message=f"Could not connect to {base_url}:{err_hint} ({e})",
                )

    async def test_key(self, provider_id: CloudProviderId | str, api_key: Optional[str] = None) -> TestKeyResult:
        """Validate key against the provider's authentication endpoint."""
        if provider_id == CloudProviderId.VOLCENGINE or str(provider_id).startswith("custom-"):
            return TestKeyResult(provider_id=provider_id, valid=False,
                message="This adapter has no verified non-billable connection check. Save the key and explicitly create an image to test model access; generation may incur charges.")
        key = api_key or self.get_key(provider_id)
        if not key and provider_id not in (CloudProviderId.LLAMA_SERVER,):
            return TestKeyResult(
                provider_id=provider_id,
                valid=False,
                message="No API key supplied or found in configuration.",
            )

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                if provider_id == CloudProviderId.OPENAI:
                    resp = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {key}"},
                    )
                    valid = resp.status_code == 200
                    msg = "OpenAI API key verified successfully." if valid else f"Invalid key (HTTP {resp.status_code})"
                    return TestKeyResult(provider_id=provider_id, valid=valid, message=msg, status_code=resp.status_code)

                elif provider_id == CloudProviderId.DEEPSEEK:
                    resp = await client.get(
                        "https://api.deepseek.com/models",
                        headers={"Authorization": f"Bearer {key}"},
                    )
                    valid = resp.status_code == 200
                    msg = "DeepSeek API key verified successfully." if valid else f"Invalid key (HTTP {resp.status_code})"
                    return TestKeyResult(provider_id=provider_id, valid=valid, message=msg, status_code=resp.status_code)

                elif provider_id == CloudProviderId.LLAMA_SERVER:
                    resp = await client.get("http://127.0.0.1:8080/health")
                    if resp.status_code != 200:
                        resp = await client.get("http://127.0.0.1:8080/v1/models")
                    valid = resp.status_code == 200
                    msg = "Embedded llama-server verified successfully." if valid else f"llama-server HTTP {resp.status_code}"
                    return TestKeyResult(provider_id=provider_id, valid=valid, message=msg, status_code=resp.status_code)

                elif provider_id == CloudProviderId.FAL:
                    resp = await client.get(
                        "https://rest.alpha.fal.ai/tokens/current",
                        headers={"Authorization": f"Key {key}"},
                    )
                    if resp.status_code == 200:
                        return TestKeyResult(provider_id=provider_id, valid=True, message="Fal.ai key verified successfully.", status_code=200)
                    elif resp.status_code in (401, 403):
                        return TestKeyResult(provider_id=provider_id, valid=False, message="Invalid Fal.ai API key.", status_code=resp.status_code)
                    else:
                        return TestKeyResult(provider_id=provider_id, valid=True, message="Fal.ai key accepted.", status_code=resp.status_code)

                elif provider_id == CloudProviderId.SILICONFLOW:
                    resp = await client.get(
                        "https://api.siliconflow.cn/v1/user/info",
                        headers={"Authorization": f"Bearer {key}"},
                    )
                    valid = resp.status_code == 200
                    msg = "SiliconFlow API key verified successfully." if valid else f"Invalid key (HTTP {resp.status_code})"
                    return TestKeyResult(provider_id=provider_id, valid=valid, message=msg, status_code=resp.status_code)

            except Exception as e:
                return TestKeyResult(
                    provider_id=provider_id,
                    valid=False,
                    message=f"Network error testing key: {e}",
                )

        return TestKeyResult(provider_id=provider_id, valid=False, message="Unsupported provider for testing.")


credentials_manager = CredentialManager()
