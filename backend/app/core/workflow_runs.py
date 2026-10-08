"""Idempotent workflow submission and durable subscriptions independent of transport."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.core.task_registry import task_registry
from app.schemas.task import RunRecord, TaskRecord, WorkflowRunRequest
from app.storage.task_store import TERMINAL_STATUSES, TaskStore, execution_task, redact_submission, task_store


class WorkflowEventSink:
    """Persist events and node outcomes before exposing them to subscribers."""

    def __init__(self, request: WorkflowRunRequest, store: TaskStore, changed: asyncio.Event, cancel: asyncio.Event) -> None:
        self.request = request
        self.store = store
        self.changed = changed
        self.cancel_event = cancel
        self.finished = False
        self.tasks = {node.id: TaskRecord(id=f"{request.run_id}:{node.id}", run_id=request.run_id,
            node_id=node.id, node_type=node.type, params=node.params,
            metadata={"engine": "cloud" if node.type in {"text.llm", "image.generate"} else "local"}) for node in request.graph.nodes}

    async def initialize(self) -> None:
        for task in self.tasks.values():
            await self.store.save_task(task)

    async def bind_inputs(self, node_id: str, inputs: dict[str, Any]) -> None:
        task = self.tasks[node_id]
        task.inputs = inputs
        execution_task.set((self.store, task))
        await self.store.save_task(task)

    async def send_text(self, data: str) -> None:
        event = json.loads(data)
        task = self.tasks.get(event.get("node_id"))
        if task:
            if event["type"] == "NODE_STATUS":
                task.status = {"completed": "succeeded", "error": "failed", "idle": "queued"}.get(event["status"], event["status"])
            elif event["type"] == "NODE_OUTPUT":
                task.outputs = event["output"]
            elif event["type"] == "NODE_ERROR":
                task.status = "failed"
                task.error = event["message"]
            await self.store.save_task(task)
        if event["type"] == "GRAPH_STARTED":
            await self.store.finish_run(self.request.run_id, "running")
        elif event["type"] == "GRAPH_FINISHED":
            outcome = {"completed": "succeeded"}.get(event["status"], event["status"])
            for unfinished in self.tasks.values():
                if unfinished.status not in TERMINAL_STATUSES:
                    unfinished.status = "cancelled" if outcome == "cancelled" else "interrupted"
                    await self.store.save_task(unfinished)
            await self.store.finish_run(self.request.run_id, outcome)
            self.finished = True
        await self.store.append_event(self.request.run_id, event)
        self.changed.set()

    async def close(self) -> None:
        """Execution has no ownership of a subscriber's socket."""


WorkflowExecutor = Callable[[WorkflowRunRequest, WorkflowEventSink], Awaitable[None]]


class WorkflowRunService:
    def __init__(self, store: TaskStore = task_store, concurrency: int = 4) -> None:
        self.store = store
        self._admission = asyncio.Lock()
        self._slots = asyncio.Semaphore(concurrency)
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._changes: dict[str, asyncio.Event] = {}
        self._cancellations: dict[str, asyncio.Event] = {}

    async def submit(self, request: WorkflowRunRequest, executor: WorkflowExecutor) -> str:
        request = request.model_copy(deep=True)
        request.run_id = request.run_id or str(uuid.uuid4())
        async with self._admission:
            existing = await self.store.get_run(request.run_id)
            if existing:
                if existing.request != redact_submission(request.model_dump()):
                    raise ValueError("Run ID already belongs to a different immutable submission")
                return request.run_id
            await self.store.create_run(RunRecord(id=request.run_id, project_id=request.project_id,
                target_node_id=request.target_node_id, request=request.model_dump()))
            changed = self._changes.setdefault(request.run_id, asyncio.Event())
            cancel = self._cancellations.setdefault(request.run_id, asyncio.Event())
            task_registry.register_task(request.run_id, "workflow_graph", cancel)
            sink = WorkflowEventSink(request, self.store, changed, cancel)
            await sink.initialize()
            self._workers[request.run_id] = asyncio.create_task(self._execute(request, sink, executor))
        return request.run_id

    async def _execute(self, request: WorkflowRunRequest, sink: WorkflowEventSink, executor: WorkflowExecutor) -> None:
        try:
            async with self._slots:
                await executor(request, sink)
            if not sink.finished:
                await sink.send_text(json.dumps({"type": "GRAPH_FINISHED", "status": "failed", "execution_time_ms": 0}))
        except asyncio.CancelledError:
            uncertain = False
            for task in sink.tasks.values():
                if task.status not in TERMINAL_STATUSES:
                    task.status = "outcome-unknown" if task.metadata.get("engine") == "cloud" else "interrupted"
                    uncertain |= task.status == "outcome-unknown"
                    task.error = "Application stopped before completion. Check the engine/provider before retrying."
                    await self.store.save_task(task)
            await self.store.finish_run(request.run_id, "outcome-unknown" if uncertain else "interrupted")
            raise
        except Exception as error:
            await sink.send_text(json.dumps({"type": "ERROR", "message": str(error)}))
            await sink.send_text(json.dumps({"type": "GRAPH_FINISHED", "status": "failed", "execution_time_ms": 0}))
        finally:
            task_registry.unregister_task(request.run_id)
            self._workers.pop(request.run_id, None)
            self._cancellations.pop(request.run_id, None)
            sink.changed.set()
            self._changes.pop(request.run_id, None)

    async def shutdown(self) -> None:
        workers = list(self._workers.values())
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    def cancel(self, run_id: str) -> bool:
        event = self._cancellations.get(run_id)
        if event is None:
            return False
        event.set()
        return True

    async def subscribe(self, run_id: str, after_sequence: int = 0) -> AsyncIterator[dict[str, Any]]:
        if await self.store.get_run(run_id) is None:
            raise LookupError("Run not found; reconnect never submits a new run")
        changed = self._changes.setdefault(run_id, asyncio.Event())
        while True:
            changed.clear()
            events = await self.store.get_events(run_id, after_sequence)
            for event in events:
                after_sequence = event["sequence"]
                yield event
                if event["type"] == "GRAPH_FINISHED":
                    return
            if len(events) == 500:
                continue
            run = await self.store.get_run(run_id)
            if run.status in TERMINAL_STATUSES:
                # A restart may have reconciled the run before a terminal event was recorded.
                yield {"type": "GRAPH_FINISHED", "run_id": run_id, "status": "completed" if run.status in {"succeeded", "cached"} else run.status,
                       "execution_time_ms": 0, "sequence": after_sequence + 1}
                return
            try:
                await asyncio.wait_for(changed.wait(), timeout=30)
            except asyncio.TimeoutError:
                continue


workflow_runs = WorkflowRunService()
