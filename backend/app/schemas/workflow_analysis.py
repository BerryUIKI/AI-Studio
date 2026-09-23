"""Pydantic schemas for ComfyUI workflow analysis, validation, and repair (M10)."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowIssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class WorkflowIssue(BaseModel):
    node_id: str
    node_class: str
    input_slot: Optional[str] = None
    issue_type: str  # missing_connection, type_mismatch, missing_model, cycle_detected, orphan_node
    message: str
    severity: WorkflowIssueSeverity = WorkflowIssueSeverity.ERROR


class WorkflowValidationReport(BaseModel):
    valid: bool
    node_count: int
    issues: List[WorkflowIssue] = Field(default_factory=list)
    missing_models: List[str] = Field(default_factory=list)
    has_cycle: bool = False


class RepairAction(BaseModel):
    node_id: str
    node_class: str
    action_type: str  # reconnect_slot, replace_model, add_node
    description: str
    target_input: Optional[str] = None
    source_node_id: Optional[str] = None
    source_output_slot: Optional[int] = None
    new_value: Optional[Any] = None


class WorkflowRepairResult(BaseModel):
    success: bool
    original_valid: bool
    repaired_valid: bool
    repairs_applied: List[RepairAction] = Field(default_factory=list)
    repaired_workflow: Dict[str, Any] = Field(default_factory=dict)
    remaining_issues: List[WorkflowIssue] = Field(default_factory=list)
