"""Tests for Milestone M12: Cross-platform desktop adapters (macOS Metal MPS & Linux)."""

import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from app.runtime.hardware import (
    detect_all_gpus,
    get_hardware_launch_flags,
    check_hardware_readiness,
)
from app.runtime.supervisor import (
    ComfySupervisor,
    get_default_engine_dir,
)
from app.schemas.hardware import GpuInfo


def test_cross_platform_runtime_paths():
    """Verify engine and runtime directory structures adapt across OS platforms."""
    engine_dir = get_default_engine_dir()
    supervisor = ComfySupervisor(port=8188)

    assert engine_dir.is_absolute()
    assert supervisor.comfy_dir.is_absolute()
    assert "comfyui" in str(supervisor.comfy_dir).lower()


def test_macos_metal_detection(monkeypatch):
    """Verify Apple Silicon Metal MPS detection and launch flags on macOS."""
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr("app.runtime.hardware.detect_nvidia_gpus", lambda: [])

    gpus = detect_all_gpus()
    assert len(gpus) == 1
    assert gpus[0].vendor == "apple_silicon"
    assert gpus[0].backend == "mps"
    assert gpus[0].status_classification == "verified"

    flags = get_hardware_launch_flags(gpus)
    assert "--force-fp16" in flags


def test_linux_rocm_detection(monkeypatch):
    """Verify Linux AMD ROCm detection when rocm-smi is present."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("app.runtime.hardware.detect_nvidia_gpus", lambda: [])

    fake_rocm_gpus = [
        GpuInfo(
            index=0,
            name="AMD Radeon RX 7900 XTX",
            vram_total_mb=24576,
            vram_free_mb=20000,
            vendor="amd",
            backend="rocm",
            status_classification="verified",
        )
    ]
    monkeypatch.setattr("app.runtime.hardware.detect_linux_non_nvidia_gpus", lambda: fake_rocm_gpus)

    gpus = detect_all_gpus()
    assert len(gpus) == 1
    assert gpus[0].backend == "rocm"
    assert gpus[0].vendor == "amd"


def test_python_executable_resolution_unix():
    """Verify supervisor identifies Unix-style virtualenv python paths."""
    supervisor = ComfySupervisor(port=8188)
    py_bin = supervisor.get_python_bin()

    assert isinstance(py_bin, Path)
    if sys.platform == "win32":
        assert py_bin.name.lower() == "python.exe"
    else:
        assert py_bin.name.lower() == "python"
