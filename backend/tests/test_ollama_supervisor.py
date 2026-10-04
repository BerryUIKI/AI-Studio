import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app, setup_no_proxy
from app.runtime.ollama_supervisor import ollama_supervisor, OllamaSupervisor


def test_setup_no_proxy():
    setup_no_proxy()
    no_proxy = os.environ.get("NO_PROXY", "")
    assert "127.0.0.1" in no_proxy
    assert "localhost" in no_proxy


@pytest.mark.asyncio
async def test_pull_model_stream_not_installed():
    supervisor = OllamaSupervisor()
    with patch.object(supervisor, "is_installed", return_value=False):
        events = []
        async for chunk in supervisor.pull_model_stream("qwen2.5:14b"):
            events.append(chunk)

        assert len(events) == 1
        assert events[0]["status"] == "error"
        assert "not installed" in events[0]["error"].lower()
        assert events[0].get("code") == "NOT_INSTALLED"


@pytest.mark.asyncio
async def test_pull_model_stream_auto_start_failure():
    supervisor = OllamaSupervisor()
    with patch.object(supervisor, "is_installed", return_value=True), \
         patch.object(supervisor, "check_health", new_callable=AsyncMock, return_value=False), \
         patch.object(supervisor, "start", return_value={"success": False, "message": "Exec error"}), \
         patch.object(supervisor, "is_running", return_value=False):

        events = []
        async for chunk in supervisor.pull_model_stream("qwen2.5:7b"):
            events.append(chunk)

        assert len(events) == 1
        assert events[0]["status"] == "error"
        assert "failed to start" in events[0]["error"].lower()


def test_ollama_install_endpoint():
    client = TestClient(app)
    with patch.object(ollama_supervisor, "install", return_value={"success": True, "message": "Installing", "installing": True}):
        res = client.post("/api/v1/ollama/install")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["installing"] is True
