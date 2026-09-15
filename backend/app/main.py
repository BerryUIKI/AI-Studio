"""FastAPI application entrypoint for AI-Workflow."""

from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.core.dag import DAGResolver, CyclicDependencyError
from app.core.cache import compute_node_hash, cache_store
from app.nodes.registry import registry
from app.schemas.node import NodeDefinition
from app.schemas.workflow import WorkflowGraph, ExecutionPlan, PlannedNodeStep

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
    """System info endpoint reporting capabilities and supported runners."""
    return {
        "name": "AI-Workflow",
        "version": "0.1.0",
        "runners": {
            "api": {"status": "ready", "type": "cloud"},
            "comfyui": {"status": "optional", "installed": False, "connected": False},
        },
        "cache": {"items_cached": cache_store.size()},
    }


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
