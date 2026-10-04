"""
Milestone 2 Verification Tests: Engines, Isolation, Hardware, and Models.

Verifies:
1. Strict removal of host Python fallback in ComfySupervisor.
2. WebUISupervisor isolated lifecycle and entrypoint checking.
3. Staged installer manifest tracking and interruption recovery.
4. External engine connection with zero process ownership.
5. Hardware and filesystem storage readiness diagnostics.
6. Pure standard-library safetensors header parsing and architecture inference.
7. REST API endpoints for M2 engines, hardware, and model catalog.
"""

import json
import struct
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.task_registry import task_registry
from app.runtime.engine_manager import EngineManager
from app.runtime.hardware import check_hardware_readiness, detect_gpus, get_storage_readiness
from app.runtime.installer import IsolatedEngineInstaller
from app.runtime.supervisor import ComfySupervisor
from app.runtime.webui_supervisor import WebUISupervisor
from app.schemas.engine import EngineOwnership, EngineStatus, EngineType, InstallPhase
from app.schemas.model import ModelArchitecture, ModelCategory
from app.storage.model_store import (
    ModelStore,
    detect_architecture,
    detect_category,
    parse_safetensors_header,
)

client = TestClient(app)


def test_supervisor_no_host_python_fallback():
    """Verify ComfySupervisor strictly refuses to launch using host Python."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_path = Path(tmpdir) / "engine"
        comfy_dir = engine_path / "comfyui"
        comfy_dir.mkdir(parents=True)
        (comfy_dir / "main.py").write_text("# entrypoint", encoding="utf-8")

        sup = ComfySupervisor(engine_dir=engine_path)
        assert sup.is_installed() is True
        assert sup.has_isolated_env() is False

        # Attempt start without isolated venv
        res = sup.start()
        assert res["success"] is False
        assert res.get("code") == "ENV_MISSING"
        assert "Sandboxed virtual environment not found" in res["message"]
        # Ensure no process was launched
        assert sup.is_running() is False


def test_webui_supervisor_isolated_lifecycle():
    """Verify WebUISupervisor isolated paths and refusal without isolated venv."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_path = Path(tmpdir) / "engine"
        sup = WebUISupervisor(engine_dir=engine_path)
        assert sup.is_installed() is False

        # Create mock webui.py
        webui_dir = engine_path / "webui"
        webui_dir.mkdir(parents=True)
        (webui_dir / "launch.py").write_text("# mock webui entrypoint", encoding="utf-8")

        assert sup.is_installed() is True
        assert sup.has_isolated_env() is False

        res = sup.start()
        assert res["success"] is False
        assert res.get("code") == "ENV_MISSING"
        assert sup.is_running() is False


def test_installer_manifest_and_interruption():
    """Verify installer tracks phases and recovers safely from interrupted installs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_path = Path(tmpdir) / "engine"
        installer_inst = IsolatedEngineInstaller(engine_dir=engine_path)

        # 1. Read initial manifest
        manifest = installer_inst.read_manifest(EngineType.COMFYUI)
        assert manifest.phase == InstallPhase.IDLE
        assert manifest.engine_type == EngineType.COMFYUI

        # 2. Simulate an interrupted install state (no active in-memory task)
        manifest.phase = InstallPhase.DOWNLOADING
        installer_inst.write_manifest(manifest)

        # 3. Reading manifest again should detect interruption
        reloaded = installer_inst.read_manifest(EngineType.COMFYUI)
        assert reloaded.phase == InstallPhase.INTERRUPTED
        assert "interrupted" in (reloaded.error_message or "").lower()

        # 4. Live polling while an install is actively running must NOT mark as interrupted
        installer_inst._active_installs.add(EngineType.COMFYUI.value)
        try:
            manifest.phase = InstallPhase.DOWNLOADING
            manifest.error_message = None
            installer_inst.write_manifest(manifest)
            live_manifest = installer_inst.read_manifest(EngineType.COMFYUI)
            assert live_manifest.phase == InstallPhase.DOWNLOADING
            assert live_manifest.error_message is None
        finally:
            installer_inst._active_installs.discard(EngineType.COMFYUI.value)


@pytest.mark.asyncio
async def test_installer_empty_dir_missing_entrypoint_rejection(tmp_path):
    """Verify that an empty engine directory or missing entrypoint is rejected and does not report COMPLETED."""
    installer_inst = IsolatedEngineInstaller(engine_dir=tmp_path)
    engine_target = tmp_path / "comfyui"
    engine_target.mkdir(parents=True, exist_ok=True)
    runtime_target = tmp_path / "runtime"

    # Mock venv creation as succeeding and creating python binary
    python_bin = installer_inst._get_python_bin(runtime_target)
    python_bin.parent.mkdir(parents=True, exist_ok=True)
    python_bin.write_text("# mock python", encoding="utf-8")
    pip_bin = installer_inst._get_pip_bin(runtime_target)
    pip_bin.write_text("# mock pip", encoding="utf-8")

    with patch.object(installer_inst, "create_isolated_venv", return_value=True):
        # Empty directory with no main.py and no .git should trigger cleanup & clone attempt,
        # but mock git clone to do nothing, simulating missing entrypoint failure
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc_mock = AsyncMock()
            proc_mock.returncode = 0
            proc_mock.communicate.return_value = (b"", b"")
            mock_exec.return_value = proc_mock

            manifest = await installer_inst.install_engine(EngineType.COMFYUI)
            assert manifest.phase == InstallPhase.FAILED
            assert "requirements.txt missing" in (manifest.error_message or "") or "entrypoint" in (manifest.error_message or "")


@pytest.mark.asyncio
async def test_installer_concurrent_lease_lock_protection(tmp_path):
    """Verify that concurrent install calls for the same engine are rejected by lease lock."""
    installer_inst = IsolatedEngineInstaller(engine_dir=tmp_path)
    lock = task_registry.get_install_lock(EngineType.COMFYUI.value)

    async with lock:
        manifest = await installer_inst.install_engine(EngineType.COMFYUI)
        assert manifest.phase == InstallPhase.FAILED
        assert "lease is already held" in (manifest.error_message or "")


@pytest.mark.asyncio
async def test_external_engine_connection_zero_ownership():
    """Verify external engine connection captures stats and never assumes process ownership."""
    mgr = EngineManager()

    # Mock ComfyUI /system_stats response
    mock_stats = {
        "system": {"os": "nt", "python_version": "3.12"},
        "devices": [{"name": "NVIDIA GeForce RTX 4090", "vram_total": 24000000000, "vram_free": 18000000000}],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_stats

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        conn = await mgr.connect_external_engine(
            engine_type=EngineType.COMFYUI,
            endpoint_url="http://127.0.0.1:8188",
            name="My Local ComfyUI",
        )

        assert conn.ownership == EngineOwnership.EXTERNAL
        assert conn.status == EngineStatus.READY
        assert conn.endpoint_url == "http://127.0.0.1:8188"
        assert conn.vram_free_mb is not None
        assert conn.vram_free_mb > 10000


def test_hardware_storage_readiness():
    """Verify storage readiness calculations against thresholds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = get_storage_readiness(Path(tmpdir), min_free_gb=0.001)
        assert storage.total_gb > 0
        assert storage.free_gb > 0
        assert storage.is_sufficient is True

        # Unrealistic threshold should report insufficient
        storage_high = get_storage_readiness(Path(tmpdir), min_free_gb=1000000.0)
        assert storage_high.is_sufficient is False


def create_synthetic_safetensors(file_path: Path, header_dict: dict) -> None:
    """Helper to create a valid minimal .safetensors binary file with given header."""
    header_json = json.dumps(header_dict).encode("utf-8")
    header_len = len(header_json)
    with open(file_path, "wb") as f:
        f.write(struct.pack("<Q", header_len))
        f.write(header_json)
        # Write dummy 64 bytes of weight data
        f.write(b"\x00" * 64)


def test_safetensors_header_and_architecture_detection():
    """Verify pure binary safetensors parsing without loading tensors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        models_dir = Path(tmpdir) / "models"
        checkpoints_dir = models_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True)

        # Create synthetic SDXL checkpoint
        sdxl_file = checkpoints_dir / "sd_xl_base_1.0.safetensors"
        sdxl_header = {
            "__metadata__": {"modelspec.architecture": "stable-diffusion-xl-v1-base"},
            "model.diffusion_model.input_blocks.4.1.transformer_blocks.0.attn2.to_k.weight": {
                "dtype": "F16",
                "shape": [2048, 2048],
                "data_offsets": [0, 64],
            },
        }
        create_synthetic_safetensors(sdxl_file, sdxl_header)

        # Create synthetic LoRA
        lora_file = models_dir / "test_lora.safetensors"
        lora_header = {
            "lora_unet_down_blocks_0_attentions_0_proj_in.lora_down.weight": {
                "dtype": "F16",
                "shape": [4, 320],
                "data_offsets": [0, 64],
            }
        }
        create_synthetic_safetensors(lora_file, lora_header)

        # Test header parser
        header, meta = parse_safetensors_header(sdxl_file)
        assert meta.get("modelspec.architecture") == "stable-diffusion-xl-v1-base"

        # Test architecture & category detection
        arch = detect_architecture(sdxl_file, header, meta)
        assert arch == ModelArchitecture.SDXL

        cat = detect_category(sdxl_file, header)
        assert cat == ModelCategory.CHECKPOINT

        lora_h, _ = parse_safetensors_header(lora_file)
        lora_cat = detect_category(lora_file, lora_h)
        assert lora_cat == ModelCategory.LORA

        # Test ModelStore scan
        store = ModelStore(engine_dir=Path(tmpdir))
        store.add_root("test_root", str(models_dir), "Test Root")
        records = store.scan_all_roots()
        assert len(records) >= 2

        sdxl_rec = next((r for r in records if r.name == "sd_xl_base_1.0"), None)
        assert sdxl_rec is not None
        assert sdxl_rec.architecture == ModelArchitecture.SDXL
        assert sdxl_rec.category == ModelCategory.CHECKPOINT
        assert "comfyui" in sdxl_rec.engine_compatibility
        assert "webui" in sdxl_rec.engine_compatibility


def test_api_m2_endpoints():
    """Verify new REST endpoints for hardware readiness, engines, and models."""
    # 1. Hardware readiness
    resp = client.get("/api/v1/hardware/readiness")
    assert resp.status_code == 200
    hw = resp.json()
    assert "has_nvidia_gpu" in hw
    assert "ready_for_local_inference" in hw
    assert "summary_message" in hw

    # 2. Engines list
    resp = client.get("/api/v1/engines")
    assert resp.status_code == 200
    engines = resp.json()
    assert isinstance(engines, list)
    assert any(e["id"] == "managed_comfyui" for e in engines)
    assert any(e["id"] == "managed_webui" for e in engines)

    # 3. Model roots
    resp = client.get("/api/v1/models/roots")
    assert resp.status_code == 200
    roots = resp.json()
    assert isinstance(roots, list)

    # 4. Engine manifest
    resp = client.get("/api/v1/runtime/comfyui/manifest")
    assert resp.status_code == 200
    manifest = resp.json()
    assert manifest["engine_type"] == "comfyui"
    assert "phase" in manifest
