"""Tests for health and system info endpoints."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ai-workflow-backend"}


def test_system_info():
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Berry AI Studio"
    assert "runners" in data


def test_cors_configuration():
    # Whitelisted origin should receive CORS header
    resp_valid = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp_valid.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # Untrusted external origin must NOT receive access-control-allow-origin header
    resp_invalid = client.get("/health", headers={"Origin": "http://malicious-site.com"})
    assert resp_invalid.headers.get("access-control-allow-origin") != "http://malicious-site.com"

