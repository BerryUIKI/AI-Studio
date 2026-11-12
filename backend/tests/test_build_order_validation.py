"""The Windows packaging guard must validate the current Tauri configuration."""

import json
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows packaging script")
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "test-build-order.ps1"


@pytest.mark.parametrize("frontend", ["../dist", None, "../other", ""])
def test_frontend_asset_directory_is_required(tmp_path: Path, frontend: str | None) -> None:
    config = tmp_path / "frontend" / "src-tauri" / "tauri.conf.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"build": {"frontendDist": frontend}}), encoding="utf-8")
    package = tmp_path / "scripts" / "package-windows-release.ps1"
    package.parent.mkdir()
    package.write_text('pnpm build\npnpm tauri build\nAssert-FileExists "$FrontendDist\\index.html"\n', encoding="utf-8")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-File", str(SCRIPT), "-RepoRoot", str(tmp_path)],
        capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if frontend == "../dist":
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Build Order Validation PASSED" in result.stdout
    else:
        assert result.returncode != 0
        assert "frontendDist" in result.stderr


def test_tauri_cannot_build_before_frontend(tmp_path: Path) -> None:
    config = tmp_path / "frontend" / "src-tauri" / "tauri.conf.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"build": {"frontendDist": "../dist"}}), encoding="utf-8")
    package = tmp_path / "scripts" / "package-windows-release.ps1"
    package.parent.mkdir()
    package.write_text('pnpm tauri build\npnpm build\nAssert-FileExists "$FrontendDist\\index.html"\n', encoding="utf-8")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-File", str(SCRIPT), "-RepoRoot", str(tmp_path)],
        capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode != 0
    assert "INCORRECT BUILD ORDER" in result.stderr
