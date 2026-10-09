"""Destructive file operations use disposable roots only."""

from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import pytest

from app.runtime.managed_files import managed_child, uninstall_managed_files
from app.schemas.engine import EngineType
from app.runtime.installer import IsolatedEngineInstaller
from app.runtime.uninstall import uninstall_managed
from app.core.task_registry import task_registry


def test_uninstall_removes_environment_preserves_entire_engine_and_shared_data(tmp_path: Path) -> None:
    engine = tmp_path / "comfyui"
    runtime = tmp_path / "runtime"
    for relative in ["models/user.safetensors", "output/art.png", "custom_nodes/user.py", "unknown/user.settings", "main.py"]:
        file = engine / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"preserve")
    runtime.mkdir()
    (runtime / "python.exe").write_bytes(b"runtime")
    shared = tmp_path / "models" / "shared.safetensors"
    shared.parent.mkdir()
    shared.write_bytes(b"shared")
    external = tmp_path / "external"
    external.mkdir()
    result = uninstall_managed_files(tmp_path, EngineType.COMFYUI)
    assert result["status"] == "uninstalled"
    assert not engine.exists() and not runtime.exists()
    assert shared.read_bytes() == b"shared"
    assert external.is_dir()
    backup = Path(result["retained_path"]) / "engine"
    assert (backup / "unknown/user.settings").read_bytes() == b"preserve"
    assert (backup / "models/user.safetensors").read_bytes() == b"preserve"
    assert result["runtime_cleanup_pending"] is None


def test_move_failure_restores_original_engine(tmp_path: Path) -> None:
    source = tmp_path / "comfyui"
    source.mkdir()
    (source / "main.py").write_bytes(b"code")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    original = Path.rename

    def rename(path: Path, target: Path) -> Path:
        if path == runtime:
            raise OSError("fixture failure")
        return original(path, target)

    with patch.object(Path, "rename", rename), pytest.raises(OSError):
        uninstall_managed_files(tmp_path, EngineType.COMFYUI)
    assert (source / "main.py").read_bytes() == b"code"
    assert runtime.is_dir()


def test_cleanup_failure_reports_retained_environment(tmp_path: Path) -> None:
    (tmp_path / "webui_runtime").mkdir()
    with patch("app.runtime.managed_files.shutil.rmtree", side_effect=OSError("fixture busy")):
        result = uninstall_managed_files(tmp_path, EngineType.WEBUI)
    assert Path(result["runtime_cleanup_pending"]).is_dir()
    assert "fixture busy" in result["warning"]


def test_managed_target_cannot_escape_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        managed_child(tmp_path, "../external")


@pytest.mark.asyncio
async def test_running_engine_and_active_tasks_prevent_uninstall(tmp_path: Path) -> None:
    installer = IsolatedEngineInstaller(tmp_path)
    target = SimpleNamespace(engine_dir=tmp_path, is_running=lambda: True, get_pid=lambda: 123)
    with pytest.raises(ValueError, match="Stop the managed"):
        await uninstall_managed(EngineType.COMFYUI, target, installer)
    assert not task_registry.maintenance_active
    target.is_running = lambda: False
    target.get_pid = lambda: None
    task_registry.register_task("fixture-uninstall-active", "fixture")
    try:
        with pytest.raises(ValueError, match="active work"):
            await uninstall_managed(EngineType.COMFYUI, target, installer)
    finally:
        task_registry.unregister_task("fixture-uninstall-active")


@pytest.mark.asyncio
async def test_uninstall_maintenance_blocks_new_admission(tmp_path: Path) -> None:
    installer = IsolatedEngineInstaller(tmp_path)
    target = SimpleNamespace(engine_dir=tmp_path, is_running=lambda: False, get_pid=lambda: None)

    def remove(root: Path, engine_type: EngineType) -> dict:
        assert task_registry.maintenance_active
        with pytest.raises(ValueError, match="maintenance"):
            task_registry.register_task("fixture-new", "fixture")
        return {"status": "not-installed", "retained_path": None}

    with patch("app.runtime.uninstall.uninstall_managed_files", side_effect=remove):
        assert (await uninstall_managed(EngineType.COMFYUI, target, installer))["status"] == "not-installed"
    assert not task_registry.maintenance_active
