"""Shared test fixtures and helpers."""
import pytest
from unittest.mock import Mock, patch
from app.schemas.engine import EngineConnection, EngineType, EngineOwnership, EngineStatus


@pytest.fixture
def mock_comfyui_connection():
    """Standard mock ComfyUI connection for tests."""
    return EngineConnection(
        id="comfyui-managed",
        name="ComfyUI (Managed)",
        engine_type=EngineType.COMFYUI,
        ownership=EngineOwnership.MANAGED,
        status=EngineStatus.RUNNING,
        endpoint_url="http://127.0.0.1:8188",
    )


@pytest.fixture
def mock_webui_connection():
    """Standard mock WebUI connection for tests."""
    return EngineConnection(
        id="webui-managed",
        name="WebUI (Managed)",
        engine_type=EngineType.WEBUI,
        ownership=EngineOwnership.MANAGED,
        status=EngineStatus.RUNNING,
        endpoint_url="http://127.0.0.1:7860",
    )


@pytest.fixture
def mock_engine_manager(mock_comfyui_connection, mock_webui_connection):
    """Mock engine_manager with standard connections."""
    connections = {
        "comfyui-managed": mock_comfyui_connection,
        "webui-managed": mock_webui_connection,
        "comfyui": mock_comfyui_connection,  # Legacy mapping
        "webui": mock_webui_connection,  # Legacy mapping
        "managed_comfyui": mock_comfyui_connection,
        "managed_webui": mock_webui_connection,
    }

    with patch("app.runners.creative_runner.engine_manager") as mock_mgr:
        mock_mgr.get_engine = Mock(side_effect=lambda id: connections.get(id))
        mock_mgr.list_connections = Mock(return_value=connections)
        yield mock_mgr
