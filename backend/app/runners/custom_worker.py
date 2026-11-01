"""Credential-free IPC for embedded JS and explicitly trusted Python adapters."""

import asyncio
import contextlib
import json
import sys
from typing import Any

OUTPUT = sys.stdout
MAX_MESSAGE_BYTES = 16 * 1024 * 1024


class _DiscardOutput:
    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        pass


def emit(value: dict[str, Any]) -> None:
    serialized = json.dumps(value, allow_nan=False)
    if len(serialized.encode()) > MAX_MESSAGE_BYTES:
        raise ValueError("Message limit exceeded")
    OUTPUT.write(serialized + "\n")
    OUTPUT.flush()


def receive() -> dict[str, Any]:
    line = sys.stdin.readline(MAX_MESSAGE_BYTES + 1)
    if not line or len(line.encode()) > MAX_MESSAGE_BYTES:
        raise ValueError("Invalid IPC input")
    return json.loads(line)


async def python_adapter(spec: dict[str, Any]) -> None:
    class Context:
        api_key = spec.get("sdk_key")

        async def request(self, request: dict[str, Any]) -> Any:
            emit({"kind": "request", "request": request})
            reply = await asyncio.to_thread(receive)
            if "error" in reply:
                raise RuntimeError("Broker request rejected")
            return reply["result"]

        async def wait(self, milliseconds: int) -> None:
            emit({"kind": "wait", "milliseconds": milliseconds})
            await asyncio.to_thread(receive)

        async def job_id(self, job_id: str) -> None:
            emit({"kind": "job_id", "job_id": job_id})
            await asyncio.to_thread(receive)

    namespace: dict[str, Any] = {}
    # Python is trusted code, not a security sandbox. Suppress arbitrary stdout.
    with contextlib.redirect_stdout(_DiscardOutput()):
        exec(compile(spec["source"], "<adapter>", "exec"), namespace)
        result = namespace["execute"](spec["input"], Context())
        if hasattr(result, "__await__"):
            result = await result
    emit({"kind": "result", "result": result})


def javascript_adapter(spec: dict[str, Any]) -> None:
    import quickjs

    context = quickjs.Context()
    context.set_memory_limit(64 * 1024 * 1024)
    context.set_max_stack_size(512 * 1024)
    context.set_time_limit(1)
    context.eval("""
        const __outbox = [], __pending = new Map();
        let __next = 0, __done = false, __result, __failed = false;
        function __message(kind, data) {
          const id = ++__next;
          return new Promise((resolve, reject) => {
            __pending.set(id, {resolve, reject});
            __outbox.push(Object.assign({kind, id}, data));
          });
        }
        const ctx = Object.freeze({
          request(request) { return __message('request', {request}); },
          job_id(job_id) { return __message('job_id', {job_id}); },
          wait(milliseconds) { return __message('wait', {milliseconds}); }
        });
        function __reply(reply) {
          const pending = __pending.get(reply.id);
          __pending.delete(reply.id);
          if (reply.error) pending.reject(new Error('Broker request rejected'));
          else pending.resolve(reply.result);
        }
    """)
    context.eval(spec["source"])
    context.eval(
        "Promise.resolve(execute("
        + json.dumps(spec["input"], allow_nan=False)
        + ",ctx)).then(r=>{__done=true;__result=r},()=>{__done=true;__failed=true});"
    )
    while True:
        for _ in range(128):
            if not context.execute_pending_job():
                break
        if context.eval("__done"):
            if context.eval("__failed"):
                raise RuntimeError("Adapter failed")
            emit(
                {
                    "kind": "result",
                    "result": json.loads(context.eval("JSON.stringify(__result)")),
                }
            )
            return
        request = json.loads(context.eval("JSON.stringify(__outbox.shift() || null)"))
        if request is None:
            raise RuntimeError("Adapter has no result or supported pending operation")
        emit(request)
        context.eval("__reply(" + json.dumps(receive(), allow_nan=False) + ")")


def main() -> None:
    spec = receive()
    sys.path.extend(spec.get("module_paths", []))
    try:
        if spec["language"] == "javascript":
            javascript_adapter(spec)
        else:
            asyncio.run(python_adapter(spec))
    except BaseException as error:
        emit(
            {
                "kind": "error",
                "message": "Calling code failed with fixture/provider input.",
                "line": error.lineno if isinstance(error, SyntaxError) else None,
            }
        )


if __name__ == "__main__":
    main()
