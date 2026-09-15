"""
ComfyUI Bridge Driver.

Provides asynchronous HTTP and WebSocket connectivity to an external or
sandboxed ComfyUI instance running on localhost (default: 8188).
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """Client for communicating with ComfyUI REST API and WebSocket events."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{self.host}:{self.port}"
        self.ws_url = f"ws://{self.host}:{self.port}/ws"

    async def check_status(self) -> Dict[str, Any]:
        """
        Probe ComfyUI instance liveness and hardware stats.
        Returns a dict with 'online' boolean and device stats if available.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/system_stats")
                if resp.status_code == 200:
                    data = resp.json()
                    devices = data.get("devices", [])
                    return {
                        "online": True,
                        "host": self.host,
                        "port": self.port,
                        "devices": devices,
                        "system": data.get("system", {}),
                    }
        except (httpx.ConnectError, httpx.TimeoutException, Exception) as err:
            logger.debug("ComfyUI offline or unreachable: %s", err)

        return {
            "online": False,
            "host": self.host,
            "port": self.port,
            "devices": [],
            "message": "ComfyUI instance not reachable",
        }

    async def get_models(self) -> Dict[str, List[str]]:
        """Retrieve lists of available checkpoints and LoRA models from ComfyUI."""
        checkpoints: List[str] = []
        loras: List[str] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/object_info")
                if resp.status_code == 200:
                    info = resp.json()
                    ckpt_loader = info.get("CheckpointLoaderSimple", {})
                    input_info = ckpt_loader.get("input", {}).get("required", {})
                    ckpt_names = input_info.get("ckpt_name", [[]])[0]
                    if isinstance(ckpt_names, list):
                        checkpoints = ckpt_names

                    lora_loader = info.get("LoraLoader", {})
                    lora_input = lora_loader.get("input", {}).get("required", {})
                    lora_names = lora_input.get("lora_name", [[]])[0]
                    if isinstance(lora_names, list):
                        loras = lora_names
        except Exception as err:
            logger.debug("Failed to retrieve ComfyUI models: %s", err)

        return {
            "checkpoints": checkpoints,
            "loras": loras,
        }

    async def queue_prompt(self, prompt_graph: Dict[str, Any], client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Submit a prompt execution DAG to ComfyUI's /prompt endpoint.
        Returns prompt_id and queue number.
        """
        cid = client_id or str(uuid.uuid4())
        payload = {"prompt": prompt_graph, "client_id": cid}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/prompt", json=payload)
            resp.raise_for_status()
            return resp.json()

    def get_view_url(self, filename: str, subfolder: str = "", folder_type: str = "output") -> str:
        """Construct the view/download URL for a generated media file."""
        return f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"


# Global default ComfyUI client instance
comfy_client = ComfyUIClient()
