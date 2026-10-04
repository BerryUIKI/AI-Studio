"""
Session and Origin Security Manager for Berry AI Studio.

Enforces:
1. Origin boundary validation on browser-facing writes, mutations, and WebSocket handshakes.
2. Per-launch ephemeral session credential generation and verification.
3. Protection of sensitive control, lifecycle, execution, and secret endpoints.
"""

import logging
import os
import secrets
from typing import Optional, Set
from fastapi import Request, WebSocket, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS: Set[str] = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
}

# Routes that perform execution, lifecycle modifications, or access secrets
SENSITIVE_PREFIXES = (
    "/api/v1/runtime/",
    "/api/v1/shutdown",
    "/api/v1/creative/execute",
    "/api/v1/workflow/run",
    "/api/v1/agent/llm/config",
    "/api/v1/cloud/credentials",
)


class SessionManager:
    """Manages the per-launch ephemeral session credential and origin validation."""

    def __init__(self) -> None:
        self._session_token: str = os.environ.get("BERRY_SESSION_TOKEN") or secrets.token_urlsafe(32)

    def get_token(self) -> str:
        return self._session_token

    def is_valid_token(self, token: Optional[str]) -> bool:
        if not token:
            return False
        return secrets.compare_digest(self._session_token, token.strip())

    def is_origin_allowed(self, origin: Optional[str]) -> bool:
        if not origin:
            # Native loopback or in-process client without Origin header
            return True
        cleaned = origin.rstrip("/")
        return cleaned in ALLOWED_ORIGINS or origin in ALLOWED_ORIGINS

    def extract_token(self, request: Request) -> Optional[str]:
        token = request.headers.get("x-session-token") or request.cookies.get("berry_session")
        if not token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
        if not token and request.query_params.get("token"):
            token = request.query_params.get("token")
        return token


session_manager = SessionManager()
