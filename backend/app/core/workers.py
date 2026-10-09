"""Bound blocking work and serialize process mutations without blocking the API loop."""

import asyncio
from typing import Callable, ParamSpec, TypeVar
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
