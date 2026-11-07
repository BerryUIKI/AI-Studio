import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.core.session import session_manager, ALLOWED_ORIGINS

client = TestClient(app)


def test_session_token_endpoints():
    resp = client.get("/api/v1/auth/session")
    assert resp.status_code == 200
    token = resp.json().get("session_token")
    assert token == session_manager.get_token()

    info_resp = client.get("/api/v1/info")
    assert info_resp.status_code == 200
    assert info_resp.json().get("session_token") == token


def test_cross_origin_untrusted_post_rejected():
    resp = client.post(
        "/api/v1/runtime/start",
        headers={"Origin": "https://untrusted.example"},
        json={"engine": "comfyui"},
    )
    assert resp.status_code == 403
    assert "Cross-origin request forbidden" in resp.json().get("detail", "")


def test_cross_origin_untrusted_get_rejected():
    resp = client.get(
        "/api/v1/agent/llm/config",
        headers={"Origin": "https://attacker.site"},
    )
    assert resp.status_code == 403


def test_cross_origin_untrusted_websocket_rejected():
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/ws/workflow/run",
            headers={"Origin": "https://untrusted.example"},
        ):
            pass
    assert exc_info.value.code == 1008


def test_invalid_session_token_rejected():
    resp = client.post(
        "/api/v1/runtime/start",
        headers={"X-Session-Token": "invalid-token-12345"},
        json={"engine": "comfyui"},
    )
    assert resp.status_code == 401
    assert "Invalid or expired session token" in resp.json().get("detail", "")


def test_valid_session_token_accepted():
    token = session_manager.get_token()
    resp = client.get(
        "/health",
        headers={"X-Session-Token": token},
    )
    assert resp.status_code == 200


def test_trusted_browser_origin_accepted():
    resp = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 200
