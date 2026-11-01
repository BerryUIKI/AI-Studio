"""A disconnected subscriber must never trigger a second inference call."""

import asyncio
import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.core.workflow_runs import WorkflowRunService
from app.schemas.task import WorkflowRunRequest
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore
from app.schemas.events import NodeOutputEvent, NodeStatusEvent


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


def test_websocket_disconnect_resumes_single_inference(tmp_path: Path) -> None:
    from app.main import app
    from app.core.cache import CacheStore

    manager = DatabaseManager(tmp_path / "socket.db")
    store = TaskStore(manager)
    service = WorkflowRunService(store)
    release = threading.Event()
    calls = 0

    async def controlled_runner(node_id: str, params: dict):
        nonlocal calls
        calls += 1
        yield NodeStatusEvent(node_id=node_id, status="running")
        await asyncio.to_thread(release.wait, 3)
        yield NodeOutputEvent(node_id=node_id, output={"text": "one output"})
        yield NodeStatusEvent(node_id=node_id, status="completed")

    with patch("app.main.workflow_runs", service), patch("app.main.task_store", store), patch(
        "app.main.run_input_text_node", controlled_runner
    ), patch("app.main.cache_store", CacheStore(manager=manager)), patch("app.main.llama_server_supervisor.is_installed", return_value=False):
        with TestClient(app) as client:
            submitted = client.post("/api/v1/workflow/submit", json={"run_id": "socket-run", "graph": {"nodes": [{"id": "text", "type": "input.text"}]}})
            assert submitted.status_code == 200
            with client.websocket_connect("/ws/workflow/run") as first:
                first.send_json({"type": "SUBSCRIBE", "run_id": "socket-run"})
                started = first.receive_json()
                running = first.receive_json()
                assert running["status"] == "running"
            release.set()
            with client.websocket_connect("/ws/workflow/run") as resumed:
                resumed.send_json({"type": "SUBSCRIBE", "run_id": "socket-run", "after_sequence": running["sequence"]})
                received = []
                while not received or received[-1]["type"] != "GRAPH_FINISHED":
                    received.append(resumed.receive_json())
            assert calls == 1
            assert any(event["type"] == "NODE_OUTPUT" for event in received)
            assert received[-1]["status"] == "completed"
            assert started["run_id"] == "socket-run"
            history = client.get("/api/v1/tasks/history").json()
            assert history[0]["outputs"] == {"text": "one output"}
            assert history[0]["status"] == "succeeded"
            assert client.post("/api/v1/workflow/submit", json={"run_id": "socket-run", "graph": {"nodes": []}}).status_code == 409
    asyncio.run(manager.close())
