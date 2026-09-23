"""FastAPI application entrypoint for Berry AI Studio."""

import asyncio
import json
import logging
import time
import uuid
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
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
    EngineOwnership,
    EngineType,
    EngineUpdateManifest,
    LauncherConfig,
    ManagerStatusResponse,
    ShutdownRequest,
    ShutdownResponse,
)
from app.schemas.hardware import HardwareReadiness
from app.schemas.model import ModelRecord, ModelRoot, ModelRootCreate
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


app_start_time = time.time()
launcher_config = LauncherConfig()


# ---------------------------------------------------------------------------
# Launcher & Environment Manager Endpoints (L01-L12)
# ---------------------------------------------------------------------------

@app.get("/api/v1/manager/status", response_model=ManagerStatusResponse)
async def manager_status() -> ManagerStatusResponse:
    """Return unified environment and process status for Berry, engines, and models."""
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    frontend_packaged = (frontend_dir / "index.html").is_file()

    managed_comfy = engine_manager.get_engine("managed_comfyui")
    managed_web = engine_manager.get_engine("managed_webui")
    external_list = [e for e in engine_manager.list_engines() if e.ownership == EngineOwnership.EXTERNAL]

    configured_clouds = sum(1 for p in credentials_manager.list_providers() if p.is_configured)
    models_count = len(model_store.list_models())

    return ManagerStatusResponse(
        app_name="Berry AI Studio",
        version="0.1.0",
        pid=os.getpid(),
        uptime_seconds=round(time.time() - app_start_time, 2),
        port=launcher_config.port,
        frontend_packaged=frontend_packaged,
        managed_comfyui=managed_comfy,
        managed_webui=managed_web,
        external_engines=external_list,
        cloud_providers_configured=configured_clouds,
        models_indexed=models_count,
        active_tasks=len(active_cancellations),
        launcher_config=launcher_config,
    )


@app.get("/api/v1/manager/config", response_model=LauncherConfig)
async def get_launcher_config() -> LauncherConfig:
    """Get current launcher configuration."""
    return launcher_config


@app.post("/api/v1/manager/config", response_model=LauncherConfig)
async def set_launcher_config(config: LauncherConfig) -> LauncherConfig:
    """Update launcher configuration."""
    global launcher_config
    launcher_config = config
    return launcher_config


@app.post("/api/v1/manager/shutdown", response_model=ShutdownResponse)
async def manager_shutdown(request: ShutdownRequest) -> ShutdownResponse:
    """
    Explicit controlled shutdown of Berry AI Studio (L07).
    Guards active generation tasks and predictably terminates managed engines if configured.
    Never terminates external user engines.
    """
    active_count = len(active_cancellations)
    if active_count > 0 and not request.force:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot shutdown: {active_count} active generation task(s) running. Provide force=true to abort tasks.",
        )

    # Abort active tasks if forced
    if active_count > 0:
        for run_id, cancel_evt in list(active_cancellations.items()):
            cancel_evt.set()

    # Determine whether to stop managed engines
    stop_managed = request.stop_managed_engines
    if stop_managed is None:
        stop_managed = launcher_config.stop_managed_engines_on_exit

    stopped_engines = []
    if stop_managed:
        if supervisor.is_running():
            supervisor.stop()
            stopped_engines.append("managed_comfyui")
        if webui_supervisor.is_running():
            webui_supervisor.stop()
            stopped_engines.append("managed_webui")

    # Schedule self-termination
    def _delayed_exit():
        logger.info("Berry AI Studio server exiting upon manager request.")
        os._exit(0)

    try:
        loop = asyncio.get_running_loop()
        loop.call_later(0.5, _delayed_exit)
    except Exception:
        pass

    return ShutdownResponse(
        status="shutting_down",
        message="Berry AI Studio shutdown initiated.",
        active_tasks_cancelled=active_count,
        managed_engines_stopped=stopped_engines,
    )



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


@app.get("/api/v1/runtime/{engine_type}/update/manifest", response_model=EngineUpdateManifest)
async def get_engine_update_manifest(engine_type: EngineType) -> EngineUpdateManifest:
    """Retrieve the update manifest and rollback state for a managed engine."""
    return installer.read_update_manifest(engine_type)


@app.post("/api/v1/runtime/{engine_type}/update", response_model=EngineUpdateManifest)
async def trigger_engine_update(engine_type: EngineType) -> EngineUpdateManifest:
    """
    Safely update a managed engine with active job checking and rollback protection (L08, L12).
    """
    has_active = len(active_cancellations) > 0
    return await installer.update_engine(engine_type, has_active_tasks_fn=lambda: has_active)


@app.get("/api/v1/updates/check")
async def check_all_updates() -> dict[str, Any]:
    """Check update availability for Berry AI Studio and managed engines separately (L08)."""
    comfy_manifest = installer.read_update_manifest(EngineType.COMFYUI)
    webui_manifest = installer.read_update_manifest(EngineType.WEBUI)

    return {
        "app": {
            "name": "Berry AI Studio",
            "current_version": "0.1.0",
            "latest_version": "0.1.0",
            "update_available": False,
            "release_notes_url": "https://github.com/BerryUIKI/AI-Studio/releases",
        },
        "engines": {
            "comfyui": {
                "installed": supervisor.is_installed(),
                "update_manifest": comfy_manifest,
            },
            "webui": {
                "installed": webui_supervisor.is_installed(),
                "update_manifest": webui_manifest,
            },
        },
    }


@app.post("/api/v1/updates/app")
async def trigger_app_update() -> dict[str, Any]:
    """
    Check and report or trigger Berry application updates (L08).
    Decoupled from inference engine updates.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    is_git_repo = (repo_root / ".git").is_dir()

    if is_git_repo:
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "pull", "--ff-only",
                cwd=str(repo_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return {
                    "mode": "git",
                    "status": "updated",
                    "message": "Application code updated successfully. Please restart Berry AI Studio.",
                    "details": stdout.decode().strip(),
                }
            else:
                return {
                    "mode": "git",
                    "status": "failed",
                    "message": f"Git update failed: {stderr.decode().strip()}",
                }
        except Exception as e:
            return {"mode": "git", "status": "error", "message": str(e)}
    else:
        return {
            "mode": "packaged",
            "status": "guidance",
            "message": "In packaged Windows release mode, download the latest package to update.",
            "download_url": "https://github.com/BerryUIKI/AI-Studio/releases",
            "notes": "User projects, credentials, and models in %LOCALAPPDATA% are strictly preserved during updates.",
        }




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


@app.post("/api/v1/models/rescan", response_model=List[ModelRecord])
async def trigger_model_rescan() -> List[ModelRecord]:
    """Force re-scan of all model root directories."""
    return await model_store.scan_all_roots_async()


@app.delete("/api/v1/models/roots/{root_id}")
async def remove_model_root(root_id: str) -> dict[str, Any]:
    """Remove a configured model root directory without deleting files (L10)."""
    removed = model_store.remove_root(root_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Model root '{root_id}' not found")
    return {"status": "removed", "root_id": root_id}



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
if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    @app.get("/", response_class=HTMLResponse)
    async def missing_frontend_page():
        """Visible packaging error when frontend dist is missing (L02)."""
        return HTMLResponse(
            content="""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Berry AI Studio - Packaging Error</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px; max-width: 600px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }
    h1 { color: #f43f5e; margin-top: 0; font-size: 22px; display: flex; align-items: center; gap: 8px; }
    p { color: #cbd5e1; line-height: 1.6; }
    code { background: #0f172a; color: #38bdf8; padding: 3px 6px; border-radius: 4px; font-family: monospace; }
    .badge { display: inline-block; background: #ef4444; color: white; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; margin-bottom: 12px; }
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">L02 Diagnostic</span>
    <h1>⚠️ Packaging Error: Frontend Build Missing</h1>
    <p>Berry AI Studio backend is running and healthy, but the frontend distribution assets (<code>frontend/dist/index.html</code>) are missing.</p>
    <p><strong>For Developers:</strong> Run the frontend build command before launching:</p>
    <p><code>cd frontend &amp;&amp; pnpm build</code></p>
    <p><strong>Status:</strong> Backend core, REST APIs, and background engine supervisors remain accessible at <code>/health</code> and <code>/api/v1/manager/status</code>.</p>
  </div>
</body>
</html>""",
            status_code=200,
        )

