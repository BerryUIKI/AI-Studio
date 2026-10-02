"""Pydantic schemas for projects and managed assets."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    name: str = Field(..., description="Project display name")


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    canvas: Optional[Dict[str, Any]] = None


class Project(ProjectBase):
    id: str = Field(..., description="Unique project UUID")
    canvas: Dict[str, Any] = Field(default_factory=lambda: {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}})
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AssetRecord(BaseModel):
    id: str = Field(..., description="Unique asset identifier")
    project_id: Optional[str] = Field(default=None, description="Associated project ID if any")
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Relative or absolute path on disk")
    media_type: str = Field(default="image", description="Asset media type: image, text, audio, etc.")
    content_hash: str = Field(..., description="SHA-256 content hash")
    byte_size: int = Field(default=0, description="Size in bytes")
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
