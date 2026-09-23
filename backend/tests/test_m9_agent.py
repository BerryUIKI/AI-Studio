"""Tests for Milestone M9: Conversational Agent workflow control & transparent action planning."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app, agent_service
from app.schemas.agent import AgentChatRequest, AgentExecuteProposalRequest, AgentProposal
from app.schemas.creative import CreativeActionRequest, CreativeActionResult, CreativeActionType

client = TestClient(app)


def test_agent_general_query():
    """Agent handles informational questions without generating a creative proposal."""
    resp = client.post("/api/v1/agent/chat", json={"message": "What can you do?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "conversation_id" in data
    assert "message" in data
    assert data["proposal"] is None
    assert "Berry AI Creative Assistant" in data["message"]["content"]


def test_agent_txt2img_intent_parsing():
    """Agent parses natural language creation prompt into structured transparent proposal."""
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "Please generate a photorealistic neon samurai in 16:9 with 30 steps"},
    )
    assert resp.status_code == 200
    data = resp.json()
    proposal = data["proposal"]
    assert proposal is not None
    assert proposal["intent"] == "txt2img"
    assert proposal["target_engine"] == "managed_comfyui"
    assert proposal["requires_user_approval"] is True
    assert proposal["approved"] is False
    assert proposal["parameters"]["aspect_ratio"] == "16:9"
    assert proposal["parameters"]["steps"] == 30
    assert "Free local execution" in proposal["cost_disclaimer"]
    assert "neon samurai" in proposal["parameters"]["prompt"]


def test_agent_compound_workflow_plan():
    """Agent parses chained instruction into multi-step action plan."""
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "Create an alpine lake at sunrise in widescreen then upscale 2x"},
    )
    assert resp.status_code == 200
    proposal = resp.json()["proposal"]
    assert proposal is not None
    assert len(proposal["chain_steps"]) == 2
    assert proposal["chain_steps"][0]["action"] == "txt2img"
    assert proposal["chain_steps"][1]["action"] == "upscale"
    assert proposal["estimated_calls"] == 2


def test_agent_video_intent_parsing():
    """Agent detects video generation request and formulates video proposal."""
    # Text-to-video
    resp1 = client.post(
        "/api/v1/agent/chat",
        json={"message": "Generate a video clip of waves crashing on rocks in fal.ai"},
    )
    assert resp1.status_code == 200
    p1 = resp1.json()["proposal"]
    assert p1["intent"] == "txt2video"
    assert p1["target_engine"] == "fal_ai"
    assert "Cloud BYOK" in p1["cost_disclaimer"]

    # Image-to-video with selected canvas asset
    resp2 = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "Animate this picture with smooth motion",
            "selected_asset_id": "asset-test-999",
        },
    )
    assert resp2.status_code == 200
    p2 = resp2.json()["proposal"]
    assert p2["intent"] == "img2video"
    assert p2["parameters"]["input_image_id"] == "asset-test-999"


@pytest.mark.asyncio
async def test_agent_execution_gate_unapproved_raises(monkeypatch):
    """Executing an unapproved proposal is blocked by the human-in-the-loop gate."""
    # Chat to create proposal
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "Draw a cozy cabin in the woods"},
    )
    proposal = resp.json()["proposal"]
    assert proposal["approved"] is False

    # Attempt to execute without approval
    exec_resp = client.post(
        "/api/v1/agent/execute",
        json={
            "proposal_id": proposal["id"],
            "proposal": proposal,
        },
    )
    assert exec_resp.status_code == 403
    assert "Explicit user approval is required" in exec_resp.json()["detail"]


@pytest.mark.asyncio
async def test_agent_execution_gate_approved_succeeds(monkeypatch):
    """Executing an approved proposal invokes CreativeRunner and returns results."""
    # Mock CreativeRunner.execute
    fake_result = CreativeActionResult(
        task_id="agent-run-123",
        action="txt2img",
        engine_id="managed_comfyui",
        model="test-model.safetensors",
        asset_id="asset-gen-001",
        image_url="/assets/asset-gen-001.png",
        width=512,
        height=512,
        success=True,
    )
    mock_execute = AsyncMock(return_value=fake_result)
    monkeypatch.setattr(agent_service.creative_runner, "execute", mock_execute)

    # Chat to create proposal
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "Draw a cozy cabin in the woods"},
    )
    proposal = resp.json()["proposal"]
    # User approves proposal
    proposal["approved"] = True

    # Execute approved proposal
    exec_resp = client.post(
        "/api/v1/agent/execute",
        json={
            "proposal_id": proposal["id"],
            "proposal": proposal,
        },
    )
    assert exec_resp.status_code == 200
    results = exec_resp.json()
    assert len(results) == 1
    assert results[0]["task_id"] == "agent-run-123"
    assert results[0]["asset_id"] == "asset-gen-001"
    assert mock_execute.called
