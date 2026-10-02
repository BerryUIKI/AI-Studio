"""Workflow execution request schemas and graph representation."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowNodeInstance(BaseModel):
    """Instance of a node placed on the canvas."""
    id: str = Field(..., description="Unique instance ID on canvas")
    type: str = Field(..., description="Node definition type identifier")
    params: Dict[str, Any] = Field(default_factory=dict, description="Configured parameter values")


class WorkflowEdgeInstance(BaseModel):
    """Connection wire between two node ports on the canvas."""
    id: str = Field(..., description="Edge ID")
    source: str = Field(..., description="Source node ID")
    source_handle: str = Field(..., description="Source output port ID")
    target: str = Field(..., description="Target node ID")
    target_handle: str = Field(..., description="Target input port ID")


class WorkflowGraph(BaseModel):
    """Complete serialized canvas workflow graph."""
    nodes: List[WorkflowNodeInstance] = Field(default_factory=list)
    edges: List[WorkflowEdgeInstance] = Field(default_factory=list)


class PlannedNodeStep(BaseModel):
    """A step within the topologically sorted execution plan."""
    node_id: str
    node_type: str
    node_hash: str
    is_cached: bool
    dependencies: List[str]


class ExecutionPlan(BaseModel):
    """Resolved execution plan with cache status per node."""
    steps: List[PlannedNodeStep]
    total_nodes: int
    cached_nodes_count: int
