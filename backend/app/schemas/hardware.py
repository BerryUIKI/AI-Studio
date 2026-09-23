"""Hardware readiness and storage diagnostic schemas (M11)."""

from typing import List, Optional
from pydantic import BaseModel, Field


class GpuInfo(BaseModel):
    index: int
    name: str
    vram_total_mb: int
    vram_free_mb: int
    driver_version: Optional[str] = None
    cuda_version: Optional[str] = None
    temperature_c: Optional[int] = None
    vendor: str = "nvidia"  # nvidia, amd, intel, apple_silicon, cpu_only
    backend: str = "cuda"  # cuda, directml, rocm, ipex, mps, cpu
    status_classification: str = "verified"  # verified, experimental, unverified


class StorageInfo(BaseModel):
    path: str
    total_gb: float
    free_gb: float
    used_gb: float
    is_sufficient: bool = True  # True if >= required threshold (e.g. 15GB)


class HardwareReadiness(BaseModel):
    has_nvidia_gpu: bool
    has_discrete_gpu: bool = False
    gpu_vendor: str = "cpu_only"  # nvidia, amd, intel, apple_silicon, cpu_only
    acceleration_backend: str = "cpu"  # cuda, directml, rocm, ipex, mps, cpu
    gpus: List[GpuInfo] = Field(default_factory=list)
    engine_storage: Optional[StorageInfo] = None
    model_storage: Optional[StorageInfo] = None
    ready_for_local_inference: bool
    recommended_engine: Optional[str] = None  # comfyui, webui, or cloud_only
    summary_message: str
    guidance_notes: List[str] = Field(default_factory=list)
    status_classification: str = "verified"  # verified, experimental, cloud_recommended
