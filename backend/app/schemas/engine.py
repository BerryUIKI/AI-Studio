"""Engine connection and installation manifest schemas."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EngineType(str, Enum):
    COMFYUI = "comfyui"
    WEBUI = "webui"


class EngineOwnership(str, Enum):
    MANAGED = "managed"      # Controlled by Berry supervisor (can start/stop)
    EXTERNAL = "external"    # Pre-existing user installation (connect-only, no process control)


class EngineStatus(str, Enum):
    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    NOT_INSTALLED = "not_installed"


class InstallPhase(str, Enum):
    IDLE = "idle"
    CHECKING = "checking"
    CREATING_VENV = "creating_venv"
    DOWNLOADING = "downloading"
    INSTALLING_DEPS = "installing_deps"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class EngineInstallManifest(BaseModel):
    engine_type: EngineType
    phase: InstallPhase = InstallPhase.IDLE
    version: Optional[str] = None
    engine_dir: str
    runtime_dir: str
    python_bin: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    last_log_line: Optional[str] = None


class EngineConnection(BaseModel):
    id: str
    name: str
    engine_type: EngineType
    ownership: EngineOwnership
    endpoint_url: str
    status: EngineStatus
    native_ui_url: Optional[str] = None
    version: Optional[str] = None
    vram_free_mb: Optional[int] = None
    capabilities: List[str] = Field(default_factory=list)
    models_path: Optional[str] = None
    last_heartbeat: Optional[float] = None
    error_message: Optional[str] = None


class EngineConnectRequest(BaseModel):
    engine_type: EngineType
    endpoint_url: str
    name: Optional[str] = None


class EngineUpdateStatus(str, Enum):
    IDLE = "idle"
    CHECKING = "checking"
    UPDATING = "updating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class EngineUpdateManifest(BaseModel):
    engine_type: EngineType
    status: EngineUpdateStatus = EngineUpdateStatus.IDLE
    previous_commit: Optional[str] = None
    target_commit: Optional[str] = None
    updated_at: Optional[str] = None
    error_message: Optional[str] = None
    rollback_supported: bool = True
    rollback_performed: bool = False


class LauncherConfig(BaseModel):
    stop_managed_engines_on_exit: bool = False
    default_engine: str = "cloud"
    browser_auto_open: bool = True
    port: int = 8000


class ManagerStatusResponse(BaseModel):
    app_name: str = "Berry AI Studio"
    version: str = "0.1.0"
    pid: int
    uptime_seconds: float
    port: int
    frontend_packaged: bool
    managed_comfyui: EngineConnection
    managed_webui: EngineConnection
    external_engines: List[EngineConnection]
    cloud_providers_configured: int
    models_indexed: int
    active_tasks: int
    launcher_config: LauncherConfig


class ShutdownRequest(BaseModel):
    force: bool = False
    stop_managed_engines: Optional[bool] = None


class ShutdownResponse(BaseModel):
    status: str
    message: str
    active_tasks_cancelled: int
    managed_engines_stopped: List[str]

