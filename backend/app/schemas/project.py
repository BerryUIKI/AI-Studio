"""Pydantic schemas for projects and managed assets."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    name: str = Field(..., description="Project display name")
    version: int = Field(default=1, description="Project schema version")


class ProjectCreate(BaseModel):
    name: str = Field(default="Untitled Project", description="Project display name")
    version: int = Field(default=1, description="Project schema version")
    canvas: Optional[Dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[int] = None
    canvas: Optional[Dict[str, Any]] = None


class Project(ProjectBase):
    id: str = Field(..., description="Unique project UUID")
    version: int = Field(default=1, description="Project schema version")
    canvas: Dict[str, Any] = Field(
        default_factory=lambda: {
            "version": 1,
            "nodes": [],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }
    )
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
    file_exists: bool = Field(default=True, description="Whether asset file physically exists on disk")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
