"""Uninstall only stopped managed engines under lifecycle and task admission leases."""

import asyncio
from typing import Any

from app.core.task_registry import task_registry
from app.core.workers import mutate_process
from app.runtime.managed_files import uninstall_managed_files
from app.schemas.engine import EngineType


async def uninstall_managed(engine_type: EngineType, supervisor: Any, installer: Any) -> dict[str, Any]:
    async def operation() -> dict[str, Any]:
        install_lock = task_registry.get_install_lock(engine_type.value)
        update_lock = task_registry.get_update_lock(engine_type.value)
        if task_registry.maintenance_active or install_lock.locked() or update_lock.locked():
            raise ValueError("An engine lifecycle operation is already in progress.")
        task_registry.maintenance_active = True
        try:
            async with install_lock, update_lock:
                if task_registry.has_active_tasks():
                    raise ValueError("Finish or cancel active work before uninstalling an engine.")

                def remove() -> dict[str, Any]:
                    if supervisor.is_running() or supervisor.get_pid() is not None:
                        raise ValueError("Stop the managed engine before uninstalling; a process may still be running.")
                    result = uninstall_managed_files(supervisor.engine_dir, engine_type)
                    manifest = installer.read_manifest(engine_type)
                    from app.schemas.engine import InstallPhase
                    manifest.phase = InstallPhase.IDLE
                    manifest.completed_at = None
                    manifest.error_message = None
                    manifest.last_log_line = "Uninstalled; engine files retained in " + str(result.get("retained_path"))
                    installer.write_manifest(manifest)
                    return result

                return await mutate_process(engine_type.value, remove)
        finally:
            task_registry.maintenance_active = False

    # Disconnecting a request must not release leases while disk mutations continue.
    worker = asyncio.create_task(operation())
    worker.add_done_callback(lambda task: None if task.cancelled() else task.exception())
    return await asyncio.shield(worker)
