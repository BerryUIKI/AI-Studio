import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.core.session import session_manager, should_require_token, ALLOWED_ORIGINS

client = TestClient(app)
# Anonymous client: bypasses the suite-wide default session header
anon = TestClient(app, headers={"X-Session-Token": ""})
anon_ws = TestClient(app)


def test_session_token_endpoint_requires_trusted_origin():
    # Trusted dev-server origin may fetch the token for the dev flow
    resp = client.get(
        "/api/v1/auth/session",
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 200
    assert resp.json().get("session_token") == session_manager.get_token()


def test_session_token_endpoint_rejects_untrusted_origin():
    resp = client.get(
        "/api/v1/auth/session",
        headers={"Origin": "https://attacker.example"},
    )
    assert resp.status_code == 403


def test_info_omits_session_token():
    resp = client.get("/api/v1/info")
    assert resp.status_code == 200
    assert "session_token" not in resp.json()


def test_index_html_injection(tmp_path):
    # The packaged flow serves index.html with the token injected inline.
    # Tested through the renderer directly: CI runners have no frontend/dist,
    # so the GET / route may be the L02 packaging-error page there.
    from app.main import render_session_bootstrapped_index

    fake_dist = tmp_path / "dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text(
        "<!doctype html><html><head><title>Berry</title></head><body></body></html>",
        encoding="utf-8",
    )
    response = render_session_bootstrapped_index(fake_dist)
    body = response.body.decode("utf-8")
    assert "window.__BERRY_SESSION__" in body
    assert session_manager.get_token() in body
    assert body.index("window.__BERRY_SESSION__") < body.index("</head>")


def test_cross_origin_untrusted_post_rejected():
    resp = client.post(
        "/api/v1/runtime/start",
        headers={"Origin": "https://untrusted.example"},
        json={"engine": "comfyui"},
    )
    assert resp.status_code == 403
    assert "Cross-origin request forbidden" in resp.json().get("detail", "")


def test_sensitive_write_requires_token():
    # Anonymous mutation on a sensitive route: 401 with the new message
    resp = anon.post("/api/v1/runtime/start", json={"engine": "comfyui"})
    assert resp.status_code == 401
    assert "Session token required" in resp.json().get("detail", "")


def test_sensitive_write_with_invalid_token_rejected():
    resp = client.post(
        "/api/v1/runtime/start",
        headers={"X-Session-Token": "invalid-token-12345"},
        json={"engine": "comfyui"},
    )
    assert resp.status_code == 401
    assert "Invalid or expired session token" in resp.json().get("detail", "")


def test_sensitive_write_with_valid_token_passes_origin_and_token_gates():
    token = session_manager.get_token()
    resp = client.post(
        "/api/v1/runtime/start",
        headers={"X-Session-Token": token},
        json={"engine": "comfyui"},
    )
    # The endpoint itself may 4xx for missing engines; the boundary must not be the blocker
    assert resp.status_code != 401
    assert resp.status_code != 403


def test_sensitive_secret_get_requires_token():
    resp = anon.get("/api/v1/agent/llm/config")
    assert resp.status_code == 401


def test_health_and_status_stay_open():
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/runtime/status").status_code == 200
    assert client.get("/api/v1/tasks/history").status_code == 200


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


def test_ws_requires_token():
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with anon_ws.websocket_connect("/ws/workflow/run", headers={"X-Session-Token": ""}):
            pass
    assert exc_info.value.code == 1008


def test_ws_accepts_valid_token():
    token = session_manager.get_token()
    with client.websocket_connect(f"/ws/workflow/run?token={token}") as ws:
        # Connection accepted; an invalid payload yields a structured error rather than a handshake rejection
        ws.send_json({"type": "SUBSCRIBE", "run_id": "nonexistent", "after_sequence": 0})
        message = ws.receive_json()
        assert message.get("type") == "ERROR"


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


def test_should_require_token_matrix():
    # Writes on sensitive routes require a token
    assert should_require_token("/api/v1/runtime/start", "POST") is True
    assert should_require_token("/api/v1/manager/shutdown", "POST") is True
    assert should_require_token("/api/v1/creative/upload", "POST") is True
    assert should_require_token("/api/v1/custom-providers", "PUT") is True
    assert should_require_token("/api/v1/models/hub/download", "POST") is True
    # Secret reads require a token even though they are GETs
    assert should_require_token("/api/v1/agent/llm/config", "GET") is True
    assert should_require_token("/api/v1/cloud/credentials", "GET") is True
    # Ordinary reads stay open
    assert should_require_token("/api/v1/runtime/status", "GET") is False
    assert should_require_token("/api/v1/tasks/history", "GET") is False
    assert should_require_token("/api/v1/models/hub/catalog", "GET") is False
    # Delivery and health are exempt
    assert should_require_token("/api/v1/auth/session", "GET") is False
    assert should_require_token("/health", "GET") is False
    # Non-sensitive writes (none expected, but be explicit)
    assert should_require_token("/api/v1/workflow/validate", "POST") is True
