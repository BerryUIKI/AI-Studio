"""Restart restores setup without writing to user-owned engine/model directories."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.runtime.engine_manager import EngineManager
from app.runtime.installer import MirrorManager
from app.schemas.engine import EngineOwnership, EngineType
from app.storage.model_store import ModelStore


def test_model_roots_and_removal_survive_restart(tmp_path: Path) -> None:
    user_models = tmp_path / "user-models"
    user_models.mkdir()
    sentinel = user_models / "unchanged.txt"
    sentinel.write_text("user-owned")
    store = ModelStore(tmp_path / "engine")
    store.add_root("stable-id", str(user_models), "User models", "custom")
    restored = ModelStore(store.engine_dir)
    assert restored.roots["stable-id"].path == str(user_models.resolve())
    assert restored.remove_root("stable-id")
    assert "stable-id" not in ModelStore(store.engine_dir).roots
    assert sentinel.read_text() == "user-owned"
    assert restored.remove_root("default_engine")
    assert "default_engine" not in ModelStore(store.engine_dir).roots


@pytest.mark.asyncio
async def test_url_connection_retains_identity_and_exact_endpoint(tmp_path: Path) -> None:
    manager = EngineManager(tmp_path / "application")
    with patch.object(manager, "test_engine_connection", new=AsyncMock(side_effect=lambda connection: connection)):
        first = await manager.connect_external_engine(EngineType.COMFYUI, "http://remote.test:8188/studio", "Studio")
    restored = EngineManager(manager.data_dir)
    connection = restored.get_engine(first.id)
    assert connection.endpoint_url == "http://remote.test:8188/studio"
    assert connection.name == "Studio"
    assert connection.ownership == EngineOwnership.EXTERNAL
    with patch.object(restored, "test_engine_connection", new=AsyncMock(side_effect=lambda connection: connection)):
        assert (await restored.connect_external_engine(EngineType.COMFYUI, first.endpoint_url)).id == first.id
    assert not restored.unbind_external_engine("managed_comfyui")
    assert restored.unbind_external_engine(first.id)
    assert EngineManager(manager.data_dir).get_engine(first.id) is None


def test_mirror_preferences_restore_atomically(tmp_path: Path) -> None:
    path = tmp_path / "application" / "mirrors.json"
    manager = MirrorManager(path)
    manager.update_config("custom", "https://git.test", "https://pip.test/simple", "https://hf.test")
    restored = MirrorManager(path)
    assert restored.get_config() == manager.get_config()
    assert restored.transform_git_url("https://github.com/example/repo") == "https://git.test/https://github.com/example/repo"
    assert restored.get_pip_index_url() == "https://pip.test/simple"
    assert not list(path.parent.glob("*.tmp"))
