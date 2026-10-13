"""Owned adapter cancellation must not terminate an unrelated process."""

import asyncio
import json
import sys

import pytest
from app.runtime.worker_ownership import (
    OwnedWorkerTree,
    worker_environment,
    worker_process_options,
)


@pytest.mark.asyncio
async def test_owned_tree_closes_without_touching_other_process() -> None:
    executable = sys._base_executable
    unrelated = await asyncio.create_subprocess_exec(
        executable, "-c", "import time; time.sleep(30)", **worker_process_options()
    )
    process = await asyncio.create_subprocess_exec(
        executable,
        "-c",
        "import sys,time; sys.stdin.readline(); print('started', flush=True); time.sleep(30)",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        **worker_process_options(),
    )
    unrelated_owner = OwnedWorkerTree(unrelated)
    owner = OwnedWorkerTree(process)
    try:
        process.stdin.write(b"start\n")
        await process.stdin.drain()
        assert (await asyncio.wait_for(process.stdout.readline(), 3)).strip() == b"started"
        await owner.close()
        assert process.returncode is not None
        assert unrelated.returncode is None
        await owner.close()
    finally:
        await owner.close()
        await unrelated_owner.close()


def test_worker_environment_excludes_provider_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARK_API_KEY", "fixture-secret")
    monkeypatch.setenv("OTHER_PRIVATE_TOKEN", "fixture-secret")
    monkeypatch.setenv("SystemRoot", "fixture-windows-directory")
    environment = worker_environment()
    assert "ARK_API_KEY" not in environment and "OTHER_PRIVATE_TOKEN" not in environment
    assert "fixture-secret" not in json.dumps(environment)
    assert next(value for name, value in environment.items() if name.lower() == "systemroot") == "fixture-windows-directory"
