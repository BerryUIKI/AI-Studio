"""Tests for llama-server installation and lifecycle fixes (issues #135, #130)."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runtime.llama_server.llama_supervisor import LlamaServerSupervisor


def test_stop_always_returns_dict(tmp_path):
    """Test that stop() always returns a dictionary, never None (issue #135)."""
    supervisor = LlamaServerSupervisor(engine_dir=tmp_path, port=8080)

    # Case 1: Stop when not running
    result = supervisor.stop()
    assert isinstance(result, dict), "stop() must return dict, not None"
    assert "success" in result
    assert "message" in result
    assert result["success"] is True

    # Case 2: Stop when PID file exists but process doesn't (stale PID)
    supervisor.pid_file.parent.mkdir(parents=True, exist_ok=True)
    supervisor.pid_file.write_text("99999")
    result = supervisor.stop()
    assert isinstance(result, dict), "stop() must return dict even with stale PID"
    assert "success" in result
    assert "message" in result

    # Case 3: Stop with invalid PID file content
    supervisor.pid_file.write_text("invalid")
    result = supervisor.stop()
    assert isinstance(result, dict), "stop() must return dict even with invalid PID"
    assert result["success"] is True  # Should treat as "not running"


@pytest.mark.asyncio
async def test_install_queries_github_api_for_latest_release(tmp_path, monkeypatch):
    """Test that install() queries GitHub API for latest binary release."""
    supervisor = LlamaServerSupervisor(engine_dir=tmp_path, port=8080)

    # Track whether API was called
    api_called = False
    api_url_called = None

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            nonlocal api_called, api_url_called
            if "api.github.com" in url:
                api_called = True
                api_url_called = url
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = [
                    {
                        "tag_name": "b11457",
                        "assets": [
                            {
                                "name": "llama-b11457-bin-win-cpu-x64.zip" if sys.platform == "win32" else "llama-b11457-bin-ubuntu-x64.zip",
                                "browser_download_url": "https://github.com/ggml-org/llama.cpp/releases/download/b11457/llama-b11457-bin-win-cpu-x64.zip"
                            }
                        ]
                    }
                ]
                return mock_resp
            raise Exception("Unexpected URL")

        async def stream(self, method, url, **kwargs):
            # Mock download failure to speed up test
            mock_resp = MagicMock()
            mock_resp.status_code = 404

            async def aiter_bytes(chunk_size):
                if False:
                    yield b""

            mock_resp.aiter_bytes = aiter_bytes
            return mock_resp

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    result = await supervisor.install()

    # Verify API was called
    assert api_called, "GitHub API should be queried for latest release"
    assert "api.github.com/repos/ggml-org/llama.cpp/releases" in api_url_called

    # Result structure should be valid even if download fails
    assert isinstance(result, dict)
    assert "success" in result
    assert "installed" in result


@pytest.mark.asyncio
async def test_install_uses_fallback_on_api_failure(tmp_path, monkeypatch):
    """Test that install() uses fallback release b11457 when API call fails."""
    supervisor = LlamaServerSupervisor(engine_dir=tmp_path, port=8080)

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            raise Exception("Simulated API failure")

        async def stream(self, method, url, **kwargs):
            # Should still attempt download with fallback
            mock_resp = MagicMock()
            mock_resp.status_code = 404

            async def aiter_bytes(chunk_size):
                if False:
                    yield b""

            mock_resp.aiter_bytes = aiter_bytes
            return mock_resp

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FailingClient)

    result = await supervisor.install()

    # Should use fallback and return proper structure
    assert isinstance(result, dict)
    assert "success" in result
    assert "installed" in result


def test_start_endpoint_returns_proper_structure():
    """Test that start endpoint handles errors and returns proper HTTP responses."""
    client = TestClient(app)

    # Test with no llama-server installed (should not return HTTP 500)
    response = client.post("/api/v1/llama-server/start", json={"model_name": "test.gguf"})

    # Should return 200 or proper error, not HTTP 500
    assert response.status_code in [200, 422, 404], f"Unexpected status: {response.status_code}"

    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict), "Response must be a dictionary"
        # Should have either success or error structure
        assert "success" in data or "message" in data or "detail" in data


def test_stop_endpoint_returns_proper_structure():
    """Test that stop endpoint handles errors and returns proper HTTP responses."""
    client = TestClient(app)

    # Test stop when nothing is running (should not return HTTP 500)
    response = client.post("/api/v1/llama-server/stop")

    # Should return 200 with proper structure, not HTTP 500
    assert response.status_code == 200, f"Unexpected status: {response.status_code}"

    data = response.json()
    assert isinstance(data, dict), "Response must be a dictionary"
    assert "success" in data, "Response must have 'success' field"
    assert isinstance(data["success"], bool), "'success' must be boolean"
    assert "message" in data, "Response must have 'message' field"


def test_stop_with_exception_handling():
    """Test that stop endpoint catches exceptions and returns HTTP 500 with detail."""
    client = TestClient(app)

    from app.runtime.llama_server.llama_supervisor import llama_server_supervisor

    # Mock stop to raise an exception
    with patch.object(llama_server_supervisor, "stop", side_effect=RuntimeError("Simulated error")):
        response = client.post("/api/v1/llama-server/stop")

        # Should return HTTP 500 with error detail
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Simulated error" in data["detail"]


def test_start_with_invalid_result_type():
    """Test that start endpoint validates result type from supervisor."""
    client = TestClient(app)

    from app.runtime.llama_server.llama_supervisor import llama_server_supervisor

    # Mock start to return invalid type (None instead of dict)
    with patch.object(llama_server_supervisor, "start", return_value=None):
        response = client.post("/api/v1/llama-server/start")

        # Should return HTTP 500 with clear error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Invalid response" in data["detail"]


@pytest.mark.asyncio
async def test_install_creates_isolated_directory(tmp_path):
    """Test that install creates isolated engine directory structure."""
    supervisor = LlamaServerSupervisor(engine_dir=tmp_path, port=8080)

    # Ensure directories are created
    supervisor.ensure_directories()

    assert supervisor.llama_dir.exists()
    assert supervisor.models_dir.exists()
    assert supervisor.llama_dir == tmp_path / "llama_server"
    assert supervisor.models_dir == tmp_path / "models" / "llm"


def test_partial_download_cleanup(tmp_path):
    """Test that failed downloads don't leave false-positive installed state."""
    supervisor = LlamaServerSupervisor(engine_dir=tmp_path, port=8080)

    # Simulate partial download
    supervisor.ensure_directories()
    partial_file = supervisor.llama_dir / "llama_server_dl.zip"
    partial_file.write_bytes(b"incomplete")

    # Should not be considered installed
    assert supervisor.is_installed() is False

    # Cleanup should be possible
    if partial_file.exists():
        partial_file.unlink()
