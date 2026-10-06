"""
Tests for engine connection routing (Issue #127).

Verifies that execution and lifecycle operations are resolved through
the selected engine connection, ensuring all operations use the same
resolved endpoint.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from app.runners.creative_runner import CreativeRunner
from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.schemas.engine import EngineConnection, EngineType, EngineOwnership, EngineStatus


@pytest.fixture
def mock_engine_manager():
    """Mock engine_manager with two test connections."""
    connections = {
        "comfyui-managed": EngineConnection(
            id="comfyui-managed",
            name="ComfyUI (Managed)",
            engine_type=EngineType.COMFYUI,
            ownership=EngineOwnership.MANAGED,
            status=EngineStatus.RUNNING,
            endpoint_url="http://127.0.0.1:8188",
        ),
        "comfyui-studio-a100": EngineConnection(
            id="comfyui-studio-a100",
            name="Studio A100",
            engine_type=EngineType.COMFYUI,
            ownership=EngineOwnership.EXTERNAL,
            status=EngineStatus.RUNNING,
            endpoint_url="http://studio.local:9000/comfy",
        ),
        "webui-managed": EngineConnection(
            id="webui-managed",
            name="WebUI (Managed)",
            engine_type=EngineType.WEBUI,
            ownership=EngineOwnership.MANAGED,
            status=EngineStatus.RUNNING,
            endpoint_url="http://127.0.0.1:7860",
        ),
    }

    with patch("app.runners.creative_runner.engine_manager") as mock_mgr:
        mock_mgr.get_connection = Mock(side_effect=lambda id: connections.get(id))
        mock_mgr.list_connections = Mock(return_value=connections)
        yield mock_mgr


def test_resolve_connection_with_valid_connection_id(mock_engine_manager):
    """Resolve connection from explicit connection_id."""
    runner = CreativeRunner()

    connection = runner._resolve_connection("comfyui-studio-a100", None)

    assert connection.id == "comfyui-studio-a100"
    assert connection.endpoint_url == "http://studio.local:9000/comfy"
    assert connection.ownership == EngineOwnership.EXTERNAL


def test_resolve_connection_with_invalid_connection_id(mock_engine_manager):
    """Raise error for unknown connection_id."""
    runner = CreativeRunner()

    with pytest.raises(ValueError) as exc_info:
        runner._resolve_connection("nonexistent-connection", None)

    assert "not found" in str(exc_info.value).lower()
    assert "comfyui-managed" in str(exc_info.value)


def test_resolve_connection_with_legacy_engine_id(mock_engine_manager):
    """Fallback to default managed connection from legacy engine_id."""
    runner = CreativeRunner()

    # Test ComfyUI mapping
    connection = runner._resolve_connection(None, "managed_comfyui")
    assert connection.id == "comfyui-managed"

    # Test WebUI mapping
    connection = runner._resolve_connection(None, "webui")
    assert connection.id == "webui-managed"


def test_resolve_connection_without_identifiers(mock_engine_manager):
    """Raise error when no connection_id or engine_id provided."""
    runner = CreativeRunner()

    with pytest.raises(ValueError) as exc_info:
        runner._resolve_connection(None, None)

    assert "no connection_id or engine_id" in str(exc_info.value).lower()


def test_create_client_for_comfyui(mock_engine_manager):
    """Create ComfyUIClient with configured base_url."""
    runner = CreativeRunner()
    connection = runner._resolve_connection("comfyui-studio-a100", None)

    client = runner._create_client(connection)

    assert client.base_url == "http://studio.local:9000/comfy"
    assert client.host == "studio.local"
    assert client.port == 9000


def test_create_client_for_webui(mock_engine_manager):
    """Create WebUIRunner with configured endpoint_url."""
    runner = CreativeRunner()
    connection = runner._resolve_connection("webui-managed", None)

    client = runner._create_client(connection)

    assert client.endpoint_url == "http://127.0.0.1:7860"


def test_cache_hash_includes_connection_id():
    """Cache hash must include connection_id to isolate results."""
    from app.runners.creative_runner import compute_creative_cache_hash

    req = CreativeActionRequest(
        action=CreativeActionType.TXT2IMG,
        prompt="test prompt",
        model="test.safetensors",
    )

    # Same request, different connections should produce different hashes
    hash1 = compute_creative_cache_hash(req, "comfyui-managed", "", "")
    hash2 = compute_creative_cache_hash(req, "comfyui-studio-a100", "", "")

    assert hash1 != hash2


@pytest.mark.asyncio
async def test_execute_resolves_connection_before_dispatch(mock_engine_manager):
    """Execute must resolve connection before creating client."""
    runner = CreativeRunner()

    req = CreativeActionRequest(
        action=CreativeActionType.TXT2IMG,
        prompt="test",
        connection_id="comfyui-studio-a100",
        model="test.safetensors",
    )

    with patch.object(runner, "_run_comfy", new_callable=AsyncMock) as mock_run_comfy:
        mock_run_comfy.return_value = {
            "asset_id": "test_asset",
            "image_url": "/api/v1/assets/test_asset/content",
            "width": 512,
            "height": 512,
        }

        with patch("app.runners.creative_runner.asset_store") as mock_store:
            mock_store.get_asset = AsyncMock(return_value=None)

            with patch("app.runners.creative_runner.cache_store") as mock_cache:
                mock_cache.get_async = AsyncMock(return_value=None)
                mock_cache.set_async = AsyncMock()

                result = await runner.execute(req)

    # Verify _run_comfy was called with a client configured for studio-a100
    assert mock_run_comfy.called
    call_args = mock_run_comfy.call_args
    client_arg = call_args[0][1]  # Second positional arg is comfy_client
    assert client_arg.base_url == "http://studio.local:9000/comfy"


@pytest.mark.asyncio
async def test_cancel_task_uses_resolved_connection(mock_engine_manager):
    """Cancellation must target the connection used by the task."""
    runner = CreativeRunner()

    # Register a task with connection_id
    task_id = "test_task_123"
    runner.active_tasks[task_id] = {
        "action": "txt2img",
        "engine": "comfyui",
        "connection_id": "comfyui-studio-a100",
        "start_time": 0,
    }

    with patch("app.runners.creative_runner.ComfyUIClient") as MockClient:
        mock_client_instance = MockClient.return_value
        mock_client_instance.interrupt = AsyncMock(return_value=True)

        result = await runner.cancel_task(task_id)

    # Verify client was created with correct connection
    MockClient.assert_called_once()
    call_kwargs = MockClient.call_args[1]
    assert call_kwargs["base_url"] == "http://studio.local:9000/comfy"

    assert result["engine_interrupted"] is True
