"""Tests for engine configuration persistence, validation, and lifecycle routing (Issue #125)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runtime.engine_manager import EngineManager, engine_manager
from app.runtime.supervisor import supervisor as comfy_supervisor
from app.runtime.webui_supervisor import webui_supervisor
from app.schemas.engine import EngineOwnership, EngineStatus, EngineType

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_engine_manager_state(tmp_path: Path):
    """Ensure each test runs with an isolated config file and reset supervisors."""
    original_data_dir = engine_manager.data_dir
    original_config_file = engine_manager.config_file
    original_configs = dict(engine_manager._configs)
    original_comfy_port = comfy_supervisor.port
    original_comfy_args = list(comfy_supervisor.extra_args)
    original_webui_port = webui_supervisor.port
    original_webui_args = list(webui_supervisor.extra_args)

    test_data_dir = tmp_path / "engine_data"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    engine_manager.data_dir = test_data_dir
    engine_manager.config_file = test_data_dir / "engine_configs.json"
    engine_manager._configs = {}

    # Reset default ports
    comfy_supervisor.port = 8188
    comfy_supervisor.extra_args = []
    webui_supervisor.port = 7860
    webui_supervisor.extra_args = []
    engine_manager._connections["managed_comfyui"].endpoint_url = "http://127.0.0.1:8188"
    engine_manager._connections["managed_comfyui"].native_ui_url = "http://127.0.0.1:8188"
    engine_manager._connections["managed_webui"].endpoint_url = "http://127.0.0.1:7860"
    engine_manager._connections["managed_webui"].native_ui_url = "http://127.0.0.1:7860"

    yield

    # Cleanup
    engine_manager.data_dir = original_data_dir
    engine_manager.config_file = original_config_file
    engine_manager._configs = original_configs
    comfy_supervisor.port = original_comfy_port
    comfy_supervisor.extra_args = original_comfy_args
    webui_supervisor.port = original_webui_port
    webui_supervisor.extra_args = original_webui_args
    engine_manager._connections["managed_comfyui"].endpoint_url = f"http://127.0.0.1:{original_comfy_port}"
    engine_manager._connections["managed_webui"].endpoint_url = f"http://127.0.0.1:{original_webui_port}"


def test_get_default_engine_config():
    """Verify retrieval of default configuration for managed instances."""
    resp_comfy = client.get("/api/v1/engines/comfyui-managed/config")
    assert resp_comfy.status_code == 200
    data_comfy = resp_comfy.json()
    assert data_comfy["instance_id"] == "comfyui-managed"
    assert data_comfy["port"] == 8188
    assert data_comfy["extra_args"] == []

    resp_webui = client.get("/api/v1/engines/webui-managed/config")
    assert resp_webui.status_code == 200
    data_webui = resp_webui.json()
    assert data_webui["instance_id"] == "webui-managed"
    assert data_webui["port"] == 7860
    assert data_webui["extra_args"] == []


def test_save_engine_config_success():
    """Verify successful save through real persistence operation."""
    payload = {
        "port": 8288,
        "extra_args": ["--lowvram", "--fast"],
    }
    resp = client.post("/api/v1/engines/comfyui-managed/config", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["instance_id"] == "comfyui-managed"
    assert data["port"] == 8288
    assert data["extra_args"] == ["--lowvram", "--fast"]
    assert data["requires_restart"] is False
    assert "successfully" in data["message"].lower()

    # Verify supervisor updated
    assert comfy_supervisor.port == 8288
    assert comfy_supervisor.extra_args == ["--lowvram", "--fast"]

    # Verify connection updated
    conn = engine_manager.get_engine("comfyui-managed")
    assert conn is not None
    assert conn.endpoint_url == "http://127.0.0.1:8288"

    # Verify instances catalog reflects saved port and extra_args
    cat_resp = client.get("/api/v1/engines/instances")
    assert cat_resp.status_code == 200
    instances = cat_resp.json()["instances"]
    comfy_inst = next((i for i in instances if i["id"] == "comfyui-managed"), None)
    assert comfy_inst is not None
    assert comfy_inst["port"] == 8288
    assert comfy_inst["endpoint"] == "http://127.0.0.1:8288"
    assert comfy_inst["extra_args"] == ["--lowvram", "--fast"]


def test_switching_selected_engines_configurations():
    """Verify switching between engines saves independent, non-conflicting configurations."""
    # 1. Save ComfyUI
    resp_comfy = client.post(
        "/api/v1/engines/comfyui-managed/config",
        json={"port": 8288, "extra_args": ["--lowvram"]},
    )
    assert resp_comfy.status_code == 200

    # 2. Switch to WebUI and save
    resp_webui = client.post(
        "/api/v1/engines/webui-managed/config",
        json={"port": 7865, "extra_args": ["--xformers", "--medvram"]},
    )
    assert resp_webui.status_code == 200

    # 3. Read back both
    get_comfy = client.get("/api/v1/engines/comfyui-managed/config").json()
    get_webui = client.get("/api/v1/engines/webui-managed/config").json()

    assert get_comfy["port"] == 8288
    assert get_comfy["extra_args"] == ["--lowvram"]

    assert get_webui["port"] == 7865
    assert get_webui["extra_args"] == ["--xformers", "--medvram"]


def test_save_engine_config_validation_failures():
    """Verify validation rejects invalid ports, conflicts, and invalid targets."""
    # 1. Invalid port range (< 1 or > 65535)
    resp_neg = client.post("/api/v1/engines/comfyui-managed/config", json={"port": -10, "extra_args": []})
    assert resp_neg.status_code == 400
    assert "between 1 and 65535" in resp_neg.json()["detail"]

    resp_high = client.post("/api/v1/engines/comfyui-managed/config", json={"port": 70000, "extra_args": []})
    assert resp_high.status_code == 400
    assert "between 1 and 65535" in resp_high.json()["detail"]

    # 2. Conflict with backend port (8000)
    resp_backend = client.post("/api/v1/engines/comfyui-managed/config", json={"port": 8000, "extra_args": []})
    assert resp_backend.status_code == 400
    assert "conflicts with Berry AI Studio backend port" in resp_backend.json()["detail"]

    # 3. Conflict with another engine (WebUI is port 7860)
    resp_conflict = client.post("/api/v1/engines/comfyui-managed/config", json={"port": 7860, "extra_args": []})
    assert resp_conflict.status_code == 400
    assert "conflicts with SD WebUI" in resp_conflict.json()["detail"]

    # 4. Unknown engine instance
    resp_unknown = client.post("/api/v1/engines/non-existent-engine/config", json={"port": 9000, "extra_args": []})
    assert resp_unknown.status_code == 404

    # 5. Built-in canvas workspace cannot be configured
    resp_canvas = client.post("/api/v1/engines/builtin-canvas/config", json={"port": 9000, "extra_args": []})
    assert resp_canvas.status_code == 400


def test_engine_config_restart_required_when_running():
    """Verify when an engine is running, save explains that a restart is required."""
    with patch.object(comfy_supervisor, "is_running", return_value=True):
        resp = client.post(
            "/api/v1/engines/comfyui-managed/config",
            json={"port": 8288, "extra_args": ["--lowvram"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["requires_restart"] is True
        assert "restart is required" in data["message"].lower()


def test_persistence_after_restart(tmp_path: Path):
    """Verify saved configuration persists across process/app restart."""
    data_dir = tmp_path / "persistence_test"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Instance 1: Save configurations
    mgr1 = EngineManager(data_dir=data_dir)
    cfg1, _ = mgr1.save_engine_config("comfyui-managed", port=8388, extra_args=["--fast", "--lowvram"])
    cfg2, _ = mgr1.save_engine_config("webui-managed", port=7960, extra_args=["--xformers"])

    assert cfg1.port == 8388
    assert cfg2.port == 7960

    # Ensure file was written to disk
    assert (data_dir / "engine_configs.json").is_file()

    # Instance 2: Simulate app restart by initializing a new EngineManager from same data_dir
    mgr2 = EngineManager(data_dir=data_dir)
    loaded_comfy = mgr2.get_engine_config("comfyui-managed")
    loaded_webui = mgr2.get_engine_config("webui-managed")

    assert loaded_comfy.port == 8388
    assert loaded_comfy.extra_args == ["--fast", "--lowvram"]

    assert loaded_webui.port == 7960
    assert loaded_webui.extra_args == ["--xformers"]

    # Verify supervisors and connections were configured on restart
    assert comfy_supervisor.port == 8388
    assert comfy_supervisor.extra_args == ["--fast", "--lowvram"]
    assert webui_supervisor.port == 7960
    assert webui_supervisor.extra_args == ["--xformers"]

    instances = mgr2.get_all_instances()
    c_inst = next(i for i in instances if i.id == "comfyui-managed")
    assert c_inst.endpoint == "http://127.0.0.1:8388"
    assert c_inst.port == 8388
    assert c_inst.extra_args == ["--fast", "--lowvram"]


def test_effective_configuration_used_in_launch(tmp_path: Path):
    """Verify saved port and launch arguments are actually included in launch command."""
    mock_py = tmp_path / "python.exe"
    mock_py.write_text("", encoding="utf-8")

    comfy_supervisor.port = 8488
    comfy_supervisor.extra_args = ["--lowvram", "--preview-method", "auto"]

    # Mock python executable and installation
    with patch("app.runtime.hardware.get_hardware_launch_flags", return_value=["--lowvram"]), \
         patch.object(comfy_supervisor, "is_installed", return_value=True), \
         patch.object(comfy_supervisor, "has_isolated_env", return_value=True), \
         patch.object(comfy_supervisor, "is_running", return_value=False), \
         patch.object(comfy_supervisor, "get_python_bin", return_value=mock_py), \
         patch.object(comfy_supervisor, "_generate_extra_model_paths_config", return_value=tmp_path / "extra.yaml"), \
         patch("app.runtime.supervisor.subprocess.Popen") as mock_popen, \
         patch.object(comfy_supervisor, "ensure_directories"), \
         patch.object(Path, "write_text"):

        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_popen.return_value = mock_proc

        res = comfy_supervisor.start()
        assert res["success"] is True

        # Inspect command line passed to subprocess.Popen
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        assert "--port" in cmd
        port_idx = cmd.index("--port")
        assert cmd[port_idx + 1] == "8488"
        assert "--lowvram" in cmd
        assert "--preview-method" in cmd
        assert "auto" in cmd


def test_preserve_ownership_and_connection_identity(tmp_path: Path):
    """Verify external engines preserve external ownership, stable IDs, and zero-process mutation."""
    mock_dir = tmp_path / "ExternalComfy"
    mock_dir.mkdir()

    # Bind external engine
    conn = engine_manager.bind_external_engine(
        engine_type_str="comfyui",
        name="Custom Studio A100",
        path_str=str(mock_dir),
        port=8588,
        extra_args=["--highvram"],
    )

    assert conn.ownership == EngineOwnership.EXTERNAL
    assert conn.id.startswith("ext_comfyui_")
    assert conn.endpoint_url == "http://127.0.0.1:8588"

    # Configure external engine port
    cfg, _ = engine_manager.save_engine_config(conn.id, port=8688, extra_args=["--highvram", "--cuda-malloc"])
    assert cfg.port == 8688

    # Verify ownership is still strictly EXTERNAL and ID is unchanged
    updated_conn = engine_manager.get_engine(conn.id)
    assert updated_conn.ownership == EngineOwnership.EXTERNAL
    assert updated_conn.id == conn.id
    assert updated_conn.endpoint_url == "http://127.0.0.1:8688"


def test_effective_configuration_used_in_execution_routing():
    """Verify creative runner uses configured port when creating clients for execution."""
    from app.runners.creative_runner import creative_runner

    # 1. Configure ComfyUI to port 8788
    engine_manager.save_engine_config("comfyui-managed", port=8788)
    conn_comfy = creative_runner._resolve_connection(connection_id="comfyui-managed", engine_id=None)
    assert conn_comfy.endpoint_url == "http://127.0.0.1:8788"
    client_comfy = creative_runner._create_client(conn_comfy)
    assert client_comfy.port == 8788
    assert client_comfy.base_url == "http://127.0.0.1:8788"

    # 2. Configure WebUI to port 7965
    engine_manager.save_engine_config("webui-managed", port=7965)
    conn_webui = creative_runner._resolve_connection(connection_id="webui-managed", engine_id=None)
    assert conn_webui.endpoint_url == "http://127.0.0.1:7965"
    client_webui = creative_runner._create_client(conn_webui)
    assert client_webui.endpoint_url == "http://127.0.0.1:7965"

