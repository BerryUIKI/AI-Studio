"""Engine connection and installation manifest schemas."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
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


class EngineConfig(BaseModel):
    instance_id: str
    port: int
    extra_args: List[str] = Field(default_factory=list)


class EngineConfigUpdateRequest(BaseModel):
    port: int
    extra_args: List[str] = Field(default_factory=list)


class EngineConfigResponse(BaseModel):
    success: bool = True
    instance_id: str
    port: int
    extra_args: List[str] = Field(default_factory=list)
    requires_restart: bool = False
    message: str = "Configuration saved successfully."


class EngineInstanceInfo(BaseModel):
    id: str
    type: str  # canvas, comfyui, webui, agents, custom
    name: str
    version: Optional[str] = None
    is_managed: bool = True
    is_builtin: bool = False
    install_path: Optional[str] = None
    status: str  # ready, running, stopped, not_installed, error, updating
    endpoint: Optional[str] = None
    pid: Optional[int] = None
    vram_used_mb: Optional[int] = None
    capabilities: List[str] = Field(default_factory=list)
    port: Optional[int] = None
    extra_args: List[str] = Field(default_factory=list)
    connection_id: Optional[str] = None


class EngineInstancesResponse(BaseModel):
    instances: List[EngineInstanceInfo]


class DetectedEngineInfo(BaseModel):
    engine_type: str  # comfyui, webui
    path: str
    version: Optional[str] = None
    has_python_env: bool = False
    python_executable: Optional[str] = None
    recommended_name: str


class EngineDetectResponse(BaseModel):
    detected: List[DetectedEngineInfo]


class EngineBindRequest(BaseModel):
    engine_type: str  # comfyui, webui
    name: str
    path: str
    port: Optional[int] = None
    extra_args: List[str] = Field(default_factory=list)


class MirrorPresetInfo(BaseModel):
    id: str
    name: str
    git_mirror: Optional[str] = None
    pypi_mirror: Optional[str] = None
    hf_mirror: Optional[str] = None


class MirrorConfigResponse(BaseModel):
    active_preset: str
    presets: List[MirrorPresetInfo]
    custom_git_mirror: Optional[str] = None
    custom_pypi_mirror: Optional[str] = None
    custom_hf_mirror: Optional[str] = None


class UpdateMirrorConfigRequest(BaseModel):
    active_preset: Literal["direct", "china_mainland", "custom"]
    custom_git_mirror: Optional[str] = None
    custom_pypi_mirror: Optional[str] = None
    custom_hf_mirror: Optional[str] = None


class EngineLogResponse(BaseModel):
    instance_id: str
    total_lines: int
    logs: List[str]


class RuntimeStartResponse(BaseModel):
    success: bool
    code: Optional[str] = None  # e.g. "NOT_INSTALLED", "ENV_MISSING", "ALREADY_RUNNING"
    message: str
    pid: Optional[int] = None




