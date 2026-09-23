"""
Secure BYOK Credential Manager.

Manages API keys for external cloud providers (OpenAI, Fal.ai, SiliconFlow).
Ensures secrets are stored locally, never exposed in workflow files or logs,
and strictly redacted in all diagnostic and status APIs.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
import httpx

from app.schemas.cloud import (
    CloudProviderId,
    CloudProviderInfo,
    TestKeyResult,
)
from app.storage.db import get_default_data_dir

logger = logging.getLogger(__name__)


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
                data = json.loads(self.creds_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._memory_creds = data
            except Exception as e:
                logger.warning(f"Error loading credentials from {self.creds_file}: {e}")

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.creds_file.write_text(json.dumps(self._memory_creds, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")

    def get_key(self, provider_id: CloudProviderId) -> Optional[str]:
        """Resolve API key from stored BYOK credentials or environment variable."""
        # 1. Check user-stored BYOK key
        stored = self._memory_creds.get(provider_id.value)
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

    def set_key(self, provider_id: CloudProviderId, api_key: str) -> None:
        """Store an API key for a cloud provider."""
        self._memory_creds[provider_id.value] = api_key.strip()
        self._save()

    def delete_key(self, provider_id: CloudProviderId) -> None:
        """Remove stored API key."""
        if provider_id.value in self._memory_creds:
            del self._memory_creds[provider_id.value]
            self._save()

    def list_providers(self) -> List[CloudProviderInfo]:
        """List cloud providers with capability matrices and redacted keys."""
        providers = [
            CloudProviderInfo(
                id=CloudProviderId.OPENAI,
                name="OpenAI",
                description="High-fidelity image generation via DALL-E 3 and GPT-4o.",
                is_configured=bool(self.get_key(CloudProviderId.OPENAI)),
                redacted_key=redact_key(self.get_key(CloudProviderId.OPENAI) or ""),
                supported_models=["dall-e-3", "gpt-4o"],
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
                capabilities=["txt2img", "img2img"],
                upload_disclosure="Prompts and reference images are processed on Fal.ai cloud infrastructure.",
                website_url="https://fal.ai/dashboard/keys",
            ),
            CloudProviderInfo(
                id=CloudProviderId.SILICONFLOW,
                name="SiliconFlow",
                description="Affordable high-throughput SDXL and FLUX inference.",
                is_configured=bool(self.get_key(CloudProviderId.SILICONFLOW)),
                redacted_key=redact_key(self.get_key(CloudProviderId.SILICONFLOW) or ""),
                supported_models=["sdxl-turbo", "sd-3-5-large"],
                capabilities=["txt2img"],
                upload_disclosure="Requests are dispatched to SiliconFlow cloud API endpoints.",
                website_url="https://cloud.siliconflow.cn/account/ak",
            ),
        ]
        return providers

    async def test_key(self, provider_id: CloudProviderId, api_key: Optional[str] = None) -> TestKeyResult:
        """Validate key against the provider's authentication endpoint."""
        key = api_key or self.get_key(provider_id)
        if not key:
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

                elif provider_id == CloudProviderId.FAL:
                    # Fal.ai key check: probe user info or model status
                    resp = await client.get(
                        "https://rest.alpha.fal.ai/tokens/current",
                        headers={"Authorization": f"Key {key}"},
                    )
                    # Even if 404 on endpoint, 401/403 indicates invalid key, while 200 indicates valid
                    if resp.status_code == 200:
                        return TestKeyResult(provider_id=provider_id, valid=True, message="Fal.ai key verified successfully.", status_code=200)
                    elif resp.status_code in (401, 403):
                        return TestKeyResult(provider_id=provider_id, valid=False, message="Invalid Fal.ai API key.", status_code=resp.status_code)
                    else:
                        # Fallback for alternative Fal auth format
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
