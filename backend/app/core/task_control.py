"""One cancellation decision tree for task and legacy workflow transports."""

import asyncio
from dataclasses import dataclass
from typing import Any

from app.core.creative_tasks import CreativeTaskService
from app.core.task_registry import TaskLifecycleRegistry
from app.core.workflow_runs import WorkflowRunService
from app.runners.creative_runner import CreativeRunner
from app.storage.task_store import TaskStore


@dataclass(frozen=True)
class TaskControlService:
    scheduler: CreativeTaskService
    creative: CreativeRunner
    workflows: WorkflowRunService
    registry: TaskLifecycleRegistry
    store: TaskStore
    cancellations: dict[str, asyncio.Event]

    async def cancel_workflow(self, run_id: str) -> bool:
        event = self.cancellations.get(run_id)
        accepted = self.workflows.cancel(run_id) or self.registry.cancel_task(run_id) or event is not None
        if not accepted:
            return False
        if event is not None:
            event.set()
        await self.store.finish_run(run_id, 'cancel-requested')
        return True

    async def cancel(self, task_id: str) -> dict[str, Any]:
        if await self.scheduler.cancel(task_id):
            return {'task_id': task_id, 'status': 'cancel-requested', 'engine_interrupted': False,
                    'disclaimer': 'Queued work will stop before dispatch. Active engine/provider work may finish; remote cancellation is not confirmed and charges may still apply.'}
        if task_id in self.creative.active_tasks or task_id in self.creative.active_cancellations:
            return await self.creative.cancel_task(task_id)
        if await self.cancel_workflow(task_id):
            return {'task_id': task_id, 'status': 'cancel-requested', 'engine_interrupted': False}
        raise LookupError(f"Active task '{task_id}' not found or already concluded.")
