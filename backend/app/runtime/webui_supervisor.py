"""
Sandboxed Stable Diffusion WebUI Process Supervisor.

Manages isolated execution of the local SD WebUI engine in a dedicated,
hermetic application directory (~/.ai-workflow/engine/webui or %LOCALAPPDATA%/AI-Workflow/engine/webui).
Guarantees zero system environment pollution, separate virtual environment from ComfyUI,
and strictly disallows host Python fallback.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from app.runtime.supervisor import get_default_engine_dir


class WebUISupervisor:
    """Supervisor managing the lifecycle of an isolated Stable Diffusion WebUI subprocess."""

    def __init__(self, engine_dir: Optional[Path] = None, port: int = 7860) -> None:
        self.engine_dir = engine_dir or get_default_engine_dir()
        self.port = port
        self.webui_dir = self.engine_dir / "webui"
        self.runtime_dir = self.engine_dir / "webui_runtime"
        self.models_dir = self.engine_dir / "models"
        self.pid_file = self.engine_dir / "webui.pid"
        self._process: Optional[subprocess.Popen] = None

    def ensure_directories(self) -> None:
        """Ensure the isolated WebUI engine directory layout exists."""
        self.engine_dir.mkdir(parents=True, exist_ok=True)
        self.webui_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        (self.models_dir / "checkpoints").mkdir(exist_ok=True)
        (self.models_dir / "loras").mkdir(exist_ok=True)
        (self.models_dir / "vae").mkdir(exist_ok=True)

    def is_installed(self) -> bool:
        """Check if the isolated WebUI installation exists and has entrypoint."""
        launch_py = self.webui_dir / "launch.py"
        webui_py = self.webui_dir / "webui.py"
        return launch_py.is_file() or webui_py.is_file()

    def get_entrypoint(self) -> Optional[Path]:
        """Return the WebUI entrypoint script."""
        launch_py = self.webui_dir / "launch.py"
        if launch_py.is_file():
            return launch_py
        webui_py = self.webui_dir / "webui.py"
        if webui_py.is_file():
            return webui_py
        return None

    def get_python_bin(self) -> Path:
        """Return the expected path to the isolated virtualenv python binary."""
        if sys.platform == "win32":
            return self.runtime_dir / "Scripts" / "python.exe"
        return self.runtime_dir / "bin" / "python"

    def has_isolated_env(self) -> bool:
        """Check if the sandboxed isolated virtual environment is ready."""
        return self.get_python_bin().is_file()

    def _verify_process_identity(self, pid: int) -> bool:
        """Verify the process at pid is actually python, avoiding recycled PID collision."""
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
                if not handle:
                    return False
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                success = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
                kernel32.CloseHandle(handle)
                if success:
                    exe_name = buf.value.lower()
                    return "python" in exe_name
                return False
            except Exception:
                return False
        else:
            try:
                proc_cmdline = Path(f"/proc/{pid}/cmdline")
                if proc_cmdline.is_file():
                    content = proc_cmdline.read_text(encoding="latin1", errors="ignore").lower()
                    return "python" in content
                os.kill(pid, 0)
                return True
            except OSError:
                return False

    def get_pid(self) -> Optional[int]:
        """Read active PID from the supervisor PID file if process is alive and verified."""
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

    def is_running(self) -> bool:
        """Check if the managed WebUI process is actively running."""
        return self.get_pid() is not None

    def get_status(self) -> Dict[str, Any]:
        """Return comprehensive status of the isolated WebUI runtime."""
        pid = self.get_pid()
        return {
            "installed": self.is_installed(),
            "isolated_env_ready": self.has_isolated_env(),
            "running": pid is not None,
            "pid": pid,
            "port": self.port,
            "engine_dir": str(self.engine_dir),
            "webui_dir": str(self.webui_dir),
            "runtime_dir": str(self.runtime_dir),
            "models_dir": str(self.models_dir),
        }

    def start(self) -> Dict[str, Any]:
        """Launch the isolated WebUI process strictly inside its hermetic environment."""
        if not self.is_installed():
            return {
                "success": False,
                "code": "NOT_INSTALLED",
                "message": f"Stable Diffusion WebUI is not installed in {self.webui_dir}. Run installer first.",
            }

        python_bin = self.get_python_bin()
        if not python_bin.is_file():
            # STRICT REQUIREMENT: Zero host Python fallback!
            return {
                "success": False,
                "code": "ENV_MISSING",
                "message": (
                    f"Sandboxed virtual environment not found at {python_bin}. "
                    "Run the isolated installer to set up the WebUI runtime without host pollution."
                ),
            }

        if self.is_running():
            return {
                "success": True,
                "message": f"WebUI is already running (PID: {self.get_pid()})",
                "pid": self.get_pid(),
            }

        entrypoint = self.get_entrypoint()
        if not entrypoint:
            return {
                "success": False,
                "code": "ENTRYPOINT_MISSING",
                "message": f"No launch.py or webui.py entrypoint found in {self.webui_dir}",
            }

        cmd = [
            str(python_bin),
            str(entrypoint),
            "--port",
            str(self.port),
            "--listen",
            "127.0.0.1",
            "--api",
            "--nowebui",
            "--ckpt-dir",
            str(self.models_dir / "checkpoints"),
            "--lora-dir",
            str(self.models_dir / "loras"),
            "--vae-dir",
            str(self.models_dir / "vae"),
        ]

        try:
            self.ensure_directories()
            self._process = subprocess.Popen(
                cmd,
                cwd=str(self.webui_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            pid = self._process.pid
            self.pid_file.write_text(str(pid), encoding="utf-8")
            return {
                "success": True,
                "message": f"WebUI launched successfully (PID: {pid})",
                "pid": pid,
            }
        except Exception as err:
            return {
                "success": False,
                "message": f"Failed to launch WebUI: {err}",
            }

    def stop(self) -> Dict[str, Any]:
        """Terminate the managed WebUI process with process identity verification."""
        pid = self.get_pid()
        if pid is None:
            return {"success": True, "message": "WebUI is not running"}

        if not self._verify_process_identity(pid):
            self._clean_pid_file()
            return {
                "success": False,
                "message": f"Process {pid} is not a verified WebUI process; refusing to kill.",
            }

        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception as err:
            return {"success": False, "message": f"Error stopping WebUI process: {err}"}
        finally:
            self._clean_pid_file()

        return {"success": True, "message": f"WebUI process {pid} stopped"}

    def _clean_pid_file(self) -> None:
        try:
            if self.pid_file.is_file():
                self.pid_file.unlink()
        except OSError:
            pass


# Global default WebUI supervisor singleton
webui_supervisor = WebUISupervisor()
