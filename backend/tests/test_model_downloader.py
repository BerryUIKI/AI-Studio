"""Unit tests for multi-mirror resumable model download engine (MH-M4)."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.storage.hub_catalog import HubCatalog
from app.runtime.model_downloader import ModelDownloader, DownloadWorker
from app.schemas.model_hub import HubModelRecord, DownloadSource


def test_target_path_resolution():
    """Verify engine destination paths for ComfyUI and WebUI."""
    downloader = ModelDownloader()
    model = HubCatalog.get_model("flux-1-schnell-fp8")
    assert model is not None

    # ComfyUI checkpoint path
    comfy_path = downloader._resolve_target_path(model, target_engine="comfyui")
    assert "models" in str(comfy_path)
    assert "checkpoints" in str(comfy_path)
    assert comfy_path.name == "flux1-schnell-fp8.safetensors"

    # WebUI checkpoint path
    webui_path = downloader._resolve_target_path(model, target_engine="webui")
    assert "models" in str(webui_path)
    assert "Stable-diffusion" in str(webui_path)
    assert webui_path.name == "flux1-schnell-fp8.safetensors"

    # LoRA category path
    lora_model = HubCatalog.get_model("lora-detail-tweaker")
    assert lora_model is not None
    comfy_lora_path = downloader._resolve_target_path(lora_model, target_engine="comfyui")
    assert "loras" in str(comfy_lora_path)

    webui_lora_path = downloader._resolve_target_path(lora_model, target_engine="webui")
    assert "Lora" in str(webui_lora_path)


def test_mirror_source_selection():
    """Verify mirror acceleration url selection based on region preference."""
    downloader = ModelDownloader()
    model = HubCatalog.get_model("flux-1-schnell-fp8")
    assert model is not None

    # Global preference (default first source)
    global_url = downloader._select_source_url(model, mirror_preset="global_default")
    assert "huggingface.co" in global_url

    # China Mainland preference selects mirror URL
    cn_url = downloader._select_source_url(model, mirror_preset="china_mainland")
    assert "hf-mirror.com" in cn_url or "Mirror" in cn_url


def test_download_worker_info_progress():
    """Verify DownloadWorker calculation of progress percentage and task info."""
    model = HubCatalog.get_model("upscaler-4x-ultrasharp")
    assert model is not None

    worker = DownloadWorker(
        task_id="dl_test123",
        model=model,
        target_engine="comfyui",
        target_path=Path("/tmp/test/4x-UltraSharp.pth"),
        source_url="https://example.com/4x-UltraSharp.pth",
    )

    info = worker.to_info()
    assert info.task_id == "dl_test123"
    assert info.status == "pending"
    assert info.progress_pct == 0.0

    # Simulate 50% download progress
    worker.downloaded_bytes = worker.total_bytes // 2
    worker.status = "downloading"
    worker.speed_bps = 5242880  # 5 MB/s
    worker.eta_seconds = 13

    info_progress = worker.to_info()
    assert info_progress.status == "downloading"
    assert 49.0 <= info_progress.progress_pct <= 51.0
    assert info_progress.speed_bps == 5242880
    assert info_progress.eta_seconds == 13


def test_downloader_task_lifecycle_controls():
    """Verify task pause, resume, and cancellation tracking in ModelDownloader."""
    downloader = ModelDownloader()
    model = HubCatalog.get_model("upscaler-4x-ultrasharp")
    assert model is not None

    worker = DownloadWorker(
        task_id="dl_lifecycle_1",
        model=model,
        target_engine="comfyui",
        target_path=Path("/tmp/test/4x-UltraSharp.pth"),
        source_url="https://example.com/4x-UltraSharp.pth",
    )
    worker.status = "downloading"
    downloader._workers[worker.task_id] = worker

    # Pause
    assert downloader.pause_task("dl_lifecycle_1") is True
    assert worker.status == "paused"
    assert not worker._pause_event.is_set()

    # Resume
    assert downloader.resume_task("dl_lifecycle_1") is True
    assert worker.status == "downloading"
    assert worker._pause_event.is_set()

    # Cancel
    assert downloader.cancel_task("dl_lifecycle_1") is True
    assert worker.status == "cancelled"
    assert worker._cancel_flag is True
