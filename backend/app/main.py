"""FastAPI application entrypoint for AI-Workflow."""

from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.nodes.registry import registry
from app.schemas.node import NodeDefinition

# Import builtin nodes to trigger auto-registration
import app.nodes.builtin  # noqa: F401

app = FastAPI(
    title="AI-Workflow Engine API",
    description="Lightweight, API-first execution engine for multimodal workflows",
    version="0.1.0",
)

# Enable CORS for local web canvas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for liveness probes."""
    return {"status": "ok", "service": "ai-workflow-backend"}


@app.get("/api/v1/info")
async def system_info() -> dict[str, object]:
    """System info endpoint reporting capabilities and supported runners."""
    return {
        "name": "AI-Workflow",
        "version": "0.1.0",
        "runners": {
            "api": {"status": "ready", "type": "cloud"},
            "comfyui": {"status": "optional", "installed": False, "connected": False},
        },
    }


@app.get("/api/v1/nodes", response_model=List[NodeDefinition])
async def list_nodes() -> List[NodeDefinition]:
    """Retrieve all registered node specifications."""
    return registry.list_all()
