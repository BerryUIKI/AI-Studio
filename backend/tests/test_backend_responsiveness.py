"""API responsiveness and bounded worker ownership under slow scans/process calls."""

import asyncio
import io
from pathlib import Path
import threading
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from PIL import Image

from app.core.workers import BlockingSnapshot, mutate_process, run_blocking
from app.main import app, manager_status
from app.storage.model_store import ModelStore
from app.storage.asset_store import AssetStore
from app.storage.db import DatabaseManager


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
    assert 1 <= maximum <= 4


@pytest.mark.asyncio
async def test_hardware_snapshot_coalesces_probes_and_reuses_observed_value() -> None:
    calls = 0

    def probe() -> dict[str, int]:
        nonlocal calls
        calls += 1
        time.sleep(0.02)
        return {"observed": calls}

    snapshot = BlockingSnapshot(probe, ttl=10)
    values = await asyncio.gather(*(snapshot.get() for _ in range(8)))
    assert values == [{"observed": 1}] * 8
    assert await snapshot.get() == {"observed": 1}
    assert calls == 1
    snapshot._updated = 0
    assert await snapshot.get() == {"observed": 2}


@pytest.mark.asyncio
async def test_health_remains_responsive_during_media_disk_write(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "assets.db")
    store = AssetStore(manager, tmp_path)
    output = io.BytesIO()
    with Image.new("RGB", (1024, 1024), "red") as image:
        image.save(output, "PNG", compress_level=0)
    entered = threading.Event()
    release = threading.Event()
    persist = store._persist_bytes

    def slow_write(data: bytes, content_hash: str, extension: str) -> str:
        entered.set()
        assert release.wait(3)
        return persist(data, content_hash, extension)

    with patch.object(store, "_persist_bytes", side_effect=slow_write):
        save = asyncio.create_task(store.save_bytes(output.getvalue(), "large.png"))
        try:
            while not entered.is_set():
                await asyncio.sleep(0.001)
            start = time.monotonic()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000") as client:
                response = await client.get("/health")
            assert response.status_code == 200
            assert time.monotonic() - start < 0.5
            assert not save.done()
        finally:
            release.set()
            try:
                assert (await save).byte_size > 3 * 1024 * 1024
            finally:
                await manager.close()


@pytest.mark.asyncio
async def test_runtime_status_probe_does_not_block_health() -> None:
    entered = threading.Event()
    release = threading.Event()

    def slow_probe() -> dict[str, bool]:
        entered.set()
        assert release.wait(3)
        return {"running": False}

    with patch("app.main.supervisor.get_status", side_effect=slow_probe):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000") as client:
            status = asyncio.create_task(client.get("/api/v1/runtime/status"))
            try:
                while not entered.is_set():
                    await asyncio.sleep(0.001)
                start = time.monotonic()
                assert (await client.get("/health")).status_code == 200
                assert time.monotonic() - start < 0.5
                assert not status.done()
            finally:
                release.set()
                assert (await status).json() == {"running": False}
