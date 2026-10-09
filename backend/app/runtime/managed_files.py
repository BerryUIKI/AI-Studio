"""Scope managed filesystem mutations and retain engine data during uninstall."""

import os
from pathlib import Path
import shutil
import stat
from typing import Any
import uuid

from app.schemas.engine import EngineType
from app.storage.config_files import write_json_atomic


def managed_child(root: Path, name: str) -> Path:
    """Reject redirected targets before any recursive removal or directory move."""
    base = root.resolve()
    target = base / name
    if target.resolve() != target or target.parent != base:
        raise ValueError(f"Managed target is redirected or outside the engine directory: {target}")
    return target


def reject_redirected_tree(target: Path) -> None:
    for directory, folders, files in os.walk(target, followlinks=False):
        for name in folders + files:
            path = Path(directory) / name
            attributes = path.lstat()
            if stat.S_ISLNK(attributes.st_mode) or getattr(attributes, "st_file_attributes", 0) & 0x400:
                raise ValueError(f"Runtime contains a link or reparse point; removal refused: {path}")


def uninstall_managed_files(root: Path, engine_type: EngineType) -> dict[str, Any]:
    """Remove the isolated environment; preserve the complete engine folder as a backup.

    Callers must own process/install/update leases and refuse running engines.
    No path is taken from a mutable installation manifest or external connection.
    """
    source = managed_child(root, engine_type.value)
    runtime = managed_child(root, "runtime" if engine_type == EngineType.COMFYUI else "webui_runtime")
    backups = managed_child(root, "retained-engine-backups")
    if runtime.exists():
        reject_redirected_tree(runtime)
    if not source.exists() and not runtime.exists():
        return {"success": True, "status": "not-installed", "retained_path": None}
    identifier = f"{engine_type.value}-{uuid.uuid4()}"
    backup = backups / identifier
    backup.mkdir(parents=True)
    staged_runtime = managed_child(root, f"uninstall-runtime-{identifier}")
    record = {"engine_type": engine_type.value, "source": str(source), "runtime": str(runtime), "status": "preparing"}
    record_path = backup / "uninstall.json"
    write_json_atomic(record_path, record)
    moved_source = moved_runtime = False
    try:
        if source.exists():
            source.rename(backup / "engine")
            moved_source = True
        if runtime.exists():
            runtime.rename(staged_runtime)
            moved_runtime = True
    except OSError:
        if moved_runtime:
            staged_runtime.rename(runtime)
        if moved_source:
            (backup / "engine").rename(source)
        record["status"] = "rolled-back"
        write_json_atomic(record_path, record)
        raise
    record["status"] = "uninstalled"
    record["retained_engine"] = str(backup / "engine") if moved_source else None
    record["runtime_cleanup_pending"] = str(staged_runtime) if moved_runtime else None
    write_json_atomic(record_path, record)
    warning = None
    if moved_runtime:
        try:
            # Recheck the resolved absolute target immediately before recursive deletion.
            managed_child(root, staged_runtime.name)
            reject_redirected_tree(staged_runtime)
            shutil.rmtree(staged_runtime)
            record["runtime_cleanup_pending"] = None
        except (OSError, ValueError) as error:
            warning = f"Engine uninstalled; environment cleanup remains at {staged_runtime}: {error}"
    write_json_atomic(record_path, record)
    return {"success": True, "status": "uninstalled", "retained_path": str(backup),
            "runtime_cleanup_pending": record["runtime_cleanup_pending"], "warning": warning}
