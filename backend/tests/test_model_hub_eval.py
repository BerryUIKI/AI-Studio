"""Unit tests for Model Hub catalog registry and 4-tier hardware evaluator (MH-M2)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage.hub_catalog import HubCatalog
from app.runtime.hardware_evaluator import (
    evaluate_model_compatibility,
    evaluate_hardware,
)

client = TestClient(app)


def test_hub_catalog_list_and_filters():
    """Verify catalog listing, category filtering, and keyword search."""
    models = HubCatalog.list_models()
    assert len(models) >= 5

    # Checkpoint filter
    checkpoints = HubCatalog.list_models(category="checkpoint")
    assert all(m.category == "checkpoint" for m in checkpoints)
    assert len(checkpoints) >= 3

    # Architecture filter
    flux_models = HubCatalog.list_models(architecture="flux")
    assert any("flux" in m.architecture.lower() for m in flux_models)

    # Search filter
    upscalers = HubCatalog.list_models(query="ultrasharp")
    assert len(upscalers) >= 1
    assert "ultrasharp" in upscalers[0].id.lower()


def test_hub_catalog_endpoint():
    """Verify GET /api/v1/models/hub/catalog endpoint."""
    resp = client.get("/api/v1/models/hub/catalog")
    assert resp.status_code == 200
    data = resp.json()

    assert "total" in data
    assert "models" in data
    assert data["total"] >= 5
    assert any(m["id"] == "flux-1-schnell-fp8" for m in data["models"])


def test_hardware_evaluation_optimal_tier():
    """Verify Tier 1: Optimal VRAM evaluation on large GPU (RTX 4090 / 24GB)."""
    model = HubCatalog.get_model("flux-1-schnell-fp8")
    assert model is not None

    eval_res = evaluate_model_compatibility(
        model=model,
        gpu_total_mb=24576,
        gpu_free_mb=20480,
        ram_avail_mb=32768,
        has_gpu=True,
    )
    assert eval_res.tier == "optimal"
    assert eval_res.tier_color == "emerald"
    assert "Optimal" in eval_res.tier_label


def test_hardware_evaluation_playable_offload_tier():
    """Verify Tier 2: Playable with RAM offload on 8GB GPU with sufficient RAM."""
    model = HubCatalog.get_model("flux-1-schnell-fp8")
    assert model is not None

    eval_res = evaluate_model_compatibility(
        model=model,
        gpu_total_mb=8192,
        gpu_free_mb=6144,
        ram_avail_mb=24576,
        has_gpu=True,
    )
    assert eval_res.tier == "playable_offload"
    assert eval_res.tier_color == "amber"
    assert "Offload" in eval_res.tier_label


def test_hardware_evaluation_no_gpu_fallback():
    """Verify Tier 4: Unsupported on cloud/no-GPU machine."""
    model = HubCatalog.get_model("flux-1-schnell-fp8")
    assert model is not None

    eval_res = evaluate_model_compatibility(
        model=model,
        gpu_total_mb=0,
        gpu_free_mb=0,
        ram_avail_mb=8192,
        has_gpu=False,
    )
    assert eval_res.tier == "unsupported"
    assert eval_res.tier_color == "rose"
    assert "云端" in eval_res.tier_label or "Cloud" in eval_res.notes


def test_evaluate_endpoint():
    """Verify POST /api/v1/models/hub/evaluate endpoint."""
    resp = client.post(
        "/api/v1/models/hub/evaluate",
        json={"model_ids": ["flux-1-schnell-fp8", "sd-1.5-v1-5-pruned"]},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "hardware_summary" in data
    assert "evaluations" in data
    assert "flux-1-schnell-fp8" in data["evaluations"]
    assert "sd-1.5-v1-5-pruned" in data["evaluations"]
    assert data["evaluations"]["flux-1-schnell-fp8"]["tier"] in [
        "optimal",
        "playable_offload",
        "heavy_paging",
        "unsupported",
    ]
