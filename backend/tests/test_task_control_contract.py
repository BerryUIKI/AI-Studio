"""Task and legacy workflow transports share truthful durable cancellation."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.main import app
from app.core.task_registry import TaskLifecycleRegistry
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore
from app.schemas.task import RunRecord


@pytest.mark.asyncio
async def test_cancellation_transports_share_run_state_and_unique_route(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / 'control.db')
    store = TaskStore(manager)
    registry = TaskLifecycleRegistry()
    events = {identity: asyncio.Event() for identity in ('legacy', 'task')}
    try:
        for identity in events:
            registry.register_task(identity, 'workflow_graph', events[identity])
            await store.create_run(RunRecord(id=identity))
        with patch('app.main.task_store', store), patch('app.main.task_registry', registry), \
             patch('app.main.active_cancellations', events), patch('app.main.creative_tasks.cancel', AsyncMock(return_value=False)):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost:8000') as client:
                for identity, endpoint in [('legacy', '/api/v1/workflow/cancel/legacy'), ('task', '/api/v1/tasks/task/cancel')]:
                    response = await client.post(endpoint)
                    assert response.status_code == 200
                    assert response.json()['status'] == 'cancel-requested'
                    assert events[identity].is_set()
                    assert (await store.get_run(identity)).status == 'cancel-requested'
        routes = [route for route in app.routes if getattr(route, 'path', None) == '/api/v1/workflow/cancel/{run_id}']
        assert len(routes) == 1
    finally:
        await manager.close()
