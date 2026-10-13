"""Own only newly spawned adapter workers and their inherited process tree."""

import asyncio
import ctypes
import os
import signal
from ctypes import wintypes


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_int64),
        ("job_time", ctypes.c_int64),
        ("flags", wintypes.DWORD),
        ("min_working_set", ctypes.c_size_t),
        ("max_working_set", ctypes.c_size_t),
        ("active_processes", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "read_ops",
            "write_ops",
            "other_ops",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("basic", _BasicLimits),
        ("io", _IoCounters),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


class OwnedWorkerTree:
    """Windows job or newly created POSIX session; not an OS security sandbox."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self.handle: int | None = None
        self._closed = False
        if os.name == "nt":
            self._attach_windows()

    def _attach_windows(self) -> None:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel.SetInformationJobObject.restype = wintypes.BOOL
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise RuntimeError("Could not establish owned adapter worker lifetime")
        process_handle = None
        try:
            limits = _ExtendedLimits()
            limits.basic.flags = (
                0x2000 | 0x100 | 0x8
            )  # kill-on-close, process memory, active process count
            limits.basic.active_processes = 8
            limits.process_memory = 512 * 1024 * 1024
            if not kernel.SetInformationJobObject(
                handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ):
                raise RuntimeError("Could not apply adapter worker limits")
            process_handle = kernel.OpenProcess(
                0x0100 | 0x0001, False, self.process.pid
            )
            if not process_handle or not kernel.AssignProcessToJobObject(
                handle, process_handle
            ):
                raise RuntimeError("Could not attach the newly spawned adapter worker")
            self.handle = handle
        except BaseException:
            kernel.CloseHandle(handle)
            raise
        finally:
            if process_handle:
                kernel.CloseHandle(process_handle)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.handle is not None:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.restype = wintypes.BOOL
            kernel.CloseHandle(self.handle)
            self.handle = None
        elif os.name != "nt":
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif self.process.returncode is None:
            self.process.kill()
        await self.process.wait()


def worker_environment() -> dict[str, str]:
    """Retain Windows runtime essentials, exclude inherited provider credentials."""
    allowed = {"systemroot", "windir", "temp", "tmp", "path", "lang"}
    return {
        name: value for name, value in os.environ.items() if name.lower() in allowed
    }


def worker_process_options() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": 0x08000000}
    return {"start_new_session": True}
