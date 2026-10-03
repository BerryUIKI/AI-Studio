"""Tests for Launcher Hub engine instances catalog endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_engine_instances_endpoint():
    """Verify that /api/v1/engines/instances returns unified workspace and engine catalog."""
    resp = client.get("/api/v1/engines/instances")
    assert resp.status_code == 200

    data = resp.json()
    assert "instances" in data
    instances = data["instances"]
    assert isinstance(instances, list)
    assert len(instances) >= 4

    # Verify Built-in Canvas
    canvas = next((i for i in instances if i["id"] == "builtin-canvas"), None)
    assert canvas is not None
    assert canvas["type"] == "canvas"
    assert canvas["is_builtin"] is True
    assert canvas["status"] == "ready"

    # Verify ComfyUI instance entry
    comfy = next((i for i in instances if i["type"] == "comfyui"), None)
    assert comfy is not None
    assert comfy["is_managed"] is True
    assert comfy["endpoint"] is not None
    assert "8188" in comfy["endpoint"]
    assert comfy["status"] in ["ready", "running", "stopped", "not_installed"]

    # Verify WebUI instance entry
    webui = next((i for i in instances if i["type"] == "webui"), None)
    assert webui is not None
    assert webui["is_managed"] is True
    assert webui["endpoint"] is not None
    assert "7860" in webui["endpoint"]

    # Verify Built-in Agents Studio
    agents = next((i for i in instances if i["id"] == "builtin-agents"), None)
    assert agents is not None
    assert agents["type"] == "agents"
    assert agents["is_builtin"] is True
    assert agents["status"] == "ready"
