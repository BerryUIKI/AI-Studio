"""FastAPI application entrypoint for AI-Workflow."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
