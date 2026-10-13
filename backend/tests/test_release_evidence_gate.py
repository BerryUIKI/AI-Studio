"""Historical mocks and absent artifacts must never satisfy release acceptance."""

import importlib.util
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "verify-release-evidence.py"
SPEC = importlib.util.spec_from_file_location("release_evidence", SOURCE)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def report(commit: str) -> dict:
    return {
        "schema_version": 1, "commit": commit,
        "environment": {"os": "Windows", "machine": "fixture", "tested_at": "2026-10-13"},
        "integrations": {"engines": ["ComfyUI@fixture", "WebUI@fixture"], "providers": ["fixture"], "models": ["sha256:fixture"]},
        "requirements": [{"id": identity, "status": "passed", "evidence_level": "packaged-live", "artifacts": ["output.txt"]} for identity in sorted(gate.REQUIREMENTS)],
        "scenarios": [{"id": identity, "status": "passed", "evidence_level": "packaged-live", "artifacts": ["output.txt"]} for identity in sorted(gate.SCENARIOS)],
    }


def test_gate_rejects_mock_only_and_wrong_head(tmp_path: Path) -> None:
    data = report("a" * 40)
    data["requirements"][0]["evidence_level"] = "mock"
    errors = gate.validate_evidence(data, "b" * 40, tmp_path)
    assert any("exact tested commit" in error for error in errors)
    assert any("mocks, historical" in error for error in errors)
    assert any("missing, empty" in error for error in errors)


def test_gate_requires_all_requirements_and_clean_machine_artifacts(tmp_path: Path) -> None:
    (tmp_path / "output.txt").write_text("Fixture gate validation, not actual release evidence.")
    data = report("a" * 40)
    assert gate.validate_evidence(data, "a" * 40, tmp_path) == []
    data["requirements"] = data["requirements"][1:]
    data["scenarios"] = []
    errors = gate.validate_evidence(data, "a" * 40, tmp_path)
    assert any("requirements: missing" in error for error in errors)
    assert any("clean-windows-package" in error for error in errors)
