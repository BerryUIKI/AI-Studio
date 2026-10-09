"""Bound blocking work and serialize process mutations without blocking the API loop."""

import asyncio
import time
from typing import Callable, Generic, ParamSpec, TypeVar
from weakref import WeakKeyDictionary

P = ParamSpec("P")
T = TypeVar("T")
_limits: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = WeakKeyDictionary()
_leases: WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, asyncio.Lock]] = WeakKeyDictionary()


async def run_blocking(function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    loop = asyncio.get_running_loop()
    limit = _limits.setdefault(loop, asyncio.Semaphore(4))
    await limit.acquire()
    work = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))

    def finished(task: asyncio.Task[T]) -> None:
        limit.release()
        if not task.cancelled():
            task.exception()  # Retrieve failures even if the requesting connection disappeared.

    work.add_done_callback(finished)
    return await asyncio.shield(work)


class BlockingSnapshot(Generic[T]):
    """Coalesce concurrent probes and retain a short-lived observed result."""

    def __init__(self, loader: Callable[[], T], ttl: float = 2.0) -> None:
        self.loader = loader
        self.ttl = ttl
        self._value: T | None = None
        self._updated = 0.0
        self._pending: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Task[T]] = WeakKeyDictionary()

    async def get(self) -> T:
        if self._value is not None and time.monotonic() - self._updated < self.ttl:
            return self._value
        loop = asyncio.get_running_loop()
        task = self._pending.get(loop)
        if task is None:
            task = asyncio.create_task(run_blocking(self.loader))
            self._pending[loop] = task

            def finished(completed: asyncio.Task[T]) -> None:
                self._pending.pop(loop, None)
                if not completed.cancelled() and completed.exception() is None:
                    self._value = completed.result()
                    self._updated = time.monotonic()

            task.add_done_callback(finished)
        return await asyncio.shield(task)


async def mutate_process(key: str, function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    leases = _leases.setdefault(asyncio.get_running_loop(), {})
    lease = leases.setdefault(key, asyncio.Lock())
    await lease.acquire()
    work = asyncio.create_task(run_blocking(function, *args, **kwargs))

    def finished(task: asyncio.Task[T]) -> None:
        lease.release()
        if not task.cancelled():
            task.exception()

    work.add_done_callback(finished)
    return await asyncio.shield(work)
