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
