import os
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from app.runtime.supervisor import ComfySupervisor
from app.runtime.webui_supervisor import WebUISupervisor
from app.runtime.llama_server.llama_supervisor import LlamaServerSupervisor


def test_comfy_rejects_unrelated_python_process():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        supervisor = ComfySupervisor(engine_dir=tmp_path / "comfyui")

        # Current test runner process is Python, but outside the supervisor runtime directory
        is_owned = supervisor._verify_process_identity(os.getpid())
        assert is_owned is False, "ComfySupervisor must not claim ownership over an unrelated Python process"


def test_webui_rejects_unrelated_python_process():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        supervisor = WebUISupervisor(engine_dir=tmp_path / "webui")

        is_owned = supervisor._verify_process_identity(os.getpid())
        assert is_owned is False, "WebUISupervisor must not claim ownership over an unrelated Python process"


def test_llama_rejects_unrelated_python_process():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        supervisor = LlamaServerSupervisor(engine_dir=tmp_path / "llama")

        is_owned = supervisor._verify_process_identity(os.getpid())
        assert is_owned is False, "LlamaServerSupervisor must not claim ownership over an unrelated process"


def test_stale_pid_cleanup_and_safe_stop():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        supervisor = ComfySupervisor(engine_dir=tmp_path / "comfyui")

        # Simulate a stale PID file pointing to our own process
        supervisor.ensure_directories()
        supervisor.pid_file.write_text(str(os.getpid()), encoding="utf-8")

        # get_pid() should detect that this process is unowned and clean up
        assert supervisor.get_pid() is None
        assert not supervisor.pid_file.is_file()

        # stop() must NOT call taskkill
        with patch("subprocess.run") as mock_run:
            res = supervisor.stop()
            assert res["success"] is True
            assert mock_run.call_count == 0


def test_owned_executable_matching():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        supervisor = ComfySupervisor(engine_dir=tmp_path / "comfyui")

        runtime_python = supervisor.runtime_dir / "Scripts" / "python.exe"
        assert supervisor._is_owned_executable(runtime_python) is True

        comfy_script = supervisor.comfy_dir / "main.py"
        assert supervisor._is_owned_executable(comfy_script) is True

        system_python = Path(os.environ.get("WINDIR", "C:\\Windows")) / "System32" / "cmd.exe"
        assert supervisor._is_owned_executable(system_python) is False
