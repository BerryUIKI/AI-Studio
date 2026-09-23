"""Model inventory, categories, architectures, and roots schemas."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ModelCategory(str, Enum):
    CHECKPOINT = "checkpoint"
    LORA = "lora"
    VAE = "vae"
    CONTROLNET = "controlnet"
    UPSCALER = "upscaler"
    TEXT_ENCODER = "text_encoder"
    UNKNOWN = "unknown"


class ModelArchitecture(str, Enum):
    SD15 = "sd15"
    SD21 = "sd21"
    SDXL = "sdxl"
    SD3 = "sd3"
    FLUX = "flux"
    ESRGAN = "esrgan"
    UNKNOWN = "unknown"


class ModelRecord(BaseModel):
    id: str
    name: str
    file_path: str
    category: ModelCategory
    architecture: ModelArchitecture
    format: str  # safetensors, ckpt, pth, bin, gguf
    size_bytes: int
    size_mb: float
    content_hash: Optional[str] = None
    engine_compatibility: List[str] = Field(default_factory=list)  # ["comfyui", "webui"]
    is_ready: bool = True
    missing_dependencies: List[str] = Field(default_factory=list)
    guidance: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelRoot(BaseModel):
    id: str
    path: str
    label: str
    engine_type: Optional[str] = None  # "comfyui", "webui", or "custom"
    is_active: bool = True
    exists: bool = True
    models_found: int = 0


class ModelRootCreate(BaseModel):
    path: str
    label: str
    engine_type: Optional[str] = "custom"

