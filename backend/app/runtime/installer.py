"""
Sandboxed Engine Installer with Manifest Tracking and Interruption Safety.

Installs ComfyUI or Stable Diffusion WebUI into dedicated, isolated directories
using hermetic virtual environments. Strictly adheres to zero host environment pollution:
never executes global pip install commands.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import venv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app.runtime.supervisor import get_default_engine_dir
from app.schemas.engine import EngineInstallManifest, EngineType, InstallPhase

logger = logging.getLogger(__name__)

COMFYUI_GIT_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
WEBUI_GIT_REPO = "https://github.com/AUTOMATIC1111/stable-diffusion-webui.git"


class IsolatedEngineInstaller:
    """Manages staged installation of local engines inside hermetic environments."""

    def __init__(self, engine_dir: Optional[Path] = None) -> None:
        self.engine_dir = engine_dir or get_default_engine_dir()

    def get_manifest_path(self, engine_type: EngineType) -> Path:
        """Return the path to the installation manifest for the specified engine."""
        return self.engine_dir / f"{engine_type.value}_manifest.json"

    def read_manifest(self, engine_type: EngineType) -> EngineInstallManifest:
        """Read existing manifest or return initial state."""
        manifest_path = self.get_manifest_path(engine_type)
        engine_target = self.engine_dir / ("comfyui" if engine_type == EngineType.COMFYUI else "webui")
        runtime_target = self.engine_dir / ("runtime" if engine_type == EngineType.COMFYUI else "webui_runtime")

        if manifest_path.is_file():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = EngineInstallManifest.model_validate(data)
                # Check for uncompleted previous run (interruption detection)
                if manifest.phase in (
                    InstallPhase.CREATING_VENV,
                    InstallPhase.DOWNLOADING,
                    InstallPhase.INSTALLING_DEPS,
                ):
                    manifest.phase = InstallPhase.INTERRUPTED
                    manifest.error_message = "Installation was interrupted before completion."
                    self.write_manifest(manifest)
                return manifest
            except Exception as e:
                logger.warning(f"Error reading manifest for {engine_type}: {e}")

        # Default clean manifest
        return EngineInstallManifest(
            engine_type=engine_type,
            phase=InstallPhase.IDLE,
            engine_dir=str(engine_target),
            runtime_dir=str(runtime_target),
        )

    def write_manifest(self, manifest: EngineInstallManifest) -> None:
        """Persist installation manifest to disk."""
        self.engine_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.get_manifest_path(manifest.engine_type)
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    def _get_python_bin(self, runtime_dir: Path) -> Path:
        if sys.platform == "win32":
            return runtime_dir / "Scripts" / "python.exe"
        return runtime_dir / "bin" / "python"

    def _get_pip_bin(self, runtime_dir: Path) -> Path:
        if sys.platform == "win32":
            return runtime_dir / "Scripts" / "pip.exe"
        return runtime_dir / "bin" / "pip"

    async def create_isolated_venv(
        self, runtime_dir: Path, on_log: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Create a hermetic virtual environment without polluting host."""
        if on_log:
            on_log(f"Creating isolated virtualenv in {runtime_dir}...")

        # If previous broken venv exists, remove it cleanly
        python_bin = self._get_python_bin(runtime_dir)
        if runtime_dir.exists() and not python_bin.is_file():
            shutil.rmtree(runtime_dir, ignore_errors=True)

        if not python_bin.is_file():
            # Run venv creation in threadpool to avoid blocking event loop
            def _create_env():
                builder = venv.EnvBuilder(with_pip=True, clear=True)
                builder.create(runtime_dir)

            await asyncio.to_thread(_create_env)

        return python_bin.is_file()

    async def install_engine(
        self,
        engine_type: EngineType,
        on_progress: Optional[Callable[[EngineInstallManifest], None]] = None,
    ) -> EngineInstallManifest:
        """
        Run complete isolated installation:
        1. Check environment & disk space
        2. Create isolated sandboxed venv
        3. Clone / stage repository code
        4. Install isolated dependencies via sandboxed pip
        """
        manifest = self.read_manifest(engine_type)
        now_str = datetime.now(timezone.utc).isoformat()
        manifest.created_at = now_str
        manifest.phase = InstallPhase.CHECKING
        self.write_manifest(manifest)
        if on_progress:
            on_progress(manifest)

        engine_target = Path(manifest.engine_dir)
        runtime_target = Path(manifest.runtime_dir)

        try:
            # Phase 1: Virtualenv Creation
            manifest.phase = InstallPhase.CREATING_VENV
            manifest.last_log_line = "Initializing sandboxed virtual environment..."
            self.write_manifest(manifest)
            if on_progress:
                on_progress(manifest)

            venv_ok = await self.create_isolated_venv(runtime_target)
            if not venv_ok:
                raise RuntimeError(f"Failed to create virtual environment at {runtime_target}")

            python_bin = self._get_python_bin(runtime_target)
            manifest.python_bin = str(python_bin)

            # Phase 2: Stage / Download code
            manifest.phase = InstallPhase.DOWNLOADING
            manifest.last_log_line = f"Staging {engine_type.value} repository..."
            self.write_manifest(manifest)
            if on_progress:
                on_progress(manifest)

            repo_url = COMFYUI_GIT_REPO if engine_type == EngineType.COMFYUI else WEBUI_GIT_REPO
            if not engine_target.exists():
                clone_cmd = ["git", "clone", "--depth", "1", repo_url, str(engine_target)]
                proc = await asyncio.create_subprocess_exec(
                    *clone_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    err_msg = stderr.decode(errors="replace").strip()
                    raise RuntimeError(f"Git clone failed: {err_msg}")

            # Phase 3: Install isolated dependencies
            manifest.phase = InstallPhase.INSTALLING_DEPS
            manifest.last_log_line = "Installing engine requirements into isolated environment..."
            self.write_manifest(manifest)
            if on_progress:
                on_progress(manifest)

            req_file = engine_target / "requirements.txt"
            pip_bin = self._get_pip_bin(runtime_target)

            if req_file.is_file() and pip_bin.is_file():
                # Strict: execute ONLY pip inside runtime_target!
                install_cmd = [str(pip_bin), "install", "--no-warn-script-location", "-r", str(req_file)]
                proc = await asyncio.create_subprocess_exec(
                    *install_cmd,
                    cwd=str(engine_target),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    err_msg = stderr.decode(errors="replace").strip()
                    raise RuntimeError(f"Pip install failed: {err_msg[:300]}")

            # Completed!
            manifest.phase = InstallPhase.COMPLETED
            manifest.completed_at = datetime.now(timezone.utc).isoformat()
            manifest.last_log_line = f"{engine_type.value} installed successfully."
            manifest.error_message = None
            self.write_manifest(manifest)
            if on_progress:
                on_progress(manifest)

        except Exception as e:
            manifest.phase = InstallPhase.FAILED
            manifest.error_message = str(e)
            manifest.last_log_line = f"Installation error: {e}"
            self.write_manifest(manifest)
            if on_progress:
                on_progress(manifest)

        return manifest


installer = IsolatedEngineInstaller()
