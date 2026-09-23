"""WebSocket event schemas for real-time execution progress streaming."""

from typing import Any, Dict, Literal, Optional, Union
from pydantic import BaseModel


class NodeStatusEvent(BaseModel):
    type: Literal["NODE_STATUS"] = "NODE_STATUS"
    node_id: str
    status: Literal["idle", "queued", "running", "cached", "completed", "error", "cancelled"]
    run_id: Optional[str] = None


class NodeProgressEvent(BaseModel):
    type: Literal["NODE_PROGRESS"] = "NODE_PROGRESS"
    node_id: str
    progress: float  # 0.0 – 1.0
    message: Optional[str] = None
    run_id: Optional[str] = None


class NodeOutputEvent(BaseModel):
    type: Literal["NODE_OUTPUT"] = "NODE_OUTPUT"
    node_id: str
    output: Dict[str, Any]
    run_id: Optional[str] = None


class NodeErrorEvent(BaseModel):
    type: Literal["NODE_ERROR"] = "NODE_ERROR"
    node_id: str
    message: str
    run_id: Optional[str] = None


class GraphStartedEvent(BaseModel):
    type: Literal["GRAPH_STARTED"] = "GRAPH_STARTED"
    total_nodes: int
    cached_nodes: int
    run_id: Optional[str] = None


class GraphFinishedEvent(BaseModel):
    type: Literal["GRAPH_FINISHED"] = "GRAPH_FINISHED"
    execution_time_ms: float
    status: str = "completed"  # "completed", "cancelled", "failed"
    run_id: Optional[str] = None


class RunCancelledEvent(BaseModel):
    type: Literal["RUN_CANCELLED"] = "RUN_CANCELLED"
    run_id: str
    message: str = "Execution run cancelled by user"


WorkflowEvent = Union[
    NodeStatusEvent,
    NodeProgressEvent,
    NodeOutputEvent,
    NodeErrorEvent,
    GraphStartedEvent,
    GraphFinishedEvent,
    RunCancelledEvent,
]
