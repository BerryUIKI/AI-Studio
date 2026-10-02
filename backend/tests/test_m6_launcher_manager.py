"""
Automated Test Suite for Milestone 6: Launcher and Environment Manager (L01-L12).
Verifies:
- Versioned manager protocol status aggregation (L04, L11)
- Launcher configuration endpoints (L07)
- Controlled shutdown with active task protection (L07)
- Engine update and rollback semantics (L08, L12)
- Updates check separating app vs engine updates (L08)
- Missing frontend packaging diagnostic page (L02)
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import active_cancellations, app, launcher_config
from app.runtime.installer import IsolatedEngineInstaller
from app.schemas.engine import EngineType, EngineUpdateStatus


@pytest.fixture
def client():
    return TestClient(app)


def test_manager_status_endpoint(client):
    """L04, L11: Verify GET /api/v1/manager/status aggregates core, engines, cloud, models, and tasks."""
    resp = client.get("/api/v1/manager/status")
    assert resp.status_code == 200
    data = resp.json()

    assert data["app_name"] == "Berry AI Studio"
    assert data["version"] == "0.1.0"
    assert data["pid"] == os.getpid()
    assert data["uptime_seconds"] >= 0
    assert "port" in data
    assert "frontend_packaged" in data
    assert "managed_comfyui" in data
    assert "managed_webui" in data
    assert "external_engines" in data
    assert "cloud_providers_configured" in data
    assert "models_indexed" in data
    assert "active_tasks" in data
    assert "launcher_config" in data


def test_manager_config_crud(client):
    """L07: Verify launcher configuration retrieval and mutation."""
    resp = client.get("/api/v1/manager/config")
    assert resp.status_code == 200
    cfg = resp.json()
    assert "stop_managed_engines_on_exit" in cfg

    # Update config
    update_payload = {
        "stop_managed_engines_on_exit": True,
        "default_engine": "managed_comfyui",
        "browser_auto_open": False,
        "port": 8000,
    }
    resp_set = client.post("/api/v1/manager/config", json=update_payload)
    assert resp_set.status_code == 200
    new_cfg = resp_set.json()
    assert new_cfg["stop_managed_engines_on_exit"] is True
    assert new_cfg["default_engine"] == "managed_comfyui"

    # Reset
    client.post("/api/v1/manager/config", json={"stop_managed_engines_on_exit": False, "default_engine": "cloud", "browser_auto_open": True, "port": 8000})


def test_manager_shutdown_guards_active_tasks(client):
    """L07: Verify shutdown prevents silent termination of running tasks unless forced."""
    fake_run_id = "test-run-active-guard"
    cancel_event = asyncio.Event()
    active_cancellations[fake_run_id] = cancel_event

    try:
        # Non-forced shutdown should fail with 409
        resp = client.post("/api/v1/manager/shutdown", json={"force": False})
        assert resp.status_code == 409
        assert "active generation task" in resp.json()["detail"]
        assert not cancel_event.is_set()

        # Forced shutdown should succeed and signal cancellation
        with patch("os._exit") as mock_exit:
            resp_force = client.post("/api/v1/manager/shutdown", json={"force": True})
            assert resp_force.status_code == 200
            assert resp_force.json()["status"] == "shutting_down"
            assert resp_force.json()["active_tasks_cancelled"] == 1
            assert cancel_event.is_set()
    finally:
        active_cancellations.pop(fake_run_id, None)


@pytest.mark.asyncio
async def test_engine_update_active_tasks_guard():
    """L12: Engine update must abort if active jobs are running."""
    fake_run_id = "test-update-active"
    active_cancellations[fake_run_id] = asyncio.Event()

    installer = IsolatedEngineInstaller()
    try:
        manifest = await installer.update_engine(
            EngineType.COMFYUI,
            has_active_tasks_fn=lambda: len(active_cancellations) > 0,
        )
        assert manifest.status == EngineUpdateStatus.FAILED
        assert "active generation tasks" in manifest.error_message
    finally:
        active_cancellations.pop(fake_run_id, None)


@pytest.mark.asyncio
async def test_engine_update_rollback_semantics():
    """L08, L12: Interrupted or failed update must record state and support rollback."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        installer = IsolatedEngineInstaller(engine_dir=tmp_path)

        # Create fake engine git repo
        engine_target = tmp_path / "comfyui"
        engine_target.mkdir(parents=True)
        git_dir = engine_target / ".git"
        git_dir.mkdir()

        # Mock subprocess to simulate git rev-parse, git pull failure, and git checkout rollback
        async def mock_exec(*args, **kwargs):
            cmd = args[0]
            subcmd = args[1] if len(args) > 1 else ""
            mock_proc = AsyncMock()

            if subcmd == "rev-parse":
                mock_proc.returncode = 0
                mock_proc.communicate.return_value = (b"commit_abc123\n", b"")
            elif subcmd == "pull":
                # Simulate failure during pull
                mock_proc.returncode = 1
                mock_proc.communicate.return_value = (b"", b"Network timeout during fetch")
            elif subcmd == "checkout":
                # Rollback checkout succeeds
                mock_proc.returncode = 0
                mock_proc.communicate.return_value = (b"HEAD is now at commit_abc123", b"")
            else:
                mock_proc.returncode = 0
                mock_proc.communicate.return_value = (b"", b"")

            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            manifest = await installer.update_engine(EngineType.COMFYUI)
            assert manifest.status == EngineUpdateStatus.ROLLED_BACK
            assert manifest.rollback_performed is True
            assert manifest.previous_commit == "commit_abc123"
            assert "Network timeout" in manifest.error_message


def test_updates_check_endpoint(client):
    """L08: Verify app updates and engine updates are presented as separate operations."""
    resp = client.get("/api/v1/updates/check")
    assert resp.status_code == 200
    data = resp.json()

    assert "app" in data
    assert data["app"]["name"] == "Berry AI Studio"
    assert "current_version" in data["app"]
    assert "latest_version" in data["app"]

    assert "engines" in data
    assert "comfyui" in data["engines"]
    assert "webui" in data["engines"]


def test_missing_frontend_diagnostic_page(client):
    """L02: Missing frontend must show an informative packaging error page, not a blank 404."""
    # Test request to root /
    resp = client.get("/")
    assert resp.status_code == 200
    # Either static index.html or diagnostic packaging error
    content = resp.text
    assert ("<!DOCTYPE html>" in content or "<!doctype html>" in content.lower())
    if "Packaging Error" in content:
        assert "frontend/dist/index.html" in content
        assert "pnpm build" in content


def test_app_update_trigger(client):
    """L08: Triggering application update should handle git or packaged mode safely."""
    resp = client.post("/api/v1/updates/app")
    assert resp.status_code == 200
    data = resp.json()
    assert "mode" in data
    assert "status" in data
    assert "message" in data
    if data["mode"] == "packaged":
        assert "download_url" in data
        assert "LOCALAPPDATA" in data.get("notes", "")
    elif data["mode"] == "git":
        assert data["status"] in ("updated", "failed", "error")
