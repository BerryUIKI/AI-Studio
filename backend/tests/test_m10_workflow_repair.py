"""Tests for Milestone M10: ComfyUI workflow construction, validation, and repair."""

import pytest
from fastapi.testclient import TestClient

from app.core.workflow_validator import WorkflowValidator
from app.core.workflow_repair import WorkflowRepairer
from app.main import app

client = TestClient(app)


def build_valid_comfyui_graph() -> dict:
    """Build a standard, structurally valid ComfyUI text-to-image prompt graph."""
    return {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "A beautiful landscape at sunset",
                "clip": ["4", 1],
            },
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "blurry, low quality",
                "clip": ["4", 1],
            },
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 8.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2],
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "BerryOutput",
                "images": ["8", 0],
            },
        },
    }


def test_validator_valid_graph():
    """Valid ComfyUI prompt graph passes validation with 0 errors."""
    graph = build_valid_comfyui_graph()
    validator = WorkflowValidator()
    report = validator.validate(graph)

    assert report.valid is True
    assert report.has_cycle is False
    assert report.node_count == 7
    assert len([i for i in report.issues if i.severity == "error"]) == 0


def test_validator_cycle_detection():
    """Validator detects topological cycles in cyclic graph."""
    graph = {
        "1": {
            "class_type": "KSampler",
            "inputs": {"latent_image": ["2", 0]},
        },
        "2": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["1", 0]},
        },
    }
    validator = WorkflowValidator()
    report = validator.validate(graph)

    assert report.valid is False
    assert report.has_cycle is True
    assert any(i.issue_type == "cycle_detected" for i in report.issues)


def test_validator_broken_link_and_missing_slots():
    """Validator detects missing required slots and links to non-existent nodes."""
    graph = {
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["999", 0],  # Node 999 does not exist
                # Missing 'vae' input slot
            },
        }
    }
    validator = WorkflowValidator()
    report = validator.validate(graph)

    assert report.valid is False
    types = [i.issue_type for i in report.issues]
    assert "broken_link" in types
    assert "missing_connection" in types


def test_validator_type_mismatch():
    """Validator detects type mismatch between connected output and expected input."""
    graph = {
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["5", 0],  # Slot 0 of EmptyLatentImage is LATENT, not VAE!
            },
        },
    }
    validator = WorkflowValidator()
    report = validator.validate(graph)

    assert report.valid is False
    assert any(i.issue_type == "type_mismatch" for i in report.issues)


def test_repairer_fixes_disconnected_workflow():
    """Repairer connects missing VAE, CLIP, and MODEL slots using available sources."""
    # Graph where VAEDecode is missing VAE, KSampler is missing MODEL, and CLIP is missing CLIP
    broken_graph = build_valid_comfyui_graph()
    del broken_graph["8"]["inputs"]["vae"]
    del broken_graph["3"]["inputs"]["model"]
    del broken_graph["6"]["inputs"]["clip"]

    # Verify it is broken first
    validator = WorkflowValidator()
    assert validator.validate(broken_graph).valid is False

    repairer = WorkflowRepairer()
    result = repairer.repair(broken_graph)

    assert result.success is True
    assert result.repaired_valid is True
    assert len(result.repairs_applied) == 3

    # Check that inputs were reconnected properly
    repaired = result.repaired_workflow
    assert repaired["8"]["inputs"]["vae"] == ["4", 2]
    assert repaired["3"]["inputs"]["model"] == ["4", 0]
    assert repaired["6"]["inputs"]["clip"] == ["4", 1]


def test_api_workflow_validate_and_repair_endpoints():
    """API endpoints /api/v1/workflow/validate and /api/v1/workflow/repair function properly."""
    broken = build_valid_comfyui_graph()
    del broken["8"]["inputs"]["vae"]

    # Validate endpoint
    val_resp = client.post("/api/v1/workflow/validate", json=broken)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid"] is False
    assert any(i["input_slot"] == "vae" for i in val_data["issues"])

    # Repair endpoint
    rep_resp = client.post("/api/v1/workflow/repair", json=broken)
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert rep_data["success"] is True
    assert rep_data["repaired_valid"] is True
    assert rep_data["repaired_workflow"]["8"]["inputs"]["vae"] == ["4", 2]


def test_repairer_blocks_ambiguous_connections():
    """Repairer blocks automatic reconnection when multiple ambiguous sources exist."""
    broken = build_valid_comfyui_graph()
    # Add a second VAE loader to create ambiguity
    broken["10"] = {
        "class_type": "VAELoader",
        "inputs": {"vae_name": "vae-ft-mse-840000-ema-pruned.safetensors"},
    }
    del broken["8"]["inputs"]["vae"]

    repairer = WorkflowRepairer()
    result = repairer.repair(broken)

    # Should have recorded a substitution_blocked action
    blocked_repairs = [r for r in result.repairs_applied if r.action_type == "substitution_blocked"]
    assert len(blocked_repairs) >= 1
    assert "ambiguous" in blocked_repairs[0].description.lower()
    # The slot should not have been blindly wired
    assert "vae" not in result.repaired_workflow["8"]["inputs"]


def test_repairer_blocks_cross_family_checkpoint_substitution():
    """Repairer blocks model substitution if indexed models belong to an incompatible or unknown family."""
    from unittest.mock import MagicMock
    from app.schemas.model import ModelRecord, ModelCategory, ModelArchitecture

    broken = build_valid_comfyui_graph()
    # Workflow expects a Flux model
    broken["4"]["inputs"]["ckpt_name"] = "flux1-schnell.safetensors"

    # Catalog only has an SD 1.5 model
    mock_catalog = MagicMock()
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

    repairer = WorkflowRepairer(model_catalog=mock_catalog)
    result = repairer.repair(broken)

    # Cross-family substitution must be blocked
    blocked = [r for r in result.repairs_applied if r.action_type == "substitution_blocked"]
    assert len(blocked) >= 1
    assert "flux" in blocked[0].description.lower()
    # The checkpoint in workflow should remain untouched (not mutated to SD1.5)
    assert result.repaired_workflow["4"]["inputs"]["ckpt_name"] == "flux1-schnell.safetensors"


def test_repairer_allows_same_family_checkpoint_substitution():
    """Repairer substitutes missing checkpoint when a candidate with matching family is indexed."""
    from unittest.mock import MagicMock
    from app.schemas.model import ModelRecord, ModelCategory, ModelArchitecture

    broken = build_valid_comfyui_graph()
    # Workflow has missing SD 1.5 checkpoint
    broken["4"]["inputs"]["ckpt_name"] = "dreamshaper_8_sd15.safetensors"

    mock_catalog = MagicMock()
    mock_catalog.get_models.return_value = [
        ModelRecord(
            id="sd15_alt",
            name="v1-5-pruned-emaonly.safetensors",
            file_path="models/v1-5-pruned-emaonly.safetensors",
            category=ModelCategory.CHECKPOINT,
            architecture=ModelArchitecture.SD15,
            format="safetensors",
            size_bytes=4000000000,
            size_mb=4000.0,
        )
    ]

    repairer = WorkflowRepairer(model_catalog=mock_catalog)
    result = repairer.repair(broken)

    substitutions = [r for r in result.repairs_applied if r.action_type == "replace_model"]
    assert len(substitutions) == 1
    assert result.repaired_workflow["4"]["inputs"]["ckpt_name"] == "v1-5-pruned-emaonly.safetensors"

