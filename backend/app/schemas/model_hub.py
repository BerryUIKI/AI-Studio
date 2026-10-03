from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field

HubModelCategory = Literal["checkpoint", "lora", "controlnet", "upscaler", "vae"]
CompatibilityTier = Literal["optimal", "playable_offload", "heavy_paging", "unsupported"]


class ModelSource(BaseModel):
    name: str
    url: str


class HubModelRecord(BaseModel):
    id: str
    name: str
    architecture: str
    category: str
    version: str
    size_bytes: int
    parameter_count: str
    quantization: Optional[str] = None
    author: str
    description: str
    preview_image_url: str
    tags: List[str] = Field(default_factory=list)
    recommended_resolution: List[int] = Field(default_factory=lambda: [1024, 1024])
    min_vram_mb: int
    optimal_vram_mb: int
    sources: List[ModelSource] = Field(default_factory=list)
    sha256: Optional[str] = None
    is_installed: bool = False
    installed_path: Optional[str] = None


class HubCatalogResponse(BaseModel):
    total: int
    models: List[HubModelRecord]


class HardwareEvaluationRequest(BaseModel):
    model_ids: Optional[List[str]] = None


class ModelEvaluation(BaseModel):
    tier: CompatibilityTier
    tier_label: str
    tier_color: str  # emerald, amber, orange, rose
    estimated_latency_sec: str
    required_vram_mb: int
    notes: str


class HardwareSummary(BaseModel):
    has_gpu: bool
    gpu_name: str
    vram_total_mb: int
    vram_free_mb: int
    ram_total_mb: int
    ram_avail_mb: int


class HardwareEvaluationResponse(BaseModel):
    hardware_summary: HardwareSummary
    evaluations: Dict[str, ModelEvaluation]


DownloadTaskStatus = Literal["pending", "downloading", "paused", "completed", "failed", "cancelled"]


class StartDownloadRequest(BaseModel):
    model_id: str
    target_engine: str = "comfyui"
    mirror_preset: Optional[str] = None


class DownloadTaskInfo(BaseModel):
    task_id: str
    model_id: str
    model_name: str
    target_engine: str
    target_path: str
    status: DownloadTaskStatus
    total_bytes: int
    downloaded_bytes: int
    progress_pct: float
    speed_bps: int = 0
    eta_seconds: Optional[int] = None
    error_message: Optional[str] = None


class DownloadTasksResponse(BaseModel):
    tasks: List[DownloadTaskInfo]
