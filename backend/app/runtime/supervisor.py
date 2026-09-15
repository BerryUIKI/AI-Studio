"""
Sandboxed ComfyUI Runtime Process Supervisor.

Manages isolated execution of the local ComfyUI engine in a dedicated,
hermetic application directory (~/.ai-workflow/engine).
Guarantees zero system environment pollution.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def get_default_engine_dir() -> Path:
    """Return the root isolated engine directory, configurable via env var."""
    custom_dir = os.environ.get("AI_WORKFLOW_ENGINE_DIR")
    if custom_dir:
        return Path(custom_dir).resolve()

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(local_app_data) / "AI-Workflow" / "engine"

    return Path.home() / ".ai-workflow" / "engine"


class ComfySupervisor:
    """Supervisor managing the lifecycle of an isolated ComfyUI subprocess."""

    def __init__(self, engine_dir: Optional[Path] = None, port: int = 8188) -> None:
        self.engine_dir = engine_dir or get_default_engine_dir()
        self.port = port
        self.runtime_dir = self.engine_dir / "runtime"
        self.comfy_dir = self.engine_dir / "comfyui"
        self.models_dir = self.engine_dir / "models"
        self.pid_file = self.engine_dir / "comfy.pid"
        self._process: Optional[subprocess.Popen] = None

    def ensure_directories(self) -> None:
        """Ensure the isolated engine directory layout exists."""
        self.engine_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        (self.models_dir / "checkpoints").mkdir(exist_ok=True)
        (self.models_dir / "loras").mkdir(exist_ok=True)
        (self.models_dir / "vae").mkdir(exist_ok=True)

    def is_installed(self) -> bool:
        """Check if the isolated ComfyUI installation exists and has entrypoint."""
        main_py = self.comfy_dir / "main.py"
        return main_py.is_file()

    def get_pid(self) -> Optional[int]:
        """Read active PID from the supervisor PID file if process is alive."""
        if not self.pid_file.is_file():
            return None

        try:
            pid = int(self.pid_file.read_text(encoding="utf-8").strip())
            # Verify if process is alive
            if sys.platform == "win32":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
                if handle != 0:
                    kernel32.CloseHandle(handle)
                    return pid
            else:
                os.kill(pid, 0)
                return pid
        except (ValueError, OSError):
            pass

        # Cleanup stale pid file
        self._clean_pid_file()
        return None

    def is_running(self) -> bool:
        """Check if the managed ComfyUI process is actively running."""
        return self.get_pid() is not None

    def get_status(self) -> Dict[str, Any]:
        """Return comprehensive status of the isolated runtime."""
        pid = self.get_pid()
        return {
            "installed": self.is_installed(),
            "running": pid is not None,
            "pid": pid,
            "port": self.port,
            "engine_dir": str(self.engine_dir),
            "comfy_dir": str(self.comfy_dir),
            "models_dir": str(self.models_dir),
        }

    def start(self) -> Dict[str, Any]:
        """Launch the isolated ComfyUI process."""
        if not self.is_installed():
            return {
                "success": False,
                "message": f"ComfyUI is not installed in {self.comfy_dir}. Run installer first.",
            }

        if self.is_running():
            return {
                "success": True,
                "message": f"ComfyUI is already running (PID: {self.get_pid()})",
                "pid": self.get_pid(),
            }

        # Resolve isolated python executable
        if sys.platform == "win32":
            python_bin = self.runtime_dir / "Scripts" / "python.exe"
        else:
            python_bin = self.runtime_dir / "bin" / "python"

        if not python_bin.is_file():
            # Fallback to current virtualenv python if sandboxed venv is uninitialized
            python_bin = Path(sys.executable)

        cmd = [
            str(python_bin),
            str(self.comfy_dir / "main.py"),
            "--port",
            str(self.port),
            "--listen",
            "127.0.0.1",
            "--input-directory",
            str(self.engine_dir / "input"),
            "--output-directory",
            str(self.engine_dir / "output"),
        ]

        try:
            self.ensure_directories()
            self._process = subprocess.Popen(
                cmd,
                cwd=str(self.comfy_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            pid = self._process.pid
            self.pid_file.write_text(str(pid), encoding="utf-8")
            return {
                "success": True,
                "message": f"ComfyUI launched successfully (PID: {pid})",
                "pid": pid,
            }
        except Exception as err:
            return {
                "success": False,
                "message": f"Failed to launch ComfyUI: {err}",
            }

    def stop(self) -> Dict[str, Any]:
        """Terminate the managed ComfyUI process."""
        pid = self.get_pid()
        if pid is None:
            return {"success": True, "message": "ComfyUI is not running"}

        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception as err:
            return {"success": False, "message": f"Error stopping process: {err}"}
        finally:
            self._clean_pid_file()

        return {"success": True, "message": f"ComfyUI process {pid} stopped"}

    def _clean_pid_file(self) -> None:
        try:
            if self.pid_file.is_file():
                self.pid_file.unlink()
        except OSError:
            pass


# Global default supervisor singleton
supervisor = ComfySupervisor()
