"""Creative task transport: admission, durable lookup, and event subscriptions."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.core.creation_services import CreationServices
from app.core.creative_tasks import CreativeQueueFull
from app.core.task_registry import task_registry
from app.schemas.creative import CreativeActionRequest, CreativeActionResult
from app.schemas.task import TaskRecord
from app.storage.task_store import TERMINAL_STATUSES


def create_creative_router(get_services: Callable[[], CreationServices]) -> APIRouter:
    router = APIRouter(prefix='/api/v1/creative', tags=['Creative tasks'])

    @router.post('/execute', response_model=CreativeActionResult)
    async def execute(req: CreativeActionRequest) -> CreativeActionResult:
        """Legacy synchronous compatibility; new clients use submit/events."""
        task_id = f'task_{uuid.uuid4()}'
        try:
            task_registry.register_task(task_id, 'creative_action', status='queued')
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        try:
            return await get_services().runner.execute(req, task_id)
        finally:
            task_registry.unregister_task(task_id)

    @router.post('/submit', status_code=202)
    async def submit(req: CreativeActionRequest) -> dict[str, str]:
        services = get_services()
        try:
            task_id = await services.scheduler.submit(req, services.runner.execute)
        except CreativeQueueFull as error:
            raise HTTPException(status_code=503, detail=str(error), headers={'Retry-After': '5'}) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {'task_id': task_id, 'status': 'queued'}

    @router.get('/tasks/{task_id}', response_model=TaskRecord)
    async def status(task_id: str) -> TaskRecord:
        task = await get_services().tasks.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail='Creative task not found.')
        return task

    @router.get('/tasks/{task_id}/events')
    async def events(task_id: str, request: Request, after_sequence: int = Query(0, ge=0)) -> StreamingResponse:
        store = get_services().tasks
        if await store.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail='Task not found')

        async def stream() -> AsyncIterator[str]:
            sequence = after_sequence
            while not await request.is_disconnected():
                events = await store.task_events(task_id, sequence)
                task = await store.get_task(task_id)
                if task is None:
                    return
                for event in events:
                    sequence = int(event['sequence'])
                    payload = {**task.model_dump(), **event}
                    yield f'id: {sequence}\ndata: {json.dumps(payload)}\n\n'
                if task.status in TERMINAL_STATUSES and len(events) < 500:
                    if not events:
                        yield f'data: {task.model_dump_json()}\n\n'
                    return
                yield ': keepalive\n\n'
                await asyncio.sleep(1)

        return StreamingResponse(stream(), media_type='text/event-stream', headers={
            'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no',
        })

    return router
