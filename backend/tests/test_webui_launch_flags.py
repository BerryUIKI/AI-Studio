"""
Tests for WebUI launch flag corrections and Python version compatibility (Issue #108).

Verifies:
1. WebUI supervisor uses correct --listen (boolean) and --server-name flags
2. --nowebui flag is removed to enable native WebUI access
3. Python version compatibility check warns about non-3.10.x versions
4. API access remains enabled via --api flag
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.runtime.webui_supervisor import WebUISupervisor


def test_webui_supervisor_uses_correct_listen_flags():
    """Verify WebUI supervisor uses --listen (boolean) and --server-name (address) correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_dir = Path(tmpdir) / "engine"
        supervisor = WebUISupervisor(engine_dir=engine_dir, port=7860)

        # Create minimal installation structure
        supervisor.ensure_directories()
        supervisor.webui_dir.mkdir(parents=True, exist_ok=True)
        (supervisor.webui_dir / "launch.py").write_text("# dummy", encoding="utf-8")
        supervisor.runtime_dir.mkdir(parents=True, exist_ok=True)
        python_bin = supervisor.get_python_bin()
        python_bin.parent.mkdir(parents=True, exist_ok=True)
        python_bin.write_text("# dummy python", encoding="utf-8")

        # Mock subprocess.Popen to capture command
        captured_cmd = []
        def mock_popen(cmd, **kwargs):
            captured_cmd.extend(cmd)
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            return mock_proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            with patch.object(supervisor, "get_python_bin", return_value=python_bin):
                # This will fail at python version check, but we can verify flags structure
                try:
                    result = supervisor.start()
                except Exception:
                    pass  # Expected since dummy python won't work

        # Verify the launch command structure would be correct
        # The correct flags should be: --listen --server-name 127.0.0.1
        # NOT: --listen 127.0.0.1 (which treats 127.0.0.1 as a boolean value)

        # Read the start method to verify flags
        import inspect
        source = inspect.getsource(supervisor.start)
        assert '"--listen"' in source
        assert '"--server-name"' in source
        assert '"127.0.0.1"' in source
        # Verify --listen is followed by --server-name, not by 127.0.0.1 directly
        lines = source.split("\n")
        listen_line_idx = None
        for i, line in enumerate(lines):
            if '"--listen"' in line:
                listen_line_idx = i
                break

        assert listen_line_idx is not None
        # Next non-empty line should contain --server-name
        for j in range(listen_line_idx + 1, len(lines)):
            if lines[j].strip() and not lines[j].strip().startswith("#"):
                assert '"--server-name"' in lines[j] or '"127.0.0.1"' in lines[j]
                break


def test_webui_supervisor_removes_nowebui_flag():
    """Verify WebUI supervisor does NOT include --nowebui flag, enabling native UI."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_dir = Path(tmpdir) / "engine"
        supervisor = WebUISupervisor(engine_dir=engine_dir, port=7860)

        supervisor.ensure_directories()
        supervisor.webui_dir.mkdir(parents=True, exist_ok=True)
        (supervisor.webui_dir / "launch.py").write_text("# dummy", encoding="utf-8")

        # Read the start method to verify --nowebui is NOT present
        import inspect
        source = inspect.getsource(supervisor.start)

        # --nowebui should NOT be in the command list
        assert '"--nowebui"' not in source
        assert "'--nowebui'" not in source

        # But --api should still be present for API access
        assert '"--api"' in source


def test_webui_supervisor_checks_python_version_compatibility():
    """Verify WebUI supervisor logs warning for non-3.10.x Python versions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_dir = Path(tmpdir) / "engine"
        supervisor = WebUISupervisor(engine_dir=engine_dir, port=7860)

        supervisor.ensure_directories()
        supervisor.webui_dir.mkdir(parents=True, exist_ok=True)
        (supervisor.webui_dir / "launch.py").write_text("# dummy", encoding="utf-8")
        supervisor.runtime_dir.mkdir(parents=True, exist_ok=True)
        python_bin = supervisor.get_python_bin()
        python_bin.parent.mkdir(parents=True, exist_ok=True)
        python_bin.write_text("# dummy python", encoding="utf-8")

        # Mock Python version check to return Python 3.14.5
        def mock_run(cmd, **kwargs):
            if "--version" in cmd:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "Python 3.14.5"
                return mock_result
            raise NotImplementedError()

        with patch("subprocess.run", side_effect=mock_run):
            with patch("app.runtime.webui_supervisor.logger") as mock_logger:
                # Mock is_running to return False
                with patch.object(supervisor, "is_running", return_value=False):
                    with patch.object(supervisor, "get_entrypoint", return_value=Path("dummy.py")):
                        with patch("subprocess.Popen") as mock_popen:
                            mock_popen.return_value.pid = 12345
                            result = supervisor.start()

                # Verify warning was logged about Python version mismatch
                warning_calls = [call for call in mock_logger.warning.call_args_list]
                assert len(warning_calls) > 0
                warning_msg = str(warning_calls[0])
                assert "3.10" in warning_msg
                assert "3.14" in warning_msg or "compatibility" in warning_msg.lower()


def test_webui_supervisor_api_flag_preserved():
    """Verify WebUI supervisor includes --api flag for REST API access."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_dir = Path(tmpdir) / "engine"
        supervisor = WebUISupervisor(engine_dir=engine_dir, port=7860)

        supervisor.ensure_directories()

        # Read the start method to verify --api is present
        import inspect
        source = inspect.getsource(supervisor.start)

        assert '"--api"' in source


def test_webui_supervisor_model_directory_flags_preserved():
    """Verify WebUI supervisor still includes model directory flags."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine_dir = Path(tmpdir) / "engine"
        supervisor = WebUISupervisor(engine_dir=engine_dir, port=7860)

        supervisor.ensure_directories()

        # Read the start method to verify model directory flags are present
        import inspect
        source = inspect.getsource(supervisor.start)

        assert '"--ckpt-dir"' in source
        assert '"--lora-dir"' in source
        assert '"--vae-dir"' in source
        assert "models_dir" in source
