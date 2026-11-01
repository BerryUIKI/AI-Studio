"""Owned worker protocol with size/deadline limits and host-side request accounting."""

import asyncio
import json
import sys
import sysconfig
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ConfigDict, JsonValue

from app.runtime.worker_ownership import (
    OwnedWorkerTree,
    worker_environment,
    worker_process_options,
)
from app.schemas.node import DataType

MAX_MESSAGE_BYTES = 16 * 1024 * 1024
Broker = Callable[[dict[str, Any]], Awaitable[JsonValue]]


class AdapterError(RuntimeError):
    """A redacted execution failure; never contains script output or credentials."""


class AdapterOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: DataType
    value: JsonValue
    reported_model: str | None = None
    applied_parameters: dict[str, JsonValue] | None = None


def _contains_secret(value: Any, secret: str) -> bool:
    if isinstance(value, str):
        return secret in value
    if isinstance(value, dict):
        return any(
            _contains_secret(key, secret) or _contains_secret(item, secret)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret(item, secret) for item in value)
    return False


async def execute_adapter(
    *,
    language: str,
    source: str,
    inputs: dict[str, Any],
    broker: Broker,
    timeout: int = 150,
    max_requests: int = 4,
    module_paths: list[str] | None = None,
    sdk_key: str | None = None,
    on_job: Callable[[str], Awaitable[None]] | None = None,
) -> AdapterOutput:
    """Only the host executes HTTP; Python SDK access is separately trusted."""
    if language not in {"javascript", "python", "python_sdk"}:
        raise AdapterError("Unsupported calling-code language")
    spec = {
        "language": language,
        "source": source,
        "input": inputs,
        "sdk_key": sdk_key,
        "module_paths": module_paths or [sysconfig.get_paths()["purelib"]],
    }
    try:
        encoded = json.dumps(spec, allow_nan=False).encode() + b"\n"
    except (ValueError, TypeError):
        raise AdapterError("Calling-code input must be JSON") from None
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise AdapterError("Calling-code input exceeds the IPC byte limit")
    process = await asyncio.create_subprocess_exec(
        sys._base_executable,
        "-I",
        "-S",
        str(Path(__file__).with_name("custom_worker.py")),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=worker_environment(),
        limit=MAX_MESSAGE_BYTES + 1,
        **worker_process_options(),
    )
    owner = None
    try:
        owner = OwnedWorkerTree(process)

        async def drive() -> AdapterOutput:
            process.stdin.write(encoded)
            await process.stdin.drain()
            requests = 0
            for _ in range(128):
                line = await process.stdout.readline()
                if not line or len(line) > MAX_MESSAGE_BYTES:
                    raise AdapterError(
                        "Calling code exited or exceeded the IPC byte limit"
                    )
                try:
                    message = json.loads(line)
                except ValueError:
                    raise AdapterError(
                        "Calling code returned an invalid IPC message"
                    ) from None
                if sdk_key and _contains_secret(message, sdk_key):
                    raise AdapterError(
                        "Calling-code output contained a credential; output rejected"
                    )
                if not isinstance(message, dict):
                    raise AdapterError("Calling code returned a non-object IPC message")
                kind = message.get("kind")
                if kind == "result":
                    try:
                        return AdapterOutput.model_validate(message["result"])
                    except (ValueError, KeyError):
                        raise AdapterError(
                            "Calling code returned an invalid five-type output"
                        ) from None
                if kind == "error":
                    raise AdapterError(
                        "Calling code failed; check the adapter with fixture input"
                    )
                reply: dict[str, Any] = {"id": message.get("id")}
                if kind == "request":
                    requests += 1
                    if requests > max_requests:
                        raise AdapterError(
                            "Calling code exceeded the configured broker request limit"
                        )
                    if not isinstance(message.get("request"), dict):
                        raise AdapterError("Invalid calling-code broker request")
                    reply["result"] = await broker(message["request"])
                elif kind == "job_id":
                    job_id = message.get("job_id")
                    if (
                        not isinstance(job_id, str)
                        or not 1 <= len(job_id) <= 256
                        or any(ord(char) < 32 for char in job_id)
                    ):
                        raise AdapterError(
                            "Provider job ID must be a nonempty string of at most 256 characters"
                        )
                    if on_job:
                        await on_job(job_id)
                    reply["result"] = None
                elif kind == "wait":
                    milliseconds = message.get("milliseconds")
                    if (
                        not isinstance(milliseconds, int)
                        or not 0 <= milliseconds <= 5000
                    ):
                        raise AdapterError(
                            "Calling-code wait must be between 0 and 5000 milliseconds"
                        )
                    await asyncio.sleep(milliseconds / 1000)
                    reply["result"] = None
                else:
                    raise AdapterError("Unsupported calling-code IPC operation")
                response = json.dumps(reply, allow_nan=False).encode() + b"\n"
                if len(response) > MAX_MESSAGE_BYTES:
                    raise AdapterError("Broker response exceeds the IPC byte limit")
                process.stdin.write(response)
                await process.stdin.drain()
            raise AdapterError("Calling code exceeded its IPC operation limit")

        try:
            return await asyncio.wait_for(drive(), timeout)
        except asyncio.TimeoutError:
            raise AdapterError(
                "Calling-code deadline exceeded; any remote outcome may be unknown. No automatic retry was sent."
            ) from None
        except (BrokenPipeError, ConnectionResetError, ValueError, TypeError):
            raise AdapterError(
                "Calling-code communication failed; no output was adopted"
            ) from None
    finally:
        if owner:
            await owner.close()
        else:
            if process.returncode is None:
                process.kill()
            await process.wait()
