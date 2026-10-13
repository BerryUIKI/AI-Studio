"""Durable task subscriptions and bounded admission do not submit duplicate work."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.creative_tasks import CreativeQueueFull, CreativeTaskService
from app.main import app
from app.schemas.creative import CreativeActionRequest
from app.schemas.task import RunRecord, TaskRecord
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore


@pytest.mark.asyncio
async def test_transition_stream_survives_restart_and_replays_without_dispatch(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / 'tasks.db')
    store = TaskStore(manager)
    try:
        await store.create_run(RunRecord(id='task'))
        task = TaskRecord(id='task', run_id='task', node_id='canvas', node_type='txt2img')
        for state in ('queued', 'running', 'succeeded'):
            task.status = state
            await store.save_task(task)
        await manager.close()
        events = await store.task_events('task')
        assert [event['status'] for event in events] == ['queued', 'running', 'succeeded']
        with patch('app.main.task_store', store), patch('app.main.creative_runner.execute', new=AsyncMock()) as execute:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as client:
                response = await client.get('/api/v1/creative/tasks/task/events?after_sequence=1')
            assert response.status_code == 200
            assert response.headers['content-type'].startswith('text/event-stream')
            assert 'id: 2' in response.text and 'id: 3' in response.text
            assert 'id: 1' not in response.text
            execute.assert_not_awaited()
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_admission_capacity_and_cancelled_worker_cleanup(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / 'queue.db')
    store = TaskStore(manager)
    service = CreativeTaskService(store, concurrency=1, capacity=1)
    await service._slots.acquire()
    try:
        execute = AsyncMock()
        task = await service.submit(CreativeActionRequest(action='txt2img'), execute)
        with pytest.raises(CreativeQueueFull):
            await service.submit(CreativeActionRequest(action='txt2img'), execute)
        assert await service.cancel(task)
        assert not service._workers and not service._cancellations
        execute.assert_not_awaited()
        assert [event['status'] for event in await store.task_events(task)] == ['queued', 'cancel-requested', 'cancelled']
    finally:
        service._slots.release()
        await service.shutdown()
        await manager.close()


@pytest.mark.asyncio
async def test_concurrent_first_access_waits_for_schema_creation(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / 'initialize.db')
    try:
        connections = await asyncio.gather(*(manager.get_connection() for _ in range(8)))
        assert all(connection is connections[0] for connection in connections)
        await connections[0].execute('SELECT * FROM task_events')
    finally:
        await manager.close()
