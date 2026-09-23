"""Pydantic models for Conversational Agent workflow control (M9)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.creative import CreativeActionType


class AgentIntent(str, Enum):
    TXT2IMG = "txt2img"
    IMG2IMG = "img2img"
    INPAINT = "inpaint"
    UPSCALE = "upscale"
    TXT2VIDEO = "txt2video"
    IMG2VIDEO = "img2video"
    GENERAL_QUERY = "general_query"


class AgentActionStep(BaseModel):
    step_number: int = 1
    action: CreativeActionType
    engine_id: str
    model: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class AgentProposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    intent: str
    title: str
    summary: str
    target_engine: str
    model: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    chain_steps: List[AgentActionStep] = Field(default_factory=list)
    estimated_calls: int = 1
    cost_disclaimer: str = "Free local engine inference"
    explanation: str = ""
    requires_user_approval: bool = True
    approved: bool = False


class AgentChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: str = "assistant"  # user, assistant, system
    content: str
    proposal: Optional[AgentProposal] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    selected_asset_id: Optional[str] = None
    preferred_engine: Optional[str] = None


class AgentChatResponse(BaseModel):
    conversation_id: str
    message: AgentChatMessage
    proposal: Optional[AgentProposal] = None


class AgentExecuteProposalRequest(BaseModel):
    proposal_id: str
    proposal: AgentProposal
    project_id: Optional[str] = None
