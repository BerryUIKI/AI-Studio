"""WebSocket event schemas for real-time execution progress streaming."""

from typing import Any, Dict, Literal, Optional, Union
from pydantic import BaseModel


class NodeStatusEvent(BaseModel):
    type: Literal["NODE_STATUS"] = "NODE_STATUS"
    node_id: str
    status: Literal["idle", "queued", "running", "cached", "completed", "error"]


class NodeProgressEvent(BaseModel):
    type: Literal["NODE_PROGRESS"] = "NODE_PROGRESS"
    node_id: str
    progress: float  # 0.0 – 1.0
    message: Optional[str] = None


class NodeOutputEvent(BaseModel):
    type: Literal["NODE_OUTPUT"] = "NODE_OUTPUT"
    node_id: str
    output: Dict[str, Any]


class NodeErrorEvent(BaseModel):
    type: Literal["NODE_ERROR"] = "NODE_ERROR"
    node_id: str
    message: str


class GraphStartedEvent(BaseModel):
    type: Literal["GRAPH_STARTED"] = "GRAPH_STARTED"
    total_nodes: int
    cached_nodes: int


class GraphFinishedEvent(BaseModel):
    type: Literal["GRAPH_FINISHED"] = "GRAPH_FINISHED"
    execution_time_ms: float


WorkflowEvent = Union[
    NodeStatusEvent,
    NodeProgressEvent,
    NodeOutputEvent,
    NodeErrorEvent,
    GraphStartedEvent,
    GraphFinishedEvent,
]
