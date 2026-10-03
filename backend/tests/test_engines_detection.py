"""Tests for LH-M3: Engine Auto-Detection, External Binding, and Mirror Management."""

import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_installer_mirrors():
    """Verify mirrors endpoint returns presets including china_mainland and direct."""
    resp = client.get("/api/v1/installer/mirrors")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_preset" in data
    assert "presets" in data
    preset_ids = [p["id"] for p in data["presets"]]
    assert "direct" in preset_ids
    assert "china_mainland" in preset_ids


def test_update_installer_mirrors():
    """Verify updating the active mirror preset."""
    resp = client.put(
        "/api/v1/installer/mirrors",
        json={"active_preset": "china_mainland"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_preset"] == "china_mainland"

    # Reset back to direct
    client.put(
        "/api/v1/installer/mirrors",
        json={"active_preset": "direct"},
    )


def test_detect_engines_empty_or_valid():
    """Verify detect endpoint executes without error."""
    resp = client.get("/api/v1/engines/detect")
    assert resp.status_code == 200
    data = resp.json()
    assert "detected" in data
    assert isinstance(data["detected"], list)


def test_detect_engines_with_mock_directory(tmp_path: Path):
    """Test engine detection heuristic with a mocked ComfyUI directory structure."""
    mock_comfy = tmp_path / "MockComfyUI"
    mock_comfy.mkdir()
    (mock_comfy / "main.py").write_text("# mock comfy main", encoding="utf-8")
    (mock_comfy / "comfy").mkdir()

    resp = client.get(f"/api/v1/engines/detect?paths={str(mock_comfy)}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["detected"]) == 1
    detected = data["detected"][0]
    assert detected["engine_type"] == "comfyui"
    assert "MockComfyUI" in detected["path"]


def test_bind_and_unbind_external_engine(tmp_path: Path):
    """Verify non-destructive binding and unbinding of an external engine."""
    mock_webui = tmp_path / "MockWebUI"
    mock_webui.mkdir()
    (mock_webui / "webui-user.bat").write_text("@echo off", encoding="utf-8")
    (mock_webui / "modules").mkdir()

    # 1. Bind external engine
    bind_resp = client.post(
        "/api/v1/engines/bind",
        json={
            "engine_type": "webui",
            "name": "My Custom WebUI",
            "path": str(mock_webui),
            "port": 7865,
        },
    )
    assert bind_resp.status_code == 201
    bind_data = bind_resp.json()
    instance_id = bind_data["id"]
    assert "ext_webui" in instance_id
    assert bind_data["ownership"] == "external"

    # 2. Check engine catalog includes newly bound instance
    cat_resp = client.get("/api/v1/engines/instances")
    assert cat_resp.status_code == 200
    inst_list = cat_resp.json()["instances"]
    bound_entry = next((i for i in inst_list if i["id"] == instance_id), None)
    assert bound_entry is not None
    assert bound_entry["name"] == "My Custom WebUI"

    # 3. Check logs endpoint for instance
    logs_resp = client.get(f"/api/v1/runtime/{instance_id}/logs")
    assert logs_resp.status_code == 200
    logs_data = logs_resp.json()
    assert logs_data["instance_id"] == instance_id
    assert len(logs_data["logs"]) > 0

    # 4. Unbind external engine
    unbind_resp = client.delete(f"/api/v1/engines/unbind/{instance_id}")
    assert unbind_resp.status_code == 200
    assert unbind_resp.json()["success"] is True

    # 5. Verify local files on disk remain untouched (non-destructive guarantee)
    assert mock_webui.exists()
    assert (mock_webui / "webui-user.bat").exists()
