"""
Stable Diffusion WebUI REST API Runner.

Executes text-to-image, image-to-image, inpainting, and upscaling directly against
SD WebUI (/sdapi/v1/*), converting base64 image responses into managed assets.
"""

import base64
import logging
from typing import Any, Dict, Optional
import httpx

from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.storage.asset_store import asset_store

logger = logging.getLogger(__name__)


class WebUIRunner:
    """Dispatches creative generation requests to Stable Diffusion WebUI API."""

    def __init__(self, endpoint_url: str = "http://127.0.0.1:7860") -> None:
        self.endpoint_url = endpoint_url.rstrip("/")

    async def execute_action(self, req: CreativeActionRequest) -> Dict[str, Any]:
        """Execute creative action via SD WebUI REST API."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            if req.action == CreativeActionType.TXT2IMG:
                return await self._run_txt2img(client, req)
            elif req.action == CreativeActionType.IMG2IMG:
                return await self._run_img2img(client, req)
            elif req.action == CreativeActionType.INPAINT:
                return await self._run_inpaint(client, req)
            elif req.action == CreativeActionType.UPSCALE:
                return await self._run_upscale(client, req)
            else:
                raise ValueError(f"Unsupported action for WebUI: {req.action}")

    async def _run_txt2img(self, client: httpx.AsyncClient, req: CreativeActionRequest) -> Dict[str, Any]:
        payload = {
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            "steps": req.steps,
            "cfg_scale": req.cfg_scale,
            "width": req.width,
            "height": req.height,
            "seed": req.seed if req.seed >= 0 else -1,
        }
        resp = await client.post(f"{self.endpoint_url}/sdapi/v1/txt2img", json=payload)
        resp.raise_for_status()
        data = resp.json()
        images = data.get("images", [])
        if not images:
            raise RuntimeError("WebUI returned no images")

        img_bytes = base64.b64decode(images[0])
        asset = await asset_store.save_bytes(img_bytes, filename="webui_txt2img.png", media_type="image/png")
        return {
            "asset_id": asset.id,
            "image_url": f"/api/v1/assets/{asset.id}/content",
            "width": req.width,
            "height": req.height,
        }

    async def _run_img2img(self, client: httpx.AsyncClient, req: CreativeActionRequest) -> Dict[str, Any]:
        if not req.input_image_id:
            raise ValueError("Input image ID required for img2img")

        rec = await asset_store.get_asset(req.input_image_id)
        if not rec:
            raise ValueError(f"Asset '{req.input_image_id}' not found")
        abs_path = asset_store.get_absolute_path(rec)
        init_b64 = base64.b64encode(abs_path.read_bytes()).decode("utf-8")

        payload = {
            "init_images": [init_b64],
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            "steps": req.steps,
            "cfg_scale": req.cfg_scale,
            "denoising_strength": req.denoise,
            "seed": req.seed if req.seed >= 0 else -1,
        }
        resp = await client.post(f"{self.endpoint_url}/sdapi/v1/img2img", json=payload)
        resp.raise_for_status()
        data = resp.json()
        images = data.get("images", [])
        if not images:
            raise RuntimeError("WebUI returned no images")

        img_bytes = base64.b64decode(images[0])
        asset = await asset_store.save_bytes(img_bytes, filename="webui_img2img.png", media_type="image/png")
        return {
            "asset_id": asset.id,
            "image_url": f"/api/v1/assets/{asset.id}/content",
            "width": req.width,
            "height": req.height,
        }

    async def _run_inpaint(self, client: httpx.AsyncClient, req: CreativeActionRequest) -> Dict[str, Any]:
        if not req.input_image_id or not req.mask_image_id:
            raise ValueError("Both input image and mask image required for inpaint")

        img_rec = await asset_store.get_asset(req.input_image_id)
        mask_rec = await asset_store.get_asset(req.mask_image_id)
        if not img_rec or not mask_rec:
            raise ValueError("Input or mask asset missing on disk")

        img_b64 = base64.b64encode(asset_store.get_absolute_path(img_rec).read_bytes()).decode("utf-8")
        mask_b64 = base64.b64encode(asset_store.get_absolute_path(mask_rec).read_bytes()).decode("utf-8")

        payload = {
            "init_images": [img_b64],
            "mask": mask_b64,
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            "steps": req.steps,
            "cfg_scale": req.cfg_scale,
            "denoising_strength": req.denoise,
            "inpainting_fill": 1,
            "inpaint_full_res": True,
            "seed": req.seed if req.seed >= 0 else -1,
        }
        resp = await client.post(f"{self.endpoint_url}/sdapi/v1/img2img", json=payload)
        resp.raise_for_status()
        data = resp.json()
        images = data.get("images", [])
        if not images:
            raise RuntimeError("WebUI returned no images")

        img_bytes = base64.b64decode(images[0])
        asset = await asset_store.save_bytes(img_bytes, filename="webui_inpaint.png", media_type="image/png")
        return {
            "asset_id": asset.id,
            "image_url": f"/api/v1/assets/{asset.id}/content",
            "width": req.width,
            "height": req.height,
        }

    async def _run_upscale(self, client: httpx.AsyncClient, req: CreativeActionRequest) -> Dict[str, Any]:
        if not req.input_image_id:
            raise ValueError("Input image ID required for upscaling")

        rec = await asset_store.get_asset(req.input_image_id)
        if not rec:
            raise ValueError(f"Asset '{req.input_image_id}' not found")
        abs_path = asset_store.get_absolute_path(rec)
        img_b64 = base64.b64encode(abs_path.read_bytes()).decode("utf-8")

        payload = {
            "image": img_b64,
            "upscaling_resize": req.upscale_factor,
            "upscaler_1": req.upscaler_name or "R-ESRGAN 4x+",
        }
        resp = await client.post(f"{self.endpoint_url}/sdapi/v1/extra-single-image", json=payload)
        resp.raise_for_status()
        data = resp.json()
        img_b64_out = data.get("image")
        if not img_b64_out:
            raise RuntimeError("WebUI returned no upscaled image")

        img_bytes = base64.b64decode(img_b64_out)
        asset = await asset_store.save_bytes(img_bytes, filename="webui_upscaled.png", media_type="image/png")
        new_width = int(req.width * req.upscale_factor)
        new_height = int(req.height * req.upscale_factor)
        return {
            "asset_id": asset.id,
            "image_url": f"/api/v1/assets/{asset.id}/content",
            "width": new_width,
            "height": new_height,
        }


webui_runner = WebUIRunner()
