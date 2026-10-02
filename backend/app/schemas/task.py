"""Task and Run models representing immutable submissions and truthful states."""

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.workflow import WorkflowGraph

TaskStatus = Literal[
    "queued",
    "running",
    "cached",
    "succeeded",
    "failed",
    "cancel-requested",
    "cancelled",
]


class RunRecord(BaseModel):
    id: str = Field(..., description="Unique run identifier")
    project_id: Optional[str] = None
    target_node_id: Optional[str] = None
    status: TaskStatus = "queued"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None


class TaskRecord(BaseModel):
    id: str = Field(..., description="Unique task identifier")
    run_id: str = Field(..., description="Parent run ID")
    node_id: str = Field(..., description="Graph node ID")
    node_type: str = Field(..., description="Type of node executed")
    status: TaskStatus = "queued"
    params: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None


class WorkflowRunRequest(BaseModel):
    graph: WorkflowGraph
    target_node_id: Optional[str] = None
    run_id: Optional[str] = None
    project_id: Optional[str] = None
