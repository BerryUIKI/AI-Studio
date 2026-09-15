"""Node and port schema definitions enforcing the 5-type contract."""

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class DataType(str, Enum):
    """The 5 universal port data types."""
    STRING = "string"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    JSON = "json"


class NodePort(BaseModel):
    """Input or output port for connecting nodes on the canvas."""
    id: str = Field(..., description="Unique port identifier within the node")
    name: str = Field(..., description="Display label for the port")
    type: DataType = Field(..., description="One of the 5 universal data types")
    required: bool = Field(default=False, description="Whether an input connection is required")
    default_value: Optional[Any] = Field(default=None, description="Fallback value when unlinked")


class ParameterType(str, Enum):
    """Types for user-configurable node parameters in the inspector panel."""
    STRING = "string"
    TEXTAREA = "textarea"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"


class SelectOption(BaseModel):
    """Option for select parameters."""
    label: str
    value: Any


class ParameterDef(BaseModel):
    """Definition for a node inspector parameter."""
    name: str = Field(..., description="Parameter key name")
    label: str = Field(..., description="UI display label")
    type: ParameterType = Field(..., description="Input widget type")
    default: Any = Field(default=None, description="Default parameter value")
    description: Optional[str] = Field(default=None, description="Helpful tooltip text")
    options: Optional[List[SelectOption]] = Field(default=None, description="Choices for select type")
    min_value: Optional[float] = Field(default=None, description="Minimum value for numbers")
    max_value: Optional[float] = Field(default=None, description="Maximum value for numbers")
    step: Optional[float] = Field(default=None, description="Step increment for numbers")


class NodeCategory(str, Enum):
    """High-level category for node grouping in UI palette."""
    INPUT = "input"
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    OUTPUT = "output"


class NodeDefinition(BaseModel):
    """Complete specification of an executable high-level node."""
    type: str = Field(..., description="Unique type identifier, e.g., 'image.flux.schnell'")
    title: str = Field(..., description="Human-readable title for canvas display")
    category: NodeCategory = Field(..., description="Palette category")
    description: str = Field(..., description="Brief description of the node function")
    inputs: List[NodePort] = Field(default_factory=list, description="Input ports")
    outputs: List[NodePort] = Field(default_factory=list, description="Output ports")
    parameters: List[ParameterDef] = Field(default_factory=list, description="Configurable parameters")
