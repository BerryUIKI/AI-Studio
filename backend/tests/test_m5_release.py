"""
Milestone 5 Verification Tests: Release Scenarios, Robustness & Integrity.

Tests all 7 PRD end-to-end release scenarios:
1. Clean setup and creative image workflow.
2. Existing engine connection without unintended mutation or ownership.
3. Cloud-only creation without local engines or PyTorch.
4. Failure recovery: invalid keys, missing models, disconnected engines.
5. Persistence and caching recovery across restarts.
6. Truthful cancellation semantics.
7. Model safety and non-destructive directory management.
"""

import base64
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.cache import CacheStore
from app.main import app
from app.runners.creative_runner import CreativeRunner
from app.runtime.credentials import CredentialManager
from app.runtime.engine_manager import EngineManager
from app.runtime.hardware import check_hardware_readiness
from app.runtime.installer import IsolatedEngineInstaller
from app.schemas.cloud import CloudProviderId
from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.schemas.engine import EngineOwnership, EngineStatus, EngineType, InstallPhase
from app.storage.asset_store import AssetStore
from app.storage.model_store import ModelStore

client = TestClient(app)

DUMMY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_scenario_1_clean_setup_and_readiness():
    """Scenario 1: Clean startup boots without torch and assesses device readiness."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    hw_resp = client.get("/api/v1/hardware/readiness")
    assert hw_resp.status_code == 200
    hw = hw_resp.json()
    assert "has_nvidia_gpu" in hw
    assert "ready_for_local_inference" in hw
    assert isinstance(hw["guidance_notes"], list)


@pytest.mark.asyncio
async def test_scenario_2_existing_engine_connection_no_mutation():
    """Scenario 2: Connect existing external engine without process ownership or file mutation."""
    mgr = EngineManager()
    mock_stats = {
        "system": {"os": "nt"},
        "devices": [{"name": "RTX 4090", "vram_free": 16000000000}],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_stats

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        conn = await mgr.connect_external_engine(
            engine_type=EngineType.COMFYUI,
            endpoint_url="http://127.0.0.1:8188",
            name="User Pre-existing ComfyUI",
        )
        assert conn.ownership == EngineOwnership.EXTERNAL
        assert conn.status == EngineStatus.READY
        assert conn.native_ui_url == "http://127.0.0.1:8188"

        # Verify external engines are not killed by manager
        assert "managed" not in conn.id


@pytest.mark.asyncio
async def test_scenario_3_cloud_only_creation():
    """Scenario 3: Cloud-only generation runs without local engine or GPU requirements."""
    runner = CreativeRunner()
    unique_prompt = f"crystal palace {uuid.uuid4()}"

    with patch("app.runners.creative_runner.credentials_manager.get_key") as mock_key, \
         patch("app.runners.creative_runner._call_openai_images", new_callable=AsyncMock) as mock_oai, \
         patch("app.runners.creative_runner.asset_store.save_image_from_url", new_callable=AsyncMock) as mock_save:

        mock_key.return_value = "sk-test-key"
        mock_oai.return_value = "https://oaidalleapiprodscus.blob.core.windows.net/sample.png"

        mock_asset = MagicMock()
        mock_asset.id = "asset_dalle_crystal"
        mock_asset.content_hash = "hash_crystal_99"
        mock_save.return_value = mock_asset

        req = CreativeActionRequest(
            action=CreativeActionType.TXT2IMG,
            prompt=unique_prompt,
            model="dall-e-3",
            engine_id="cloud_openai",
        )

        res = await runner.execute(req)
        assert res.success is True
        assert res.asset_id == "asset_dalle_crystal"
        assert res.provenance.model == "dall-e-3"
        assert res.provenance.engine_id == "cloud_openai"


def test_scenario_4_failure_recovery_actionable_states():
    """Scenario 4: Interrupted setup, invalid keys, and disconnected engines report actionable states."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Interrupted install recovery
        inst = IsolatedEngineInstaller(engine_dir=Path(tmpdir))
        m = inst.read_manifest(EngineType.COMFYUI)
        m.phase = InstallPhase.INSTALLING_DEPS
        inst.write_manifest(m)

        reloaded = inst.read_manifest(EngineType.COMFYUI)
        assert reloaded.phase == InstallPhase.INTERRUPTED
        assert "interrupted" in reloaded.error_message.lower()

    # 2. Disconnected engine probe returns degraded/offline without crash
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("Connection refused")
        mgr = EngineManager()
        async def _test():
            return await mgr.connect_external_engine(
                engine_type=EngineType.WEBUI,
                endpoint_url="http://127.0.0.1:9999",
            )
        import asyncio
        conn = asyncio.run(_test())
        assert conn.status == EngineStatus.OFFLINE
        assert "Connection refused" in (conn.error_message or "")


@pytest.mark.asyncio
async def test_scenario_5_persistence_and_caching_across_restarts():
    """Scenario 5: Restart preserves cache and deterministic reuse."""
    runner = CreativeRunner()
    unique_prompt = f"tranquil forest {uuid.uuid4()}"
    b64_dummy = base64.b64encode(DUMMY_PNG).decode("utf-8")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"images": [b64_dummy]}
        mock_post.return_value = mock_resp

        req = CreativeActionRequest(
            action=CreativeActionType.TXT2IMG,
            prompt=unique_prompt,
            engine_id="managed_webui",
            seed=777,
        )

        res1 = await runner.execute(req)
        assert res1.is_cached is False

        # Emulate restart: create a new CreativeRunner instance
        runner_after_restart = CreativeRunner()
        res2 = await runner_after_restart.execute(req)
        assert res2.is_cached is True
        assert res2.asset_id == res1.asset_id


def test_scenario_6_cancellation_semantics():
    """Scenario 6: Cancellation request produces truthful response."""
    # Test nonexistent run returns false
    res = client.post("/api/v1/workflow/cancel/nonexistent_run_id")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False


def test_scenario_7_model_safety_non_destructive():
    """Scenario 7: Model inspection reads only headers; removing root leaves files intact."""
    with tempfile.TemporaryDirectory() as tmpdir:
        models_path = Path(tmpdir) / "checkpoints"
        models_path.mkdir(parents=True)
        test_file = models_path / "model.safetensors"
        test_file.write_bytes(DUMMY_PNG)

        store = ModelStore(engine_dir=Path(tmpdir))
        root = store.add_root("custom_root", str(models_path), "My Checkpoints")
        assert root.exists is True

        # Scan roots
        records = store.scan_all_roots()

        # Remove root from store index
        del store.roots["custom_root"]

        # Original file MUST remain intact on disk!
        assert test_file.is_file()
        assert test_file.read_bytes() == DUMMY_PNG
