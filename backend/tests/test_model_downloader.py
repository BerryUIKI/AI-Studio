"""Unit tests for multi-mirror resumable model download engine (MH-M4)."""

import pytest
import asyncio
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
    assert webui_path == comfy_path
    assert webui_path.name == "flux1-schnell-fp8.safetensors"

    # LoRA category path
    lora_model = HubCatalog.get_model("sdxl-lora-detail-tweaker")
    assert lora_model is not None
    comfy_lora_path = downloader._resolve_target_path(lora_model, target_engine="comfyui")
    assert "loras" in str(comfy_lora_path)

    webui_lora_path = downloader._resolve_target_path(lora_model, target_engine="webui")
    assert webui_lora_path == comfy_lora_path


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


def test_download_worker_info_progress(tmp_path: Path) -> None:
    """Verify DownloadWorker calculation of progress percentage and task info."""
    model = HubCatalog.get_model("esrgan-4x-ultrasharp")
    assert model is not None

    worker = DownloadWorker(
        task_id="dl_test123",
        model=model,
        target_engine="comfyui",
        target_path=tmp_path / "4x-UltraSharp.pth",
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


@pytest.mark.asyncio
async def test_downloader_task_lifecycle_controls(tmp_path: Path) -> None:
    """Verify task pause, resume, and cancellation tracking in ModelDownloader."""
    downloader = ModelDownloader()
    model = HubCatalog.get_model("esrgan-4x-ultrasharp")
    assert model is not None

    worker = DownloadWorker(
        task_id="dl_lifecycle_1",
        model=model,
        target_engine="comfyui",
        target_path=tmp_path / "4x-UltraSharp.pth",
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
    with patch("app.runtime.model_downloader.installer.engine_dir", tmp_path):
        assert await downloader.cancel_task("dl_lifecycle_1") is True
    assert downloader.list_tasks() == []
    assert worker._cancel_flag is True


@pytest.mark.asyncio
async def test_download_worker_size_mismatch_rejection(tmp_path):
    """Verify that artifact size mismatch rejects promotion and leaves existing target untouched."""
    target_file = tmp_path / "model.safetensors"
    target_file.write_text("existing_good_version")
    part_file = tmp_path / "model.safetensors.part"
    part_file.write_bytes(b"short")

    dummy_model = HubModelRecord(
        id="test-model",
        name="Test Model",
        architecture="flux",
        category="checkpoint",
        version="1.0",
        size_bytes=100,  # Expects 100 bytes, part is only 5 bytes
        parameter_count="12B",
        author="test",
        description="test",
        preview_image_url="test",
        min_vram_mb=4000,
        optimal_vram_mb=8000,
    )

    worker = DownloadWorker(
        task_id="test_size_fail",
        model=dummy_model,
        target_engine="comfyui",
        target_path=target_file,
        source_url="https://example.com/test",
    )
    # Bypass actual network download loop
    worker._download_loop = MagicMock(return_value=asyncio.sleep(0, result=True))

    await worker.run()

    assert worker.status == "failed"
    assert "size mismatch" in worker.error_message
    assert target_file.exists()
    assert target_file.read_text() == "existing_good_version"
    assert part_file.exists()


@pytest.mark.asyncio
async def test_download_worker_sha256_mismatch_rejection(tmp_path):
    """Verify that SHA-256 integrity mismatch rejects promotion and preserves existing target."""
    target_file = tmp_path / "model.safetensors"
    target_file.write_text("existing_good_version")
    part_file = tmp_path / "model.safetensors.part"
    part_file.write_bytes(b"corrupted_content")

    dummy_model = HubModelRecord(
        id="test-model",
        name="Test Model",
        architecture="flux",
        category="checkpoint",
        version="1.0",
        size_bytes=len(b"corrupted_content"),
        sha256="0000000000000000000000000000000000000000000000000000000000000000",
        parameter_count="12B",
        author="test",
        description="test",
        preview_image_url="test",
        min_vram_mb=4000,
        optimal_vram_mb=8000,
    )

    worker = DownloadWorker(
        task_id="test_sha_fail",
        model=dummy_model,
        target_engine="comfyui",
        target_path=target_file,
        source_url="https://example.com/test",
    )
    worker._download_loop = MagicMock(return_value=asyncio.sleep(0, result=True))

    await worker.run()

    assert worker.status == "failed"
    assert "SHA-256 integrity mismatch" in worker.error_message
    assert target_file.exists()
    assert target_file.read_text() == "existing_good_version"


@pytest.mark.asyncio
async def test_download_worker_atomic_promotion_success(tmp_path):
    """Verify that valid download promotes part file atomically and overwrites destination."""
    import hashlib

    target_file = tmp_path / "model.safetensors"
    target_file.write_text("old_version")
    part_file = tmp_path / "model.safetensors.part"
    valid_content = b"new_verified_model_weights_12345"
    part_file.write_bytes(valid_content)

    correct_sha256 = hashlib.sha256(valid_content).hexdigest()

    dummy_model = HubModelRecord(
        id="test-model",
        name="Test Model",
        architecture="flux",
        category="checkpoint",
        version="1.0",
        size_bytes=len(valid_content),
        sha256=correct_sha256,
        parameter_count="12B",
        author="test",
        description="test",
        preview_image_url="test",
        min_vram_mb=4000,
        optimal_vram_mb=8000,
    )

    worker = DownloadWorker(
        task_id="test_success",
        model=dummy_model,
        target_engine="comfyui",
        target_path=target_file,
        source_url="https://example.com/test",
    )
    worker._download_loop = MagicMock(return_value=asyncio.sleep(0, result=True))

    await worker.run()

    assert worker.status == "completed"
    assert worker.error_message is None
    assert not part_file.exists()
    assert target_file.exists()
    assert target_file.read_bytes() == valid_content



@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "downloading", "paused", "failed", "cancelled", "completed"])
async def test_remove_download_cleans_only_partial_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    downloader = ModelDownloader()
    monkeypatch.setattr("app.runtime.model_downloader.installer.engine_dir", tmp_path)
    model = HubCatalog.get_model("esrgan-4x-ultrasharp")
    worker = DownloadWorker("remove", model, "comfyui", tmp_path / "model.pth", "")
    downloader._workers[worker.task_id] = worker
    worker.status = status
    worker.target_path.write_bytes(b"installed model")
    worker.part_path.write_bytes(b"partial")
    unrelated = tmp_path / "other.pth"
    unrelated.write_bytes(b"unrelated")
    assert await downloader.cancel_task(worker.task_id)
    assert downloader.list_tasks() == []
    assert worker.target_path.read_bytes() == b"installed model"
    assert unrelated.read_bytes() == b"unrelated"
    assert worker.part_path.exists() == (status == "completed")
    assert not await downloader.cancel_task(worker.task_id)


@pytest.mark.asyncio
async def test_remove_waits_until_writer_is_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    downloader = ModelDownloader()
    monkeypatch.setattr("app.runtime.model_downloader.installer.engine_dir", tmp_path)
    worker = DownloadWorker("writer", HubCatalog.get_model("esrgan-4x-ultrasharp"), "comfyui", tmp_path / "model.pth", "")
    downloader._workers[worker.task_id] = worker
    opened = asyncio.Event()
    closed = asyncio.Event()

    async def writer() -> None:
        try:
            with worker.part_path.open("wb") as stream:
                stream.write(b"partial")
                opened.set()
                await asyncio.Event().wait()
        finally:
            closed.set()

    worker._task = asyncio.create_task(writer())
    await opened.wait()
    assert await downloader.cancel_task(worker.task_id)
    assert closed.is_set()
    assert not worker.part_path.exists()


@pytest.mark.asyncio
async def test_remove_rejects_external_partial_and_retains_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    downloader = ModelDownloader()
    monkeypatch.setattr("app.runtime.model_downloader.installer.engine_dir", tmp_path / "owned")
    worker = DownloadWorker("external", HubCatalog.get_model("esrgan-4x-ultrasharp"), "comfyui", tmp_path / "external.pth", "")
    downloader._workers[worker.task_id] = worker
    worker.part_path.write_bytes(b"do not delete")
    with pytest.raises(OSError):
        await downloader.cancel_task(worker.task_id)
    assert worker.part_path.read_bytes() == b"do not delete"
    assert downloader.list_tasks()[0].status == "failed"
