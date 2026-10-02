"""Unit tests for DAG topological sorting, cycle detection, and dirty-check caching."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.dag import DAGResolver, CyclicDependencyError
from app.core.cache import compute_node_hash, cache_store
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
