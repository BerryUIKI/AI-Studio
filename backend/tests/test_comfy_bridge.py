"""Tests for ComfyUI bridge driver, status probes, and model discovery."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.runners.comfy_runner import ComfyUIClient

client = TestClient(app)


@pytest.mark.asyncio
async def test_comfy_client_offline_graceful():
    """When ComfyUI is not running on localhost, check_status should return online=False gracefully."""
    c = ComfyUIClient(host="127.0.0.1", port=59999, timeout=0.1)
    status = await c.check_status()
    assert status["online"] is False
    assert status["port"] == 59999
    assert "devices" in status


@pytest.mark.asyncio
async def test_comfy_client_online_mocked():
    """When ComfyUI returns system_stats, check_status should extract devices accurately."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)
    mock_payload = {
        "devices": [
            {"name": "NVIDIA GeForce RTX 4090", "type": "cuda", "vram_total": 24576, "vram_free": 18200}
        ],
        "system": {"os": "windows", "python_version": "3.12.0"}
    }

    mock_resp = httpx.Response(200, json=mock_payload)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        status = await c.check_status()
        assert status["online"] is True
        assert len(status["devices"]) == 1
        assert status["devices"][0]["name"] == "NVIDIA GeForce RTX 4090"


@pytest.mark.asyncio
async def test_comfy_client_get_models_mocked():
    """Model discovery parses CheckpointLoaderSimple and LoraLoader definitions."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)
    mock_object_info = {
        "CheckpointLoaderSimple": {
            "input": {
                "required": {
                    "ckpt_name": [["v1-5-pruned-emaonly.safetensors", "sd_xl_base_1.0.safetensors"]]
                }
            }
        },
        "LoraLoader": {
            "input": {
                "required": {
                    "lora_name": [["lcm-lora-sdv1-5.safetensors", "detail_enhancer.safetensors"]]
                }
            }
        }
    }

    mock_resp = httpx.Response(200, json=mock_object_info)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        models = await c.get_models()
        assert "v1-5-pruned-emaonly.safetensors" in models["checkpoints"]
        assert "sd_xl_base_1.0.safetensors" in models["checkpoints"]
        assert "lcm-lora-sdv1-5.safetensors" in models["loras"]


def test_api_comfy_status_endpoint():
    """FastAPI endpoint /api/v1/comfy/status should return valid status json."""
    resp = client.get("/api/v1/comfy/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "online" in data
    assert "port" in data


def test_api_comfy_models_endpoint():
    """FastAPI endpoint /api/v1/comfy/models should return checkpoints and loras lists."""
    resp = client.get("/api/v1/comfy/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "checkpoints" in data
    assert "loras" in data
