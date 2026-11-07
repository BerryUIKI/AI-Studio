"""Tests for GPU stats monitoring endpoint and runtime helper (LH-M4)."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.runtime.hardware import get_gpu_stats
from app.schemas.hardware import GpuStatsResponse

client = TestClient(app)


def test_gpu_stats_endpoint_live():
    """Verify that /api/v1/hardware/gpu-stats returns 200 and schema conforms."""
    resp = client.get("/api/v1/hardware/gpu-stats")
    assert resp.status_code == 200
    data = resp.json()

    assert "has_gpu" in data
    assert "vendor" in data
    assert "name" in data
    assert "vram_total_mb" in data
    assert "vram_used_mb" in data
    assert "vram_free_mb" in data
    assert "processes" in data
    assert isinstance(data["processes"], list)


def test_gpu_stats_fallback_when_smi_fails():
    """Verify that get_gpu_stats gracefully handles nvidia-smi failure or absence."""
    with patch("subprocess.run", side_effect=FileNotFoundError("nvidia-smi not found")):
        stats = get_gpu_stats()
        assert isinstance(stats, GpuStatsResponse)
        assert stats.has_gpu is False
        assert stats.vendor == "none"
        assert stats.vram_total_mb == 0
        assert stats.processes == []


def test_gpu_stats_mocked_nvidia_smi():
    """Verify parsing when nvidia-smi returns valid metrics and compute processes."""
    gpu_output = "NVIDIA GeForce RTX 4090, 550.54.14, 52, 28, 24576, 6144, 18432\n"
    proc_output = "1234, 4096\n5678, 1024\n"

    def mock_run(args, **kwargs):
        mock_res = MagicMock()
        mock_res.returncode = 0
        if "--query-gpu" in args[1]:
            mock_res.stdout = gpu_output
        elif "--query-compute-apps" in args[1]:
            mock_res.stdout = proc_output
        else:
            mock_res.stdout = ""
        return mock_res

    with patch("subprocess.run", side_effect=mock_run):
        stats = get_gpu_stats()
        assert stats.has_gpu is True
        assert stats.vendor == "nvidia"
        assert "RTX 4090" in stats.name
        assert stats.driver_version == "550.54.14"
        assert stats.temperature_c == 52
        assert stats.utilization_pct == 28
        assert stats.vram_total_mb == 24576
        assert stats.vram_used_mb == 6144
        assert stats.vram_free_mb == 18432
        assert len(stats.processes) == 2
        assert stats.processes[0].pid == 1234
        assert stats.processes[0].vram_used_mb == 4096
