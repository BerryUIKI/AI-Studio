"""Helper to create mock engine manager for tests requiring connection routing."""

from unittest.mock import Mock
from app.schemas.engine import EngineType

def create_mock_engine_manager_patch():
    """Create a mock engine_manager that returns default managed connections."""
    mock_connection_comfy = Mock()
    mock_connection_comfy.id = "comfyui-managed"
    mock_connection_comfy.url = "http://127.0.0.1:8188"
    mock_connection_comfy.engine_type = EngineType.COMFYUI

    mock_connection_webui = Mock()
    mock_connection_webui.id = "webui-managed"
    mock_connection_webui.url = "http://127.0.0.1:7860"
    mock_connection_webui.engine_type = EngineType.WEBUI

    def get_connection_side_effect(conn_id):
        if conn_id == "comfyui-managed":
            return mock_connection_comfy
        elif conn_id == "webui-managed":
            return mock_connection_webui
        return None

    mock_engine_mgr = Mock()
    mock_engine_mgr.get_connection = Mock(side_effect=get_connection_side_effect)
    mock_engine_mgr.list_connections = Mock(return_value={
        "comfyui-managed": mock_connection_comfy,
        "webui-managed": mock_connection_webui,
    })

    return mock_engine_mgr
