"""A PID or generic HTTP success is not an observed healthy engine API."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from app.runtime.service_health import ServiceHealthProbe, observed_runtime_status
from app.schemas.engine import EngineType


@pytest.mark.asyncio
async def test_probe_coalesces_requests_and_validates_response() -> None:
    calls = 0

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={"system": {"os": "fixture"}})

    probe = ServiceHealthProbe(transport=httpx.MockTransport(respond))
    observations = await asyncio.gather(*(probe.get(EngineType.COMFYUI, 8188) for _ in range(8)))
    assert all(item.healthy for item in observations)
    assert calls == 1
    assert (await probe.get(EngineType.COMFYUI, 8188)).healthy
    assert calls == 1


@pytest.mark.asyncio
async def test_process_starting_unhealthy_and_healthy_are_distinct() -> None:
    probe = ServiceHealthProbe(ttl=0, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})))
    target = SimpleNamespace(port=8188, _started_at=time.monotonic(), get_status=lambda: {"installed": True, "running": True, "pid": 123})
    with patch("app.runtime.service_health.service_health", probe):
        status = await observed_runtime_status(EngineType.COMFYUI, target)
        assert status["process_running"]
        assert status["service_healthy"] is False
        assert status["lifecycle_state"] == "starting"
        target._started_at = time.monotonic() - 31
        assert (await observed_runtime_status(EngineType.COMFYUI, target))["lifecycle_state"] == "unhealthy"
        status = await observed_runtime_status(EngineType.WEBUI, target)
        assert status["lifecycle_state"] == "ready"
        assert status["service_checked_at"] > 0


@pytest.mark.asyncio
async def test_stopped_or_absent_engine_never_claims_service_health() -> None:
    for installed, state in [(False, "not-installed"), (True, "stopped")]:
        target = SimpleNamespace(port=8188, get_status=lambda: {"installed": installed, "running": False})
        status = await observed_runtime_status(EngineType.COMFYUI, target)
        assert status["lifecycle_state"] == state
        assert status["service_healthy"] is None
