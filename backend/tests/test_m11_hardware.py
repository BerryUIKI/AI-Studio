"""Tests for Milestone M11: Non-NVIDIA discrete GPU detection, readiness, and launch flag injection."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.runtime.hardware import (
    check_hardware_readiness,
    get_hardware_launch_flags,
)
from app.schemas.hardware import GpuInfo, HardwareReadiness


def test_hardware_launch_flags_matrix():
    """Verify launch flag generation for various GPU vendors and VRAM configurations."""
    # 1. No GPU / CPU fallback
    assert get_hardware_launch_flags([]) == ["--cpu"]

    # 2. High-VRAM NVIDIA (standard)
    nvidia_high = [
        GpuInfo(
            index=0,
            name="NVIDIA GeForce RTX 4090",
            vram_total_mb=24576,
            vram_free_mb=20000,
            vendor="nvidia",
            backend="cuda",
            status_classification="verified",
        )
    ]
    assert get_hardware_launch_flags(nvidia_high) == []

    # 3. Low-VRAM NVIDIA (<6GB)
    nvidia_low = [
        GpuInfo(
            index=0,
            name="NVIDIA GeForce GTX 1650",
            vram_total_mb=4096,
            vram_free_mb=3500,
            vendor="nvidia",
            backend="cuda",
            status_classification="verified",
        )
    ]
    assert get_hardware_launch_flags(nvidia_low) == ["--lowvram"]

    # 4. AMD Radeon RX 7900 XTX (DirectML)
    amd_gpu = [
        GpuInfo(
            index=0,
            name="AMD Radeon RX 7900 XTX",
            vram_total_mb=24576,
            vram_free_mb=22000,
            vendor="amd",
            backend="directml",
            status_classification="verified",
        )
    ]
    flags = get_hardware_launch_flags(amd_gpu)
    assert "--directml" in flags
    assert "--use-split-cross-attention" in flags

    # 5. Intel Arc A770 (DirectML)
    intel_gpu = [
        GpuInfo(
            index=0,
            name="Intel Arc A770 Graphics",
            vram_total_mb=16384,
            vram_free_mb=14000,
            vendor="intel",
            backend="directml",
            status_classification="verified",
        )
    ]
    flags = get_hardware_launch_flags(intel_gpu)
    assert "--directml" in flags
    assert "--use-split-cross-attention" in flags

    # 6. Apple Silicon (Metal)
    apple_gpu = [
        GpuInfo(
            index=0,
            name="Apple M3 Max",
            vram_total_mb=36864,
            vram_free_mb=30000,
            vendor="apple_silicon",
            backend="mps",
            status_classification="verified",
        )
    ]
    assert get_hardware_launch_flags(apple_gpu) == ["--force-fp16"]


@pytest.mark.asyncio
async def test_readiness_with_amd_reference_hardware(monkeypatch):
    """Readiness assessment classifies AMD Radeon reference hardware as candidate_unverified."""
    mock_amd = [
        GpuInfo(
            index=0,
            name="AMD Radeon RX 7800 XT",
            vram_total_mb=16384,
            vram_free_mb=14000,
            vendor="amd",
            backend="directml",
            status_classification="candidate_unverified",
        )
    ]
    monkeypatch.setattr("app.runtime.hardware.detect_all_gpus", lambda: mock_amd)

    readiness: HardwareReadiness = await check_hardware_readiness()

    assert readiness.has_discrete_gpu is True
    assert readiness.has_nvidia_gpu is False
    assert readiness.gpu_vendor == "amd"
    assert readiness.acceleration_backend == "directml"
    assert readiness.status_classification == "candidate_unverified"
    assert readiness.ready_for_local_inference is True
    assert "Candidate Architecture" in readiness.summary_message


@pytest.mark.asyncio
async def test_readiness_with_intel_arc_hardware(monkeypatch):
    """Readiness assessment classifies Intel Arc reference hardware as candidate_unverified."""
    mock_intel = [
        GpuInfo(
            index=0,
            name="Intel Arc A770 Graphics",
            vram_total_mb=16384,
            vram_free_mb=15000,
            vendor="intel",
            backend="directml",
            status_classification="candidate_unverified",
        )
    ]
    monkeypatch.setattr("app.runtime.hardware.detect_all_gpus", lambda: mock_intel)

    readiness: HardwareReadiness = await check_hardware_readiness()

    assert readiness.has_discrete_gpu is True
    assert readiness.gpu_vendor == "intel"
    assert readiness.acceleration_backend == "directml"
    assert readiness.status_classification == "candidate_unverified"
    assert readiness.ready_for_local_inference is True
    assert "Candidate Architecture" in readiness.summary_message


@pytest.mark.asyncio
async def test_readiness_with_verified_nvidia_hardware(monkeypatch):
    """Readiness assessment classifies NVIDIA CUDA with physical evidence as verified."""
    mock_nvidia = [
        GpuInfo(
            index=0,
            name="NVIDIA GeForce RTX 3060",
            vram_total_mb=12288,
            vram_free_mb=10000,
            driver_version="572.70",
            vendor="nvidia",
            backend="cuda",
            status_classification="verified",
        )
    ]
    monkeypatch.setattr("app.runtime.hardware.detect_all_gpus", lambda: mock_nvidia)

    readiness: HardwareReadiness = await check_hardware_readiness()

    assert readiness.has_discrete_gpu is True
    assert readiness.has_nvidia_gpu is True
    assert readiness.gpu_vendor == "nvidia"
    assert readiness.acceleration_backend == "cuda"
    assert readiness.status_classification == "verified"
    assert readiness.ready_for_local_inference is True
    assert "Ready: NVIDIA GeForce RTX 3060" in readiness.summary_message



@pytest.mark.asyncio
async def test_readiness_cpu_only_cloud_recommendation(monkeypatch):
    """Readiness assessment recommends Cloud BYOK when no discrete GPU is available."""
    monkeypatch.setattr("app.runtime.hardware.detect_all_gpus", lambda: [])

    readiness: HardwareReadiness = await check_hardware_readiness()

    assert readiness.has_discrete_gpu is False
    assert readiness.has_nvidia_gpu is False
    assert readiness.gpu_vendor == "cpu_only"
    assert readiness.acceleration_backend == "cpu"
    assert readiness.status_classification == "cloud_recommended"
    assert readiness.ready_for_local_inference is False
    assert readiness.recommended_engine == "cloud_only"
    assert any("Cloud API inference" in note for note in readiness.guidance_notes)


def test_system_info_endpoint():
    """Verify GET /api/v1/system/info returns 200 with HardwareReadiness model."""
    client = TestClient(app)
    resp = client.get("/api/v1/system/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "has_discrete_gpu" in data
    assert "has_nvidia_gpu" in data
    assert "gpu_vendor" in data
    assert "acceleration_backend" in data
    assert "gpus" in data
    assert "summary_message" in data
    assert "status_classification" in data

