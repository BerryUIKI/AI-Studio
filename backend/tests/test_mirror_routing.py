"""Capture effective install/download sources without installing engines or packages."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.runtime.installer import COMFYUI_GIT_REPO, IsolatedEngineInstaller, MirrorManager
from app.runtime.model_downloader import ModelDownloader
from app.schemas.engine import EngineType
from app.storage.hub_catalog import HubCatalog


@pytest.mark.asyncio
@pytest.mark.parametrize("preset,git_prefix,pip_index", [
    ("direct", "", "https://pypi.org/simple"),
    ("china_mainland", "https://mirror.ghproxy.com/", "https://pypi.tuna.tsinghua.edu.cn/simple"),
    ("custom", "https://git.test/", "https://pip.test/simple"),
])
async def test_install_commands_use_selected_mirrors(tmp_path: Path, preset: str,
                                                    git_prefix: str, pip_index: str) -> None:
    installer = IsolatedEngineInstaller(tmp_path / "engine")
    mirrors = MirrorManager(tmp_path / "mirrors.json")
    mirrors.update_config("custom", "https://git.test", "https://pip.test/simple", "https://hf.test")
    commands: list[tuple[str, ...]] = []

    async def create_venv(runtime: Path) -> bool:
        for executable in (installer._get_python_bin(runtime), installer._get_pip_bin(runtime)):
            executable.parent.mkdir(parents=True, exist_ok=True)
            executable.write_text("fixture")
        return True

    async def subprocess(*args: str, **kwargs: object) -> SimpleNamespace:
        commands.append(args)
        if "clone" in args:
            target = Path(args[-1])
            target.mkdir(parents=True)
            (target / "main.py").write_text("fixture")
            (target / "requirements.txt").write_text("fixture")
        return SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(b"", b"")))

    with patch("app.runtime.installer.mirror_manager", mirrors), patch(
        "app.runtime.installer.find_git_executable", return_value="fixture-git"
    ), patch.object(installer, "create_isolated_venv", side_effect=create_venv), patch(
        "app.runtime.installer.asyncio.create_subprocess_exec", side_effect=subprocess
    ):
        manifest = await installer.install_engine(EngineType.COMFYUI, mirror_preset=preset)
    assert manifest.phase == "completed", manifest.error_message
    clone = next(command for command in commands if "clone" in command)
    assert clone[-2] == git_prefix + COMFYUI_GIT_REPO
    assert manifest.source_url == clone[-2]
    assert manifest.pip_index_url == pip_index
    pip = next(command for command in commands if "install" in command)
    assert Path(pip[0]).is_relative_to(installer.engine_dir)
    assert pip[pip.index("--index-url") + 1] == pip_index


def test_model_download_restores_global_setting_and_honors_explicit_override(tmp_path: Path) -> None:
    path = tmp_path / "mirrors.json"
    MirrorManager(path).update_config("custom", custom_hf_mirror="https://hf.test")
    mirrors = MirrorManager(path)
    model = HubCatalog.get_model("flux-1-schnell-fp8")
    with patch("app.runtime.model_downloader.mirror_manager", mirrors):
        downloader = ModelDownloader()
        assert downloader._select_source_url(model, None).startswith("https://hf.test/")
        assert downloader._select_source_url(model, "direct").startswith("https://huggingface.co/")
        assert "hf-mirror.com" in downloader._select_source_url(model, "china_mainland")
    assert mirrors.git_override_args() == []
    mirrors.update_config("custom", custom_git_mirror="https://git.test")
    assert mirrors.git_override_args() == ["-c", "url.https://git.test/https://github.com/.insteadOf=https://github.com/"]
