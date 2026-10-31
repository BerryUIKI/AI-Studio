"""Observed API health is separate from installation and process ownership."""

import asyncio
from dataclasses import dataclass
import time
from typing import Any

import httpx

from app.core.workers import run_blocking
from app.schemas.engine import EngineType


@dataclass(frozen=True)
class ServiceObservation:
    healthy: bool
    checked_at: float
    error: str | None = None


class ServiceHealthProbe:
    def __init__(self, ttl: float = 2, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.ttl = ttl
        self.transport = transport
        self._cache: dict[tuple[EngineType, int, int | None], tuple[float, ServiceObservation]] = {}
        self._pending: dict[tuple[asyncio.AbstractEventLoop, EngineType, int, int | None], asyncio.Task[ServiceObservation]] = {}

    async def get(self, engine_type: EngineType, port: int, pid: int | None = None) -> ServiceObservation:
        key = (engine_type, port, pid)
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < self.ttl:
            return cached[1]
        pending_key = (asyncio.get_running_loop(), engine_type, port, pid)
        task = self._pending.get(pending_key)
        if task is None:
            task = asyncio.create_task(self._probe(engine_type, port))
            self._pending[pending_key] = task

            def finished(completed: asyncio.Task[ServiceObservation]) -> None:
                self._pending.pop(pending_key, None)
                if not completed.cancelled() and completed.exception() is None:
                    if len(self._cache) >= 128:
                        self._cache.pop(next(iter(self._cache)))
                    self._cache[key] = (time.monotonic(), completed.result())

            task.add_done_callback(finished)
        return await asyncio.shield(task)

    async def _probe(self, engine_type: EngineType, port: int) -> ServiceObservation:
        path = "/system_stats" if engine_type == EngineType.COMFYUI else "/sdapi/v1/options"
        try:
            async with httpx.AsyncClient(timeout=2, trust_env=False, transport=self.transport) as client:
                response = await client.get(f"http://127.0.0.1:{port}{path}")
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict) or (engine_type == EngineType.COMFYUI and not isinstance(payload.get("system"), dict)):
                raise ValueError("The service returned an unexpected API response")
            return ServiceObservation(True, time.time())
        except (httpx.HTTPError, ValueError) as error:
            return ServiceObservation(False, time.time(), f"Service health check failed: {error}. Check engine logs and the configured port.")


service_health = ServiceHealthProbe()


async def observed_runtime_status(engine_type: EngineType, supervisor: Any) -> dict[str, Any]:
    status = await run_blocking(supervisor.get_status)
    running = bool(status.get("running"))
    status.update(process_running=running, service_healthy=None, service_checked_at=None, health_error=None)
    if not status.get("installed"):
        state = "not-installed"
    elif not running:
        failed = status.get("process_exit_code") not in (None, 0)
        state = "failed" if failed else "stopped"
        if failed:
            status["health_error"] = f"Engine process exited with code {status['process_exit_code']}. Check engine logs before restarting."
    else:
        observation = await service_health.get(engine_type, supervisor.port, status.get("pid"))
        status.update(service_healthy=observation.healthy, service_checked_at=observation.checked_at, health_error=observation.error)
        started = getattr(supervisor, "_started_at", None)
        state = "ready" if observation.healthy else "starting" if started is not None and time.monotonic() - started < 30 else "unhealthy"
    status["lifecycle_state"] = state
    return status
