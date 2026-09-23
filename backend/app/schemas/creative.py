"""Schemas for high-level creative image actions, provenance, and results."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreativeActionType(str, Enum):
    TXT2IMG = "txt2img"
    IMG2IMG = "img2img"
    INPAINT = "inpaint"
    UPSCALE = "upscale"


class CreativeActionRequest(BaseModel):
    action: CreativeActionType
    prompt: str = ""
    negative_prompt: str = "low quality, blurry, deformed, bad anatomy"
    model: str = "v1-5-pruned-emaonly.safetensors"
    engine_id: str = "managed_comfyui"  # managed_comfyui, managed_webui, or cloud
    aspect_ratio: str = "1:1"  # 1:1, 16:9, 9:16, 4:3
    width: int = 512
    height: int = 512
    steps: int = 20
    cfg_scale: float = 7.0
    seed: int = -1  # -1 for random
    denoise: float = 0.75  # For img2img and inpaint (0.0 to 1.0)
    input_image_id: Optional[str] = None  # Reference asset ID for img2img / inpaint / upscale
    mask_image_id: Optional[str] = None   # Binary mask asset ID for inpaint
    upscale_factor: float = 2.0           # 2.0 or 4.0
    upscaler_name: str = "R-ESRGAN 4x+"


class GenerationProvenance(BaseModel):
    action: CreativeActionType
    prompt: str
    negative_prompt: Optional[str] = None
    model: str
    engine_id: str
    seed: int
    steps: int
    cfg_scale: float
    dimensions: str  # e.g. "512x512"
    created_at: str
    source_asset_id: Optional[str] = None
    mask_asset_id: Optional[str] = None
    execution_time_ms: Optional[float] = None


class CreativeActionResult(BaseModel):
    success: bool
    task_id: str
    asset_id: Optional[str] = None
    image_url: Optional[str] = None
    width: int = 512
    height: int = 512
    provenance: Optional[GenerationProvenance] = None
    is_cached: bool = False
    error_message: Optional[str] = None
