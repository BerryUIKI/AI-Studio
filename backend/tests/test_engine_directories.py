"""Directory actions use actual registered paths and never mutate their contents."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.runtime.engine_manager import EngineManager
from app.runtime.open_directory import open_directory


def test_open_managed_directory_and_explain_missing_path(tmp_path: Path) -> None:
    manager = EngineManager(tmp_path / "config")
    folder = tmp_path / "comfyui"
    target = SimpleNamespace(comfy_dir=folder)
    with patch("app.runtime.engine_manager.comfy_supervisor", target), patch("app.main.engine_manager", manager), patch("app.main.open_directory") as opened:
        client = TestClient(app)
        assert client.post("/api/v1/engines/comfyui-managed/open-directory").status_code == 404
        opened.assert_not_called()
        folder.mkdir()
        result = client.post("/api/v1/engines/comfyui-managed/open-directory")
        assert result.json()["path"] == str(folder.resolve())
        opened.assert_called_once_with(folder.resolve())


def test_external_directory_and_removal_preserve_files(tmp_path: Path) -> None:
    manager = EngineManager(tmp_path / "config")
    folder = tmp_path / "external"
    folder.mkdir()
    file = folder / "user.model"
    file.write_bytes(b"retain")
    connection = manager.bind_external_engine("comfyui", "External", str(folder))
    assert manager.get_install_directory(connection.id) == folder.resolve()
    assert manager.unbind_external_engine(connection.id)
    assert file.read_bytes() == b"retain"


def test_platform_open_receives_configured_directory(tmp_path: Path) -> None:
    with patch("app.runtime.open_directory.sys.platform", "win32"), patch("app.runtime.open_directory.os.startfile", create=True) as opened:
        open_directory(tmp_path)
        opened.assert_called_once_with(str(tmp_path.resolve()))
