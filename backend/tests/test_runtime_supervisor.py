"""Unit tests for sandboxed ComfyUI runtime supervisor."""

import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.runtime.supervisor import ComfySupervisor

client = TestClient(app)


def test_supervisor_paths_and_directory_creation():
    """Supervisor creates isolated directory hierarchy without touching system directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_path = Path(tmpdir) / "test_engine"
        sup = ComfySupervisor(engine_dir=engine_path)
        assert sup.is_installed() is False
        assert sup.is_running() is False

        sup.ensure_directories()
        assert engine_path.is_dir()
        assert (engine_path / "models" / "checkpoints").is_dir()
        assert (engine_path / "models" / "loras").is_dir()
        assert (engine_path / "models" / "vae").is_dir()


def test_supervisor_installation_detection():
    """Supervisor correctly detects presence of comfyui/main.py entrypoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_path = Path(tmpdir) / "test_engine"
        sup = ComfySupervisor(engine_dir=engine_path)
        assert sup.is_installed() is False

        # Create mock main.py
        comfy_dir = engine_path / "comfyui"
        comfy_dir.mkdir(parents=True)
        (comfy_dir / "main.py").write_text("# mock comfyui entrypoint\n", encoding="utf-8")

        assert sup.is_installed() is True
        status = sup.get_status()
        assert status["installed"] is True
        assert status["running"] is False


def test_supervisor_start_when_not_installed():
    """Attempting to start uninstalled ComfyUI returns a helpful descriptive error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_path = Path(tmpdir) / "test_engine"
        sup = ComfySupervisor(engine_dir=engine_path)
        res = sup.start()
        assert res["success"] is False
        assert "not installed" in res["message"]


def test_supervisor_stop_when_not_running():
    """Stopping an inactive process succeeds cleanly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_path = Path(tmpdir) / "test_engine"
        sup = ComfySupervisor(engine_dir=engine_path)
        res = sup.stop()
        assert res["success"] is True
        assert "not running" in res["message"]


def test_api_runtime_endpoints():
    """FastAPI runtime endpoints return valid responses."""
    status_resp = client.get("/api/v1/runtime/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "installed" in data
    assert "running" in data
    assert "engine_dir" in data

    # Test stop endpoint
    stop_resp = client.post("/api/v1/runtime/stop")
    assert stop_resp.status_code == 200
    assert "success" in stop_resp.json()
