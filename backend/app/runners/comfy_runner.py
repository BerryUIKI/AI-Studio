"""
ComfyUI Bridge Driver.

Provides asynchronous HTTP and WebSocket connectivity to an external or
sandboxed ComfyUI instance running on localhost (default: 8188).
Polls /history for real output files and persists them to managed asset storage.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from app.runners.macro_compiler import build_comfy_txt2img_graph
from app.schemas.events import (
    NodeErrorEvent,
    NodeOutputEvent,
    NodeProgressEvent,
    NodeStatusEvent,
    WorkflowEvent,
)
from app.storage.asset_store import asset_store

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

    async def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """Retrieve execution history for a given prompt_id."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/history/{prompt_id}")
            resp.raise_for_status()
            return resp.json()

    async def poll_history_outputs(
        self, prompt_id: str, max_wait: float = 120.0, interval: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Poll /history/{prompt_id} until completion, returning actual image output metadata.
        """
        elapsed = 0.0
        while elapsed < max_wait:
            try:
                history_data = await self.get_history(prompt_id)
                if prompt_id in history_data:
                    prompt_record = history_data[prompt_id]
                    status_info = prompt_record.get("status", {})
                    if status_info.get("status_str") == "error":
                        messages = status_info.get("messages", [])
                        raise RuntimeError(f"ComfyUI execution error: {messages}")

                    outputs = prompt_record.get("outputs", {})
                    images: List[Dict[str, Any]] = []
                    for node_output in outputs.values():
                        if "images" in node_output:
                            images.extend(node_output["images"])
                    if images:
                        return images
            except Exception as err:
                if "ComfyUI execution error" in str(err):
                    raise
                logger.debug("Polling history for %s: %s", prompt_id, err)

            await asyncio.sleep(interval)
            elapsed += interval

        raise TimeoutError(f"ComfyUI execution timed out after {max_wait}s for prompt {prompt_id}")

    def get_view_url(self, filename: str, subfolder: str = "", folder_type: str = "output") -> str:
        """Construct the view/download URL for a generated media file."""
        return f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"

    async def interrupt(self) -> bool:
        """Interrupt active execution on ComfyUI via POST /interrupt."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/interrupt")
                return resp.status_code == 200
        except Exception as err:
            logger.debug("ComfyUI interrupt failed or not reachable: %s", err)
            return False


# Global default ComfyUI client instance
comfy_client = ComfyUIClient()


async def run_comfy_txt2img_node(
    node_id: str,
    inputs: Dict[str, Any],
    params: Dict[str, Any],
) -> AsyncGenerator[WorkflowEvent, None]:
    """
    Execute an image.comfy.txt2img node by compiling it to a ComfyUI prompt DAG.
    Yields real-time streaming events and retrieves real outputs.
    """
    yield NodeStatusEvent(node_id=node_id, status="running")
    yield NodeProgressEvent(node_id=node_id, progress=0.05, message="Checking local ComfyUI connectivity...")

    status = await comfy_client.check_status()
    if not status["online"]:
        yield NodeErrorEvent(
            node_id=node_id,
            message=f"Local ComfyUI is offline at {comfy_client.base_url}. Please start ComfyUI or use cloud image generation.",
        )
        yield NodeStatusEvent(node_id=node_id, status="error")
        return

    prompt: str = inputs.get("prompt", "")
    negative_prompt: str = inputs.get("negative_prompt", "") or params.get("negative_prompt", "")
    checkpoint: str = params.get("checkpoint", "v1-5-pruned-emaonly.safetensors")
    steps: int = int(params.get("steps", 20))
    cfg: float = float(params.get("cfg", 7.0))
    aspect_ratio: str = params.get("aspect_ratio", "1:1")
    lora_name: Optional[str] = params.get("lora_name")

    yield NodeProgressEvent(node_id=node_id, progress=0.15, message="Compiling high-level parameters to ComfyUI DAG...")

    prompt_graph = build_comfy_txt2img_graph(
        prompt=prompt,
        negative_prompt=negative_prompt,
        checkpoint=checkpoint,
        steps=steps,
        cfg=cfg,
        aspect_ratio=aspect_ratio,
        lora_name=lora_name,
    )

    try:
        yield NodeProgressEvent(node_id=node_id, progress=0.25, message="Submitting workflow to ComfyUI /prompt...")
        result = await comfy_client.queue_prompt(prompt_graph)
        prompt_id = result.get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return a valid prompt_id")

        yield NodeProgressEvent(node_id=node_id, progress=0.4, message=f"Queued in ComfyUI (ID: {prompt_id[:8]}...)...")

        # Poll history for real rendered image outputs
        yield NodeProgressEvent(node_id=node_id, progress=0.6, message="Waiting for ComfyUI rendering to finish...")
        images = await comfy_client.poll_history_outputs(prompt_id)
        if not images:
            raise RuntimeError("ComfyUI completed but produced no image output records")

        primary_image = images[0]
        filename = primary_image.get("filename", "")
        subfolder = primary_image.get("subfolder", "")
        folder_type = primary_image.get("type", "output")
        remote_view_url = comfy_client.get_view_url(filename, subfolder, folder_type)

        yield NodeProgressEvent(node_id=node_id, progress=0.85, message="Adopting output into local asset store...")
        asset = await asset_store.save_image_from_url(remote_view_url, filename=filename)

        local_media_url = f"/api/v1/assets/{asset.id}/content"
        yield NodeProgressEvent(node_id=node_id, progress=1.0, message="Image rendered and persisted successfully.")
        yield NodeOutputEvent(
            node_id=node_id,
            output={
                "image": local_media_url,
                "asset_id": asset.id,
                "filename": filename,
                "content_hash": asset.content_hash,
            },
        )
        yield NodeStatusEvent(node_id=node_id, status="completed")

    except Exception as err:
        logger.exception("Error executing ComfyUI workflow: %s", err)
        yield NodeErrorEvent(node_id=node_id, message=f"ComfyUI execution failed: {err}")
        yield NodeStatusEvent(node_id=node_id, status="error")
