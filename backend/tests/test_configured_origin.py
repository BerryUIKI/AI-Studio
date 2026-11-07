"""Custom-port browser startup retains exact-origin and WebSocket boundaries."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.core.session import configured_loopback_origins


@pytest.mark.parametrize("port", [8000, 8029, 65535])
def test_configured_origins_are_exact_loopback_addresses(port: int) -> None:
    assert configured_loopback_origins(port) == {
        f"http://127.0.0.1:{port}", f"http://localhost:{port}",
    }


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_invalid_backend_port_fails_explicitly(port: int) -> None:
    with pytest.raises(ValueError, match="BERRY_PORT"):
        configured_loopback_origins(port)


def test_fresh_custom_port_app_accepts_its_browser_and_rejects_other_origins(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(BERRY_PORT="8029", BERRY_DATA_DIR=str(tmp_path / "data"),
               AI_WORKFLOW_ENGINE_DIR=str(tmp_path / "engines"))
    script = """
import json
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.main import app
from app.core.session import session_manager

client = TestClient(app)
allowed = 'http://127.0.0.1:8029'
blocked = ['http://127.0.0.1:8030', 'http://127.0.0.1.evil.test:8029',
           'http://192.168.1.1:8029', 'https://attacker.test']
health = client.get('/health', headers={'Origin': allowed})
preflight = client.options('/health', headers={'Origin': allowed,
                          'Access-Control-Request-Method': 'GET'})
websocket_code = None
try:
    with client.websocket_connect('/ws/workflow/run', headers={'Origin': blocked[0]}):
        pass
except WebSocketDisconnect as error:
    websocket_code = error.code
print(json.dumps({'health': health.status_code, 'preflight': preflight.status_code,
                 'cors_origin': preflight.headers.get('access-control-allow-origin'),
                 'blocked': [client.get('/health', headers={'Origin': origin}).status_code
                             for origin in blocked], 'websocket_code': websocket_code,
                 'token_rejected': client.get('/health', headers={
                     'Origin': allowed, 'X-Session-Token': 'invalid-test-token'}).status_code}))
"""
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True,
                            text=True, cwd=Path(__file__).resolve().parents[1], timeout=30, check=True)
    assert json.loads(result.stdout.strip().splitlines()[-1]) == {
        "health": 200, "preflight": 200, "cors_origin": "http://127.0.0.1:8029",
        "blocked": [403, 403, 403, 403], "websocket_code": 1008, "token_rejected": 401,
    }
