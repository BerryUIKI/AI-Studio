"""Schemas for BYOK cloud providers, credentials, capabilities, and key tests."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class CloudProviderId(str, Enum):
    OPENAI = "openai"
    FAL = "fal"
    SILICONFLOW = "siliconflow"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    LLAMA_SERVER = "llama_server"


class LLMConfig(BaseModel):
    provider: str = "llama_server"  # llama_server, ollama, siliconflow, deepseek, openai, custom
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
    id: CloudProviderId
    name: str
    description: str
    is_configured: bool
    redacted_key: Optional[str] = None  # e.g. "sk-...1234", never raw secret
    supported_models: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)  # ["txt2img", "img2img", "inpaint", "upscale"]
    upload_disclosure: str
    website_url: str


class SetCredentialRequest(BaseModel):
    provider_id: CloudProviderId
    api_key: str


class TestKeyRequest(BaseModel):
    provider_id: CloudProviderId
    api_key: Optional[str] = None  # If omitted, test the currently stored key


class TestKeyResult(BaseModel):
    provider_id: CloudProviderId
    valid: bool
    message: str
    status_code: Optional[int] = None
