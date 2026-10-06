"""Unit tests for DAG topological sorting, cycle detection, and dirty-check caching."""

import logging
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.dag import DAGResolver, CyclicDependencyError
from app.core.cache import compute_node_hash, cache_store, CacheStore
from app.schemas.workflow import WorkflowEdgeInstance, WorkflowGraph, WorkflowNodeInstance

client = TestClient(app)


def test_topological_sort_linear():
    # Node 1 -> Node 2 -> Node 3
    graph = WorkflowGraph(
        nodes=[
            WorkflowNodeInstance(id="n1", type="input.text", params={"value": "sunset"}),
            WorkflowNodeInstance(id="n2", type="text.llm", params={"model": "gpt-4o"}),
            WorkflowNodeInstance(id="n3", type="image.generate", params={"model": "flux-schnell"}),
        ],
        edges=[
            WorkflowEdgeInstance(id="e1", source="n1", source_handle="text", target="n2", target_handle="prompt"),
            WorkflowEdgeInstance(id="e2", source="n2", source_handle="result", target="n3", target_handle="prompt"),
        ],
    )
    resolver = DAGResolver(graph)
    sorted_nodes = resolver.topological_sort()
    assert [n.id for n in sorted_nodes] == ["n1", "n2", "n3"]


def test_cycle_detection():
    # Circular dependency: n1 -> n2 -> n1
    graph = WorkflowGraph(
        nodes=[
            WorkflowNodeInstance(id="n1", type="input.text"),
            WorkflowNodeInstance(id="n2", type="text.llm"),
        ],
        edges=[
            WorkflowEdgeInstance(id="e1", source="n1", source_handle="text", target="n2", target_handle="prompt"),
            WorkflowEdgeInstance(id="e2", source="n2", source_handle="result", target="n1", target_handle="prompt"),
        ],
    )
    resolver = DAGResolver(graph)
    with pytest.raises(CyclicDependencyError):
        resolver.topological_sort()


def test_single_node_ancestor_resolution():
    # n1 -> n2, n3 is disconnected
    graph = WorkflowGraph(
        nodes=[
            WorkflowNodeInstance(id="n1", type="input.text"),
            WorkflowNodeInstance(id="n2", type="text.llm"),
            WorkflowNodeInstance(id="n3", type="image.generate"),
        ],
        edges=[
            WorkflowEdgeInstance(id="e1", source="n1", source_handle="text", target="n2", target_handle="prompt"),
        ],
    )
    resolver = DAGResolver(graph)
    # Target only n2 -> should return [n1, n2], ignoring n3
    target_nodes = resolver.topological_sort(target_node_id="n2")
    assert [n.id for n in target_nodes] == ["n1", "n2"]


def test_deterministic_hashing():
    h1 = compute_node_hash("image.generate", {"steps": 4, "aspect_ratio": "1:1"}, ["parent_hash_a"])
    # Same parameters in different dict order must yield identical hash
    h2 = compute_node_hash("image.generate", {"aspect_ratio": "1:1", "steps": 4}, ["parent_hash_a"])
    assert h1 == h2

    # Modified parameter must yield different hash
    h3 = compute_node_hash("image.generate", {"steps": 5, "aspect_ratio": "1:1"}, ["parent_hash_a"])
    assert h1 != h3


def test_semantic_node_hash_provider_identity():
    from app.core.cache import compute_semantic_node_hash
    from app.runners.creative_runner import compute_creative_cache_hash
    from app.schemas.creative import CreativeActionRequest, CreativeActionType

    bindings = [("prompt", "upstream_hash_1", "text")]
    base_params = {"model": "flux-schnell", "steps": 4}

    # Different provider_id must yield different hash (Invariant #5)
    h_fal = compute_semantic_node_hash("image.generate", base_params, bindings, provider_id="fal_ai")
    h_sf = compute_semantic_node_hash("image.generate", base_params, bindings, provider_id="siliconflow")
    assert h_fal != h_sf

    # Creative cache hash must also differentiate between providers
    req1 = CreativeActionRequest(
        action=CreativeActionType.TXT2IMG,
        prompt="neon cat",
        model="flux-schnell",
        engine_id="fal_ai",
        seed=42,
    )
    req2 = CreativeActionRequest(
        action=CreativeActionType.TXT2IMG,
        prompt="neon cat",
        model="flux-schnell",
        engine_id="siliconflow",
        seed=42,
    )
    assert compute_creative_cache_hash(req1, connection_id="comfyui-managed") != compute_creative_cache_hash(req2, connection_id="comfyui-managed")


def test_workflow_plan_endpoint():
    cache_store.clear()
    graph = {
        "nodes": [
            {"id": "n1", "type": "input.text", "params": {"value": "cyberpunk city"}},
            {"id": "n2", "type": "image.generate", "params": {"model": "flux-schnell"}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "source_handle": "text", "target": "n2", "target_handle": "prompt"}
        ],
    }

    # 1. First run -> neither is cached
    res = client.post("/api/v1/workflow/plan", json=graph)
    assert res.status_code == 200
    plan = res.json()
    assert plan["total_nodes"] == 2
    assert plan["cached_nodes_count"] == 0
    assert not plan["steps"][0]["is_cached"]

    # 2. Simulate caching the first node output
    first_node_hash = plan["steps"][0]["node_hash"]
    cache_store.set(first_node_hash, {"text": "cyberpunk city"})

    # 3. Second run -> first node should be cached
    res2 = client.post("/api/v1/workflow/plan", json=graph)
    assert res2.status_code == 200
    plan2 = res2.json()
    assert plan2["cached_nodes_count"] == 1
    assert plan2["steps"][0]["is_cached"] is True
    assert plan2["steps"][1]["is_cached"] is False


@pytest.mark.asyncio
async def test_cache_sqlite_error_logging(caplog):
    """Verify exceptions during SQLite operations log errors instead of silent suppression."""
    from unittest.mock import AsyncMock, patch

    broken_manager = AsyncMock()
    broken_manager.get_connection = AsyncMock(side_effect=RuntimeError("SQLite connection lock failed"))

    failing_cache = CacheStore(manager=broken_manager)

    with caplog.at_level(logging.ERROR):
        # Test get_async error logging
        res = await failing_cache.get_async("dummy_hash")
        assert res is None
        assert "Cache DB get operation failed: SQLite connection lock failed" in caplog.text

        # Test set_async error logging
        await failing_cache.set_async("dummy_hash", {"out": "test"})
        assert "Cache DB set operation failed: SQLite connection lock failed" in caplog.text

        # Test clear_all_async error logging
        await failing_cache.clear_all_async()
        assert "Cache DB clear operation failed: SQLite connection lock failed" in caplog.text


def test_semantic_node_hash_preserves_non_secret_keys():
    """Verify parameters containing 'key' like chroma_key or animation_key are NOT stripped from hash."""
    from app.core.cache import compute_semantic_node_hash

    hash1 = compute_semantic_node_hash(
        node_type="image.chroma",
        params={"chroma_key": "#00FF00", "tolerance": 0.2, "api_key": "secret123"},
        input_bindings=[],
    )
    hash2 = compute_semantic_node_hash(
        node_type="image.chroma",
        params={"chroma_key": "#0000FF", "tolerance": 0.2, "api_key": "secret123"},
        input_bindings=[],
    )
    # Different chroma_key must produce different hashes (not stripped!)
    assert hash1 != hash2

    # Changing transient api_key should produce identical hashes (stripped)
    hash3 = compute_semantic_node_hash(
        node_type="image.chroma",
        params={"chroma_key": "#00FF00", "tolerance": 0.2, "api_key": "different_secret"},
        input_bindings=[],
    )
    assert hash1 == hash3


@pytest.mark.asyncio
async def test_cache_invalidates_missing_output_assets(tmp_path):
    """Verify that a cache hit requires output assets to exist, invalidating broken entries if missing (fixes #111)."""
    from app.storage.db import DatabaseManager
    from app.storage.asset_store import AssetStore

    db_path = tmp_path / "test_cache.db"
    db_mgr = DatabaseManager(db_path=db_path)
    asset_mgr = AssetStore(manager=db_mgr, base_dir=tmp_path)
    test_cache = CacheStore(manager=db_mgr, asset_store=asset_mgr)

    # 1. Save dummy asset
    asset = await asset_mgr.save_bytes(b"image_content_12345", "test.png", media_type="image")
    asset_file = asset_mgr.get_absolute_path(asset)
    assert asset_file.is_file()

    dummy_hash = "hash_with_asset_output_123"
    output_payload = {
        "asset_id": asset.id,
        "image_url": f"/api/v1/assets/{asset.id}/content",
        "width": 512,
        "height": 512,
    }

    # Store in cache
    await test_cache.set_async(dummy_hash, output_payload)

    # Cache hit while file exists
    cached = await test_cache.get_async(dummy_hash)
    assert cached is not None
    assert cached["asset_id"] == asset.id

    # 2. Delete physical asset file
    asset_file.unlink()
    assert not asset_file.exists()

    # 3. Next get_async should detect missing output, invalidate cache, and return None
    cached_after_delete = await test_cache.get_async(dummy_hash)
    assert cached_after_delete is None

    # Check that cache is now cleared from SQLite as well
    conn = await db_mgr.get_connection()
    async with conn.execute("SELECT output_json FROM cache_entries WHERE node_hash = ?", (dummy_hash,)) as cur:
        row = await cur.fetchone()
        assert row is None


@pytest.mark.asyncio
async def test_cache_startup_reconciliation_purges_orphans(tmp_path):
    """Verify that startup reconciliation scans and purges orphan cache entries whose assets are gone."""
    from app.storage.db import DatabaseManager
    from app.storage.asset_store import AssetStore

    db_path = tmp_path / "test_reconcile.db"
    db_mgr = DatabaseManager(db_path=db_path)
    asset_mgr = AssetStore(manager=db_mgr, base_dir=tmp_path)
    test_cache = CacheStore(manager=db_mgr, asset_store=asset_mgr)

    # 1. Create two assets and cache entries
    asset1 = await asset_mgr.save_bytes(b"content1", "asset1.png", media_type="image")
    asset2 = await asset_mgr.save_bytes(b"content2", "asset2.png", media_type="image")

    await test_cache.set_async("hash1", {"asset_id": asset1.id, "image_url": f"/api/v1/assets/{asset1.id}/content"})
    await test_cache.set_async("hash2", {"asset_id": asset2.id, "image_url": f"/api/v1/assets/{asset2.id}/content"})

    # 2. Delete file for asset2
    asset_mgr.get_absolute_path(asset2).unlink()

    # Clear memory cache so reconciliation tests SQLite scan
    test_cache.clear()

    # 3. Run reconciliation
    purged = await test_cache.reconcile_orphan_references_async()
    assert purged == 1

    # hash1 remains, hash2 is gone
    assert await test_cache.get_async("hash1") is not None
    assert await test_cache.get_async("hash2") is None

