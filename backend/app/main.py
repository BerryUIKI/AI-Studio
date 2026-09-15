"""FastAPI application entrypoint for AI-Workflow."""

import json
import time
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.cache import cache_store, compute_node_hash
from app.core.dag import CyclicDependencyError, DAGResolver
from app.nodes.registry import registry
from app.runners.api_runner import NODE_RUNNERS, run_input_text_node
from app.runners.comfy_runner import comfy_client, run_comfy_txt2img_node
from app.runtime.supervisor import supervisor

# Register ComfyUI node runners
NODE_RUNNERS["image.comfy.txt2img"] = run_comfy_txt2img_node
from app.schemas.events import (
    GraphFinishedEvent,
    GraphStartedEvent,
    NodeOutputEvent,
    NodeStatusEvent,
)
from app.schemas.node import NodeDefinition
from app.schemas.workflow import ExecutionPlan, PlannedNodeStep, WorkflowGraph

# Import builtin nodes to trigger auto-registration
import app.nodes.builtin  # noqa: F401

app = FastAPI(
    title="AI-Workflow Engine API",
    description="Lightweight, API-first execution engine for multimodal workflows",
    version="0.1.0",
)

# Enable CORS for local web canvas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for liveness probes."""
    return {"status": "ok", "service": "ai-workflow-backend"}


@app.get("/api/v1/info")
async def system_info() -> dict[str, object]:
    installed = supervisor.is_installed()
    return {
        "name": "AI-Workflow",
        "version": "0.1.0",
        "runners": {
            "api": {"status": "ready", "type": "cloud"},
            "comfyui": {"status": "optional", "installed": installed, "connected": False},
        },
        "cache": {"items_cached": cache_store.size()},
    }


@app.get("/api/v1/comfy/status")
async def comfy_status() -> dict[str, Any]:
    """Check connectivity and hardware stats of the local ComfyUI instance."""
    return await comfy_client.check_status()


@app.get("/api/v1/comfy/models")
async def comfy_models() -> dict[str, List[str]]:
    """Retrieve available checkpoints and LoRA models from ComfyUI."""
    return await comfy_client.get_models()


@app.get("/api/v1/runtime/status")
async def runtime_status() -> dict[str, Any]:
    """Check the status of the sandboxed ComfyUI runtime and process supervisor."""
    return supervisor.get_status()


@app.post("/api/v1/runtime/start")
async def runtime_start() -> dict[str, Any]:
    """Launch the isolated ComfyUI subprocess via supervisor."""
    return supervisor.start()


@app.post("/api/v1/runtime/stop")
async def runtime_stop() -> dict[str, Any]:
    """Stop the isolated ComfyUI subprocess via supervisor."""
    return supervisor.stop()


@app.get("/api/v1/nodes", response_model=List[NodeDefinition])
async def list_nodes() -> List[NodeDefinition]:
    """Retrieve all registered node specifications."""
    return registry.list_all()


@app.post("/api/v1/workflow/plan", response_model=ExecutionPlan)
async def generate_plan(graph: WorkflowGraph, target_node: str | None = None) -> ExecutionPlan:
    """Analyze workflow graph, validate DAG cycles, and compute dirty-check cache hashes."""
    try:
        resolver = DAGResolver(graph)
        sorted_nodes = resolver.topological_sort(target_node_id=target_node)
    except CyclicDependencyError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))

    steps: List[PlannedNodeStep] = []
    node_hashes: dict[str, str] = {}
    cached_count = 0

    for node in sorted_nodes:
        parents = resolver.get_parent_ids(node.id)
        parent_hashes = [node_hashes[pid] for pid in parents if pid in node_hashes]

        h = compute_node_hash(node.type, node.params, parent_hashes)
        node_hashes[node.id] = h
        is_cached = cache_store.has(h)
        if is_cached:
            cached_count += 1

        steps.append(
            PlannedNodeStep(
                node_id=node.id,
                node_type=node.type,
                node_hash=h,
                is_cached=is_cached,
                dependencies=parents,
            )
        )

    return ExecutionPlan(
        steps=steps,
        total_nodes=len(steps),
        cached_nodes_count=cached_count,
    )


@app.websocket("/ws/workflow/run")
async def websocket_run_workflow(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time workflow execution.

    Accepts a WorkflowGraph JSON payload, resolves DAG order, applies cache,
    and streams NodeStatusEvent / NodeOutputEvent / GraphFinishedEvent back
    to the canvas for live status badge updates.
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        graph = WorkflowGraph.model_validate_json(raw)
    except Exception as e:
        await websocket.send_text(json.dumps({"type": "ERROR", "message": f"Invalid graph payload: {e}"}))
        await websocket.close()
        return

    try:
        resolver = DAGResolver(graph)
        sorted_nodes = resolver.topological_sort()
    except CyclicDependencyError as e:
        await websocket.send_text(json.dumps({"type": "ERROR", "message": str(e)}))
        await websocket.close()
        return

    # Compute execution plan with cache
    node_hashes: Dict[str, str] = {}
    node_outputs: Dict[str, Dict[str, Any]] = {}
    cached_count = 0

    for node in sorted_nodes:
        parents = resolver.get_parent_ids(node.id)
        parent_hashes = [node_hashes[pid] for pid in parents if pid in node_hashes]
        h = compute_node_hash(node.type, node.params, parent_hashes)
        node_hashes[node.id] = h
        if cache_store.has(h):
            cached_count += 1

    start_time = time.monotonic()
    await websocket.send_text(
        GraphStartedEvent(total_nodes=len(sorted_nodes), cached_nodes=cached_count).model_dump_json()
    )

    for node in sorted_nodes:
        node_hash = node_hashes[node.id]

        # Serve from cache if available
        if cache_store.has(node_hash):
            cached_output = cache_store.get(node_hash)
            await websocket.send_text(NodeStatusEvent(node_id=node.id, status="cached").model_dump_json())
            await websocket.send_text(NodeOutputEvent(node_id=node.id, output=cached_output or {}).model_dump_json())
            node_outputs[node.id] = cached_output or {}
            continue

        # Resolve inputs from upstream node outputs
        inputs: Dict[str, Any] = {}
        for edge in graph.edges:
            if edge.target == node.id and edge.source in node_outputs:
                source_output = node_outputs[edge.source]
                if edge.source_handle in source_output:
                    inputs[edge.target_handle] = source_output[edge.source_handle]

        # Dispatch to appropriate runner
        runner = NODE_RUNNERS.get(node.type)
        if runner is None:
            await websocket.send_text(
                json.dumps({"type": "NODE_ERROR", "node_id": node.id, "message": f"No runner for node type: {node.type}"})
            )
            continue

        output: Dict[str, Any] = {}
        try:
            # input.text has a different signature (no inputs dict)
            if node.type == "input.text":
                async for event in run_input_text_node(node.id, node.params):
                    await websocket.send_text(event.model_dump_json())
                    if isinstance(event, NodeOutputEvent):
                        output = event.output
            else:
                async for event in runner(node.id, inputs, node.params):
                    await websocket.send_text(event.model_dump_json())
                    if isinstance(event, NodeOutputEvent):
                        output = event.output
        except Exception as e:
            await websocket.send_text(
                json.dumps({"type": "NODE_ERROR", "node_id": node.id, "message": str(e)})
            )
            continue

        # Cache the result for future runs
        if output:
            cache_store.set(node_hash, output)
            node_outputs[node.id] = output

    elapsed_ms = (time.monotonic() - start_time) * 1000
    await websocket.send_text(GraphFinishedEvent(execution_time_ms=elapsed_ms).model_dump_json())

    try:
        await websocket.close()
    except Exception:
        pass
