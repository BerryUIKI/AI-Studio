"""Admission, disconnect-independent execution and cancellation ownership."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.creative_tasks import CreativeTaskService
from app.core.task_registry import task_registry
from app.main import app
from app.runners.creative_runner import CreativeRunner
from app.schemas.creative import CreativeActionRequest
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore


@pytest.mark.asyncio
async def test_submit_returns_before_inference_and_cancel_preserves_real_result(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "tasks.db")
    store = TaskStore(manager)
    service = CreativeTaskService(store, concurrency=1)
    runner = CreativeRunner()
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def dispatch(*args: object) -> dict:
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()
        return {"asset_id": "output", "image_url": "/api/v1/assets/output/content", "width": 32, "height": 24}

    try:
        with patch("app.main.creative_tasks", service), patch("app.main.creative_runner", runner), patch("app.main.task_store", store), patch(
            "app.runners.creative_runner.task_store", store
        ), patch.object(runner, "_run_cloud", side_effect=dispatch), patch(
            "app.runners.creative_runner.cache_store.get_async", new=AsyncMock(return_value=None)
        ), patch("app.runners.creative_runner.cache_store.set_async", new=AsyncMock()), patch(
            "app.runners.creative_runner.asset_store.get_asset", new=AsyncMock(return_value=SimpleNamespace(width=32, height=24))
        ):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
                response = await asyncio.wait_for(client.post("/api/v1/creative/submit", json={"action": "txt2img", "engine_id": "fal_ai", "seed": 42}), 2)
                assert response.status_code == 202
                task_id = response.json()["task_id"]
                await asyncio.wait_for(entered.wait(), 2)
                assert (await client.post(f"/api/v1/tasks/{task_id}/cancel")).json()["status"] == "cancel-requested"
                assert (await client.get(f"/api/v1/creative/tasks/{task_id}")).json()["status"] == "cancel-requested"
                # The HTTP subscriber ends while inference remains owned by the service.
            assert not release.is_set()
            release.set()
            await asyncio.gather(*list(service._workers.values()))
            task = await store.get_task(task_id)
            assert calls == 1
            assert task.status == "succeeded"
            assert task.metadata["cancel_requested"] is True
            assert task.outputs["asset_id"] == "output"
            assert not await store.request_cancel(task_id)
            assert (await store.get_task(task_id)).status == "succeeded"
            assert not any(item["id"] == task_id for item in task_registry.list_active_tasks())
    finally:
        release.set()
        await service.shutdown()
        await manager.close()


@pytest.mark.asyncio
async def test_queued_cancel_never_dispatches_or_interrupts_other_task(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "tasks.db")
    store = TaskStore(manager)
    service = CreativeTaskService(store, concurrency=1)
    runner = AsyncMock()
    release = asyncio.Event()
    runner.side_effect = lambda *args: release.wait()
    request = CreativeActionRequest(action="txt2img", engine_id="fal_ai")
    try:
        # Occupy the bounded queue without invoking an engine.
        await service._slots.acquire()
        task_id = await service.submit(request, runner)
        assert any(item["id"] == task_id and item["status"] == "queued" for item in task_registry.list_active_tasks())
        assert await service.cancel(task_id)
        assert (await store.get_task(task_id)).status == "cancelled"
        service._slots.release()
        await asyncio.gather(*list(service._workers.values()), return_exceptions=True)
        runner.assert_not_awaited()
        assert (await store.get_task(task_id)).status == "cancelled"
        assert (await store.get_run(task_id)).status == "cancelled"
    finally:
        release.set()
        await service.shutdown()
        await manager.close()
