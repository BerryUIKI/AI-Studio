"""Regression tests for shared model paths and actual launch arguments (#107)."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.runtime.installer import installer
from app.runtime.model_downloader import ModelDownloader
from app.runtime.supervisor import ComfySupervisor
from app.runtime.webui_supervisor import WebUISupervisor
from app.storage.hub_catalog import HubCatalog


def test_comfy_supervisor_generates_extra_model_paths_config(tmp_path: Path) -> None:
    supervisor = ComfySupervisor(engine_dir=tmp_path / "engine")
    supervisor.ensure_directories()
    config_path = supervisor._generate_extra_model_paths_config()
    assert config_path == supervisor.engine_dir / "extra_model_paths.yaml"
    content = config_path.read_text(encoding="utf-8")
    assert "berry_shared:" in content
    assert f"base_path: {supervisor.models_dir}" in content
    for subfolder in ("checkpoints", "vae", "loras", "upscale_models", "controlnet"):
        assert f"{subfolder}: {subfolder}/" in content


def test_webui_supervisor_uses_engine_dir_models(tmp_path: Path) -> None:
    supervisor = WebUISupervisor(engine_dir=tmp_path / "engine")
    assert supervisor.models_dir == supervisor.engine_dir / "models"


def test_model_downloader_resolves_consistent_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(installer, "engine_dir", tmp_path / "engine")
    manager = ModelDownloader()
    base = HubCatalog.get_model("flux-1-schnell-fp8")
    assert base is not None
    for category, subfolder in (("checkpoint", "checkpoints"), ("lora", "loras"), ("vae", "vae")):
        model = base.model_copy(update={"category": category})
        comfy_path = manager._resolve_target_path(model, "comfyui")
        webui_path = manager._resolve_target_path(model, "webui")
        assert comfy_path == webui_path
        assert comfy_path.parent == installer.engine_dir / "models" / subfolder


def test_downloaded_models_accessible_to_both_engines(tmp_path: Path) -> None:
    engine_dir = tmp_path / "engine"
    comfy = ComfySupervisor(engine_dir=engine_dir)
    webui = WebUISupervisor(engine_dir=engine_dir)
    comfy.ensure_directories()
    webui.ensure_directories()
    assert comfy.models_dir == webui.models_dir == engine_dir / "models"
    checkpoint = comfy.models_dir / "checkpoints" / "test.safetensors"
    checkpoint.write_bytes(b"dummy checkpoint data")
    assert (webui.models_dir / "checkpoints" / checkpoint.name).read_bytes() == checkpoint.read_bytes()


def test_comfy_start_command_includes_extra_model_paths(tmp_path: Path) -> None:
    supervisor = ComfySupervisor(engine_dir=tmp_path / "engine")
    supervisor.ensure_directories()
    supervisor.comfy_dir.mkdir(parents=True, exist_ok=True)
    (supervisor.comfy_dir / "main.py").write_text("# dummy", encoding="utf-8")
    python_bin = supervisor.get_python_bin()
    python_bin.parent.mkdir(parents=True, exist_ok=True)
    python_bin.write_text("# dummy", encoding="utf-8")
    with (
        patch.object(supervisor, "is_running", return_value=False),
        patch("app.runtime.hardware.get_hardware_launch_flags", return_value=[]),
        patch("app.runtime.supervisor.subprocess.Popen", return_value=Mock(pid=12345)) as launch,
    ):
        assert supervisor.start()["success"] is True
    cmd = launch.call_args.args[0]
    index = cmd.index("--extra-model-paths-config")
    assert cmd[index + 1] == str(supervisor.engine_dir / "extra_model_paths.yaml")
    assert Path(cmd[index + 1]).is_file()


def test_webui_start_command_includes_model_dir_flags(tmp_path: Path) -> None:
    supervisor = WebUISupervisor(engine_dir=tmp_path / "engine")
    supervisor.ensure_directories()
    for subfolder in ("checkpoints", "loras", "vae"):
        assert (supervisor.models_dir / subfolder).is_dir()
