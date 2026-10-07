"""Tests for versioned durable project storage and missing asset recovery."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.storage.asset_store import asset_store
from app.storage.project_store import project_store

client = TestClient(app)


@pytest.mark.asyncio
async def test_versioned_project_crud():
    """Verify versioned project creation, updating, and retrieval."""
    canvas_payload = {
        "version": 1,
        "nodes": [
            {
                "id": "node_text_1",
                "type": "workflowNode",
                "position": {"x": 120, "y": 240},
                "data": {"type": "input.text", "parameters": {"value": "Concept prompt"}},
            },
            {
                "id": "node_image_1",
                "type": "imageCard",
                "position": {"x": 480, "y": 240},
                "data": {
                    "assetId": "asset_test_123",
                    "imageUrl": "/api/v1/assets/asset_test_123/content",
                    "width": 1024,
                    "height": 1024,
                    "provenance": {
                        "action": "txt2img",
                        "prompt": "Concept prompt",
                        "seed": 42,
                        "steps": 20,
                        "cfg_scale": 7.0,
                        "dimensions": "1024x1024",
                        "connection_id": "comfyui-managed",
                        "engine_id": "comfyui",
                        "model": "flux",
                        "created_at": "2026-10-07T00:00:00Z",
                    },
                },
            },
        ],
        "edges": [
            {
                "id": "edge_lineage_1",
                "source": "node_text_1",
                "target": "node_image_1",
            }
        ],
        "viewport": {"x": 100, "y": -50, "zoom": 1.25},
        "generationHistory": [
            {
                "id": "gen_1",
                "action": "txt2img",
                "prompt": "Concept prompt",
                "assetId": "asset_test_123",
            }
        ],
    }

    # 1. Create project with version and canvas
    proj = await project_store.create_project(
        ProjectCreate(name="Landscape Concept", version=1, canvas=canvas_payload)
    )
    assert proj.id is not None
    assert proj.version == 1
    assert proj.name == "Landscape Concept"
    assert len(proj.canvas["nodes"]) == 2
    assert proj.canvas["viewport"]["zoom"] == 1.25

    # 2. Retrieve project via API
    res = client.get(f"/api/v1/projects/{proj.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == proj.id
    assert data["version"] == 1
    assert len(data["canvas"]["nodes"]) == 2
    assert data["canvas"]["viewport"] == {"x": 100, "y": -50, "zoom": 1.25}
    assert len(data["canvas"]["generationHistory"]) == 1

    # 3. Update project canvas (e.g. autosave)
    updated_canvas = dict(canvas_payload)
    updated_canvas["viewport"] = {"x": 200, "y": 50, "zoom": 0.8}
    updated = await project_store.update_project(
        proj.id, ProjectUpdate(name="Landscape Concept v2", canvas=updated_canvas)
    )
    assert updated is not None
    assert updated.name == "Landscape Concept v2"
    assert updated.canvas["viewport"]["zoom"] == 0.8

    # 4. List projects contains updated project
    listed = await project_store.list_projects()
    found = next((p for p in listed if p.id == proj.id), None)
    assert found is not None
    assert found.name == "Landscape Concept v2"
    assert found.version == 1


@pytest.mark.asyncio
async def test_missing_asset_detection():
    """Verify that asset records accurately reflect missing physical files on disk."""
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02"
    asset = await asset_store.save_bytes(fake_png, filename="removable_asset.png")
    assert asset.file_exists is True

    # Physical file exists
    abs_path = asset_store.get_absolute_path(asset)
    assert abs_path.is_file()

    # Fetch via API
    res = client.get(f"/api/v1/assets/{asset.id}")
    assert res.status_code == 200
    assert res.json()["file_exists"] is True

    res_content = client.get(f"/api/v1/assets/{asset.id}/content")
    assert res_content.status_code == 200

    # Delete physical file on disk to simulate missing asset
    abs_path.unlink()
    assert not abs_path.exists()

    # Re-fetch asset record
    missing_record = await asset_store.get_asset(asset.id)
    assert missing_record is not None
    assert missing_record.file_exists is False

    # Fetching content endpoint returns 404
    res_missing_content = client.get(f"/api/v1/assets/{asset.id}/content")
    assert res_missing_content.status_code == 404
    assert "missing on disk" in res_missing_content.json()["detail"].lower()
