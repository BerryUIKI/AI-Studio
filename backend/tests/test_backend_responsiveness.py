"""API responsiveness and bounded worker ownership under slow scans/process calls."""

import asyncio
from pathlib import Path
import threading
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.workers import mutate_process, run_blocking
from app.main import app, manager_status
from app.storage.model_store import ModelStore


@pytest.mark.asyncio
async def test_health_and_task_lookup_remain_responsive_during_library_scan(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    for index in range(1000):
        (root / f"fixture-{index}.ckpt").write_bytes(b"fixture")
    store = ModelStore(tmp_path / "engine")
    store.add_root("fixture", str(root), "Fixture")
    entered = threading.Event()
    release = threading.Event()
    original = store._scan_all_roots

    def slow_scan() -> list:
        entered.set()
        assert release.wait(3)
        return original()

    with patch.object(store, "_scan_all_roots", side_effect=slow_scan), patch("app.main.model_store", store), patch(
        "app.main.task_store.get_task", new=AsyncMock(return_value=None)
    ):
        scan = asyncio.create_task(store.scan_all_roots_async(force=True))
        try:
            while not entered.is_set():
                await asyncio.sleep(0.001)
            start = time.monotonic()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000") as client:
                health, task = await asyncio.gather(client.get("/health"), client.get("/api/v1/creative/tasks/missing"))
            elapsed = time.monotonic() - start
            assert health.status_code == 200
            assert task.status_code == 404
            assert elapsed < 0.5
            assert not scan.done()
            assert (await manager_status()).models_indexed == 0
        finally:
            release.set()
            await scan
    assert store.inventory_count() == 1000
    with patch.object(store, "scan_all_roots", side_effect=AssertionError("Status must not scan")):
        with patch("app.main.model_store", store):
            assert (await manager_status()).models_indexed == 1000
        assert len(await store.scan_all_roots_async()) == 1000


@pytest.mark.asyncio
async def test_cancelled_request_keeps_process_lease_until_mutation_finishes() -> None:
    entered = threading.Event()
    release = threading.Event()
    order: list[str] = []

    def first() -> None:
        entered.set()
        assert release.wait(3)
        order.append("first")

    request = asyncio.create_task(mutate_process("fixture-process", first))
    while not entered.is_set():
        await asyncio.sleep(0.001)
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    following = asyncio.create_task(mutate_process("fixture-process", lambda: order.append("second")))
    await asyncio.sleep(0.02)
    assert order == []
    release.set()
    await following
    assert order == ["first", "second"]


@pytest.mark.asyncio
async def test_worker_pool_is_bounded() -> None:
    active = 0
    maximum = 0
    lock = threading.Lock()

    def blocking() -> None:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.02)
        with lock:
            active -= 1

    await asyncio.gather(*(run_blocking(blocking) for _ in range(12)))
    assert maximum == 4
