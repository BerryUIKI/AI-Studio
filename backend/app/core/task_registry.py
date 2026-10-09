"""
Authoritative Task & Lifecycle Registry for Berry AI Studio.

Ensures:
1. Unified tracking across workflow graphs, creative actions, and background tasks.
2. Accurate live count of active in-flight jobs.
3. Cancellation token coordination for both workflow runs and canvas actions.
4. Exclusive leases for high-impact lifecycle actions such as engine updates.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskLifecycleRegistry:
    """Central registry tracking all active workflows, generative tasks, and engine leases."""

    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._cancellations: Dict[str, asyncio.Event] = {}
        self._update_locks: Dict[str, asyncio.Lock] = {}
        self._install_locks: Dict[str, asyncio.Lock] = {}

    def register_task(
        self,
        task_id: str,
        task_type: str,
        cancel_event: Optional[asyncio.Event] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "running",
    ) -> asyncio.Event:
        """Register a task with its cancellation event and optional metadata."""
        event = cancel_event or asyncio.Event()
        self._tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "status": status,
            "metadata": metadata or {},
        }
        self._cancellations[task_id] = event
        return event

    def unregister_task(self, task_id: str) -> None:
        """Unregister a concluded task."""
        self._tasks.pop(task_id, None)
        self._cancellations.pop(task_id, None)

    def get_cancel_event(self, task_id: str) -> Optional[asyncio.Event]:
        """Retrieve the cancellation event for a task."""
        return self._cancellations.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Signal cancellation to a task."""
        event = self._cancellations.get(task_id)
        if event:
            event.set()
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = "cancel-requested"
            return True
        return False

    def has_active_tasks(self) -> bool:
        """Return True if any active tasks are currently running."""
        return len(self._tasks) > 0

    def active_tasks_count(self) -> int:
        """Return the count of active tasks."""
        return len(self._tasks)

    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """List summary of all active tasks."""
        res = []
        for tid, t in self._tasks.items():
            entry = {**t.get("metadata", {}), "id": tid, "type": t["type"], "status": t["status"]}
            res.append(entry)
        return res

    def get_update_lock(self, engine_key: str) -> asyncio.Lock:
        """Retrieve or create an exclusive async lease lock for an engine update."""
        if engine_key not in self._update_locks:
            self._update_locks[engine_key] = asyncio.Lock()
        return self._update_locks[engine_key]

    def get_install_lock(self, engine_key: str) -> asyncio.Lock:
        """Retrieve or create an exclusive async lease lock for an engine installation."""
        if not hasattr(self, "_install_locks"):
            self._install_locks: Dict[str, asyncio.Lock] = {}
        if engine_key not in self._install_locks:
            self._install_locks[engine_key] = asyncio.Lock()
        return self._install_locks[engine_key]


task_registry = TaskLifecycleRegistry()

