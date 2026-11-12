"""A cancelled SDK worker must not leave its inherited child process running."""

import asyncio
import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path

import pytest
from app.runtime.worker_ownership import OwnedWorkerTree, worker_process_options


@pytest.mark.asyncio
async def test_child_process_stops_with_its_owned_worker() -> None:
    source = "import sys,subprocess,time; sys.stdin.readline(); child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); print(child.pid,flush=True); time.sleep(30)"
    process = await asyncio.create_subprocess_exec(
        sys._base_executable,
        "-c",
        source,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        **worker_process_options(),
    )
    owner = OwnedWorkerTree(process)
    handle = None
    try:
        process.stdin.write(b"start\n")
        await process.stdin.drain()
        child_pid = int(await asyncio.wait_for(process.stdout.readline(), 3))
        if os.name == "nt":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [
                wintypes.DWORD,
                wintypes.BOOL,
                wintypes.DWORD,
            ]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.GetExitCodeProcess.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.DWORD),
            ]
            kernel.GetExitCodeProcess.restype = wintypes.BOOL
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x1000, False, child_pid)
            assert handle
        await owner.close()
        for _ in range(100):
            if os.name == "nt":
                code = wintypes.DWORD()
                assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
                stopped = code.value != 259
            else:
                path = Path(f"/proc/{child_pid}/stat")
                stopped = not path.exists() or path.read_text().rsplit(")", 1)[
                    1
                ].strip().startswith("Z")
            if stopped:
                break
            await asyncio.sleep(0.02)
        assert stopped
    finally:
        await owner.close()
        if handle:
            kernel.CloseHandle(handle)
