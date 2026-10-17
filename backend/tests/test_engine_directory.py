"""Branded engine defaults preserve legacy files and explicit user paths (#225)."""

from pathlib import Path

import pytest
from app.runtime.installer import IsolatedEngineInstaller
from app.runtime.supervisor import ComfySupervisor, get_default_engine_dir
from app.runtime.webui_supervisor import WebUISupervisor


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
@pytest.mark.parametrize("legacy_exists", [False, True])
def test_branded_default_and_legacy_compatibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str, legacy_exists: bool
) -> None:
    monkeypatch.delenv("AI_WORKFLOW_ENGINE_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("app.runtime.supervisor.sys.platform", platform)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    branded = tmp_path / "Berry-AI-Studio" / "engine"
    legacy = (
        tmp_path / ("AI-Workflow" if platform == "win32" else ".ai-workflow") / "engine"
    )
    if legacy_exists:
        legacy.mkdir(parents=True)
        (legacy / "model.part").write_bytes(b"incomplete")
        # A separately prepared directory must not silently switch existing users.
        branded.mkdir(parents=True)
    expected = legacy if legacy_exists else branded
    assert get_default_engine_dir() == expected
    assert ComfySupervisor().engine_dir == expected
    assert WebUISupervisor().engine_dir == expected
    assert IsolatedEngineInstaller().engine_dir == expected
    if legacy_exists:
        assert (legacy / "model.part").read_bytes() == b"incomplete"
        assert list(branded.iterdir()) == []
    else:
        assert not branded.exists()  # Resolution alone creates no directories.


def test_explicit_engine_directory_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom = tmp_path / "user-chosen"
    monkeypatch.setenv("AI_WORKFLOW_ENGINE_DIR", str(custom))
    assert get_default_engine_dir() == custom.resolve()
    assert not custom.exists()
