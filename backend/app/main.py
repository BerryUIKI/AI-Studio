"""FastAPI application entrypoint for Berry AI Studio."""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.cache import (
    cache_store,
    compute_content_hash,
    compute_node_hash,
    compute_semantic_node_hash,
)
from app.core.dag import CyclicDependencyError, DAGResolver
from app.nodes.registry import registry
from app.runners.api_runner import NODE_RUNNERS, run_input_text_node
from app.runners.comfy_runner import comfy_client, run_comfy_txt2img_node
from app.runners.creative_runner import creative_runner
from app.runtime.supervisor import supervisor
from app.runtime.webui_supervisor import webui_supervisor
from app.runtime.engine_manager import engine_manager
from app.runtime.hardware import check_hardware_readiness
from app.runtime.installer import installer
from app.runtime.credentials import credentials_manager
from app.storage.model_store import model_store
from app.schemas.creative import CreativeActionRequest, CreativeActionResult
from app.schemas.cloud import (
    CloudProviderId,
    CloudProviderInfo,
    SetCredentialRequest,
    TestKeyRequest,
    TestKeyResult,
)
from app.schemas.engine import (
    EngineConnection,
    EngineConnectRequest,
    EngineInstallManifest,
    EngineType,
)
from app.schemas.hardware import HardwareReadiness
from app.schemas.model import ModelRecord, ModelRoot
from app.schemas.events import (
    GraphFinishedEvent,
    GraphStartedEvent,
    NodeErrorEvent,
    NodeOutputEvent,
    NodeStatusEvent,
    RunCancelledEvent,
)
from app.schemas.node import NodeDefinition
from app.schemas.project import Project, ProjectCreate, ProjectUpdate, AssetRecord
from app.schemas.task import WorkflowRunRequest
from app.schemas.workflow import ExecutionPlan, PlannedNodeStep, WorkflowGraph
from app.storage.asset_store import asset_store
from app.storage.db import db_manager
from app.storage.project_store import project_store

# Register ComfyUI node runners
NODE_RUNNERS["image.comfy.txt2img"] = run_comfy_txt2img_node

# Import builtin nodes to trigger auto-registration
import app.nodes.builtin  # noqa: F401

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Berry AI Studio Engine API",
    description="Lightweight, API-first creative engine with persistent projects and deterministic caching",
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

# Active run cancellation tracker: run_id -> asyncio.Event
active_cancellations: Dict[str, asyncio.Event] = {}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for liveness probes."""
    return {"status": "ok", "service": "ai-workflow-backend"}


@app.get("/api/v1/info")
async def system_info() -> dict[str, object]:
    installed = supervisor.is_installed()
    return {
        "name": "Berry AI Studio",
        "version": "0.1.0",
        "runners": {
            "api": {"status": "ready", "type": "cloud"},
            "comfyui": {"status": "optional", "installed": installed, "connected": False},
        },
        "cache": {"items_cached": cache_store.size()},
    }


# ---------------------------------------------------------------------------
# Engine & Supervisor Endpoints
# ---------------------------------------------------------------------------

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


@app.get("/api/v1/runtime/webui/status")
async def runtime_webui_status() -> dict[str, Any]:
    """Check the status of the sandboxed WebUI runtime and supervisor."""
    return webui_supervisor.get_status()


@app.post("/api/v1/runtime/webui/start")
async def runtime_webui_start() -> dict[str, Any]:
    """Launch the isolated WebUI subprocess via supervisor."""
    return webui_supervisor.start()


@app.post("/api/v1/runtime/webui/stop")
async def runtime_webui_stop() -> dict[str, Any]:
    """Stop the isolated WebUI subprocess via supervisor."""
    return webui_supervisor.stop()


@app.get("/api/v1/runtime/{engine_type}/manifest", response_model=EngineInstallManifest)
async def get_engine_manifest(engine_type: EngineType) -> EngineInstallManifest:
    """Retrieve the installation manifest for an isolated engine."""
    return installer.read_manifest(engine_type)


@app.post("/api/v1/runtime/{engine_type}/install", response_model=EngineInstallManifest)
async def trigger_engine_install(engine_type: EngineType) -> EngineInstallManifest:
    """Start or check isolated installation of an engine without host pollution."""
    # Spawn in background task to avoid blocking HTTP call
    asyncio.create_task(installer.install_engine(engine_type))
    return installer.read_manifest(engine_type)


# ---------------------------------------------------------------------------
# Hardware & Engine Management Endpoints (M2)
# ---------------------------------------------------------------------------

@app.get("/api/v1/hardware/readiness", response_model=HardwareReadiness)
async def get_hardware_readiness() -> HardwareReadiness:
    """Diagnose GPU VRAM, drivers, and filesystem storage readiness for local inference."""
    return await check_hardware_readiness()


@app.get("/api/v1/engines", response_model=List[EngineConnection])
async def list_engines() -> List[EngineConnection]:
    """List all available managed and external engine connections."""
    return engine_manager.list_engines()


@app.post("/api/v1/engines/connect", response_model=EngineConnection)
async def connect_external_engine(request: EngineConnectRequest) -> EngineConnection:
    """Connect to a running user engine without process ownership."""
    return await engine_manager.connect_external_engine(
        engine_type=request.engine_type,
        endpoint_url=request.endpoint_url,
        name=request.name,
    )


@app.post("/api/v1/engines/{engine_id}/test", response_model=EngineConnection)
async def test_engine(engine_id: str) -> EngineConnection:
    """Test connectivity and readiness of a registered engine."""
    conn = await engine_manager.test_connection_by_id(engine_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Engine '{engine_id}' not found")
    return conn


# ---------------------------------------------------------------------------
# Model Catalog & Roots Endpoints (M2)
# ---------------------------------------------------------------------------

@app.get("/api/v1/models", response_model=List[ModelRecord])
async def list_models() -> List[ModelRecord]:
    """List all models currently discovered across registered roots."""
    return await model_store.scan_all_roots_async()


@app.post("/api/v1/models/scan", response_model=List[ModelRecord])
async def trigger_model_scan() -> List[ModelRecord]:
    """Force re-scan of all model root directories."""
    return await model_store.scan_all_roots_async()


@app.get("/api/v1/models/roots", response_model=List[ModelRoot])
async def list_model_roots() -> List[ModelRoot]:
    """List all configured model root directories."""
    return model_store.list_roots()


class AddModelRootRequest(BaseModel):
    path: str
    label: str
    engine_type: Optional[str] = None


@app.post("/api/v1/models/roots", response_model=ModelRoot)
async def add_model_root(req: AddModelRootRequest) -> ModelRoot:
    """Register a new user-specified directory for model discovery."""
    root_id = f"root_{abs(hash(req.path)) % 10000}"
    return model_store.add_root(root_id, req.path, req.label, req.engine_type)


# ---------------------------------------------------------------------------
# Creative Primary Canvas Endpoints (M3)
# ---------------------------------------------------------------------------

@app.post("/api/v1/creative/execute", response_model=CreativeActionResult)
async def execute_creative_action(req: CreativeActionRequest) -> CreativeActionResult:
    """Execute high-level image creation action (txt2img, img2img, inpaint, upscale)."""
    return await creative_runner.execute(req)


@app.post("/api/v1/creative/upload", response_model=AssetRecord)
async def upload_creative_asset(file: UploadFile = File(...)) -> AssetRecord:
    """Upload user image asset directly onto the creative canvas."""
    data = await file.read()
    filename = file.filename or "uploaded_image.png"
    content_type = file.content_type or "image/png"
    return await asset_store.save_bytes(data, filename=filename, media_type=content_type)


# ---------------------------------------------------------------------------
# Cloud Providers & BYOK Credentials Endpoints (M4)
# ---------------------------------------------------------------------------

@app.get("/api/v1/cloud/providers", response_model=List[CloudProviderInfo])
async def list_cloud_providers() -> List[CloudProviderInfo]:
    """List available BYOK cloud providers with redacted secrets and capabilities."""
    return credentials_manager.list_providers()


@app.post("/api/v1/cloud/credentials", response_model=CloudProviderInfo)
async def set_cloud_credential(req: SetCredentialRequest) -> CloudProviderInfo:
    """Store or update a BYOK cloud API key locally without exposure."""
    credentials_manager.set_key(req.provider_id, req.api_key)
    providers = credentials_manager.list_providers()
    target = next((p for p in providers if p.id == req.provider_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Provider not found")
    return target


@app.post("/api/v1/cloud/credentials/test", response_model=TestKeyResult)
async def test_cloud_credential(req: TestKeyRequest) -> TestKeyResult:
    """Validate a BYOK API key against the external provider endpoint."""
    return await credentials_manager.test_key(req.provider_id, req.api_key)


@app.delete("/api/v1/cloud/credentials/{provider_id}")
async def delete_cloud_credential(provider_id: CloudProviderId) -> dict[str, bool]:
    """Delete a stored BYOK API key."""
    credentials_manager.delete_key(provider_id)
    return {"success": True}


@app.get("/api/v1/nodes", response_model=List[NodeDefinition])
async def list_nodes() -> List[NodeDefinition]:
    """Retrieve all registered node specifications."""
    return registry.list_all()


# ---------------------------------------------------------------------------
# Project & Asset REST Endpoints (M1 Persistence)
# ---------------------------------------------------------------------------

@app.get("/api/v1/projects", response_model=List[Project])
async def list_projects() -> List[Project]:
    return await project_store.list_projects()


@app.post("/api/v1/projects", response_model=Project)
async def create_project(data: ProjectCreate) -> Project:
    return await project_store.create_project(data)


@app.get("/api/v1/projects/{project_id}", response_model=Project)
async def get_project(project_id: str) -> Project:
    proj = await project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@app.put("/api/v1/projects/{project_id}", response_model=Project)
async def update_project(project_id: str, data: ProjectUpdate) -> Project:
    proj = await project_store.update_project(project_id, data)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@app.delete("/api/v1/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, bool]:
    success = await project_store.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True}


@app.get("/api/v1/assets", response_model=List[AssetRecord])
async def list_assets(project_id: Optional[str] = None) -> List[AssetRecord]:
    return await asset_store.list_assets(project_id=project_id)


@app.get("/api/v1/assets/{asset_id}", response_model=AssetRecord)
async def get_asset(asset_id: str) -> AssetRecord:
    rec = await asset_store.get_asset(asset_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Asset not found")
    return rec


@app.get("/api/v1/assets/{asset_id}/content")
async def get_asset_content(asset_id: str) -> FileResponse:
    rec = await asset_store.get_asset(asset_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Asset not found")
    abs_path = asset_store.get_absolute_path(rec)
    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Asset file missing on disk")
    return FileResponse(abs_path, media_type="image/png")


@app.post("/api/v1/workflow/cancel/{run_id}")
async def cancel_workflow_run(run_id: str) -> dict[str, Any]:
    if run_id in active_cancellations:
        active_cancellations[run_id].set()
        return {"success": True, "run_id": run_id, "status": "cancel-requested"}
    return {"success": False, "message": f"Run '{run_id}' not found or already completed"}


# ---------------------------------------------------------------------------
# Workflow Planning & Execution
# ---------------------------------------------------------------------------

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
        # Build deterministic port bindings from upstream edges
        bindings: List[tuple[str, str, str]] = []
        parents = resolver.get_parent_ids(node.id)
        parent_hashes = [node_hashes[pid] for pid in parents if pid in node_hashes]

        for edge in graph.edges:
            if edge.target == node.id and edge.source in node_hashes:
                # Use source computation hash as upstream content proxy for planning
                bindings.append((edge.target_handle, node_hashes[edge.source], edge.source_handle))

        # Support both port-aware semantic hash and legacy hash
        if bindings:
            h = compute_semantic_node_hash(node.type, node.params, bindings)
        else:
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
    WebSocket endpoint for real-time workflow execution with:
    - Targeted single-node execution
    - Port-aware semantic caching
    - Strict failure boundaries (aborts dependent child nodes)
    - Run cancellation support
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        parsed = json.loads(raw)
        # Parse either WorkflowRunRequest or raw WorkflowGraph
        if "graph" in parsed:
            run_request = WorkflowRunRequest.model_validate(parsed)
            graph = run_request.graph
            target_node = run_request.target_node_id
            run_id = run_request.run_id or str(uuid.uuid4())
        else:
            graph = WorkflowGraph.model_validate(parsed)
            target_node = None
            run_id = str(uuid.uuid4())
    except Exception as e:
        await websocket.send_text(json.dumps({"type": "ERROR", "message": f"Invalid graph payload: {e}"}))
        await websocket.close()
        return

    # Register cancellation token
    cancel_event = asyncio.Event()
    active_cancellations[run_id] = cancel_event

    try:
        resolver = DAGResolver(graph)
        sorted_nodes = resolver.topological_sort(target_node_id=target_node)
    except CyclicDependencyError as e:
        await websocket.send_text(json.dumps({"type": "ERROR", "message": str(e), "run_id": run_id}))
        await websocket.close()
        active_cancellations.pop(run_id, None)
        return
    except ValueError as e:
        await websocket.send_text(json.dumps({"type": "ERROR", "message": str(e), "run_id": run_id}))
        await websocket.close()
        active_cancellations.pop(run_id, None)
        return

    # Check cache status for active nodes
    cached_count = 0
    node_outputs: Dict[str, Dict[str, Any]] = {}

    start_time = time.monotonic()
    await websocket.send_text(
        GraphStartedEvent(run_id=run_id, total_nodes=len(sorted_nodes), cached_nodes=cached_count).model_dump_json()
    )

    failed_node_ids: set[str] = set()

    for node in sorted_nodes:
        # Check cancellation
        if cancel_event.is_set():
            await websocket.send_text(RunCancelledEvent(run_id=run_id).model_dump_json())
            elapsed_ms = (time.monotonic() - start_time) * 1000
            await websocket.send_text(
                GraphFinishedEvent(run_id=run_id, execution_time_ms=elapsed_ms, status="cancelled").model_dump_json()
            )
            break

        # Check if any upstream ancestor failed
        ancestors = resolver._get_ancestors(node.id)
        if any(anc in failed_node_ids for anc in ancestors):
            # Abort this node due to upstream failure
            await websocket.send_text(
                NodeStatusEvent(node_id=node.id, status="cancelled", run_id=run_id).model_dump_json()
            )
            continue

        # Resolve inputs and compute deterministic port bindings
        inputs: Dict[str, Any] = {}
        bindings: List[tuple[str, str, str]] = []

        for edge in graph.edges:
            if edge.target == node.id and edge.source in node_outputs:
                source_output = node_outputs[edge.source]
                if edge.source_handle in source_output:
                    val = source_output[edge.source_handle]
                    inputs[edge.target_handle] = val
                    bindings.append((edge.target_handle, compute_content_hash(val), edge.source_handle))

        # Compute port-aware semantic hash
        if bindings:
            node_hash = compute_semantic_node_hash(node.type, node.params, bindings)
        else:
            node_hash = compute_node_hash(node.type, node.params, [])

        # Check cache (memory or SQLite)
        cached_output = await cache_store.get_async(node_hash)
        if cached_output is not None:
            await websocket.send_text(NodeStatusEvent(node_id=node.id, status="cached", run_id=run_id).model_dump_json())
            await websocket.send_text(
                NodeOutputEvent(node_id=node.id, output=cached_output, run_id=run_id).model_dump_json()
            )
            node_outputs[node.id] = cached_output
            continue

        # Dispatch to runner
        runner = NODE_RUNNERS.get(node.type)
        if runner is None:
            failed_node_ids.add(node.id)
            err_msg = f"No runner for node type: {node.type}"
            await websocket.send_text(NodeErrorEvent(node_id=node.id, message=err_msg, run_id=run_id).model_dump_json())
            await websocket.send_text(NodeStatusEvent(node_id=node.id, status="error", run_id=run_id).model_dump_json())
            continue

        output: Dict[str, Any] = {}
        node_has_error = False

        try:
            if node.type == "input.text":
                async for event in run_input_text_node(node.id, node.params):
                    if cancel_event.is_set():
                        break
                    event.run_id = run_id
                    await websocket.send_text(event.model_dump_json())
                    if isinstance(event, NodeOutputEvent):
                        output = event.output
            else:
                async for event in runner(node.id, inputs, node.params):
                    if cancel_event.is_set():
                        break
                    event.run_id = run_id
                    await websocket.send_text(event.model_dump_json())
                    if isinstance(event, NodeErrorEvent):
                        node_has_error = True
                    elif isinstance(event, NodeOutputEvent):
                        output = event.output
        except Exception as e:
            node_has_error = True
            await websocket.send_text(NodeErrorEvent(node_id=node.id, message=str(e), run_id=run_id).model_dump_json())
            await websocket.send_text(NodeStatusEvent(node_id=node.id, status="error", run_id=run_id).model_dump_json())

        if node_has_error:
            failed_node_ids.add(node.id)
            # Notify cancellation for all unexecuted descendants
            descendants = resolver.get_descendants(node.id)
            for desc_id in descendants:
                await websocket.send_text(
                    NodeStatusEvent(node_id=desc_id, status="cancelled", run_id=run_id).model_dump_json()
                )
            # Conclude run as failed
            elapsed_ms = (time.monotonic() - start_time) * 1000
            await websocket.send_text(
                GraphFinishedEvent(run_id=run_id, execution_time_ms=elapsed_ms, status="failed").model_dump_json()
            )
            break

        # Cache successful output
        if output:
            await cache_store.set_async(node_hash, output)
            node_outputs[node.id] = output

    else:
        # Loop completed without break
        elapsed_ms = (time.monotonic() - start_time) * 1000
        await websocket.send_text(
            GraphFinishedEvent(run_id=run_id, execution_time_ms=elapsed_ms, status="completed").model_dump_json()
        )

    active_cancellations.pop(run_id, None)

    try:
        await websocket.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Static Frontend Single-App Serving (Production/Release Mode)
# ---------------------------------------------------------------------------

frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
