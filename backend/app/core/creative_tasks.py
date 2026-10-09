"""Creative submissions survive HTTP disconnects and expose IDs before inference."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable

from app.core.task_registry import task_registry
from app.schemas.creative import CreativeActionRequest, CreativeActionResult
from app.schemas.task import RunRecord, TaskRecord
from app.storage.task_store import TERMINAL_STATUSES, TaskStore, task_store

CreativeExecutor = Callable[[CreativeActionRequest, str], Awaitable[CreativeActionResult]]


class CreativeTaskService:
    def __init__(self, store: TaskStore = task_store, concurrency: int = 2) -> None:
        self.store = store
        self._slots = asyncio.Semaphore(concurrency)
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._cancellations: dict[str, asyncio.Event] = {}
        self._connections: dict[str, asyncio.Lock] = {}
        self._dispatched: set[str] = set()

    async def submit(self, request: CreativeActionRequest, executor: CreativeExecutor) -> str:
        request = request.model_copy(deep=True)
        task_id = f"task_{uuid.uuid4()}"
        cancel = asyncio.Event()
        task_registry.register_task(task_id, "creative_action", cancel, {"action": request.action.value}, status="queued")
        self._cancellations[task_id] = cancel
        try:
            await self.store.create_run(RunRecord(id=task_id, project_id=request.project_id, request=request.model_dump()))
            await self.store.save_task(TaskRecord(id=task_id, run_id=task_id, node_id="canvas",
                node_type=request.action.value, params=request.model_dump()))
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
                    await executor(request, task_id)
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
        return True

    async def shutdown(self) -> None:
        workers = list(self._workers.values())
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


creative_tasks = CreativeTaskService()
