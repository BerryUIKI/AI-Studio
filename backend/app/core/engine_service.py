"""Typed engine connection and serialized managed-lifecycle operations."""

from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any, Protocol

from app.core.workers import mutate_process, run_blocking
from app.runtime.engine_manager import EngineManager
from app.schemas.engine import EngineType, EngineInstanceInfo, DetectedEngineInfo, EngineConfig, EngineConfigUpdateRequest


class ManagedSupervisor(Protocol):
    def start(self) -> dict[str, Any]: ...
    def stop(self) -> dict[str, Any]: ...
    def get_status(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class EngineService:
    manager: EngineManager
    managed: Mapping[EngineType, ManagedSupervisor]

    async def status(self, engine: EngineType) -> dict[str, Any]:
        return await run_blocking(self.managed[engine].get_status)

    async def start(self, engine: EngineType) -> dict[str, Any]:
        return await mutate_process(engine.value, self.managed[engine].start)

    async def stop(self, engine: EngineType) -> dict[str, Any]:
        return await mutate_process(engine.value, self.managed[engine].stop)

    async def instances(self) -> list[EngineInstanceInfo]:
        return await run_blocking(self.manager.get_all_instances)

    async def detect(self, paths: str | None) -> list[DetectedEngineInfo]:
        return await run_blocking(self.manager.detect_engines, [item.strip() for item in paths.split(',')] if paths else None)

    async def save_config(self, instance_id: str, request: EngineConfigUpdateRequest) -> tuple[EngineConfig, bool]:
        return await run_blocking(self.manager.save_engine_config, instance_id=instance_id,
                                 port=request.port, extra_args=request.extra_args)
