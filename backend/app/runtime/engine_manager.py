"""
Engine Connection Manager.

Connects to managed (supervised) and external (user-running) ComfyUI and
Stable Diffusion WebUI instances. For external engines, guarantees ZERO process
ownership: never attempts to kill external processes or mutate user installations.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional
import httpx

from app.runtime.supervisor import supervisor as comfy_supervisor
from app.runtime.webui_supervisor import webui_supervisor
from app.schemas.engine import (
    EngineConnection,
    EngineOwnership,
    EngineStatus,
    EngineType,
)

logger = logging.getLogger(__name__)


class EngineManager:
    """Registry and coordinator for local inference engine connections."""

    def __init__(self) -> None:
        self._connections: Dict[str, EngineConnection] = {}
        self._init_managed_engines()

    def _init_managed_engines(self) -> None:
        """Register the built-in managed engine slots."""
        # Managed ComfyUI
        self._connections["managed_comfyui"] = EngineConnection(
            id="managed_comfyui",
            name="Managed ComfyUI (Isolated)",
            engine_type=EngineType.COMFYUI,
            ownership=EngineOwnership.MANAGED,
            endpoint_url=f"http://127.0.0.1:{comfy_supervisor.port}",
            native_ui_url=f"http://127.0.0.1:{comfy_supervisor.port}",
            status=EngineStatus.STOPPED if comfy_supervisor.is_installed() else EngineStatus.NOT_INSTALLED,
            capabilities=["txt2img", "img2img", "workflows"],
        )

        # Managed WebUI
        self._connections["managed_webui"] = EngineConnection(
            id="managed_webui",
            name="Managed SD WebUI (Isolated)",
            engine_type=EngineType.WEBUI,
            ownership=EngineOwnership.MANAGED,
            endpoint_url=f"http://127.0.0.1:{webui_supervisor.port}",
            native_ui_url=f"http://127.0.0.1:{webui_supervisor.port}",
            status=EngineStatus.STOPPED if webui_supervisor.is_installed() else EngineStatus.NOT_INSTALLED,
            capabilities=["txt2img", "img2img", "inpaint", "extras"],
        )

    def list_engines(self) -> List[EngineConnection]:
        """Return list of all registered engines with refreshed managed statuses."""
        # Sync managed ComfyUI status
        comfy_conn = self._connections.get("managed_comfyui")
        if comfy_conn:
            if not comfy_supervisor.is_installed():
                comfy_conn.status = EngineStatus.NOT_INSTALLED
            elif comfy_supervisor.is_running():
                comfy_conn.status = EngineStatus.RUNNING
            else:
                comfy_conn.status = EngineStatus.STOPPED

        # Sync managed WebUI status
        webui_conn = self._connections.get("managed_webui")
        if webui_conn:
            if not webui_supervisor.is_installed():
                webui_conn.status = EngineStatus.NOT_INSTALLED
            elif webui_supervisor.is_running():
                webui_conn.status = EngineStatus.RUNNING
            else:
                webui_conn.status = EngineStatus.STOPPED

        return list(self._connections.values())

    def get_engine(self, engine_id: str) -> Optional[EngineConnection]:
        """Retrieve connection details for a specific engine."""
        self.list_engines()  # refresh statuses
        return self._connections.get(engine_id)

    async def connect_external_engine(
        self, engine_type: EngineType, endpoint_url: str, name: Optional[str] = None
    ) -> EngineConnection:
        """
        Connect to an existing user-managed engine instance.
        Zero process ownership: does not touch process or write PID.
        """
        endpoint = endpoint_url.rstrip("/")
        engine_id = f"external_{engine_type.value}_{abs(hash(endpoint)) % 10000}"
        display_name = name or f"External {engine_type.value.capitalize()} ({endpoint})"

        connection = EngineConnection(
            id=engine_id,
            name=display_name,
            engine_type=engine_type,
            ownership=EngineOwnership.EXTERNAL,
            endpoint_url=endpoint,
            native_ui_url=endpoint,
            status=EngineStatus.OFFLINE,
            capabilities=["txt2img", "img2img"],
        )

        # Validate external engine health immediately
        connection = await self.test_engine_connection(connection)
        self._connections[engine_id] = connection
        return connection

    async def test_engine_connection(self, connection: EngineConnection) -> EngineConnection:
        """Probe engine endpoint and update status and capabilities."""
        endpoint = connection.endpoint_url
        async with httpx.AsyncClient(timeout=4.0) as client:
            try:
                if connection.engine_type == EngineType.COMFYUI:
                    # Query /system_stats
                    resp = await client.get(f"{endpoint}/system_stats")
                    if resp.status_code == 200:
                        data = resp.json()
                        connection.status = EngineStatus.READY
                        devices = data.get("devices", [])
                        if devices and isinstance(devices, list):
                            vram_free = devices[0].get("vram_free", 0)
                            connection.vram_free_mb = int(vram_free / (1024 * 1024))
                        connection.error_message = None
                    else:
                        connection.status = EngineStatus.DEGRADED
                        connection.error_message = f"ComfyUI returned HTTP {resp.status_code}"
                elif connection.engine_type == EngineType.WEBUI:
                    # Query /sdapi/v1/options or /sdapi/v1/progress
                    resp = await client.get(f"{endpoint}/sdapi/v1/options")
                    if resp.status_code == 200:
                        connection.status = EngineStatus.READY
                        connection.error_message = None
                    else:
                        # Try /sdapi/v1/progress as fallback
                        resp_prog = await client.get(f"{endpoint}/sdapi/v1/progress")
                        if resp_prog.status_code == 200:
                            connection.status = EngineStatus.READY
                            connection.error_message = None
                        else:
                            connection.status = EngineStatus.DEGRADED
                            connection.error_message = f"WebUI returned HTTP {resp.status_code}"

                connection.last_heartbeat = time.time()

            except Exception as e:
                connection.status = EngineStatus.OFFLINE
                connection.error_message = f"Connection failed: {e}"

        return connection

    async def test_connection_by_id(self, engine_id: str) -> Optional[EngineConnection]:
        """Test health of a registered engine connection by its ID."""
        conn = self._connections.get(engine_id)
        if not conn:
            return None
        return await self.test_engine_connection(conn)


# Global engine manager singleton
engine_manager = EngineManager()
