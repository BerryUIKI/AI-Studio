"""The standalone worker suspends requests and keeps host APIs out of JS."""

import asyncio
import json
import sys
import sysconfig
from pathlib import Path

import pytest
from app.runtime.worker_ownership import (
    OwnedWorkerTree,
    worker_environment,
    worker_process_options,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "language,source",
    [
        (
            "javascript",
            """async function execute(input,ctx) {
    const response=await ctx.request({body:{prompt:input.prompt}});
    return {type:'json',value:{response,host:typeof process}}; }""",
        ),
        (
            "python",
            "async def execute(input,ctx):\n    print('discarded diagnostic')\n    response=await ctx.request({'body':{'prompt':input['prompt']}})\n    return {'type':'json','value':{'response':response,'host':'undefined'}}",
        ),
    ],
)
async def test_standalone_worker_broker_roundtrip(language: str, source: str) -> None:
    worker = Path(__file__).resolve().parents[1] / "app/runners/custom_worker.py"
    process = await asyncio.create_subprocess_exec(
        sys._base_executable,
        "-I",
        "-S",
        str(worker),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=worker_environment(),
        **worker_process_options(),
    )
    owner = OwnedWorkerTree(process)
    try:
        spec = {
            "language": language,
            "source": source,
            "input": {"prompt": "fixture"},
            "module_paths": [sysconfig.get_paths()["purelib"]],
        }
        process.stdin.write((json.dumps(spec) + "\n").encode())
        await process.stdin.drain()
        request = json.loads(await asyncio.wait_for(process.stdout.readline(), 3))
        assert request["kind"] == "request" and request["request"] == {
            "body": {"prompt": "fixture"}
        }
        process.stdin.write(
            (
                json.dumps({"id": request.get("id"), "result": {"fixture": True}})
                + "\n"
            ).encode()
        )
        await process.stdin.drain()
        result = json.loads(await asyncio.wait_for(process.stdout.readline(), 3))
        assert result["kind"] == "result"
        assert result["result"]["value"] == {
            "response": {"fixture": True},
            "host": "undefined",
        }
    finally:
        await owner.close()
