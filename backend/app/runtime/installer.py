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
from typing import Any, Callable, Dict, List, Optional

from app.core.task_registry import task_registry
from app.core.workers import run_blocking
from app.runtime.managed_files import managed_child, reject_redirected_tree
from app.runtime.supervisor import get_default_engine_dir
from app.storage.db import get_default_data_dir
from app.storage.config_files import write_json_atomic
from app.schemas.engine import (
    EngineInstallManifest,
    EngineType,
    InstallPhase,
    EngineUpdateManifest,
    EngineUpdateStatus,
)

logger = logging.getLogger(__name__)

COMFYUI_GIT_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
WEBUI_GIT_REPO = "https://github.com/AUTOMATIC1111/stable-diffusion-webui.git"


def find_git_executable() -> Optional[str]:
    """
    Find Git executable in this order:
    1. Bundled portable Git (runtime/git/cmd/git.exe) - for clean-machine packages
    2. System Git in PATH - for development environments

    Returns the git command to use, or None if Git is not available.
    """
    # Check for bundled portable Git (packaged distribution)
    if sys.platform == "win32":
        # Try to find root directory by walking up from current file
        current = Path(__file__).resolve()
        for parent in [current.parent.parent.parent, current.parent.parent.parent.parent]:
            bundled_git = parent / "runtime" / "git" / "cmd" / "git.exe"
            if bundled_git.is_file():
                logger.info(f"Using bundled portable Git: {bundled_git}")
                return str(bundled_git)
    else:
        # Linux/macOS: check for bundled git in runtime/git/bin/git
        current = Path(__file__).resolve()
        for parent in [current.parent.parent.parent, current.parent.parent.parent.parent]:
            bundled_git = parent / "runtime" / "git" / "bin" / "git"
            if bundled_git.is_file():
                logger.info(f"Using bundled portable Git: {bundled_git}")
                return str(bundled_git)

    # Fall back to system Git
    git_path = shutil.which("git")
    if git_path:
        logger.info(f"Using system Git: {git_path}")
        return "git"

    logger.warning("Git not found in bundled runtime or system PATH")
    return None


class IsolatedEngineInstaller:
    """Manages staged installation of local engines inside hermetic environments."""

    # Class-level set of currently active installation tasks (engine_type.value)
    _active_installs: set[str] = set()

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
                # Only mark as INTERRUPTED if there is NO active in-memory install worker running!
                if manifest.phase in (
                    InstallPhase.CHECKING,
                    InstallPhase.CREATING_VENV,
                    InstallPhase.DOWNLOADING,
                    InstallPhase.INSTALLING_DEPS,
                ):
                    if engine_type.value not in self._active_installs:
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

    def _get_expected_entrypoints(self, engine_type: EngineType, engine_target: Path) -> list[Path]:
        """Return expected entrypoint script paths for the engine."""
        if engine_type == EngineType.COMFYUI:
            return [engine_target / "main.py"]
        elif engine_type == EngineType.WEBUI:
            return [engine_target / "launch.py", engine_target / "webui.py"]
        return []

    def validate_installation(self, engine_type: EngineType, engine_target: Path, runtime_target: Path) -> None:
        """
        Validate that the engine installation is complete and healthy:
        1. Virtual environment Python binary exists
        2. Expected entrypoint script exists
        3. Engine requirements.txt exists
        """
        python_bin = self._get_python_bin(runtime_target)
        if not python_bin.is_file():
            raise RuntimeError(f"Hermetic Python binary missing at {python_bin}")

        entrypoints = self._get_expected_entrypoints(engine_type, engine_target)
        if not any(ep.is_file() for ep in entrypoints):
            expected_names = " or ".join(ep.name for ep in entrypoints) or "entrypoint"
            raise RuntimeError(f"Engine entrypoint ({expected_names}) missing in {engine_target}")

        req_file = engine_target / "requirements.txt"
        if not req_file.is_file():
            raise RuntimeError(f"Engine requirements.txt missing in {engine_target}")

    async def create_isolated_venv(
        self, runtime_dir: Path, on_log: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Create a hermetic virtual environment without polluting host."""
        if runtime_dir.name not in {"runtime", "webui_runtime"} or runtime_dir != managed_child(self.engine_dir, runtime_dir.name):
            raise ValueError("Virtual environment target is outside the designated managed runtime")
        if on_log:
            on_log(f"Creating isolated virtualenv in {runtime_dir}...")

        # If previous broken venv exists, remove it cleanly
        python_bin = self._get_python_bin(runtime_dir)
        if runtime_dir.exists() and not python_bin.is_file():
            await run_blocking(reject_redirected_tree, runtime_dir)
            await run_blocking(shutil.rmtree, runtime_dir)

        if not python_bin.is_file():
            # Run venv creation in threadpool to avoid blocking event loop
            def _create_env() -> None:
                builder = venv.EnvBuilder(with_pip=True, clear=True)
                builder.create(runtime_dir)

            await run_blocking(_create_env)

        return python_bin.is_file()

    async def install_engine(
        self,
        engine_type: EngineType,
        on_progress: Optional[Callable[[EngineInstallManifest], None]] = None,
        mirror_preset: Optional[str] = None,
    ) -> EngineInstallManifest:
        """
        Run complete isolated installation:
        1. Acquire per-engine install lock
        2. Check environment & create isolated sandboxed venv
        3. Clone / stage repository code into staging or target
        4. Install isolated dependencies via sandboxed pip
        5. Validate entrypoint and health before marking completed
        """
        engine_key = engine_type.value
        install_lock = task_registry.get_install_lock(engine_key)

        if install_lock.locked():
            manifest = self.read_manifest(engine_type)
            manifest.phase = InstallPhase.FAILED
            manifest.error_message = f"An installation lease is already held for {engine_type.value}."
            self.write_manifest(manifest)
            return manifest

        async with install_lock:
            self._active_installs.add(engine_key)
            try:
                repo_url = mirror_manager.transform_git_url(
                    COMFYUI_GIT_REPO if engine_type == EngineType.COMFYUI else WEBUI_GIT_REPO, mirror_preset)
                pip_index = mirror_manager.get_pip_index_url(mirror_preset)
                manifest = self.read_manifest(engine_type)
                manifest.source_url = repo_url
                manifest.pip_index_url = pip_index
                now_str = datetime.now(timezone.utc).isoformat()
                manifest.created_at = now_str
                manifest.phase = InstallPhase.CHECKING
                self.write_manifest(manifest)
                if on_progress:
                    on_progress(manifest)

                engine_target = managed_child(self.engine_dir, engine_type.value)
                runtime_target = managed_child(self.engine_dir, "runtime" if engine_type == EngineType.COMFYUI else "webui_runtime")
                manifest.engine_dir = str(engine_target)
                manifest.runtime_dir = str(runtime_target)

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

                entrypoints = self._get_expected_entrypoints(engine_type, engine_target)

                # If destination directory exists but has no valid entrypoint or git repo, clean it up before cloning
                if engine_target.exists():
                    has_entrypoint = any(ep.is_file() for ep in entrypoints)
                    has_git = (engine_target / ".git").is_dir()
                    if not has_entrypoint or not has_git:
                        if any(engine_target.iterdir()):
                            raise RuntimeError("Existing engine entrypoint or repository is incomplete. Use Uninstall to preserve the folder before reinstalling.")
                        await run_blocking(engine_target.rmdir)

                if not engine_target.exists():
                    git_exe = find_git_executable()
                    if not git_exe:
                        raise RuntimeError(
                            "Git is required for engine installation but was not found. "
                            "Please install Git from https://git-scm.com or ensure the portable Git bundle is present."
                        )

                    clone_cmd = [git_exe, "clone", "--depth", "1", repo_url, str(engine_target)]
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

                if not req_file.is_file():
                    raise RuntimeError(f"requirements.txt missing in {engine_target}")
                if not pip_bin.is_file():
                    raise RuntimeError(f"Hermetic pip binary missing in {runtime_target}")

                # Strict: execute ONLY pip inside runtime_target!
                install_cmd = [str(pip_bin), "install", "--no-warn-script-location", "-r", str(req_file)]
                install_cmd.extend(["--index-url", pip_index])
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

                # Phase 4: Validation
                self.validate_installation(engine_type, engine_target, runtime_target)

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
            finally:
                self._active_installs.discard(engine_key)

        return manifest

    def get_update_manifest_path(self, engine_type: EngineType) -> Path:
        """Return the path to the update manifest for the specified engine."""
        return self.engine_dir / f"{engine_type.value}_update_manifest.json"

    def read_update_manifest(self, engine_type: EngineType) -> EngineUpdateManifest:
        """Read update manifest or return initial state."""
        path = self.get_update_manifest_path(engine_type)
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return EngineUpdateManifest.model_validate(data)
            except Exception as e:
                logger.warning(f"Error reading update manifest for {engine_type}: {e}")
        return EngineUpdateManifest(engine_type=engine_type)

    def write_update_manifest(self, manifest: EngineUpdateManifest) -> None:
        """Persist update manifest to disk."""
        self.engine_dir.mkdir(parents=True, exist_ok=True)
        path = self.get_update_manifest_path(manifest.engine_type)
        path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    async def update_engine(
        self,
        engine_type: EngineType,
        has_active_tasks_fn: Optional[Callable[[], bool]] = None,
    ) -> EngineUpdateManifest:
        """
        Safely update managed engine:
        1. Check active jobs (abort if running)
        2. Record current git commit hash as rollback checkpoint
        3. Pull git updates
        4. Install updated requirements into isolated venv
        5. On failure, rollback to previous commit
        """
        engine_key = engine_type.value
        update_lock = task_registry.get_update_lock(engine_key)
        git_mirror_args = mirror_manager.git_override_args()
        pip_index_args = ["--index-url", mirror_manager.get_pip_index_url()]

        # Acquire exclusive update lease for this engine
        if update_lock.locked():
            manifest = self.read_update_manifest(engine_type)
            manifest.status = EngineUpdateStatus.FAILED
            manifest.error_message = f"An update lease is already held for {engine_type.value}."
            self.write_update_manifest(manifest)
            return manifest

        async with update_lock:
            # Guard: active jobs recheck under exclusive lease
            if (has_active_tasks_fn and has_active_tasks_fn()) or task_registry.has_active_tasks():
                manifest = self.read_update_manifest(engine_type)
                manifest.status = EngineUpdateStatus.FAILED
                manifest.error_message = "Cannot update engine while active generation tasks are running."
                self.write_update_manifest(manifest)
                return manifest

            manifest = EngineUpdateManifest(
                engine_type=engine_type,
                status=EngineUpdateStatus.CHECKING,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            self.write_update_manifest(manifest)

            engine_target = self.engine_dir / ("comfyui" if engine_type == EngineType.COMFYUI else "webui")
            runtime_target = self.engine_dir / ("runtime" if engine_type == EngineType.COMFYUI else "webui_runtime")

            if not engine_target.is_dir() or not (engine_target / ".git").is_dir():
                manifest.status = EngineUpdateStatus.FAILED
                manifest.error_message = f"Engine directory {engine_target} is not a valid git repository or not installed."
                self.write_update_manifest(manifest)
                return manifest

            previous_commit: Optional[str] = None
            previous_requirements: Optional[str] = None
            req_file = engine_target / "requirements.txt"
            pip_bin = self._get_pip_bin(runtime_target)

            try:
                # Step 1: Capture previous commit hash & requirements snapshot
                git_exe = find_git_executable()
                if not git_exe:
                    raise RuntimeError(
                        "Git is required for engine updates but was not found. "
                        "Please install Git from https://git-scm.com or ensure the portable Git bundle is present."
                    )

                rev_proc = await asyncio.create_subprocess_exec(
                    git_exe, "rev-parse", "HEAD",
                    cwd=str(engine_target),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                rev_out, _ = await rev_proc.communicate()
                if rev_proc.returncode == 0:
                    previous_commit = rev_out.decode().strip()
                    manifest.previous_commit = previous_commit

                if req_file.is_file():
                    try:
                        previous_requirements = req_file.read_text(encoding="utf-8")
                    except Exception:
                        pass

                # Live recheck right before modifying filesystem
                if (has_active_tasks_fn and has_active_tasks_fn()) or task_registry.has_active_tasks():
                    manifest.status = EngineUpdateStatus.FAILED
                    manifest.error_message = "Active tasks started during update preparation. Update aborted."
                    self.write_update_manifest(manifest)
                    return manifest

                manifest.status = EngineUpdateStatus.UPDATING
                self.write_update_manifest(manifest)

                # Step 2: Fetch and pull latest updates
                pull_proc = await asyncio.create_subprocess_exec(
                    git_exe, *git_mirror_args, "pull", "--ff-only",
                    cwd=str(engine_target),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                pull_out, pull_err = await pull_proc.communicate()
                if pull_proc.returncode != 0:
                    raise RuntimeError(f"Git pull failed: {pull_err.decode(errors='replace').strip()}")

                # Get new commit hash
                rev_proc2 = await asyncio.create_subprocess_exec(
                    git_exe, "rev-parse", "HEAD",
                    cwd=str(engine_target),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                rev_out2, _ = await rev_proc2.communicate()
                if rev_proc2.returncode == 0:
                    manifest.target_commit = rev_out2.decode().strip()

                # Step 3: Update dependencies in isolated venv
                if req_file.is_file() and pip_bin.is_file():
                    pip_proc = await asyncio.create_subprocess_exec(
                        str(pip_bin), "install", "--no-warn-script-location", "-r", str(req_file), *pip_index_args,
                        cwd=str(engine_target),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _, pip_err = await pip_proc.communicate()
                    if pip_proc.returncode != 0:
                        raise RuntimeError(f"Pip dependency update failed: {pip_err.decode(errors='replace')[:200]}")

                manifest.status = EngineUpdateStatus.COMPLETED
                manifest.error_message = None
                self.write_update_manifest(manifest)

            except Exception as e:
                manifest.status = EngineUpdateStatus.FAILED
                manifest.error_message = str(e)

                # Perform comprehensive rollback (code and dependencies)
                if previous_commit:
                    try:
                        logger.info(f"Rolling back {engine_type.value} to previous commit {previous_commit}...")
                        rollback_proc = await asyncio.create_subprocess_exec(
                            git_exe, "checkout", previous_commit,
                            cwd=str(engine_target),
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        await rollback_proc.communicate()
                        if rollback_proc.returncode == 0:
                            # Also restore dependencies to match previous commit
                            if req_file.is_file() and pip_bin.is_file():
                                try:
                                    rb_pip = await asyncio.create_subprocess_exec(
                                        str(pip_bin), "install", "--no-warn-script-location", "-r", str(req_file), *pip_index_args,
                                        cwd=str(engine_target),
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE,
                                    )
                                    await rb_pip.communicate()
                                except Exception as p_err:
                                    logger.warning(f"Dependency rollback warning for {engine_type.value}: {p_err}")

                            manifest.status = EngineUpdateStatus.ROLLED_BACK
                            manifest.rollback_performed = True
                    except Exception as rb_err:
                        logger.error(f"Rollback failed for {engine_type.value}: {rb_err}")

                self.write_update_manifest(manifest)

            return manifest


class MirrorManager:
    """Manages active network mirror presets for high-speed download in China Mainland or restricted networks."""

    def __init__(self, config_file: Optional[Path] = None) -> None:
        self.config_file = config_file or get_default_data_dir() / "mirror_config.json"
        self.active_preset: str = "direct"
        self.custom_git_mirror: Optional[str] = None
        self.custom_pypi_mirror: Optional[str] = None
        self.custom_hf_mirror: Optional[str] = None

        self.presets = [
            {
                "id": "direct",
                "name": "Direct (Official Global)",
                "git_mirror": None,
                "pypi_mirror": "https://pypi.org/simple",
                "hf_mirror": "https://huggingface.co",
            },
            {
                "id": "china_mainland",
                "name": "China Mainland (Accelerated)",
                "git_mirror": "https://mirror.ghproxy.com/",
                "pypi_mirror": "https://pypi.tuna.tsinghua.edu.cn/simple",
                "hf_mirror": "https://hf-mirror.com",
            },
            {
                "id": "custom",
                "name": "Custom Mirrors",
                "git_mirror": None,
                "pypi_mirror": None,
                "hf_mirror": None,
            },
        ]

        if self.config_file.is_file():
            try:
                config = json.loads(self.config_file.read_text(encoding="utf-8"))
                if not isinstance(config, dict):
                    raise ValueError("Mirror configuration must be an object")
                preset = config.get("active_preset", "direct")
                self.active_preset = preset if preset in {"direct", "china_mainland", "custom"} else "direct"
                for field in ("custom_git_mirror", "custom_pypi_mirror", "custom_hf_mirror"):
                    setattr(self, field, config.get(field))
            except (OSError, ValueError, TypeError) as error:
                logger.warning("Could not restore mirror configuration: %s", error)

    def get_config(self) -> Dict[str, Any]:
        return {
            "active_preset": self.active_preset,
            "presets": self.presets,
            "custom_git_mirror": self.custom_git_mirror,
            "custom_pypi_mirror": self.custom_pypi_mirror,
            "custom_hf_mirror": self.custom_hf_mirror,
        }

    def update_config(
        self,
        active_preset: str,
        custom_git_mirror: Optional[str] = None,
        custom_pypi_mirror: Optional[str] = None,
        custom_hf_mirror: Optional[str] = None,
    ) -> Dict[str, Any]:
        if active_preset not in {"direct", "china_mainland", "custom"}:
            raise ValueError("Unknown mirror preset")
        self.active_preset = active_preset
        if custom_git_mirror is not None:
            self.custom_git_mirror = custom_git_mirror
        if custom_pypi_mirror is not None:
            self.custom_pypi_mirror = custom_pypi_mirror
        if custom_hf_mirror is not None:
            self.custom_hf_mirror = custom_hf_mirror
        write_json_atomic(self.config_file, {key: value for key, value in self.get_config().items() if key != "presets"})
        return self.get_config()

    def transform_git_url(self, repo_url: str, preset: Optional[str] = None) -> str:
        active = preset or self.active_preset
        if active == "china_mainland":
            return f"https://mirror.ghproxy.com/{repo_url}"
        if active == "custom" and self.custom_git_mirror:
            prefix = self.custom_git_mirror.rstrip("/")
            return f"{prefix}/{repo_url}"
        return repo_url

    def git_override_args(self) -> List[str]:
        target = self.transform_git_url("https://github.com/")
        return ["-c", f"url.{target}.insteadOf=https://github.com/"] if target != "https://github.com/" else []

    def get_pip_index_url(self, preset: Optional[str] = None) -> str:
        active = preset or self.active_preset
        if active == "china_mainland":
            return "https://pypi.tuna.tsinghua.edu.cn/simple"
        if active == "custom" and self.custom_pypi_mirror:
            return self.custom_pypi_mirror
        return "https://pypi.org/simple"

    def transform_model_url(self, url: str, preset: Optional[str] = None) -> str:
        active = preset or self.active_preset
        endpoint = "https://hf-mirror.com" if active == "china_mainland" else self.custom_hf_mirror if active == "custom" else None
        if endpoint and url.startswith("https://huggingface.co/"):
            return endpoint.rstrip("/") + url[len("https://huggingface.co"):]
        return url


installer = IsolatedEngineInstaller()
mirror_manager = MirrorManager()


