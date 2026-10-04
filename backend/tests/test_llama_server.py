"""Unit tests for Embedded llama-server (llama.cpp) Runtime and Universal GGUF Support."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runtime.llama_server.llama_supervisor import (
    LlamaModelInfo,
    LlamaServerRuntimeStatus,
    LlamaServerSupervisor,
    llama_server_supervisor,
)
from app.runtime.credentials import credentials_manager
from app.runtime.model_downloader import model_downloader
from app.storage.hub_catalog import HubCatalog


def test_embedded_llama_binary_discovery_in_engine_dir(tmp_path: Path):
    supervisor = LlamaServerSupervisor(engine_dir=tmp_path)
    assert supervisor.get_binary_path() is None
    assert supervisor.is_installed() is False

    # Simulate placed llama-server executable
    bin_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    mock_bin = supervisor.llama_dir / bin_name
    mock_bin.parent.mkdir(parents=True, exist_ok=True)
    mock_bin.write_text("mock binary", encoding="utf-8")

    assert supervisor.get_binary_path() == mock_bin
    assert supervisor.is_installed() is True


def test_list_local_gguf_models(tmp_path: Path):
    supervisor = LlamaServerSupervisor(engine_dir=tmp_path)
    supervisor.ensure_directories()

    # Create dummy GGUF models in models/llm/
    model1 = supervisor.models_dir / "qwen2.5-7b-instruct-q4_k_m.gguf"
    model1.write_bytes(b"\x00" * 1024)

    model2 = supervisor.models_dir / "deepseek-r1-distill-qwen-7b-q4_k_m.gguf"
    model2.write_bytes(b"\x00" * 2048)

    models = supervisor.list_local_models()
    assert len(models) == 2
    names = [m.name for m in models]
    assert "qwen2.5-7b-instruct-q4_k_m.gguf" in names
    assert "deepseek-r1-distill-qwen-7b-q4_k_m.gguf" in names


@pytest.mark.asyncio
async def test_llama_server_status(tmp_path: Path):
    supervisor = LlamaServerSupervisor(engine_dir=tmp_path)
    with patch.object(supervisor, "is_installed", return_value=True), \
         patch.object(supervisor, "is_running", return_value=True), \
         patch.object(supervisor, "check_health", new_callable=AsyncMock, return_value=True):

        status = await supervisor.get_status()
        assert status.installed is True
        assert status.running is True
        assert status.port == 8080
        assert status.endpoint == "http://127.0.0.1:8080/v1"


def test_llama_server_endpoints():
    client = TestClient(app)

    # Test GET status
    res = client.get("/api/v1/llama-server/status")
    assert res.status_code == 200
    data = res.json()
    assert "installed" in data
    assert "running" in data
    assert data["port"] == 8080

    # Test GET models
    with patch.object(llama_server_supervisor, "list_local_models", return_value=[
        LlamaModelInfo(name="qwen2.5-1.5b.gguf", path="/path/to/m.gguf", size_bytes=1000)
    ]):
        res_models = client.get("/api/v1/llama-server/models")
        assert res_models.status_code == 200
        models_data = res_models.json()
        assert len(models_data) == 1
        assert models_data[0]["name"] == "qwen2.5-1.5b.gguf"

    # Test POST start
    with patch.object(llama_server_supervisor, "start", return_value={"success": True, "pid": 12345}):
        res_start = client.post("/api/v1/llama-server/start", json={"model_name": "qwen2.5-1.5b.gguf"})
        assert res_start.status_code == 200
        assert res_start.json()["success"] is True

    # Test POST stop
    with patch.object(llama_server_supervisor, "stop", return_value={"success": True, "message": "stopped"}):
        res_stop = client.post("/api/v1/llama-server/stop")
        assert res_stop.status_code == 200
        assert res_stop.json()["success"] is True


def test_hub_catalog_gguf_models():
    llm_models = HubCatalog.list_models(category="llm")
    assert len(llm_models) >= 3

    model_ids = [m.id for m in llm_models]
    assert "qwen2.5-7b-instruct-q4_k_m" in model_ids
    assert "qwen2.5-1.5b-instruct-q4_k_m" in model_ids
    assert "deepseek-r1-distill-qwen-7b-q4_k_m" in model_ids

    # Check GGUF destination path resolution
    target_rec = HubCatalog.get_model("qwen2.5-7b-instruct-q4_k_m")
    assert target_rec is not None
    resolved_path = model_downloader._resolve_target_path(target_rec, "llama_server")
    assert resolved_path.name.endswith(".gguf")
    assert "models" in str(resolved_path)
    assert "llm" in str(resolved_path)


def test_credentials_llm_config_defaults():
    cfg = credentials_manager.get_llm_config()
    assert cfg.enabled is True
    assert "8080" in cfg.base_url or "11434" in cfg.base_url
