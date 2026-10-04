"""
Embedded Ollama Runtime Supervisor and Model Provisioning Engine.

Manages isolated execution and lifecycle of local Ollama runtime:
- Automatic detection of bundled or system Ollama binary
- Subprocess supervisor (start/stop/health check/pid tracking)
- Model pulling and inspection (/api/pull, /api/tags, /api/show)
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


class OllamaModelInfo(BaseModel):
    name: str
    size_bytes: int = 0
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None
    modified_at: Optional[str] = None
    status: str = "ready"  # ready, pulling, downloading, error


class OllamaRuntimeStatus(BaseModel):
    installed: bool = False
    binary_path: Optional[str] = None
    running: bool = False
    pid: Optional[int] = None
    port: int = 11434
    endpoint: str = "http://127.0.0.1:11434"
    models: List[OllamaModelInfo] = Field(default_factory=list)
    version: Optional[str] = None
    error_message: Optional[str] = None


class OllamaSupervisor:
    """Manages the isolated Ollama service process and model pulls."""

    def __init__(self, engine_dir: Optional[Path] = None, port: int = 11434) -> None:
        self.engine_dir = engine_dir or get_default_engine_dir()
        self.port = port
        self.ollama_dir = self.engine_dir / "ollama"
        self.models_dir = self.ollama_dir / "models"
        self.pid_file = self.ollama_dir / "ollama.pid"
        self._process: Optional[subprocess.Popen] = None
        self._pulling_tasks: Dict[str, Dict[str, Any]] = {}

    def get_binary_path(self) -> Optional[Path]:
        """Locate embedded or system Ollama binary without polluting global environment."""
        app_root = Path(__file__).resolve().parent.parent.parent.parent
        candidates = [
            # 1. Bundled inside distribution app directory runtime/ollama
            app_root / "runtime" / "ollama" / "ollama.exe" if sys.platform == "win32" else app_root / "runtime" / "ollama" / "ollama",
            # 2. Bundled inside isolated engine directory
            self.ollama_dir / "ollama.exe" if sys.platform == "win32" else self.ollama_dir / "ollama",
            self.ollama_dir / "bin" / "ollama.exe" if sys.platform == "win32" else self.ollama_dir / "bin" / "ollama",
            # 3. Local app data program install (isolated to user profile)
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe" if sys.platform == "win32" else None,
        ]

        for cand in candidates:
            if cand and cand.is_file():
                return cand

        # 4. System PATH check
        sys_cmd = shutil.which("ollama")
        if sys_cmd:
            return Path(sys_cmd)

        return None

    def is_installed(self) -> bool:
        return self.get_binary_path() is not None

    def ensure_directories(self) -> None:
        self.ollama_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def get_pid(self) -> Optional[int]:
        if not self.pid_file.is_file():
            return None
        try:
            pid = int(self.pid_file.read_text(encoding="utf-8").strip())
            # Verify process is alive
            if sys.platform == "win32":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x1000, False, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return pid
            else:
                os.kill(pid, 0)
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
        """Ping local Ollama HTTP endpoint bypassing any system proxies."""
        try:
            async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
                res = await client.get(f"http://127.0.0.1:{self.port}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def get_status(self) -> OllamaRuntimeStatus:
        bin_path = self.get_binary_path()
        installed = bin_path is not None
        running = self.is_running()
        models: List[OllamaModelInfo] = []
        ver: Optional[str] = None

        # Even if PID is not ours, check if port 11434 is responding (e.g. background Ollama service)
        healthy = await self.check_health()
        if healthy:
            running = True
            try:
                async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                    tags_res = await client.get(f"http://127.0.0.1:{self.port}/api/tags")
                    if tags_res.status_code == 200:
                        data = tags_res.json()
                        for m in data.get("models", []):
                            details = m.get("details", {})
                            models.append(
                                OllamaModelInfo(
                                    name=m.get("name", "unknown"),
                                    size_bytes=m.get("size", 0),
                                    parameter_size=details.get("parameter_size"),
                                    quantization_level=details.get("quantization_level"),
                                    modified_at=m.get("modified_at"),
                                    status="ready",
                                )
                            )
                    ver_res = await client.get(f"http://127.0.0.1:{self.port}/api/version")
                    if ver_res.status_code == 200:
                        ver = ver_res.json().get("version")
            except Exception as e:
                logger.debug(f"Failed to fetch ollama models/version: {e}")

        return OllamaRuntimeStatus(
            installed=installed,
            binary_path=str(bin_path) if bin_path else None,
            running=running,
            pid=self.get_pid(),
            port=self.port,
            endpoint=f"http://127.0.0.1:{self.port}",
            models=models,
            version=ver,
        )

    def start(self) -> Dict[str, Any]:
        """Launch isolated Ollama server process."""
        bin_path = self.get_binary_path()
        if not bin_path:
            return {
                "success": False,
                "message": "Ollama executable not found. Please install or download Ollama runtime.",
            }

        if self.is_running():
            return {
                "success": True,
                "message": f"Ollama is already running (PID: {self.get_pid()})",
                "pid": self.get_pid(),
            }

        self.ensure_directories()
        env = os.environ.copy()
        env["OLLAMA_HOST"] = f"127.0.0.1:{self.port}"
        env["OLLAMA_MODELS"] = str(self.models_dir)

        cmd = [str(bin_path), "serve"]
        try:
            self._process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            pid = self._process.pid
            self.pid_file.write_text(str(pid), encoding="utf-8")
            return {
                "success": True,
                "message": f"Ollama started successfully (PID: {pid})",
                "pid": pid,
            }
        except Exception as err:
            return {
                "success": False,
                "message": f"Failed to start Ollama: {err}",
            }

    def stop(self) -> Dict[str, Any]:
        """Terminate managed Ollama server process."""
        pid = self.get_pid()
        if not pid:
            return {"success": True, "message": "Ollama is not running"}

        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
            else:
                os.kill(pid, 15)
        except Exception as e:
            return {"success": False, "message": f"Error terminating Ollama: {e}"}
        finally:
            self._clean_pid_file()

        return {"success": True, "message": f"Ollama process {pid} stopped"}

    def install(self) -> Dict[str, Any]:
        """Provide automated or direct download instructions for the embedded Ollama runtime without polluting host global environment."""
        if self.is_installed():
            return {
                "success": True,
                "message": "Embedded Ollama is already installed and ready.",
                "installed": True,
            }

        target_dir = str(self.ollama_dir)
        if sys.platform == "win32":
            return {
                "success": True,
                "message": f"Place ollama.exe into the isolated runtime directory: {target_dir} or install Ollama for Windows.",
                "target_dir": target_dir,
                "installed": False,
                "download_url": "https://ollama.com/download/windows",
            }
        else:
            return {
                "success": True,
                "message": f"Place ollama into the isolated directory: {target_dir}",
                "target_dir": target_dir,
                "installed": False,
                "download_url": "https://ollama.com",
            }

    async def pull_model_stream(self, model_name: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream model pulling progress from Ollama /api/pull, ensuring Ollama is active and bypassing proxies."""
        if not self.is_installed():
            yield {
                "status": "error",
                "error": f"Embedded Ollama binary not found. Please place ollama into {self.ollama_dir} or install Ollama locally.",
                "code": "NOT_INSTALLED",
            }
            return

        # Ensure Ollama daemon is running, auto-start if needed
        if not (await self.check_health()):
            logger.info("Ollama is not running. Auto-starting Ollama service...")
            start_res = self.start()
            if not start_res.get("success") and not self.is_running():
                yield {
                    "status": "error",
                    "error": f"Failed to start local Ollama engine: {start_res.get('message', 'Unknown error')}",
                    "code": "START_FAILED",
                }
                return

            # Wait up to 6 seconds for Ollama HTTP endpoint to become healthy
            ready = False
            for _ in range(12):
                await asyncio.sleep(0.5)
                if await self.check_health():
                    ready = True
                    break

            if not ready:
                yield {
                    "status": "error",
                    "error": f"Ollama service started but is not responding on port {self.port}.",
                    "code": "PORT_UNRESPONSIVE",
                }
                return

        url = f"http://127.0.0.1:{self.port}/api/pull"
        self._pulling_tasks[model_name] = {"status": "pulling", "total": 0, "completed": 0}

        try:
            async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
                async with client.stream("POST", url, json={"name": model_name, "stream": True}) as response:
                    if response.status_code != 200:
                        yield {"status": "error", "error": f"Ollama returned HTTP error ({response.status_code})"}
                        return

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            status = data.get("status", "")
                            total = data.get("total", 0)
                            completed = data.get("completed", 0)
                            self._pulling_tasks[model_name] = {
                                "status": status,
                                "total": total,
                                "completed": completed,
                            }
                            yield data
                        except Exception:
                            continue
        except Exception as e:
            yield {"status": "error", "error": str(e)}
        finally:
            self._pulling_tasks.pop(model_name, None)


# Global singleton instance
ollama_supervisor = OllamaSupervisor()
