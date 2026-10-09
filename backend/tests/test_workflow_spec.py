"""Planning uses actual output content and valid persistent execution results."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.cache import CacheStore
from app.core.workflow_runs import WorkflowEventSink
from app.core.workflow_spec import resolve_workflow_node
from app.main import _execute_workflow_request, generate_plan
from app.runners.api_runner import NODE_RUNNERS
from app.schemas.task import RunRecord, WorkflowRunRequest
from app.schemas.workflow import WorkflowGraph
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore


@pytest.mark.asyncio
async def test_plan_matches_execution_after_persistent_cache_reopen(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "cache.db")
    cache = CacheStore(manager)
    store = TaskStore(manager)
    graph = WorkflowGraph(nodes=[{"id": "text", "type": "input.text", "params": {"value": "same content"}},
                                 {"id": "preview", "type": "output.preview"}],
                          edges=[{"id": "edge", "source": "text", "source_handle": "text", "target": "preview", "target_handle": "media"}])
    request = WorkflowRunRequest(run_id="fixture-run", graph=graph)
    try:
        await store.create_run(RunRecord(id=request.run_id))
        sink = WorkflowEventSink(request, store, asyncio.Event(), asyncio.Event())
        await sink.initialize()
        with patch("app.main.cache_store", cache), patch("app.core.workflow_spec.cache_store", cache):
            before = await generate_plan(graph)
            assert before.cached_nodes_count == 0
            await _execute_workflow_request(request, sink)
            cache.clear()
            await manager.close()
            after = await generate_plan(graph)
            assert after.cached_nodes_count == 2
            assert [step.node_hash for step in before.steps] == [step.node_hash for step in after.steps]
            graph.nodes[0].id = "renamed"
            graph.edges[0].source = "renamed"
            assert (await generate_plan(graph)).cached_nodes_count == 2
            graph.nodes[0].params["value"] = "changed content"
            assert (await generate_plan(graph)).cached_nodes_count == 0
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_unknown_upstream_output_is_not_a_proxy_cache_hit() -> None:
    graph = WorkflowGraph(nodes=[{"id": "llm", "type": "text.llm"}, {"id": "preview", "type": "output.preview"}],
                          edges=[{"id": "edge", "source": "llm", "source_handle": "result", "target": "preview", "target_handle": "media"}])
    spec = await resolve_workflow_node(graph.nodes[1], graph, {}, NODE_RUNNERS["output.preview"])
    assert spec.node_hash is None
    assert spec.cached_output is None
    assert "not yet known" in spec.cache_reason


@pytest.mark.asyncio
async def test_model_replacement_changes_identity_with_same_filename_and_size(tmp_path: Path) -> None:
    model = tmp_path / "model.safetensors"
    model.write_bytes(b"first model")
    graph = WorkflowGraph(nodes=[{"id": "local", "type": "image.comfy.txt2img", "params": {"checkpoint": model.name}}])
    with patch("app.core.workflow_spec.model_store.scan_all_roots_async", new_callable=AsyncMock, return_value=[SimpleNamespace(file_path=str(model))]), patch(
        "app.core.workflow_spec.cache_store.get_async", new=AsyncMock(return_value=None)
    ):
        first = await resolve_workflow_node(graph.nodes[0], graph, {}, NODE_RUNNERS["image.comfy.txt2img"])
        model.write_bytes(b"other model")
        changed = await resolve_workflow_node(graph.nodes[0], graph, {}, NODE_RUNNERS["image.comfy.txt2img"])
    assert first.node_hash != changed.node_hash


@pytest.mark.asyncio
async def test_effective_endpoint_defaults_and_runner_revision_participate(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "cache.db")
    cache = CacheStore(manager)
    graph = WorkflowGraph(nodes=[{"id": "llm", "type": "text.llm", "params": {"model": "gpt-4o"}}])
    node = graph.nodes[0]
    try:
        with patch("app.core.workflow_spec.cache_store", cache), patch.dict("os.environ", {"OPENAI_API_BASE": "https://one.test", "OPENAI_API_KEY": "fixture-key", "LLM_API_KEY": ""}):
            first = await resolve_workflow_node(node, graph, {}, NODE_RUNNERS[node.type])
            assert first.params["temperature"] == 0.7
            assert first.params["base_url"] == "https://one.test"
            assert first.params["api_key"] == "fixture-key"
            node.params["temperature"] = 0.7
            assert (await resolve_workflow_node(node, graph, {}, NODE_RUNNERS[node.type])).node_hash == first.node_hash
            runner_file = tmp_path / "runner.py"
            runner_file.write_text("first implementation")
            with patch("app.core.workflow_spec.inspect.getsourcefile", return_value=str(runner_file)):
                original = await resolve_workflow_node(node, graph, {}, NODE_RUNNERS[node.type])
                runner_file.write_text("changed implementation")
                assert (await resolve_workflow_node(node, graph, {}, NODE_RUNNERS[node.type])).node_hash != original.node_hash
        with patch("app.core.workflow_spec.cache_store", cache), patch.dict("os.environ", {"OPENAI_API_BASE": "https://two.test"}):
            assert (await resolve_workflow_node(node, graph, {}, NODE_RUNNERS[node.type])).node_hash != first.node_hash
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_cached_output_with_wrong_declared_type_is_not_reused(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "cache.db")
    cache = CacheStore(manager)
    graph = WorkflowGraph(nodes=[{"id": "text", "type": "input.text", "params": {"value": "text"}}])
    try:
        with patch("app.core.workflow_spec.cache_store", cache):
            spec = await resolve_workflow_node(graph.nodes[0], graph, {}, NODE_RUNNERS["input.text"])
            await cache.set_async(spec.node_hash, {"text": 42})
            spec = await resolve_workflow_node(graph.nodes[0], graph, {}, NODE_RUNNERS["input.text"])
            assert spec.cached_output is None
            assert await cache.get_async(spec.node_hash) is None
    finally:
        await manager.close()
