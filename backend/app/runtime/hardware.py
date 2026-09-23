"""
Hardware and storage readiness diagnostics.

Queries NVIDIA GPU stats via nvidia-smi and checks filesystem storage thresholds.
Operates with zero heavy dependencies (no PyTorch, no CUDA C-extensions).
"""

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from app.runtime.supervisor import get_default_engine_dir
from app.schemas.hardware import GpuInfo, HardwareReadiness, StorageInfo


def detect_gpus() -> List[GpuInfo]:
    """Query NVIDIA GPUs using nvidia-smi without importing PyTorch."""
    gpus: List[GpuInfo] = []
    try:
        # Query: index, name, memory.total, memory.free, driver_version, temperature.gpu
        res = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.free,driver_version,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    try:
                        idx = int(parts[0])
                        name = parts[1]
                        vram_total = int(float(parts[2]))
                        vram_free = int(float(parts[3]))
                        driver_ver = parts[4] if len(parts) > 4 else None
                        temp = int(float(parts[5])) if len(parts) > 5 and parts[5].isdigit() else None
                        gpus.append(
                            GpuInfo(
                                index=idx,
                                name=name,
                                vram_total_mb=vram_total,
                                vram_free_mb=vram_free,
                                driver_version=driver_ver,
                                temperature_c=temp,
                            )
                        )
                    except (ValueError, IndexError):
                        continue
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass

    return gpus


def get_storage_readiness(directory: Path, min_free_gb: float = 15.0) -> StorageInfo:
    """Calculate disk storage metrics for the target directory."""
    directory.mkdir(parents=True, exist_ok=True)
    try:
        usage = shutil.disk_usage(directory)
        total_gb = round(usage.total / (1024**3), 2)
        free_gb = round(usage.free / (1024**3), 2)
        used_gb = round(usage.used / (1024**3), 2)
        is_sufficient = free_gb >= min_free_gb
        return StorageInfo(
            path=str(directory),
            total_gb=total_gb,
            free_gb=free_gb,
            used_gb=used_gb,
            is_sufficient=is_sufficient,
        )
    except Exception:
        return StorageInfo(
            path=str(directory),
            total_gb=0.0,
            free_gb=0.0,
            used_gb=0.0,
            is_sufficient=False,
        )


async def check_hardware_readiness(engine_dir: Optional[Path] = None) -> HardwareReadiness:
    """Assess overall system readiness for local AI inference and engines."""
    root_dir = engine_dir or get_default_engine_dir()
    models_dir = root_dir / "models"

    # Run detection in thread to avoid blocking event loop
    gpus = await asyncio.to_thread(detect_gpus)
    engine_storage = await asyncio.to_thread(get_storage_readiness, root_dir, 10.0)
    model_storage = await asyncio.to_thread(get_storage_readiness, models_dir, 15.0)

    has_nvidia = len(gpus) > 0
    guidance: List[str] = []

    if has_nvidia:
        primary_gpu = gpus[0]
        if primary_gpu.vram_total_mb >= 12000:
            ready = True
            rec_engine = "comfyui"
            summary = f"Ready: {primary_gpu.name} ({primary_gpu.vram_total_mb}MB VRAM) has excellent capacity for local generation."
            guidance.append("SDXL, Flux Schnell, and SD 1.5 can run comfortably at high batch sizes.")
        elif primary_gpu.vram_total_mb >= 6000:
            ready = True
            rec_engine = "comfyui"
            summary = f"Ready: {primary_gpu.name} ({primary_gpu.vram_total_mb}MB VRAM) is capable of local generation."
            guidance.append("SD 1.5 and SDXL are supported; Flux may require low-vram offload.")
        else:
            ready = True
            rec_engine = "comfyui"
            summary = f"Limited: {primary_gpu.name} has only {primary_gpu.vram_total_mb}MB VRAM. Low-VRAM flags recommended."
            guidance.append("SD 1.5 supported in low-vram mode; cloud API inference recommended for larger models.")
    else:
        ready = False
        rec_engine = "cloud_only"
        summary = "No NVIDIA GPU detected. Local inference unavailable or not recommended."
        guidance.append("Use Cloud API inference (OpenAI, Fal.ai, SiliconFlow) for high-speed generation without GPU hardware.")

    if not engine_storage.is_sufficient:
        guidance.append(f"Low engine disk space: {engine_storage.free_gb}GB available on {engine_storage.path} (10GB recommended).")

    if not model_storage.is_sufficient:
        guidance.append(f"Low model storage space: {model_storage.free_gb}GB available on {model_storage.path} (15GB recommended).")

    return HardwareReadiness(
        has_nvidia_gpu=has_nvidia,
        gpus=gpus,
        engine_storage=engine_storage,
        model_storage=model_storage,
        ready_for_local_inference=ready,
        recommended_engine=rec_engine,
        summary_message=summary,
        guidance_notes=guidance,
    )
