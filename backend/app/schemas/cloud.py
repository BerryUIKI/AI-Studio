"""Schemas for BYOK cloud providers, credentials, capabilities, and key tests."""

import re
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class CloudProviderId(str, Enum):
    OPENAI = "openai"
    FAL = "fal"
    SILICONFLOW = "siliconflow"
    DEEPSEEK = "deepseek"
    LLAMA_SERVER = "llama_server"
    VOLCENGINE = "volcengine"


class LLMConfig(BaseModel):
    provider: str = "llama_server"  # llama_server, siliconflow, deepseek, openai, custom
    model: str = "qwen2.5-7b-instruct-q4_k_m.gguf"
    base_url: str = "http://127.0.0.1:8080/v1"
    api_key: Optional[str] = None
    temperature: float = 0.7
    enabled: bool = True


class SetLLMConfigRequest(BaseModel):
    provider: str
    model: str
    base_url: str
    api_key: Optional[str] = None
    temperature: float = 0.7
    enabled: bool = True


class CloudProviderInfo(BaseModel):
    id: CloudProviderId | str
    name: str
    description: str
    is_configured: bool
    redacted_key: Optional[str] = None  # e.g. "sk-...1234", never raw secret
    supported_models: List[str] = Field(default_factory=list)
    action_models: Dict[str, List[str]] = Field(default_factory=dict)
    capabilities: List[str] = Field(default_factory=list)  # ["txt2img", "img2img", "inpaint", "upscale"]
    upload_disclosure: str
    website_url: str
    key_test_supported: bool = True


class _ProviderRequest(BaseModel):
    provider_id: CloudProviderId | str

    @field_validator("provider_id", mode="before")
    @classmethod
    def validate_provider_id(cls, value: str) -> CloudProviderId | str:
        if not isinstance(value, str):
            raise ValueError("Provider identifier must be a string")
        try:
            return CloudProviderId(value)
        except ValueError:
            if not re.fullmatch(r"custom-[a-z0-9][a-z0-9-]{0,62}", value):
                raise ValueError("Unknown provider identifier") from None
            return value


class SetCredentialRequest(_ProviderRequest):
    api_key: str


class TestKeyRequest(_ProviderRequest):
    api_key: Optional[str] = None  # If omitted, test the currently stored key


class TestKeyResult(BaseModel):
    provider_id: CloudProviderId | str
    valid: bool
    message: str
    status_code: Optional[int] = None
