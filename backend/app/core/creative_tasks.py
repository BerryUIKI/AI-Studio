"""Creative submissions survive HTTP disconnects and expose IDs before inference."""

import asyncio
import uuid
from weakref import WeakValueDictionary
from collections.abc import Awaitable, Callable

from app.core.task_registry import task_registry
from app.schemas.creative import CreativeActionRequest, CreativeActionResult
from app.schemas.task import RunRecord, TaskRecord
from app.storage.task_store import TERMINAL_STATUSES, TaskStore, task_store

CreativeExecutor = Callable[[CreativeActionRequest, str], Awaitable[CreativeActionResult]]


class CreativeQueueFull(ValueError):
    """Admission is refused before creating a task when capacity is exhausted."""


class CreativeTaskService:
    def __init__(self, store: TaskStore = task_store, concurrency: int = 2, capacity: int = 64) -> None:
        if concurrency < 1 or capacity < concurrency:
            raise ValueError("Queue capacity must be at least its positive concurrency")
        self.store = store
        self.capacity = capacity
        self._slots = asyncio.Semaphore(concurrency)
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._cancellations: dict[str, asyncio.Event] = {}
        self._connections: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        self._dispatched: set[str] = set()

    async def execute_and_wait(self, request: CreativeActionRequest, executor: CreativeExecutor) -> CreativeActionResult:
        """Use the shared admission/lifecycle path for approved Agent steps."""
        task_id = await self.submit(request, executor)
        worker = self._workers[task_id]
        await asyncio.shield(worker)
        task = await self.store.get_task(task_id)
        if task is None:
            raise RuntimeError("Submitted task record is unavailable")
        if task.outputs:
            return CreativeActionResult.model_validate(task.outputs)
        return CreativeActionResult(success=False, task_id=task_id, error_message=task.error or task.status)

    async def submit(self, request: CreativeActionRequest, executor: CreativeExecutor) -> str:
        if len(self._cancellations) >= self.capacity:
            raise CreativeQueueFull("Creation queue is full. Wait for an active task or cancel queued work before retrying.")
        request = request.model_copy(deep=True)
        if (request.connection_id or request.engine_id).startswith("custom-"):
            from app.core.workers import run_blocking
            from app.runners.creative_runner import resolve_execution_plan

            plan = await run_blocking(resolve_execution_plan, request)
            for field in ("provider_revision", "credential_revision", "dependency_revision"):
                setattr(request, field, plan.custom_identity[field])
        task_id = f"task_{uuid.uuid4()}"
        cancel = asyncio.Event()
        task_registry.register_task(task_id, "creative_action", cancel, {"action": request.action.value}, status="queued")
        self._cancellations[task_id] = cancel
        try:
            await self.store.create_run(RunRecord(id=task_id, project_id=request.project_id, request=request.model_dump()))
            await self.store.save_task(TaskRecord(id=task_id, run_id=task_id, node_id="canvas",
                node_type=request.action.value, params=request.model_dump(), metadata={"dispatch_started": False}))
        except BaseException:
            task_registry.unregister_task(task_id)
            self._cancellations.pop(task_id, None)
            raise
        self._workers[task_id] = asyncio.create_task(self._execute(task_id, request, executor, cancel))
        return task_id

    async def _execute(self, task_id: str, request: CreativeActionRequest, executor: CreativeExecutor, cancel: asyncio.Event) -> None:
        try:
            async with self._slots:
                # Local creative actions serialize per connection. Cancellation never
                # interrupts unrelated jobs through an engine-wide interrupt endpoint.
                connection = request.connection_id or request.engine_id or "cloud"
                lock = self._connections.setdefault(connection, asyncio.Lock())
                async with lock:
                    if cancel.is_set():
                        task = await self.store.get_task(task_id)
                        task.status = "cancelled"
                        task.error = "Cancelled before dispatch; no engine work was submitted."
                        await self.store.save_task(task)
                        await self.store.finish_run(task_id, "cancelled")
                        return
                    task_registry.register_task(task_id, "creative_action", cancel, {"action": request.action.value})
                    self._dispatched.add(task_id)
                    result = await executor(request, task_id)
                    task = await self.store.get_task(task_id)
                    if task and task.status not in TERMINAL_STATUSES:
                        task.status = "succeeded" if result.success else "failed"
                        task.outputs = result.model_dump()
                        task.error = result.error_message
                        await self.store.save_task(task)
                        await self.store.finish_run(task_id, task.status)
        except BaseException as error:
            task = await self.store.get_task(task_id)
            if task and task.status not in TERMINAL_STATUSES:
                task.status = ("outcome-unknown" if task.metadata.get("engine") == "cloud" else "interrupted") if isinstance(error, asyncio.CancelledError) else "failed"
                task.error = str(error) or "Application stopped before the execution outcome was recorded. Check the provider before retrying."
                await self.store.save_task(task)
                await self.store.finish_run(task_id, task.status)
            if isinstance(error, asyncio.CancelledError):
                raise
        finally:
            task_registry.unregister_task(task_id)
            self._workers.pop(task_id, None)
            self._cancellations.pop(task_id, None)
            self._dispatched.discard(task_id)

    async def cancel(self, task_id: str) -> bool:
        cancel = self._cancellations.get(task_id)
        if cancel is None:
            return False
        if not await self.store.request_cancel(task_id):
            return False
        cancel.set()
        task_registry.cancel_task(task_id)
        if task_id not in self._dispatched:
            task = await self.store.get_task(task_id)
            task.status = "cancelled"
            task.error = "Cancelled before dispatch; no engine work was submitted."
            await self.store.save_task(task)
            await self.store.finish_run(task_id, "cancelled")
            worker = self._workers.get(task_id)
            if worker:
                worker.cancel()
            task_registry.unregister_task(task_id)
            self._workers.pop(task_id, None)
            self._cancellations.pop(task_id, None)
        return True

    async def shutdown(self) -> None:
        workers = list(self._workers.values())
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


creative_tasks = CreativeTaskService()
