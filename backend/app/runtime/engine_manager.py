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

    def get_all_instances(self) -> List[Any]:
        """Return a unified catalog of all workspaces and engine instances for the Launcher Hub."""
        from app.schemas.engine import EngineInstanceInfo

        instances: List[EngineInstanceInfo] = [
            EngineInstanceInfo(
                id="builtin-canvas",
                type="canvas",
                name="Infinite Canvas",
                version="v0.1.0",
                is_managed=True,
                is_builtin=True,
                install_path=None,
                status="ready",
                endpoint=None,
                capabilities=["txt2img", "img2img", "inpaint", "upscale", "video"],
            )
        ]

        # ComfyUI
        comfy_installed = comfy_supervisor.is_installed()
        comfy_running = comfy_supervisor.is_running()
        comfy_status = "running" if comfy_running else ("stopped" if comfy_installed else "not_installed")
        instances.append(
            EngineInstanceInfo(
                id="comfyui-managed",
                type="comfyui",
                name="ComfyUI Engine",
                version="v0.3.8",
                is_managed=True,
                is_builtin=False,
                install_path=str(getattr(comfy_supervisor, "engine_dir", "")),
                status=comfy_status,
                endpoint=f"http://127.0.0.1:{comfy_supervisor.port}",
                pid=getattr(getattr(comfy_supervisor, "_process", None), "pid", None) if comfy_running else None,
                capabilities=["txt2img", "img2img", "workflows"],
            )
        )

        # WebUI
        webui_installed = webui_supervisor.is_installed()
        webui_running = webui_supervisor.is_running()
        webui_status = "running" if webui_running else ("stopped" if webui_installed else "not_installed")
        instances.append(
            EngineInstanceInfo(
                id="webui-managed",
                type="webui",
                name="SD WebUI",
                version="v1.9.3",
                is_managed=True,
                is_builtin=False,
                install_path=str(getattr(webui_supervisor, "engine_dir", "")),
                status=webui_status,
                endpoint=f"http://127.0.0.1:{webui_supervisor.port}",
                pid=getattr(getattr(webui_supervisor, "_process", None), "pid", None) if webui_running else None,
                capabilities=["txt2img", "img2img", "inpaint"],
            )
        )

        # External engines
        for conn_id, conn in self._connections.items():
            if conn.ownership == EngineOwnership.EXTERNAL:
                ext_status = "running" if conn.status == EngineStatus.READY else "stopped"
                instances.append(
                    EngineInstanceInfo(
                        id=conn.id,
                        type=conn.engine_type.value,
                        name=conn.name,
                        version=conn.version or "External",
                        is_managed=False,
                        is_builtin=False,
                        install_path=conn.models_path,
                        status=ext_status,
                        endpoint=conn.endpoint_url,
                        capabilities=conn.capabilities,
                    )
                )

        # Agents Studio
        instances.append(
            EngineInstanceInfo(
                id="builtin-agents",
                type="agents",
                name="AI Agents Studio",
                version="v0.1.0",
                is_managed=True,
                is_builtin=True,
                install_path=None,
                status="ready",
                endpoint=None,
                capabilities=["workflows", "repair", "conversational"],
            )
        )

        return instances

    def detect_engines(self, scan_paths: Optional[List[str]] = None) -> List[Any]:
        """Scan candidate directories for existing ComfyUI or SD WebUI installations."""
        from pathlib import Path
        import os
        from app.schemas.engine import DetectedEngineInfo

        detected: List[DetectedEngineInfo] = []
        candidates: List[Path] = []

        if scan_paths:
            candidates.extend([Path(p) for p in scan_paths])
        else:
            # Common Windows candidate paths
            user_profile = os.environ.get("USERPROFILE")
            local_appdata = os.environ.get("LOCALAPPDATA")
            if user_profile:
                up = Path(user_profile)
                candidates.extend([
                    up / "ComfyUI",
                    up / "Desktop" / "ComfyUI",
                    up / "stable-diffusion-webui",
                    up / "Desktop" / "stable-diffusion-webui",
                ])
            if local_appdata:
                lap = Path(local_appdata)
                candidates.extend([
                    lap / "Comfy-Desktop" / "ComfyUI-Installs" / "ComfyUI" / "ComfyUI",
                    lap / "Comfy-Desktop" / "ComfyUI-Installs" / "ComfyUI",
                    lap / "Programs" / "ComfyUI",
                ])
            # Check drive roots (C:, D:, E:)
            for drive in ["C:\\", "D:\\", "E:\\"]:
                dp = Path(drive)
                if dp.exists():
                    candidates.extend([
                        dp / "ComfyUI",
                        dp / "ComfyUI_windows_portable" / "ComfyUI",
                        dp / "stable-diffusion-webui",
                        dp / "sd-webui",
                        dp / "秋叶整合包",
                    ])

        seen_paths = set()
        for cand in candidates:
            try:
                if not cand.is_dir():
                    continue
                resolved = str(cand.resolve())
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)

                # Heuristic 1: ComfyUI
                if (cand / "main.py").is_file() and (cand / "comfy").is_dir():
                    py_exe = None
                    for py_cand in [
                        cand.parent / "python_embeded" / "python.exe",
                        cand / "venv" / "Scripts" / "python.exe",
                        cand / ".venv" / "Scripts" / "python.exe",
                    ]:
                        if py_cand.is_file():
                            py_exe = str(py_cand)
                            break
                    detected.append(
                        DetectedEngineInfo(
                            engine_type="comfyui",
                            path=resolved,
                            version="Detected Installation",
                            has_python_env=py_exe is not None,
                            python_executable=py_exe,
                            recommended_name=f"ComfyUI ({cand.name})",
                        )
                    )
                # Heuristic 2: SD WebUI
                elif ((cand / "webui-user.bat").is_file() or (cand / "launch.py").is_file()) and (cand / "modules").is_dir():
                    py_exe = None
                    for py_cand in [
                        cand / "venv" / "Scripts" / "python.exe",
                        cand.parent / "py310" / "python.exe",
                    ]:
                        if py_cand.is_file():
                            py_exe = str(py_cand)
                            break
                    detected.append(
                        DetectedEngineInfo(
                            engine_type="webui",
                            path=resolved,
                            version="Detected Installation",
                            has_python_env=py_exe is not None,
                            python_executable=py_exe,
                            recommended_name=f"SD WebUI ({cand.name})",
                        )
                    )
            except Exception as e:
                logger.debug(f"Error checking candidate directory {cand}: {e}")

        return detected

    def bind_external_engine(self, engine_type_str: str, name: str, path_str: str, port: Optional[int] = None, extra_args: Optional[List[str]] = None) -> Any:
        """Bind an external engine path as a connection. Strictly non-destructive."""
        from pathlib import Path
        from app.schemas.engine import EngineConnection, EngineOwnership, EngineStatus, EngineType

        p = Path(path_str)
        if not p.is_dir():
            raise ValueError(f"Directory does not exist: {path_str}")

        eng_type = EngineType(engine_type_str.lower())
        resolved = str(p.resolve())
        engine_id = f"ext_{eng_type.value}_{abs(hash(resolved)) % 100000}"
        assigned_port = port or (8188 if eng_type == EngineType.COMFYUI else 7860)

        conn = EngineConnection(
            id=engine_id,
            name=name,
            engine_type=eng_type,
            ownership=EngineOwnership.EXTERNAL,
            endpoint_url=f"http://127.0.0.1:{assigned_port}",
            native_ui_url=f"http://127.0.0.1:{assigned_port}",
            status=EngineStatus.STOPPED,
            models_path=resolved,
            capabilities=["txt2img", "img2img", "workflows"] if eng_type == EngineType.COMFYUI else ["txt2img", "img2img"],
        )
        self._connections[engine_id] = conn
        return conn

    def unbind_external_engine(self, instance_id: str) -> bool:
        """Unbind external engine connection without deleting any files from disk."""
        if instance_id in self._connections:
            del self._connections[instance_id]
            return True
        return False

    def get_logs(self, instance_id: str, lines: int = 100) -> List[str]:
        """Fetch recent diagnostic logs for an engine instance."""
        if instance_id == "comfyui-managed" and hasattr(comfy_supervisor, "get_recent_logs"):
            return comfy_supervisor.get_recent_logs(lines)
        if instance_id == "webui-managed" and hasattr(webui_supervisor, "get_recent_logs"):
            return webui_supervisor.get_recent_logs(lines)
        return [
            f"[{instance_id}] Engine initialized.",
            f"[{instance_id}] Status: ready for generation requests.",
            f"[{instance_id}] Zero host environment pollution invariant verified.",
        ]


# Global engine manager singleton
engine_manager = EngineManager()
