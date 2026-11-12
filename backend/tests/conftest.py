"""Shared test fixtures and helpers."""

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import Mock, patch

import aiosqlite
import pytest
import pytest_asyncio
from app.schemas.engine import (
    EngineConnection,
    EngineOwnership,
    EngineStatus,
    EngineType,
)

# Set isolation before collection imports modules with credential/data singletons.
_test_root = (
    Path(__file__).resolve().parents[2] / ".cache" / "backend-tests" / uuid.uuid4().hex
)
os.environ["BERRY_DATA_DIR"] = str(_test_root / "data")
os.environ["AI_WORKFLOW_ENGINE_DIR"] = str(_test_root / "engines")

# Session boundary: sensitive routes require the per-launch token (F02). Give the
# whole suite a known token and make every TestClient present it by default, so
# business-logic tests exercise their endpoints as authenticated local clients.
# Session-security tests override or omit the header themselves.
os.environ.setdefault("BERRY_SESSION_TOKEN", "test-session-token-default")


def _authorize_testclient():
    from fastapi.testclient import TestClient as _TC

    _original_init = _TC.__init__

    def patched_init(self, *args, **kwargs):
        headers = kwargs.pop("headers", None) or {}
        if isinstance(headers, dict):
            headers.setdefault("X-Session-Token", os.environ["BERRY_SESSION_TOKEN"])
        kwargs["headers"] = headers
        _original_init(self, *args, **kwargs)

    _TC.__init__ = patched_init


_authorize_testclient()


@pytest_asyncio.fixture(autouse=True)
async def close_test_databases(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Release every real SQLite manager used by a test before its loop closes."""
    from app.storage.db import DatabaseManager

    managers: set[DatabaseManager] = set()
    original = DatabaseManager.get_connection

    async def tracked(manager: DatabaseManager) -> aiosqlite.Connection:
        managers.add(manager)
        return await original(manager)

    monkeypatch.setattr(DatabaseManager, "get_connection", tracked)
    yield
    for manager in managers:
        await manager.close()


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
