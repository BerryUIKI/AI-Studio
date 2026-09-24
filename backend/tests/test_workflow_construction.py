"""Tests for Bounded Workflow Construction, Validation, Approval Enforcement, and Recovery Guidance (M10)."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.core.workflow_catalog import BOUNDED_WORKFLOWS, WorkflowCatalog
from app.core.agent_service import AgentService
from app.schemas.agent import (
    AgentChatRequest,
    AgentProposal,
    ReviewableWorkflowGraph,
    WorkflowNodeStage,
)
from app.schemas.creative import CreativeActionType, CreativeActionResult
from app.schemas.model import ModelRecord, ModelCategory, ModelArchitecture
from app.main import app

client = TestClient(app)


def test_bounded_workflow_catalog_listing():
    """WorkflowCatalog lists exactly the 6 bounded supported workflows."""
    workflows = WorkflowCatalog.list_workflows()
    assert len(workflows) == 6

    wf_ids = {w["workflow_id"] for w in workflows}
    expected_ids = {
        "comfy.txt2img.standard",
        "comfy.img2img.standard",
        "comfy.inpaint.standard",
        "comfy.upscale.esrgan",
        "comfy.img2video.svd",
        "comfy.txt2video.animatediff",
    }
    assert wf_ids == expected_ids

    for w in workflows:
        assert w["title"]
        assert w["category"] in ("image", "video", "upscale")
        assert len(w["required_nodes"]) > 0
        assert len(w["required_models"]) > 0


def test_construct_txt2img_bounded_workflow():
    """Txt2Img bounded workflow constructs a valid ComfyUI prompt graph with reviewable stages."""
    graph, reviewable = WorkflowCatalog.construct_workflow(
        "comfy.txt2img.standard",
        {"prompt": "A beautiful sunset over mountains", "aspect_ratio": "16:9", "steps": 25},
    )

    assert reviewable.workflow_id == "comfy.txt2img.standard"
    assert reviewable.node_count == 7
    assert len(reviewable.stages) == 6
    assert reviewable.is_valid is True
    assert len(reviewable.validation_issues) == 0

    # Ensure raw latents / ports are not leaked to canvas (structure is encapsulated)
    assert "3" in graph  # KSampler
    assert "4" in graph  # CheckpointLoaderSimple
    assert graph["4"]["inputs"]["ckpt_name"] == "v1-5-pruned-emaonly.safetensors"


def test_construct_img2video_bounded_workflow():
    """Img2Video SVD workflow constructs valid graph with stages and models."""
    graph, reviewable = WorkflowCatalog.construct_workflow(
        "comfy.img2video.svd",
        {"input_image_id": "asset-123", "num_frames": 25, "fps": 16},
    )

    assert reviewable.workflow_id == "comfy.img2video.svd"
    assert reviewable.node_count == 6
    assert len(reviewable.stages) == 6
    assert "svd_xt.safetensors" in reviewable.required_models
    assert reviewable.is_valid is True


def test_construct_animatediff_bounded_workflow():
    """AnimateDiff text-to-video workflow constructs valid graph and stages."""
    graph, reviewable = WorkflowCatalog.construct_workflow(
        "comfy.txt2video.animatediff",
        {"prompt": "Ocean waves rolling onto the beach", "video_frames": 16, "fps": 8},
    )

    assert reviewable.workflow_id == "comfy.txt2video.animatediff"
    assert reviewable.node_count == 8
    assert len(reviewable.stages) == 6
    assert "mm_sd_v15_v2.ckpt" in reviewable.required_models
    assert reviewable.is_valid is True


def test_construct_workflow_with_missing_models_detection():
    """When catalog is indexed and missing required model, validation flags it with recovery guidance."""
    mock_catalog = MagicMock()
    # Catalog contains only SD1.5, missing SVD
    mock_catalog.get_models.return_value = [
        ModelRecord(
            id="sd15",
            name="v1-5-pruned-emaonly.safetensors",
            file_path="models/v1-5-pruned-emaonly.safetensors",
            category=ModelCategory.CHECKPOINT,
            architecture=ModelArchitecture.SD15,
            format="safetensors",
            size_bytes=4000000000,
            size_mb=4000.0,
        )
    ]

    graph, reviewable = WorkflowCatalog.construct_workflow(
        "comfy.img2video.svd",
        {"input_image_id": "test-img"},
        model_catalog=mock_catalog,
    )

    assert "svd_xt.safetensors" in reviewable.missing_models
    assert reviewable.is_valid is False
    assert reviewable.recovery_guidance is not None
    assert "Missing required model(s)" in reviewable.recovery_guidance
    assert "svd_xt.safetensors" in reviewable.recovery_guidance


def test_construct_unknown_workflow_raises_error():
    """Unknown workflow ID raises ValueError."""
    with pytest.raises(ValueError, match="Unknown bounded workflow"):
        WorkflowCatalog.construct_workflow("comfy.nonexistent.workflow", {})


@pytest.mark.asyncio
async def test_agent_populates_workflow_graph_for_comfyui():
    """AgentService populates proposal.workflow_graph with stages and models when targeting ComfyUI."""
    service = AgentService()
    req = AgentChatRequest(message="Generate a scenic mountain lake in 16:9 using ComfyUI")
    resp = await service.process_chat(req)

    assert resp.proposal is not None
    assert resp.proposal.target_engine == "managed_comfyui"
    assert resp.proposal.workflow_graph is not None
    assert resp.proposal.workflow_graph.workflow_id == "comfy.txt2img.standard"
    assert len(resp.proposal.workflow_graph.stages) == 6
    assert resp.proposal.workflow_graph.is_valid is True


@pytest.mark.asyncio
async def test_agent_execute_proposal_enforces_approval_gate():
    """AgentService rejects execution if user has not explicitly approved the proposal."""
    service = AgentService()
    proposal = AgentProposal(
        intent="txt2img",
        title="Test Proposal",
        summary="Test",
        target_engine="managed_comfyui",
        model="v1-5-pruned-emaonly.safetensors",
        approved=False,  # Unapproved!
    )

    with pytest.raises(PermissionError, match="Cannot execute unapproved proposal"):
        await service.execute_proposal(proposal)


@pytest.mark.asyncio
async def test_agent_execute_proposal_blocks_invalid_workflow():
    """AgentService rejects execution if workflow_graph validation failed, providing recovery guidance."""
    service = AgentService()
    invalid_graph = ReviewableWorkflowGraph(
        workflow_id="comfy.img2video.svd",
        workflow_title="SVD Workflow",
        node_count=5,
        stages=[],
        required_nodes=[],
        required_models=["svd_xt.safetensors"],
        missing_models=["svd_xt.safetensors"],
        is_valid=False,
        validation_issues=["Missing required checkpoint svd_xt.safetensors"],
        recovery_guidance="Download svd_xt.safetensors into your engine models directory or switch to Fal.ai BYOK.",
    )

    proposal = AgentProposal(
        intent="img2video",
        title="SVD Video Plan",
        summary="Test SVD",
        target_engine="managed_comfyui",
        model="svd_xt.safetensors",
        workflow_graph=invalid_graph,
        approved=True,  # Approved by user, but structurally/dependency invalid
    )

    with pytest.raises(ValueError, match="Cannot execute invalid workflow proposal"):
        await service.execute_proposal(proposal)


def test_endpoint_get_bounded_workflows():
    """GET /api/v1/workflow/bounded returns the catalog of 6 bounded workflows."""
    resp = client.get("/api/v1/workflow/bounded")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 6
    assert any(w["workflow_id"] == "comfy.txt2img.standard" for w in data)
