"""
Unit & Integration Tests for Task Cancellation, Cloud Actions & Engine Interruption (R07-R09, R14, L07).
Verifies:
- Active task cancellation for creative runner and workflow DAG runs
- Truthful cloud cancellation disclaimer disclosure (R14)
- Engine interrupt dispatch for ComfyUI and WebUI
- Manager shutdown active-task protection when creative tasks are in flight
- Cloud inpainting, upscaling, and img2img execution & unsupported error explanations
"""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app, active_cancellations
from app.runners.creative_runner import creative_runner
from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.runners.comfy_runner import comfy_client
from app.runners.webui_runner import WebUIRunner


@pytest.fixture
def client():
    return TestClient(app)


def test_list_active_tasks_and_cancel_endpoints(client):
    """R14: Test listing active tasks and canceling via REST endpoints."""
    # Register mock workflow run
    run_id = "test-workflow-run-123"
    cancel_evt = asyncio.Event()
    active_cancellations[run_id] = cancel_evt

    # Register mock creative runner task
    task_id = "task_9999999999"
    creative_runner.active_tasks[task_id] = {
        "action": "txt2img",
        "engine": "managed_comfyui",
        "start_time": 1000.0,
    }
    task_cancel_evt = asyncio.Event()
    creative_runner.active_cancellations[task_id] = task_cancel_evt

    try:
        # 1. Query active tasks
        resp = client.get("/api/v1/tasks/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_tasks_count"] == 2
        task_ids = [t["id"] for t in data["tasks"]]
        assert run_id in task_ids
        assert task_id in task_ids

        # 2. Cancel workflow run
        resp_cancel_wf = client.post(f"/api/v1/workflow/cancel/{run_id}")
        assert resp_cancel_wf.status_code == 200
        assert cancel_evt.is_set()

        # 3. Cancel creative action (ComfyUI interrupt)
        with patch.object(comfy_client, "interrupt", new_callable=AsyncMock) as mock_interrupt:
            mock_interrupt.return_value = True
            resp_cancel_cr = client.post(f"/api/v1/tasks/{task_id}/cancel")
            assert resp_cancel_cr.status_code == 200
            assert task_cancel_evt.is_set()
            assert resp_cancel_cr.json()["engine_interrupted"] is True
            mock_interrupt.assert_awaited_once()

    finally:
        active_cancellations.pop(run_id, None)
        creative_runner.active_tasks.pop(task_id, None)
        creative_runner.active_cancellations.pop(task_id, None)


def test_cloud_cancellation_discloses_remote_limitation(client):
    """R14: Truthful disclosure that remote cloud computation may continue."""
    task_id = "task_cloud_cancel_123"
    creative_runner.active_tasks[task_id] = {
        "action": "txt2img",
        "engine": "cloud_fal",
        "start_time": 1000.0,
    }
    cancel_evt = asyncio.Event()
    creative_runner.active_cancellations[task_id] = cancel_evt

    try:
        resp = client.post(f"/api/v1/tasks/{task_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert cancel_evt.is_set()
        assert data["disclaimer"] is not None
        assert "cloud providers may continue" in data["disclaimer"].lower()
    finally:
        creative_runner.active_tasks.pop(task_id, None)
        creative_runner.active_cancellations.pop(task_id, None)


def test_manager_shutdown_guards_creative_tasks(client):
    """L07: Manager shutdown must block if creative tasks are running unless force=True."""
    task_id = "task_shutdown_guard_test"
    creative_runner.active_tasks[task_id] = {
        "action": "inpaint",
        "engine": "managed_webui",
        "start_time": 1000.0,
    }
    cancel_evt = asyncio.Event()
    creative_runner.active_cancellations[task_id] = cancel_evt

    try:
        # Non-forced shutdown should fail with 409
        resp = client.post("/api/v1/manager/shutdown", json={"force": False})
        assert resp.status_code == 409
        assert "active generation task" in resp.json()["detail"]
        assert not cancel_evt.is_set()

        # Forced shutdown should succeed and cancel the creative task
        with patch("os._exit") as mock_exit:
            resp_force = client.post("/api/v1/manager/shutdown", json={"force": True})
            assert resp_force.status_code == 200
            assert resp_force.json()["status"] == "shutting_down"
            assert resp_force.json()["active_tasks_cancelled"] >= 1
            assert cancel_evt.is_set()
    finally:
        creative_runner.active_tasks.pop(task_id, None)
        creative_runner.active_cancellations.pop(task_id, None)


@pytest.mark.asyncio
async def test_comfy_client_and_webui_runner_interrupt():
    """Verify interrupt methods send correct POST endpoints to ComfyUI and WebUI."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200

        # ComfyUI
        c_client = comfy_client
        res_comfy = await c_client.interrupt()
        assert res_comfy is True
        mock_post.assert_awaited_with(f"{c_client.base_url}/interrupt")

        # WebUI
        w_runner = WebUIRunner("http://127.0.0.1:7860")
        res_webui = await w_runner.interrupt()
        assert res_webui is True
        mock_post.assert_awaited_with("http://127.0.0.1:7860/sdapi/v1/interrupt")


def test_cloud_actions_unsupported_combinations_explain_missing(client):
    """R07: Unsupported cloud action combinations must explain what is missing."""
    # Attempt cloud upscaling without Fal.ai key configured
    req = {
        "action": "upscale",
        "engine_id": "cloud_openai",
        "model": "dall-e-3",
        "prompt": "upscale test",
        "upscale_factor": 2.0,
    }
    resp = client.post("/api/v1/creative/execute", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "source image is required" in data["error_message"].lower()
