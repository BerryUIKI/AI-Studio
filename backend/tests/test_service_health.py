"""A PID or generic HTTP success is not an observed healthy engine API."""

import asyncio
import time
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.runtime.service_health import ServiceHealthProbe, observed_runtime_status
from app.schemas.engine import EngineInstanceInfo, EngineType
from app.core.engine_service import EngineService
from app.runtime.supervisor import ComfySupervisor
from app.runtime.webui_supervisor import WebUISupervisor


@pytest.mark.asyncio
async def test_instance_catalog_marks_observed_ready_services_as_running() -> None:
    manager = Mock()
    manager.get_all_instances.return_value = [EngineInstanceInfo(id="comfyui-managed", type="comfyui", name="Fixture", status="stopped")]
    target = SimpleNamespace()
    service = EngineService(manager, {EngineType.COMFYUI: target})
    observation = {"process_running": True, "service_healthy": True, "service_checked_at": 1.0, "lifecycle_state": "ready", "health_error": None}
    with patch("app.core.engine_service.observed_runtime_status", AsyncMock(return_value=observation)):
        instance = (await service.instances())[0]
    assert instance.status == "running"
    assert instance.lifecycle_state == "ready"
    assert instance.service_healthy is True


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
    await probe.get(EngineType.COMFYUI, 8188, pid=123)
    await probe.get(EngineType.COMFYUI, 8188, pid=456)
    assert calls == 3
    assert (await probe.get(EngineType.COMFYUI, 8188)).healthy
    assert calls == 3


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


def test_supervisor_retains_identity_of_its_actual_live_child(tmp_path: Path) -> None:
    target = ComfySupervisor(tmp_path)
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    target._process = process
    try:
        assert target.get_pid() == process.pid
        assert target._verify_process_identity(process.pid)
    finally:
        process.terminate()
        process.wait(timeout=5)
    assert target.get_pid() is None


@pytest.mark.asyncio
async def test_failed_process_returns_actionable_diagnostics() -> None:
    target = SimpleNamespace(port=8188, get_status=lambda: {"installed": True, "running": False, "process_exit_code": 4})
    status = await observed_runtime_status(EngineType.COMFYUI, target)
    assert status["lifecycle_state"] == "failed"
    assert "code 4" in status["health_error"]
    assert "logs" in status["health_error"]


@pytest.mark.parametrize("supervisor_type", [ComfySupervisor, WebUISupervisor])
def test_failed_termination_preserves_process_status(tmp_path: Path, supervisor_type: type) -> None:
    target = supervisor_type(tmp_path)
    target._process = SimpleNamespace(pid=123, poll=lambda: None)
    with patch("sys.platform", "win32"), patch("subprocess.run", return_value=SimpleNamespace(returncode=1)):
        result = target.stop()
    assert result["success"] is False
    assert target.get_pid() == 123
    assert "termination failed" in result["message"]
