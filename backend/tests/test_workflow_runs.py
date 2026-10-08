"""A disconnected subscriber must never trigger a second inference call."""

import asyncio
import json
from pathlib import Path

import pytest

from app.core.workflow_runs import WorkflowRunService
from app.schemas.task import WorkflowRunRequest
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore


@pytest.mark.asyncio
async def test_reconnect_and_duplicate_submission_execute_once(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "runs.db")
    service = WorkflowRunService(TaskStore(manager))
    request = WorkflowRunRequest(run_id="one-run", graph={"nodes": []})
    calls = 0
    release = asyncio.Event()

    async def execute(request, sink) -> None:
        nonlocal calls
        calls += 1
        await sink.send_text(json.dumps({"type": "GRAPH_STARTED", "total_nodes": 0, "cached_nodes": 0}))
        await release.wait()
        await sink.send_text(json.dumps({"type": "GRAPH_FINISHED", "status": "completed", "execution_time_ms": 1}))

    try:
        await service.submit(request, execute)
        first = service.subscribe("one-run")
        started = await anext(first)
        await first.aclose()
        assert await service.submit(request, execute) == "one-run"
        release.set()
        resumed = [event async for event in service.subscribe("one-run", started["sequence"])]
        assert resumed[-1]["status"] == "completed"
        assert calls == 1
        with pytest.raises(ValueError, match="different immutable"):
            await service.submit(WorkflowRunRequest(run_id="one-run", graph={"nodes": [{"id": "changed", "type": "input.text"}]}), execute)
        await asyncio.gather(*service._workers.values())
        await manager.close()
        restarted = WorkflowRunService(TaskStore(manager))
        replay = [event async for event in restarted.subscribe("one-run", started["sequence"])]
        assert replay[-1]["status"] == "completed"
        assert calls == 1
    finally:
        release.set()
        await asyncio.gather(*service._workers.values())
        await manager.close()
