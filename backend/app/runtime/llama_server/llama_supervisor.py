"""
Embedded llama-server (llama.cpp) Runtime Supervisor and Model Provisioning Engine.

Manages isolated execution and lifecycle of local llama-server runtime:
- Automatic detection of bundled or isolated llama-server binary
- Subprocess supervisor (start/stop/health check/pid tracking)
- Standard OpenAI-compatible HTTP endpoint (/v1/chat/completions, /v1/models)
- Shares unified GGUF models directly with the workflow canvas (engine/models/llm)
- Zero host pollution design
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from app.runtime.supervisor import get_default_engine_dir

logger = logging.getLogger(__name__)


class LlamaModelInfo(BaseModel):
    name: str
    path: str
    size_bytes: int = 0
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None
    modified_at: Optional[str] = None
    status: str = "ready"  # ready, loading, error


class LlamaServerRuntimeStatus(BaseModel):
    installed: bool = False
    binary_path: Optional[str] = None
    running: bool = False
    pid: Optional[int] = None
    port: int = 8080
    endpoint: str = "http://127.0.0.1:8080"
    active_model: Optional[str] = None
    models: List[LlamaModelInfo] = Field(default_factory=list)
    version: Optional[str] = None
    error_message: Optional[str] = None


class LlamaServerSupervisor:
    """Manages the isolated llama-server (llama.cpp) service process and GGUF models."""

    def __init__(self, engine_dir: Optional[Path] = None, port: int = 8080) -> None:
        self.engine_dir = engine_dir or get_default_engine_dir()
        self.port = port
        self.llama_dir = self.engine_dir / "llama_server"
        # Shared with workflow canvas: engine/models/llm/
        self.models_dir = self.engine_dir / "models" / "llm"
        self.pid_file = self.llama_dir / "llama_server.pid"
        self._process: Optional[subprocess.Popen] = None
        self._active_model_path: Optional[Path] = None

    def get_binary_path(self) -> Optional[Path]:
        """Locate embedded llama-server executable."""
        app_root = Path(__file__).resolve().parent.parent.parent.parent
        bin_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
        candidates = [
            # 1. Bundled inside distribution app directory runtime/llama_server
            app_root / "runtime" / "llama_server" / bin_name,
            # 2. Inside isolated engine directory
            self.llama_dir / bin_name,
            self.llama_dir / "bin" / bin_name,
            # 3. Third party build directory (if compiled from submodule)
            app_root / "third_party" / "llama.cpp" / "build" / "bin" / bin_name,
        ]

        for cand in candidates:
            if cand and cand.is_file():
                return cand

        # 4. Fallback check for system command
        sys_cmd = shutil.which("llama-server")
        if sys_cmd:
            return Path(sys_cmd)

        return None

    def is_installed(self) -> bool:
        return self.get_binary_path() is not None

    def ensure_directories(self) -> None:
        self.llama_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def _is_owned_executable(self, exe_path: Path) -> bool:
        """Ensure the executable matches the expected llama-server binary or lives in self.llama_dir."""
        try:
            exe_res = exe_path.resolve()
            expected_bin = self.get_binary_path()
            if expected_bin and exe_res == expected_bin.resolve():
                return True
            llama_res = self.llama_dir.resolve()
            if llama_res in exe_res.parents:
                return "llama" in exe_res.name.lower()
        except Exception:
            pass
        return False

    def _verify_process_identity(self, pid: int) -> bool:
        """Verify the process at pid is actually llama-server owned by this supervisor."""
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x1000, False, pid)
                if not handle:
                    return False
                try:
                    buf = ctypes.create_unicode_buffer(1024)
                    size = wintypes.DWORD(1024)
                    success = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
                    if success:
                        exe_path = Path(buf.value)
                        return self._is_owned_executable(exe_path)
                    return False
                finally:
                    kernel32.CloseHandle(handle)
            except Exception:
                return False
        else:
            try:
                proc_exe = Path(f"/proc/{pid}/exe")
                if proc_exe.exists():
                    resolved = Path(os.readlink(proc_exe))
                    if self._is_owned_executable(resolved):
                        return True
                proc_cmdline = Path(f"/proc/{pid}/cmdline")
                if proc_cmdline.is_file():
                    content = proc_cmdline.read_text(encoding="latin1", errors="ignore")
                    if "llama-server" in content or str(self.llama_dir) in content:
                        return True
                return False
            except (OSError, Exception):
                return False

    def get_pid(self) -> Optional[int]:
        if not self.pid_file.is_file():
            return None
        try:
            pid = int(self.pid_file.read_text(encoding="utf-8").strip())
            if self._verify_process_identity(pid):
                return pid
        except (ValueError, OSError):
            pass
        self._clean_pid_file()
        return None

    def _clean_pid_file(self) -> None:
        try:
            if self.pid_file.is_file():
                self.pid_file.unlink()
        except OSError:
            pass

    def is_running(self) -> bool:
        return self.get_pid() is not None

    async def check_health(self) -> bool:
        """Ping local llama-server HTTP health endpoint bypassing any system proxies."""
        try:
            async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
                res = await client.get(f"http://127.0.0.1:{self.port}/health")
                return res.status_code == 200
        except Exception:
            return False

    def list_local_models(self) -> List[LlamaModelInfo]:
        """Scan models directory for available .gguf files."""
        self.ensure_directories()
        models: List[LlamaModelInfo] = []
        # Search both self.models_dir and parent models/
        scan_paths = [self.models_dir, self.engine_dir / "models"]
        seen_names = set()

        for p in scan_paths:
            if not p.is_dir():
                continue
            for f in p.glob("*.gguf"):
                if f.name in seen_names:
                    continue
                seen_names.add(f.name)
                try:
                    stat = f.stat()
                    models.append(
                        LlamaModelInfo(
                            name=f.name,
                            path=str(f.resolve()),
                            size_bytes=stat.st_size,
                            modified_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                            status="ready",
                        )
                    )
                except Exception:
                    pass
        return models

    async def get_status(self) -> LlamaServerRuntimeStatus:
        bin_path = self.get_binary_path()
        installed = self.is_installed()
        running = self.is_running()
        models = self.list_local_models()

        healthy = await self.check_health()
        if healthy:
            running = True

        return LlamaServerRuntimeStatus(
            installed=installed,
            binary_path=str(bin_path) if bin_path else None,
            running=running,
            pid=self.get_pid(),
            port=self.port,
            endpoint=f"http://127.0.0.1:{self.port}/v1",
            active_model=str(self._active_model_path.name) if self._active_model_path else (models[0].name if models else None),
            models=models,
        )

    def start(self, model_filename_or_path: Optional[str] = None, vram_gpu_layers: int = 99) -> Dict[str, Any]:
        """Launch isolated llama-server process with specified GGUF model."""
        bin_path = self.get_binary_path()
        if not bin_path:
            return {
                "success": False,
                "message": f"llama-server executable not found. Please place llama-server into {self.llama_dir}",
            }

        # Resolve model path
        models = self.list_local_models()
        target_model: Optional[Path] = None

        if model_filename_or_path:
            cand = Path(model_filename_or_path)
            if cand.is_file():
                target_model = cand
            else:
                cand_in_dir = self.models_dir / model_filename_or_path
                if cand_in_dir.is_file():
                    target_model = cand_in_dir

        if not target_model and models:
            target_model = Path(models[0].path)

        if not target_model:
            return {
                "success": False,
                "message": "No GGUF models found in models directory. Please download a GGUF model first.",
            }

        if self.is_running():
            # If already running with the exact model, return success
            if self._active_model_path == target_model:
                return {
                    "success": True,
                    "message": f"llama-server is already running with {target_model.name} (PID: {self.get_pid()})",
                    "pid": self.get_pid(),
                }
            # Switch model: stop current instance
            self.stop()

        self.ensure_directories()
        self._active_model_path = target_model

        cmd = [
            str(bin_path),
            "-m", str(target_model),
            "--port", str(self.port),
            "--host", "127.0.0.1",
            "-ngl", str(vram_gpu_layers),  # Offload layers to GPU
            "-c", "4096",                   # Context window
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            pid = self._process.pid
            self.pid_file.write_text(str(pid), encoding="utf-8")
            return {
                "success": True,
                "message": f"llama-server started successfully with {target_model.name} (PID: {pid})",
                "pid": pid,
                "model": target_model.name,
            }
        except Exception as err:
            return {
                "success": False,
                "message": f"Failed to start llama-server: {err}",
            }

    def stop(self) -> Dict[str, Any]:
        """Terminate managed llama-server process."""
        pid = self.get_pid()
        if not pid:
            return {"success": True, "message": "llama-server is not running"}

        if not self._verify_process_identity(pid):
            self._clean_pid_file()
            return {
                "success": False,
                "message": f"Process {pid} is not a verified llama-server process; refusing to terminate.",
            }

        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
            else:
                os.kill(pid, 15)
            return {"success": True, "message": f"llama-server process {pid} terminated"}
        except Exception as e:
            return {"success": False, "message": f"Error terminating llama-server: {e}"}
        finally:
            self._clean_pid_file()
            self._active_model_path = None

    async def install(self) -> Dict[str, Any]:
        """Download and unpack official pre-compiled standalone llama-server binary without host pollution."""
        self.ensure_directories()
        bin_path = self.get_binary_path()
        if bin_path:
            return {
                "success": True,
                "installed": True,
                "message": f"llama-server is already installed at {bin_path}",
                "binary_path": str(bin_path),
            }

        import zipfile
        logger.info(f"Downloading pre-compiled llama-server to {self.llama_dir}...")

        # Binary download candidate sources
        if sys.platform == "win32":
            sources = [
                "https://ghfast.top/https://github.com/ggml-org/llama.cpp/releases/download/b4800/llama-b4800-bin-win-cpu-x64.zip",
                "https://github.com/ggml-org/llama.cpp/releases/download/b4800/llama-b4800-bin-win-cpu-x64.zip",
            ]
        else:
            sources = [
                "https://ghfast.top/https://github.com/ggml-org/llama.cpp/releases/download/b4800/llama-b4800-bin-ubuntu-x64.zip",
                "https://github.com/ggml-org/llama.cpp/releases/download/b4800/llama-b4800-bin-ubuntu-x64.zip",
            ]

        archive_path = self.llama_dir / "llama_server_dl.zip"
        download_success = False

        for url in sources:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(connect=15.0, read=180.0, write=60.0, pool=15.0), follow_redirects=True, trust_env=False) as client:
                    async with client.stream("GET", url) as resp:
                        if resp.status_code == 200:
                            with open(archive_path, "wb") as f:
                                async for chunk in resp.aiter_bytes(chunk_size=1024 * 64):
                                    f.write(chunk)
                            download_success = True
                            break
            except Exception as err:
                logger.warning(f"Failed downloading llama-server from {url}: {err}")

        if not download_success or not archive_path.exists():
            return {
                "success": False,
                "installed": False,
                "message": f"Could not auto-download llama-server. Place llama-server.exe into {self.llama_dir}",
                "target_dir": str(self.llama_dir),
            }

        # Unpack archive
        try:
            with zipfile.ZipFile(archive_path, "r") as z:
                z.extractall(self.llama_dir)
            archive_path.unlink(missing_ok=True)
            # Ensure permissions on POSIX
            new_bin = self.get_binary_path()
            if new_bin and sys.platform != "win32":
                try:
                    os.chmod(new_bin, 0o755)
                except Exception:
                    pass
            return {
                "success": True,
                "installed": True,
                "message": f"llama-server successfully installed to {self.llama_dir}",
                "binary_path": str(new_bin) if new_bin else None,
            }
        except Exception as unpack_err:
            archive_path.unlink(missing_ok=True)
            return {
                "success": False,
                "installed": False,
                "message": f"Error unpacking llama-server archive: {unpack_err}",
                "target_dir": str(self.llama_dir),
            }


# Global singleton instance
llama_server_supervisor = LlamaServerSupervisor()
