"""Real disposable subprocess output is bounded and sanitized before persistence."""

from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from app.runtime.process_diagnostics import ProcessDiagnostics, redact_log
from app.runtime.engine_manager import EngineManager


def test_real_stdout_stderr_are_redacted_and_survive_reader_restart(tmp_path: Path) -> None:
    logs = ProcessDiagnostics(tmp_path / "engine.log")
    process = subprocess.Popen([sys.executable, "-c",
        "import sys; print('api_key=fixture-secret'); print('ERROR: missing checkpoint',file=sys.stderr); print('Authorization: Bearer fixture-token')"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    logs.attach(process)
    assert process.wait(timeout=5) == 0
    assert logs.reader is not None
    logs.reader.join(timeout=5)
    assert not logs.reader.is_alive()
    persisted = logs.path.read_text(encoding="utf-8")
    assert "fixture-secret" not in persisted and "fixture-token" not in persisted
    assert "ERROR: missing checkpoint" in persisted
    assert ProcessDiagnostics(logs.path).recent(2) == logs.recent(2)


def test_log_rotation_and_reads_are_bounded(tmp_path: Path) -> None:
    logs = ProcessDiagnostics(tmp_path / "engine.log", max_bytes=1024)
    process = subprocess.Popen([sys.executable, "-c", "for n in range(1000): print(str(n) + 'x'*100)"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    logs.attach(process)
    process.wait(timeout=5)
    logs.reader.join(timeout=5)
    files = list(tmp_path.glob("engine.log*"))
    assert len(files) <= 3
    assert all(file.stat().st_size <= 1024 for file in files)
    assert logs.recent(1)[0].startswith("999")


def test_missing_logs_do_not_claim_verification(tmp_path: Path) -> None:
    assert ProcessDiagnostics(tmp_path / "absent.log").recent() == []
    assert "fixture-token" not in redact_log('https://fixture.invalid/?token=fixture-token')
    assert "fixture secret" not in redact_log('"password": "fixture secret"')
    assert "fixture-secret" not in redact_log('"api_key": "fixture-secret"')
    assert "fixture-basic" not in redact_log('Authorization: Basic fixture-basic')


def test_engine_catalog_returns_actual_logs_or_empty(tmp_path: Path) -> None:
    manager = EngineManager(tmp_path)
    assert manager.get_logs("external-missing") == []
    with patch("app.runtime.engine_manager.comfy_supervisor.get_recent_logs", return_value=["ERROR: fixture failure"]):
        assert manager.get_logs("managed_comfyui") == ["ERROR: fixture failure"]


def test_capture_file_failure_does_not_leave_process_pipe_undrained(tmp_path: Path) -> None:
    logs = ProcessDiagnostics(tmp_path / "engine.log")
    process = subprocess.Popen([sys.executable, "-c", "print('x'*100000)"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    with patch("app.runtime.process_diagnostics.RotatingFileHandler", side_effect=OSError("fixture disk failure")):
        logs.attach(process)
    assert process.wait(timeout=5) == 0
    logs.reader.join(timeout=5)
    assert "fixture disk failure" in logs.recent()[0]
