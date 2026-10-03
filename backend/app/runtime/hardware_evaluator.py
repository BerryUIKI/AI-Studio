"""Hardware Compatibility Evaluation Engine (MH-M2)."""

import os
import sys
from typing import Dict, List, Optional
from app.runtime.hardware import get_gpu_stats
from app.schemas.model_hub import (
    HubModelRecord,
    ModelEvaluation,
    HardwareSummary,
    HardwareEvaluationResponse,
)


def get_system_ram_mb() -> tuple[int, int]:
    """Return (total_ram_mb, available_ram_mb)."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        return int(vm.total / (1024 * 1024)), int(vm.available / (1024 * 1024))
    except ImportError:
        # Fallback for Windows without psutil
        if sys.platform == "win32":
            try:
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                total_mb = int(stat.ullTotalPhys / (1024 * 1024))
                avail_mb = int(stat.ullAvailPhys / (1024 * 1024))
                return total_mb, avail_mb
            except Exception:
                pass
        return 16384, 8192


def evaluate_model_compatibility(
    model: HubModelRecord,
    gpu_total_mb: int,
    gpu_free_mb: int,
    ram_avail_mb: int,
    has_gpu: bool,
) -> ModelEvaluation:
    """Compute 4-tier runnability classification for a given model."""
    weight_mb = int(model.size_bytes / (1024 * 1024))
    buffer_mb = 2048 if model.category == "checkpoint" else 512
    required_footprint = weight_mb + buffer_mb

    # Case 1: No dedicated GPU present (or cloud mode)
    if not has_gpu or gpu_total_mb <= 0:
        if weight_mb < 150:  # Small upscaler or tiny LoRA can run on CPU
            return ModelEvaluation(
                tier="playable_offload",
                tier_label="CPU运行 (无独立显卡)",
                tier_color="amber",
                estimated_latency_sec="5-15s",
                required_vram_mb=required_footprint,
                notes="No GPU detected; will execute on host CPU.",
            )
        return ModelEvaluation(
            tier="unsupported",
            tier_label="无法运行 (无独立显卡，建议云端)",
            tier_color="rose",
            estimated_latency_sec="N/A",
            required_vram_mb=required_footprint,
            notes="Requires dedicated NVIDIA GPU. Recommend using Cloud BYOK generation.",
        )

    # Case 2: Tier 1 — Optimal VRAM (Native speed, zero CPU swap)
    if gpu_total_mb >= (required_footprint + 1024):
        # Latency estimations
        if "schnell" in model.architecture:
            latency = "4-8s"
        elif "sdxl" in model.architecture:
            latency = "1-3s"
        elif "sd-1.5" in model.architecture:
            latency = "<1s"
        elif model.category == "upscaler":
            latency = "<1s"
        else:
            latency = "3-10s"

        return ModelEvaluation(
            tier="optimal",
            tier_label="极致流畅 (Optimal)",
            tier_color="emerald",
            estimated_latency_sec=latency,
            required_vram_mb=required_footprint,
            notes="Model fits entirely in dedicated VRAM without host memory swapping.",
        )

    # Case 3: Tier 2 — Playable with RAM Offload (Paged execution via PCIe)
    if (gpu_total_mb + ram_avail_mb) >= (required_footprint + 4096):
        offload_amount = max(0, required_footprint - gpu_total_mb)
        if "dev" in model.architecture:
            latency = "25-45s"
        elif "schnell" in model.architecture:
            latency = "12-25s"
        else:
            latency = "10-25s"

        return ModelEvaluation(
            tier="playable_offload",
            tier_label="需共享内存 (RAM Offload)",
            tier_color="amber",
            estimated_latency_sec=latency,
            required_vram_mb=required_footprint,
            notes=f"Dedicated VRAM is tight; offloads ~{offload_amount}MB to host RAM via PCIe.",
        )

    # Case 4: Tier 3 — Heavy Paging (Memory under extreme pressure)
    if (gpu_total_mb + ram_avail_mb) >= required_footprint:
        return ModelEvaluation(
            tier="heavy_paging",
            tier_label="严重卡顿 (Heavy Paging)",
            tier_color="orange",
            estimated_latency_sec=">60s",
            required_vram_mb=required_footprint,
            notes="Host memory under high pressure; severe swapping may cause stutter.",
        )

    # Case 5: Tier 4 — Unsupported / Out of Memory Risk
    return ModelEvaluation(
        tier="unsupported",
        tier_label="无法运行 (易爆显存，建议云端)",
        tier_color="rose",
        estimated_latency_sec="N/A",
        required_vram_mb=required_footprint,
        notes="Total available memory is insufficient; CUDA Out-Of-Memory expected. Recommend Cloud BYOK.",
    )


def evaluate_hardware(models: List[HubModelRecord]) -> HardwareEvaluationResponse:
    """Evaluate full catalog against live host hardware telemetry."""
    gpu_stats = get_gpu_stats()
    ram_total_mb, ram_avail_mb = get_system_ram_mb()

    has_gpu = bool(gpu_stats.has_gpu and gpu_stats.vendor == "nvidia")
    gpu_total = gpu_stats.vram_total_mb if has_gpu else 0
    gpu_free = gpu_stats.vram_free_mb if has_gpu else 0
    gpu_name = gpu_stats.name if has_gpu else "No Dedicated GPU"

    summary = HardwareSummary(
        has_gpu=has_gpu,
        gpu_name=gpu_name,
        vram_total_mb=gpu_total,
        vram_free_mb=gpu_free,
        ram_total_mb=ram_total_mb,
        ram_avail_mb=ram_avail_mb,
    )

    evaluations: Dict[str, ModelEvaluation] = {}
    for m in models:
        evaluations[m.id] = evaluate_model_compatibility(
            model=m,
            gpu_total_mb=gpu_total,
            gpu_free_mb=gpu_free,
            ram_avail_mb=ram_avail_mb,
            has_gpu=has_gpu,
        )

    return HardwareEvaluationResponse(
        hardware_summary=summary,
        evaluations=evaluations,
    )
