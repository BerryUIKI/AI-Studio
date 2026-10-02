"""
Comprehensive verification tests for Milestone 1:
- Targeted single-node execution
- Port-aware semantic caching
- Strict failure boundaries & dependent blocking
- output.preview runner execution
- Task cancellation semantics
- SQLite project & asset persistence
- ComfyUI real output polling
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.cache import cache_store, compute_content_hash, compute_semantic_node_hash
from app.core.dag import DAGResolver
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.workflow import WorkflowEdgeInstance, WorkflowGraph, WorkflowNodeInstance
from app.storage.asset_store import asset_store
from app.storage.project_store import project_store
from app.runners.comfy_runner import ComfyUIClient, run_comfy_txt2img_node

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Targeted Single-Node Execution
# ---------------------------------------------------------------------------

def test_targeted_node_execution_websocket():
    """Targeted execution only runs target node and its upstream ancestors, skipping unrelated nodes."""
    graph_payload = {
        "target_node_id": "n2",
        "run_id": "test_run_targeted",
        "graph": {
            "nodes": [
                {"id": "n1", "type": "input.text", "params": {"value": "hello berry"}},
                {"id": "n2", "type": "output.preview", "params": {}},
                {"id": "n3_unrelated", "type": "input.text", "params": {"value": "unrelated"}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "source_handle": "text", "target": "n2", "target_handle": "media"}
            ],
        },
    }

    executed_nodes = []
    with client.websocket_connect("/ws/workflow/run") as ws:
        ws.send_text(json.dumps(graph_payload))
        while True:
            try:
                raw = ws.receive_text()
                event = json.loads(raw)
                if event.get("type") == "NODE_OUTPUT":
                    executed_nodes.append(event.get("node_id"))
                elif event.get("type") == "GRAPH_FINISHED":
                    break
            except Exception:
                break

    assert "n1" in executed_nodes
    assert "n2" in executed_nodes
    assert "n3_unrelated" not in executed_nodes


# ---------------------------------------------------------------------------
# 2. Port-Aware Semantic Caching
# ---------------------------------------------------------------------------

def test_port_aware_cache_discrimination():
    """Swapping port connections produces distinct semantic hashes."""
    bindings_a = [
        ("input_a", "hash_content_1", "output_1"),
        ("input_b", "hash_content_2", "output_2"),
    ]
    bindings_b = [
        ("input_a", "hash_content_2", "output_2"),
        ("input_b", "hash_content_1", "output_1"),
    ]

    h1 = compute_semantic_node_hash("image.combine", {"mode": "blend"}, bindings_a)
    h2 = compute_semantic_node_hash("image.combine", {"mode": "blend"}, bindings_b)

    assert h1 != h2, "Swapping port inputs must yield distinct cache hashes"


def test_content_hash_invalidation():
    """Changing upstream output content changes hash and avoids stale cache hits."""
    h_text1 = compute_content_hash("sunset over ocean")
    h_text2 = compute_content_hash("sunset over mountains")

    binding1 = [("prompt", h_text1, "text")]
    binding2 = [("prompt", h_text2, "text")]

    node_hash1 = compute_semantic_node_hash("image.generate", {"model": "flux-schnell"}, binding1)
    node_hash2 = compute_semantic_node_hash("image.generate", {"model": "flux-schnell"}, binding2)

    assert node_hash1 != node_hash2


# ---------------------------------------------------------------------------
# 3. Failure Boundary & Downstream Blocking
# ---------------------------------------------------------------------------

def test_failure_propagation_blocks_dependents():
    """When an upstream node fails, dependent nodes are cancelled and not executed."""
    graph_payload = {
        "run_id": "test_run_fail",
        "graph": {
            "nodes": [
                {"id": "n1", "type": "unknown.invalid_type", "params": {}},
                {"id": "n2", "type": "output.preview", "params": {}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "source_handle": "out", "target": "n2", "target_handle": "media"}
            ],
        },
    }

    statuses = {}
    with client.websocket_connect("/ws/workflow/run") as ws:
        ws.send_text(json.dumps(graph_payload))
        while True:
            try:
                raw = ws.receive_text()
                event = json.loads(raw)
                if event.get("type") == "NODE_STATUS":
                    statuses[event["node_id"]] = event["status"]
                elif event.get("type") == "GRAPH_FINISHED":
                    assert event.get("status") == "failed"
                    break
            except Exception:
                break

    assert statuses.get("n1") == "error"
    assert statuses.get("n2") == "cancelled"


# ---------------------------------------------------------------------------
# 4. output.preview Runner Execution
# ---------------------------------------------------------------------------

def test_output_preview_runner():
    """output.preview executes cleanly and passes through image/text media."""
    graph_payload = {
        "graph": {
            "nodes": [
                {"id": "n1", "type": "input.text", "params": {"value": "rendered preview card text"}},
                {"id": "n2", "type": "output.preview", "params": {}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "source_handle": "text", "target": "n2", "target_handle": "media"}
            ],
        }
    }

    preview_output = None
    with client.websocket_connect("/ws/workflow/run") as ws:
        ws.send_text(json.dumps(graph_payload))
        while True:
            try:
                raw = ws.receive_text()
                event = json.loads(raw)
                if event.get("type") == "NODE_OUTPUT" and event.get("node_id") == "n2":
                    preview_output = event.get("output")
                elif event.get("type") == "GRAPH_FINISHED":
                    break
            except Exception:
                break

    assert preview_output is not None
    assert preview_output.get("result") == "rendered preview card text"


# ---------------------------------------------------------------------------
# 5. Task Cancellation Semantics
# ---------------------------------------------------------------------------

def test_cancellation_endpoint():
    """POST /api/v1/workflow/cancel/{run_id} requests truthful cancellation."""
    # Test nonexistent run
    res = client.post("/api/v1/workflow/cancel/nonexistent_run")
    assert res.status_code == 200
    assert res.json()["success"] is False


# ---------------------------------------------------------------------------
# 6. SQLite Project and Asset Persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_crud_persistence():
    """Projects and canvas state are saved and restored accurately across calls."""
    # Create project
    proj = await project_store.create_project(ProjectCreate(name="My First Artwork"))
    assert proj.id is not None
    assert proj.name == "My First Artwork"

    # Update canvas
    updated_canvas = {
        "nodes": [{"id": "node_1", "type": "input.text"}],
        "edges": [],
        "viewport": {"x": 50, "y": 100, "zoom": 1.5},
    }
    updated = await project_store.update_project(proj.id, ProjectUpdate(canvas=updated_canvas))
    assert updated is not None
    assert updated.canvas["viewport"]["zoom"] == 1.5

    # Retrieve from DB
    loaded = await project_store.get_project(proj.id)
    assert loaded is not None
    assert loaded.name == "My First Artwork"
    assert len(loaded.canvas["nodes"]) == 1

    # REST endpoint test
    res = client.get(f"/api/v1/projects/{proj.id}")
    assert res.status_code == 200
    assert res.json()["id"] == proj.id


@pytest.mark.asyncio
async def test_asset_store_content_addressable():
    """Assets are hashed and stored with content-addressable deduplication."""
    fake_png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    asset = await asset_store.save_bytes(fake_png_data, filename="test_pixel.png")

    assert asset.id is not None
    assert asset.byte_size == len(fake_png_data)
    assert len(asset.content_hash) == 64

    # Fetch by ID
    loaded_asset = await asset_store.get_asset(asset.id)
    assert loaded_asset is not None
    assert loaded_asset.content_hash == asset.content_hash

    # Verify physical file exists on disk
    abs_path = asset_store.get_absolute_path(loaded_asset)
    assert abs_path.is_file()
    assert abs_path.read_bytes() == fake_png_data


# ---------------------------------------------------------------------------
# 7. ComfyUI Output Polling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_comfy_history_polling():
    """ComfyUI client polls /history/{prompt_id} and extracts real output images."""
    client_instance = ComfyUIClient(host="127.0.0.1", port=8188)

    mock_history_payload = {
        "sample_prompt_123": {
            "status": {"status_str": "success", "completed": True, "messages": []},
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "Berry_output_001.png", "subfolder": "", "type": "output"}
                    ]
                }
            },
        }
    }

    with patch.object(client_instance, "get_history", new_callable=AsyncMock) as mock_get_hist:
        mock_get_hist.return_value = mock_history_payload
        images = await client_instance.poll_history_outputs("sample_prompt_123", max_wait=2.0)
        assert len(images) == 1
        assert images[0]["filename"] == "Berry_output_001.png"
