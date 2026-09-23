"""Tests for Milestone M8: Unified Berry CLI backend support."""

import asyncio
import pytest
from fastapi.testclient import TestClient

from app.main import app, active_cancellations

client = TestClient(app)


def test_upload_base64_image_success():
    """Test successful base64 asset upload via the CLI/backend endpoint."""
    # 1x1 transparent PNG in base64
    tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

    resp = client.post(
        "/api/v1/creative/upload-base64",
        json={
            "filename": "cli_test_image.png",
            "content_base64": tiny_png_b64,
            "media_type": "image",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["filename"] == "cli_test_image.png"
    assert data["media_type"] == "image"
    assert data["byte_size"] > 0
    assert "content_hash" in data


def test_upload_base64_invalid_data():
    """Test handling of invalid base64 payload."""
    resp = client.post(
        "/api/v1/creative/upload-base64",
        json={
            "filename": "bad.png",
            "content_base64": "not-valid-base-64!!!",
            "media_type": "image",
        },
    )
    assert resp.status_code == 400
    assert "Invalid base64 payload" in resp.json()["detail"]


def test_active_tasks_and_cancel_endpoints():
    """Test task inspection and cancellation endpoints."""
    # Register an active task cancellation token
    test_task_id = "test-task-cli-123"
    cancel_event = asyncio.Event()
    active_cancellations[test_task_id] = cancel_event

    try:
        # Active tasks query
        resp = client.get("/api/v1/tasks/active")
        assert resp.status_code == 200
        tasks = resp.json()
        assert "tasks" in tasks
        assert any(t["id"] == test_task_id for t in tasks["tasks"])

        # Cancel the active task
        cancel_resp = client.post(f"/api/v1/tasks/{test_task_id}/cancel")
        assert cancel_resp.status_code == 200
        data = cancel_resp.json()
        assert data["task_id"] == test_task_id
        assert data["status"] == "cancelled"
        assert cancel_event.is_set()

        # Cancel a non-existent task returns 404
        nonexistent_resp = client.post("/api/v1/tasks/nonexistent-task-id/cancel")
        assert nonexistent_resp.status_code == 404
    finally:
        active_cancellations.pop(test_task_id, None)
