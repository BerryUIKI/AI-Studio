"""FastAPI application entrypoint for Berry AI Studio."""

import asyncio
from contextlib import asynccontextmanager
import json
import logging
import time
import uuid
import os
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
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
from app.core.agent_service import AgentService
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentExecuteProposalRequest,
    AgentProposal,
)
from app.core.workflow_validator import WorkflowValidator
from app.core.workflow_repair import WorkflowRepairer
from app.core.workflow_catalog import WorkflowCatalog
from app.schemas.workflow_analysis import (
    WorkflowValidationReport,
    WorkflowRepairResult,
)
from app.core.session import session_manager, ALLOWED_ORIGINS
from app.core.task_registry import task_registry
from app.core.workflow_runs import WorkflowEventSink, workflow_runs
from app.core.execution_contract import ExecutionContractError, validate_execution_contract
from app.core.media_validator import (
    validate_and_inspect_media,
    sanitize_filename,
    MEDIA_SECURITY_HEADERS,
)
from app.runtime.supervisor import supervisor
from app.runtime.webui_supervisor import webui_supervisor
from app.runtime.llama_server.llama_supervisor import (
    llama_server_supervisor,
    LlamaServerRuntimeStatus,
    LlamaModelInfo,
)
from app.runtime.engine_manager import engine_manager
from app.runtime.hardware import check_hardware_readiness, get_gpu_stats
from app.runtime.installer import installer, mirror_manager
from app.runtime.credentials import credentials_manager, redact_key
from app.storage.model_store import model_store
from app.schemas.creative import CreativeActionRequest, CreativeActionResult
from app.schemas.cloud import (
    CloudProviderId,
    CloudProviderInfo,
    LLMConfig,
    SetCredentialRequest,
    SetLLMConfigRequest,
    TestKeyRequest,
    TestKeyResult,
)
from app.schemas.engine import (
    EngineConfig,
    EngineConfigResponse,
    EngineConfigUpdateRequest,
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
    EngineInstanceInfo,
    EngineInstancesResponse,
    DetectedEngineInfo,
    EngineDetectResponse,
    EngineBindRequest,
    MirrorPresetInfo,
    MirrorConfigResponse,
    UpdateMirrorConfigRequest,
    EngineLogResponse,
    RuntimeStartResponse,
)
from app.schemas.hardware import HardwareReadiness, GpuStatsResponse
from app.schemas.model import ModelRecord, ModelRoot, ModelRootCreate
from app.schemas.model_hub import (
    HubCatalogResponse,
    HardwareEvaluationRequest,
    HardwareEvaluationResponse,
    StartDownloadRequest,
    DownloadTaskInfo,
    DownloadTasksResponse,
)
from app.storage.hub_catalog import HubCatalog
from app.runtime.hardware_evaluator import evaluate_hardware
from app.runtime.model_downloader import model_downloader
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
from app.schemas.task import WorkflowRunRequest, WorkflowSubscription
from app.schemas.task import TaskRecord
from app.storage.task_store import task_store
from app.schemas.workflow import ExecutionPlan, PlannedNodeStep, WorkflowGraph
from app.storage.asset_store import asset_store
from app.storage.db import db_manager
from app.storage.project_store import project_store

# Register ComfyUI node runners
NODE_RUNNERS["image.comfy.txt2img"] = run_comfy_txt2img_node

# Import builtin nodes to trigger auto-registration
import app.nodes.builtin  # noqa: F401

def setup_logging() -> None:
    """Configure centralized logging format and level."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def setup_no_proxy() -> None:
    """Ensure local loopback addresses bypass any HTTP/HTTPS proxies (such as Clash)."""
    current_no_proxy = os.environ.get("NO_PROXY", os.environ.get("no_proxy", ""))
    needed = ["localhost", "127.0.0.1", "::1", "0.0.0.0"]
    existing = [p.strip() for p in current_no_proxy.split(",") if p.strip()]
    for n in needed:
        if n not in existing:
            existing.append(n)
    merged = ",".join(existing)
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    setup_no_proxy()
    logger.info("Berry AI Studio API starting up...")
    await task_store.reconcile_interrupted()
    
    # Startup reconciliation: reconcile orphan cache entries whose assets are missing
    try:
        await cache_store.reconcile_orphan_references_async()
    except Exception as e:
        logger.warning(f"Failed to reconcile cache output references on startup: {e}")

    # Auto-start embedded llama-server if installed in isolated app engine directory
    try:
        if llama_server_supervisor.is_installed() and not llama_server_supervisor.is_running():
            models = llama_server_supervisor.list_local_models()
            if models:
                logger.info(f"Detected installed embedded llama-server, auto-starting with {models[0].name}...")
                llama_server_supervisor.start(models[0].name)
    except Exception as e:
        logger.warning(f"Failed to auto-start embedded llama-server: {e}")

    yield

    logger.info("Berry AI Studio API shutting down...")
    try:
        if llama_server_supervisor.is_running():
            logger.info("Stopping embedded llama-server process...")
            llama_server_supervisor.stop()
    except Exception as e:
        logger.debug(f"Error stopping llama-server on shutdown: {e}")


setup_logging()
setup_no_proxy()
logger = logging.getLogger("berry_ai_studio")

app = FastAPI(
    title="Berry AI Studio Engine API",
    description="Lightweight, API-first creative engine with persistent projects and deterministic caching",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for local web canvas and desktop clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_boundary_middleware(request: Request, call_next):
    origin = request.headers.get("origin")

    # 1. Reject untrusted cross-origin requests
    if origin and not session_manager.is_origin_allowed(origin):
        logger.warning(f"Blocked request from untrusted origin: {origin} to {request.url.path}")
        return JSONResponse(
            status_code=403,
            content={"detail": "Cross-origin request forbidden from untrusted origin"},
        )

    # 2. Check session token if supplied
    token = session_manager.extract_token(request)
    if token and not session_manager.is_valid_token(token):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired session token"},
        )

    response = await call_next(request)
    return response


# Active run cancellation tracker: run_id -> asyncio.Event
active_cancellations: Dict[str, asyncio.Event] = {}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for liveness probes."""
    return {"status": "ok", "service": "ai-workflow-backend"}


@app.get("/api/v1/auth/session")
async def get_session_token() -> dict[str, str]:
    """Get active session token for the current app launch."""
    return {"session_token": session_manager.get_token()}


@app.get("/api/v1/info")
async def system_info() -> dict[str, object]:
    installed = supervisor.is_installed()
    return {
        "name": "Berry AI Studio",
        "version": "0.1.0",
        "session_token": session_manager.get_token(),
        "runners": {
            "api": {"status": "ready", "type": "cloud"},
            "comfyui": {"status": "optional", "installed": installed, "connected": False},
        },
        "cache": {"items_cached": cache_store.size()},
    }


app_start_time = time.time()
launcher_config = LauncherConfig(port=int(os.environ.get("BERRY_PORT", "8000")))


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

    active_tasks_count = len(active_cancellations) + len(creative_runner.active_tasks)

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
        active_tasks=active_tasks_count,
        launcher_config=launcher_config,
    )


@app.get("/api/v1/system/info", response_model=HardwareReadiness)
async def get_system_hardware_info() -> HardwareReadiness:
    """Return hardware readiness diagnostics, GPU vendor info, and storage metrics (M8, M11)."""
    return await check_hardware_readiness()


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
    active_count = len(active_cancellations) + len(creative_runner.active_tasks)
    if active_count > 0 and not request.force:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot shutdown: {active_count} active generation task(s) running. Provide force=true to abort tasks.",
        )

    # Abort active tasks if forced
    if active_count > 0:
        for run_id, cancel_evt in list(active_cancellations.items()):
            cancel_evt.set()
        for task_id in list(creative_runner.active_tasks.keys()):
            await creative_runner.cancel_task(task_id)

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


@app.get("/api/v1/tasks/active")
async def list_active_tasks() -> Dict[str, Any]:
    """List all currently executing generation and workflow tasks (R14)."""
    tasks = []
    for run_id in active_cancellations:
        tasks.append({"id": run_id, "type": "workflow_graph", "status": "running"})
    for task_id, info in creative_runner.active_tasks.items():
        tasks.append({
            "id": task_id,
            "type": "creative_action",
            "action": info.get("action"),
            "engine": info.get("engine"),
            "status": "running",
            "start_time": info.get("start_time"),
        })
    return {"active_tasks_count": len(tasks), "tasks": tasks}


@app.post("/api/v1/tasks/{task_id}/cancel")
async def cancel_task_endpoint(task_id: str) -> Dict[str, Any]:
    """
    Cancel an active creative task (R14).
    Discloses remote cancellation limitations truthfully for cloud providers.
    """
    if task_id in creative_runner.active_tasks or task_id in creative_runner.active_cancellations:
        return await creative_runner.cancel_task(task_id)
    if task_id in active_cancellations:
        active_cancellations[task_id].set()
        return {"task_id": task_id, "status": "cancelled", "engine_interrupted": False}
    raise HTTPException(status_code=404, detail=f"Active task '{task_id}' not found or already concluded.")


@app.get("/api/v1/tasks/history", response_model=List[TaskRecord])
async def generation_task_history(project_id: Optional[str] = None) -> List[TaskRecord]:
    """Return durable outcomes, effective parameters, provenance and recovery guidance."""
    return await task_store.list_tasks(project_id=project_id)


@app.post("/api/v1/workflow/cancel/{run_id}")
async def cancel_workflow_run(run_id: str) -> Dict[str, Any]:
    """Cancel an active DAG workflow run (R14)."""
    if workflow_runs.cancel(run_id) or run_id in active_cancellations:
        if run_id in active_cancellations:
            active_cancellations[run_id].set()
        return {"run_id": run_id, "success": True, "status": "cancelled"}
    return {"run_id": run_id, "success": False, "status": "not_found"}


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


@app.post("/api/v1/runtime/start", response_model=RuntimeStartResponse)
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


@app.post("/api/v1/runtime/webui/start", response_model=RuntimeStartResponse)
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
    Safely update a managed engine with active job checking, exclusive lease, and rollback protection (L08, L12).
    """
    def _is_busy() -> bool:
        return (
            len(active_cancellations) > 0
            or len(creative_runner.active_tasks) > 0
            or task_registry.has_active_tasks()
        )

    return await installer.update_engine(engine_type, has_active_tasks_fn=_is_busy)


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


@app.get("/api/v1/hardware/gpu-stats", response_model=GpuStatsResponse)
async def get_hardware_gpu_stats() -> GpuStatsResponse:
    """Retrieve real-time GPU utilization, VRAM usage, and active compute processes (LH-M4)."""
    return get_gpu_stats()


@app.get("/api/v1/engines", response_model=List[EngineConnection])
async def list_engines() -> List[EngineConnection]:
    """List all available managed and external engine connections."""
    return engine_manager.list_engines()


@app.get("/api/v1/engines/instances", response_model=EngineInstancesResponse)
async def list_engine_instances() -> EngineInstancesResponse:
    """Return a unified catalog of all workspaces and engine instances for the Launcher Hub."""
    instances = engine_manager.get_all_instances()
    return EngineInstancesResponse(instances=instances)


@app.get("/api/v1/engines/detect", response_model=EngineDetectResponse)
async def detect_local_engines(paths: Optional[str] = None) -> EngineDetectResponse:
    """Scan candidate directories for existing ComfyUI or SD WebUI installations."""
    scan_paths = [p.strip() for p in paths.split(",")] if paths else None
    detected = engine_manager.detect_engines(scan_paths)
    return EngineDetectResponse(detected=detected)


@app.post("/api/v1/engines/bind", response_model=EngineConnection, status_code=201)
async def bind_external_engine(request: EngineBindRequest) -> EngineConnection:
    """Bind an external engine directory into the catalog without process mutation."""
    try:
        return engine_manager.bind_external_engine(
            engine_type_str=request.engine_type,
            name=request.name,
            path_str=request.path,
            port=request.port,
            extra_args=request.extra_args,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/engines/unbind/{instance_id}")
async def unbind_external_engine(instance_id: str) -> dict[str, Any]:
    """Unbind an external engine from the catalog. Non-destructive: preserves all files."""
    success = engine_manager.unbind_external_engine(instance_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Engine instance '{instance_id}' not found")
    return {"success": True, "message": f"Engine instance '{instance_id}' unbound successfully"}


@app.get("/api/v1/engines/{instance_id}/config", response_model=EngineConfig)
async def get_engine_config(instance_id: str) -> EngineConfig:
    """Retrieve persistent configuration (port, extra CLI arguments) for an engine instance."""
    try:
        return engine_manager.get_engine_config(instance_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/engines/{instance_id}/config", response_model=EngineConfigResponse)
@app.put("/api/v1/engines/{instance_id}/config", response_model=EngineConfigResponse)
async def update_engine_config(instance_id: str, request: EngineConfigUpdateRequest) -> EngineConfigResponse:
    """
    Persist engine configuration (port, launch arguments).
    Applies immediately to connection routing, updates supervisor launch settings,
    and indicates whether a running engine requires a restart.
    """
    try:
        cfg, requires_restart = engine_manager.save_engine_config(
            instance_id=instance_id,
            port=request.port,
            extra_args=request.extra_args,
        )
        msg = "Configuration saved successfully."
        if requires_restart:
            msg = "Configuration saved. Engine restart is required for changes to take effect."
        return EngineConfigResponse(
            success=True,
            instance_id=cfg.instance_id,
            port=cfg.port,
            extra_args=cfg.extra_args,
            requires_restart=requires_restart,
            message=msg,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save engine configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to persist engine configuration: {e}")


@app.get("/api/v1/runtime/{instance_id}/logs", response_model=EngineLogResponse)
async def get_engine_logs(instance_id: str, lines: int = 100) -> EngineLogResponse:
    """Fetch recent diagnostic logs for an engine instance."""
    logs = engine_manager.get_logs(instance_id, lines)
    return EngineLogResponse(instance_id=instance_id, total_lines=len(logs), logs=logs)


@app.get("/api/v1/installer/mirrors", response_model=MirrorConfigResponse)
async def get_installer_mirrors() -> MirrorConfigResponse:
    """Get active network download mirror configuration and available presets."""
    cfg = mirror_manager.get_config()
    return MirrorConfigResponse.model_validate(cfg)


@app.put("/api/v1/installer/mirrors", response_model=MirrorConfigResponse)
async def update_installer_mirrors(request: UpdateMirrorConfigRequest) -> MirrorConfigResponse:
    """Update active mirror preset or custom mirror URLs."""
    cfg = mirror_manager.update_config(
        active_preset=request.active_preset,
        custom_git_mirror=request.custom_git_mirror,
        custom_pypi_mirror=request.custom_pypi_mirror,
        custom_hf_mirror=request.custom_hf_mirror,
    )
    return MirrorConfigResponse.model_validate(cfg)




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
# Model Hub & Hardware Evaluation Endpoints (MH-M2)
# ---------------------------------------------------------------------------

@app.get("/api/v1/models/hub/catalog", response_model=HubCatalogResponse)
async def list_model_hub_catalog(
    category: Optional[str] = None,
    architecture: Optional[str] = None,
    query: Optional[str] = None,
) -> HubCatalogResponse:
    """Retrieve curated model hub catalog with optional filtering (MH-M2)."""
    models = HubCatalog.list_models(category=category, architecture=architecture, query=query)
    return HubCatalogResponse(total=len(models), models=models)


@app.post("/api/v1/models/hub/evaluate", response_model=HardwareEvaluationResponse)
async def evaluate_models_hardware(req: HardwareEvaluationRequest) -> HardwareEvaluationResponse:
    """Evaluate 4-tier hardware compatibility for requested or all catalog models (MH-M2)."""
    if req.model_ids:
        models = [HubCatalog.get_model(mid) for mid in req.model_ids]
        filtered_models = [m for m in models if m is not None]
    else:
        filtered_models = HubCatalog.list_models()
    return evaluate_hardware(filtered_models)


@app.post("/api/v1/models/hub/download", response_model=DownloadTaskInfo, status_code=202)
async def start_model_download(req: StartDownloadRequest) -> DownloadTaskInfo:
    """Initiate resumable background download with mirror acceleration (MH-M4)."""
    try:
        return model_downloader.start_download(
            model_id=req.model_id,
            target_engine=req.target_engine,
            mirror_preset=req.mirror_preset,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/models/hub/tasks", response_model=DownloadTasksResponse)
async def list_download_tasks() -> DownloadTasksResponse:
    """List active and completed model download tasks with transfer speed and ETA (MH-M4)."""
    tasks = model_downloader.list_tasks()
    return DownloadTasksResponse(tasks=tasks)


@app.post("/api/v1/models/hub/tasks/{task_id}/pause")
async def pause_download_task(task_id: str) -> dict[str, Any]:
    """Pause an active downloading task (MH-M4)."""
    success = model_downloader.pause_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found or cannot be paused")
    return {"status": "paused", "task_id": task_id}


@app.post("/api/v1/models/hub/tasks/{task_id}/resume")
async def resume_download_task(task_id: str) -> dict[str, Any]:
    """Resume a paused download task (MH-M4)."""
    success = model_downloader.resume_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found or cannot be resumed")
    return {"status": "resumed", "task_id": task_id}


@app.delete("/api/v1/models/hub/tasks/{task_id}")
async def cancel_download_task(task_id: str) -> dict[str, Any]:
    """Cancel and delete an active or paused download task (MH-M4)."""
    success = model_downloader.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return {"status": "cancelled", "task_id": task_id}


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
    filename = sanitize_filename(file.filename)
    validated_mime, w, h = validate_and_inspect_media(data, filename)
    category = "video" if validated_mime.startswith("video/") else "image"
    return await asset_store.save_bytes(data, filename=filename, media_type=category, width=w, height=h)


class AssetUploadBase64Request(BaseModel):
    filename: str
    content_base64: str
    media_type: str = "image"


@app.post("/api/v1/creative/upload-base64", response_model=AssetRecord)
async def upload_creative_asset_base64(req: AssetUploadBase64Request) -> AssetRecord:
    """Upload asset encoded in base64 (used by CLI and programmatic API clients)."""
    import base64
    import binascii
    try:
        data = base64.b64decode(req.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {exc}")
    filename = sanitize_filename(req.filename)
    validated_mime, w, h = validate_and_inspect_media(data, filename)
    category = "video" if validated_mime.startswith("video/") else "image"
    return await asset_store.save_bytes(data, filename=filename, media_type=category, width=w, height=h)


agent_service = AgentService(
    model_catalog=model_store,
    credential_manager=credentials_manager,
    creative_runner=creative_runner,
)


@app.post("/api/v1/agent/chat", response_model=AgentChatResponse)
async def agent_chat_endpoint(req: AgentChatRequest) -> AgentChatResponse:
    """Conversational Agent chat endpoint: processes natural language intent and formulates a transparent action plan (M9)."""
    return await agent_service.process_chat(req)


@app.post("/api/v1/agent/execute", response_model=List[CreativeActionResult])
async def agent_execute_proposal_endpoint(req: AgentExecuteProposalRequest) -> List[CreativeActionResult]:
    """Execute an approved Agent proposal under strict human-in-the-loop confirmation (M9)."""
    try:
        return await agent_service.execute_proposal(req.proposal, project_id=req.project_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


workflow_validator = WorkflowValidator(model_catalog=model_store)
workflow_repairer = WorkflowRepairer(model_catalog=model_store)


@app.get("/api/v1/workflow/bounded")
async def list_bounded_workflows() -> List[Dict[str, Any]]:
    """Return the registry of bounded supported ComfyUI workflows (M10)."""
    return WorkflowCatalog.list_workflows()


@app.post("/api/v1/workflow/validate", response_model=WorkflowValidationReport)
async def validate_comfy_workflow(workflow: Dict[str, Any]) -> WorkflowValidationReport:
    """Validate a ComfyUI prompt workflow DAG, verifying port types, required slots, and model dependencies (M10)."""
    return workflow_validator.validate(workflow)


@app.post("/api/v1/workflow/repair", response_model=WorkflowRepairResult)
async def repair_comfy_workflow(workflow: Dict[str, Any]) -> WorkflowRepairResult:
    """Repair broken links, missing slots, and missing checkpoints in a ComfyUI workflow DAG (M10)."""
    return workflow_repairer.repair(workflow)






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
    try:
        credentials_manager.set_key(req.provider_id, req.api_key)
    except Exception as e:
        logger.error(f"Failed to persist credential: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to persist credentials: {e}")
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
    try:
        credentials_manager.delete_key(provider_id)
    except Exception as e:
        logger.error(f"Failed to delete credential: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update stored credentials: {e}")
    return {"success": True}


# ---------------------------------------------------------------------------
# LLM Provider & Agent Base Endpoints (Local llama.cpp / OpenAI / SiliconFlow)
# ---------------------------------------------------------------------------

@app.get("/api/v1/agent/llm/config", response_model=LLMConfig)
async def get_agent_llm_config() -> LLMConfig:
    """Get active LLM provider configuration for the Agent base (llama-server / SiliconFlow / OpenAI)."""
    cfg = credentials_manager.get_llm_config()
    redacted_api_key = redact_key(cfg.api_key) if cfg.api_key else ""
    return LLMConfig(
        provider=cfg.provider,
        model=cfg.model,
        base_url=cfg.base_url,
        api_key=redacted_api_key,
        temperature=cfg.temperature,
        enabled=cfg.enabled,
    )


@app.post("/api/v1/agent/llm/config", response_model=LLMConfig)
async def set_agent_llm_config(req: SetLLMConfigRequest) -> LLMConfig:
    """Save or update LLM provider configuration."""
    existing = credentials_manager.get_llm_config()
    effective_api_key = req.api_key
    if not effective_api_key or "..." in effective_api_key or effective_api_key == "****":
        effective_api_key = existing.api_key

    cfg = LLMConfig(
        provider=req.provider,
        model=req.model,
        base_url=req.base_url,
        api_key=effective_api_key,
        temperature=req.temperature,
        enabled=req.enabled,
    )
    try:
        credentials_manager.set_llm_config(cfg)
    except Exception as e:
        logger.error(f"Failed to persist LLM config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to persist LLM configuration: {e}")

    return LLMConfig(
        provider=cfg.provider,
        model=cfg.model,
        base_url=cfg.base_url,
        api_key=redact_key(cfg.api_key) if cfg.api_key else "",
        temperature=cfg.temperature,
        enabled=cfg.enabled,
    )


@app.post("/api/v1/agent/llm/test", response_model=TestKeyResult)
async def test_agent_llm_endpoint(config: Optional[LLMConfig] = None) -> TestKeyResult:
    """Test connectivity to configured LLM endpoint (llama-server local / remote API)."""
    return await credentials_manager.test_llm_connection(config)


# ---------------------------------------------------------------------------
# Embedded llama-server (llama.cpp) Runtime & Model Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/llama-server/status", response_model=LlamaServerRuntimeStatus)
async def get_llama_server_runtime_status() -> LlamaServerRuntimeStatus:
    """Get active status of the embedded llama-server runtime."""
    return await llama_server_supervisor.get_status()


class LlamaServerStartRequest(BaseModel):
    model_name: Optional[str] = None
    vram_gpu_layers: int = 99


@app.post("/api/v1/llama-server/start")
async def start_llama_server_runtime(req: Optional[LlamaServerStartRequest] = None) -> Dict[str, Any]:
    """Start embedded llama-server process with selected GGUF model."""
    try:
        model_name = req.model_name if req else None
        gpu_layers = req.vram_gpu_layers if req else 99
        result = llama_server_supervisor.start(model_name, vram_gpu_layers=gpu_layers)
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Invalid response from llama-server supervisor")
        return result
    except Exception as e:
        logger.error(f"Failed to start llama-server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start llama-server: {str(e)}")


@app.post("/api/v1/llama-server/stop")
async def stop_llama_server_runtime() -> Dict[str, Any]:
    """Stop embedded llama-server process."""
    try:
        result = llama_server_supervisor.stop()
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Invalid response from llama-server supervisor")
        return result
    except Exception as e:
        logger.error(f"Failed to stop llama-server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop llama-server: {str(e)}")


@app.post("/api/v1/llama-server/install")
async def install_llama_server_runtime() -> Dict[str, Any]:
    """Provision or download pre-compiled standalone llama-server binary."""
    return await llama_server_supervisor.install()


@app.get("/api/v1/llama-server/models", response_model=List[LlamaModelInfo])
async def list_llama_server_models() -> List[LlamaModelInfo]:
    """List local .gguf models available in engine/models/llm and shared canvas models."""
    return llama_server_supervisor.list_local_models()


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

    ext = abs_path.suffix.lower()
    safe_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
    }
    content_type = safe_types.get(ext)
    disposition = "inline"
    if not content_type:
        content_type = "application/octet-stream"
        disposition = "attachment"

    return FileResponse(
        abs_path,
        media_type=content_type,
        filename=sanitize_filename(rec.filename),
        content_disposition_type=disposition,
        headers=MEDIA_SECURITY_HEADERS,
    )


@app.post("/api/v1/workflow/cancel/{run_id}")
async def cancel_workflow_run(run_id: str) -> dict[str, Any]:
    if workflow_runs.cancel(run_id) or run_id in active_cancellations:
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
        validate_execution_contract(graph, sorted_nodes, NODE_RUNNERS)
    except CyclicDependencyError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except ExecutionContractError as err:
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


@app.post("/api/v1/workflow/submit")
async def submit_workflow(request: WorkflowRunRequest) -> dict[str, str]:
    """Admit an immutable run once; subscribers never resubmit inference."""
    try:
        run_id = await workflow_runs.submit(request, _execute_workflow_request)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    return {"run_id": run_id, "status": "accepted"}


@app.websocket("/ws/workflow/run")
async def websocket_run_workflow(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    if origin and not session_manager.is_origin_allowed(origin):
        logger.warning(f"Rejecting WebSocket handshake from unauthorized origin: {origin}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    token = websocket.query_params.get("token") or websocket.headers.get("x-session-token")
    if token and not session_manager.is_valid_token(token):
        logger.warning("Rejecting WebSocket handshake with invalid session token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        parsed = json.loads(await websocket.receive_text())
        after_sequence = 0
        if parsed.get("type") == "SUBSCRIBE":
            subscription = WorkflowSubscription.model_validate(parsed)
            run_id = subscription.run_id
            after_sequence = subscription.after_sequence
        else:
            request = WorkflowRunRequest.model_validate(parsed if "graph" in parsed else {"graph": parsed})
            run_id = await workflow_runs.submit(request, _execute_workflow_request)
        async for event in workflow_runs.subscribe(run_id, after_sequence):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info("Workflow subscriber disconnected; execution continues independently")
    except (ValueError, LookupError) as error:
        await websocket.send_json({"type": "ERROR", "message": str(error)})
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass


async def _execute_workflow_request(request: WorkflowRunRequest, websocket: WorkflowEventSink) -> None:
    """Execute into a durable event sink without owning any client connection."""
    graph = request.graph
    target_node = request.target_node_id
    run_id = request.run_id
    # Register cancellation token
    cancel_event = websocket.cancel_event
    active_cancellations[run_id] = cancel_event
    task_registry.register_task(
        task_id=run_id,
        task_type="workflow_graph",
        cancel_event=cancel_event,
        metadata={"target_node": target_node},
    )

    try:
        resolver = DAGResolver(graph)
        sorted_nodes = resolver.topological_sort(target_node_id=target_node)
        validate_execution_contract(graph, sorted_nodes, NODE_RUNNERS)
    except ExecutionContractError as e:
        await websocket.send_text(NodeErrorEvent(node_id=e.node_id, message=str(e), run_id=run_id).model_dump_json())
        for node in graph.nodes:
            await websocket.send_text(NodeStatusEvent(node_id=node.id, status="error" if node.id == e.node_id else "cancelled", run_id=run_id).model_dump_json())
        await websocket.send_text(GraphFinishedEvent(run_id=run_id, execution_time_ms=0, status="failed").model_dump_json())
        await websocket.close()
        active_cancellations.pop(run_id, None)
        task_registry.unregister_task(run_id)
        return
    except CyclicDependencyError as e:
        await websocket.send_text(json.dumps({"type": "ERROR", "message": str(e), "run_id": run_id}))
        await websocket.close()
        active_cancellations.pop(run_id, None)
        task_registry.unregister_task(run_id)
        return
    except ValueError as e:
        await websocket.send_text(json.dumps({"type": "ERROR", "message": str(e), "run_id": run_id}))
        await websocket.close()
        active_cancellations.pop(run_id, None)
        task_registry.unregister_task(run_id)
        return

    # Check cache status for active nodes
    cached_count = 0
    node_outputs: Dict[str, Dict[str, Any]] = {}

    start_time = time.monotonic()
    failed_node_ids: set[str] = set()

    try:
        await websocket.send_text(
            GraphStartedEvent(run_id=run_id, total_nodes=len(sorted_nodes), cached_nodes=cached_count).model_dump_json()
        )

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

            await websocket.bind_inputs(node.id, inputs)

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
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected during execution of node %s (run_id: %s)", node.id, run_id)
                cancel_event.set()
                break
            except Exception as e:
                node_has_error = True
                try:
                    await websocket.send_text(NodeErrorEvent(node_id=node.id, message=str(e), run_id=run_id).model_dump_json())
                    await websocket.send_text(NodeStatusEvent(node_id=node.id, status="error", run_id=run_id).model_dump_json())
                except (WebSocketDisconnect, RuntimeError):
                    cancel_event.set()
                    break

            if cancel_event.is_set():
                await websocket.send_text(RunCancelledEvent(run_id=run_id).model_dump_json())
                await websocket.send_text(GraphFinishedEvent(run_id=run_id, execution_time_ms=(time.monotonic() - start_time) * 1000, status="cancelled").model_dump_json())
                break

            definition = registry.get(node.type)
            if not node_has_error and definition and any(port.id not in output for port in definition.outputs):
                node_has_error = True
                await websocket.send_text(NodeErrorEvent(node_id=node.id, message="Runner did not return its declared outputs", run_id=run_id).model_dump_json())

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
                GraphFinishedEvent(run_id=run_id, execution_time_ms=elapsed_ms, status="failed" if failed_node_ids else "completed").model_dump_json()
            )

    except WebSocketDisconnect:
        logger.info("Client cleanly disconnected from workflow run %s", run_id)
        cancel_event.set()
    finally:
        active_cancellations.pop(run_id, None)
        task_registry.unregister_task(run_id)
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

