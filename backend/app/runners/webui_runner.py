"""
Stable Diffusion WebUI REST API Runner.

Executes text-to-image, image-to-image, inpainting, and upscaling directly against
SD WebUI (/sdapi/v1/*), converting base64 image responses into managed assets.
"""

import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.storage.asset_store import asset_store
from app.runners.mask_converter import normalize_mask_for_webui, validate_mask_dimensions

logger = logging.getLogger(__name__)


class WebUIRunner:
    """Dispatches creative generation requests to Stable Diffusion WebUI API."""

    def __init__(self, endpoint_url: str = "http://127.0.0.1:7860") -> None:
        self.endpoint_url = endpoint_url.rstrip("/")

    async def get_models(self, client: Optional[httpx.AsyncClient] = None) -> List[Dict[str, Any]]:
        """Retrieve available checkpoints from SD WebUI (/sdapi/v1/sd-models)."""
        is_local = "127.0.0.1" in self.endpoint_url or "localhost" in self.endpoint_url
        if client is not None:
            resp = await client.get(f"{self.endpoint_url}/sdapi/v1/sd-models")
            resp.raise_for_status()
            return resp.json()
        async with httpx.AsyncClient(timeout=30.0, trust_env=not is_local) as c:
            resp = await c.get(f"{self.endpoint_url}/sdapi/v1/sd-models")
            resp.raise_for_status()
            return resp.json()

    async def resolve_checkpoint(
        self, client: httpx.AsyncClient, requested_model: Optional[str]
    ) -> Dict[str, Any]:
        """Validate and resolve requested model checkpoint against WebUI available models.

        Raises ValueError if requested_model is not installed or available.
        """
        models = await self.get_models(client=client)
        if not models:
            raise ValueError("No checkpoint models available in WebUI (/sdapi/v1/sd-models returned empty list).")

        if not requested_model:
            # Check current options if available
            try:
                opt_resp = await client.get(f"{self.endpoint_url}/sdapi/v1/options")
                if opt_resp.status_code == 200:
                    current_ckpt = (opt_resp.json().get("sd_model_checkpoint") or "").lower()
                    if current_ckpt:
                        for m in models:
                            if current_ckpt in (m.get("title", "").lower(), m.get("model_name", "").lower()):
                                return m
            except Exception:
                pass
            return models[0]

        target = requested_model.strip().lower()
        target_clean = target.removesuffix(".safetensors").removesuffix(".ckpt").strip()

        # 1. Exact match on title, model_name, filename, or stem
        for m in models:
            title = m.get("title", "").strip().lower()
            model_name = m.get("model_name", "").strip().lower()
            filename = Path(m.get("filename", "")).name.lower()
            stem = Path(m.get("filename", "")).stem.lower()

            if target in (title, model_name, filename, stem):
                return m
            if target_clean in (model_name, stem):
                return m

        # 2. Substring or prefix match (e.g. target matches title prefix before hash)
        for m in models:
            title = m.get("title", "").strip().lower()
            if target in title or title.startswith(target) or (target_clean and target_clean in title):
                return m

        available = [m.get("title") or m.get("model_name") for m in models]
        raise ValueError(
            f"Model checkpoint '{requested_model}' is not available in WebUI. "
            f"Available checkpoints: {available}"
        )

    async def execute_action(
        self, req: CreativeActionRequest, client: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Any]:
        """Execute creative action via SD WebUI REST API."""
        if client is not None:
            return await self._dispatch_action(client, req)

        is_local = "127.0.0.1" in self.endpoint_url or "localhost" in self.endpoint_url
        async with httpx.AsyncClient(timeout=120.0, trust_env=not is_local) as c:
            return await self._dispatch_action(c, req)

    async def _dispatch_action(self, client: httpx.AsyncClient, req: CreativeActionRequest) -> Dict[str, Any]:
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

    async def interrupt(self) -> bool:
        """Interrupt active execution on SD WebUI via POST /sdapi/v1/interrupt."""
        try:
            is_local = "127.0.0.1" in self.endpoint_url or "localhost" in self.endpoint_url
            async with httpx.AsyncClient(timeout=5.0, trust_env=not is_local) as client:
                resp = await client.post(f"{self.endpoint_url}/sdapi/v1/interrupt")
                return resp.status_code == 200
        except Exception as err:
            logger.debug("WebUI interrupt failed or not reachable: %s", err)
            return False

    async def _run_txt2img(self, client: httpx.AsyncClient, req: CreativeActionRequest) -> Dict[str, Any]:
        checkpoint_info = await self.resolve_checkpoint(client, req.model)
        checkpoint_title = checkpoint_info.get("title") or req.model
        effective_model = checkpoint_info.get("title") or checkpoint_info.get("model_name") or req.model
        model_hash = checkpoint_info.get("hash") or checkpoint_info.get("sha256") or ""

        payload = {
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            "steps": req.steps,
            "cfg_scale": req.cfg_scale,
            "width": req.width,
            "height": req.height,
            "seed": req.seed if req.seed >= 0 else -1,
            "override_settings": {
                "sd_model_checkpoint": checkpoint_title,
            },
            "override_settings_restore_afterwards": False,
            "sd_model_checkpoint": checkpoint_title,
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
            "width": asset.width or req.width,
            "height": asset.height or req.height,
            "effective_model": effective_model,
            "model_hash": model_hash,
            "model_revision": model_hash,
        }

    async def _run_img2img(self, client: httpx.AsyncClient, req: CreativeActionRequest) -> Dict[str, Any]:
        if not req.input_image_id:
            raise ValueError("Input image ID required for img2img")

        checkpoint_info = await self.resolve_checkpoint(client, req.model)
        checkpoint_title = checkpoint_info.get("title") or req.model
        effective_model = checkpoint_info.get("title") or checkpoint_info.get("model_name") or req.model
        model_hash = checkpoint_info.get("hash") or checkpoint_info.get("sha256") or ""

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
            "override_settings": {
                "sd_model_checkpoint": checkpoint_title,
            },
            "override_settings_restore_afterwards": False,
            "sd_model_checkpoint": checkpoint_title,
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
            "width": asset.width or req.width,
            "height": asset.height or req.height,
            "effective_model": effective_model,
            "model_hash": model_hash,
            "model_revision": model_hash,
        }

    async def _run_inpaint(self, client: httpx.AsyncClient, req: CreativeActionRequest) -> Dict[str, Any]:
        if not req.input_image_id or not req.mask_image_id:
            raise ValueError("Both input image and mask image required for inpaint")

        checkpoint_info = await self.resolve_checkpoint(client, req.model)
        checkpoint_title = checkpoint_info.get("title") or req.model
        effective_model = checkpoint_info.get("title") or checkpoint_info.get("model_name") or req.model
        model_hash = checkpoint_info.get("hash") or checkpoint_info.get("sha256") or ""

        img_rec = await asset_store.get_asset(req.input_image_id)
        mask_rec = await asset_store.get_asset(req.mask_image_id)
        if not img_rec or not mask_rec:
            raise ValueError("Input or mask asset missing on disk")

        img_path = asset_store.get_absolute_path(img_rec)
        mask_path = asset_store.get_absolute_path(mask_rec)

        # Validate mask dimensions match source (Issue #106)
        from PIL import Image
        with Image.open(img_path) as source_img:
            validate_mask_dimensions(mask_path, source_img.width, source_img.height)

        # Convert mask for WebUI (Issue #106): grayscale white=edit, black=protect
        mask_bytes = mask_path.read_bytes()
        converted_mask_bytes = normalize_mask_for_webui(mask_bytes)

        img_b64 = base64.b64encode(img_path.read_bytes()).decode("utf-8")
        mask_b64 = base64.b64encode(converted_mask_bytes).decode("utf-8")

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
            "override_settings": {
                "sd_model_checkpoint": checkpoint_title,
            },
            "override_settings_restore_afterwards": False,
            "sd_model_checkpoint": checkpoint_title,
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
            "width": asset.width or req.width,
            "height": asset.height or req.height,
            "effective_model": effective_model,
            "model_hash": model_hash,
            "model_revision": model_hash,
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
        new_width = int(round(req.width * req.upscale_factor))
        new_height = int(round(req.height * req.upscale_factor))
        asset_w = getattr(asset, "width", None)
        asset_h = getattr(asset, "height", None)
        asset_id = getattr(asset, "id", None)
        final_w = asset_w if isinstance(asset_w, int) else new_width
        final_h = asset_h if isinstance(asset_h, int) else new_height
        return {
            "asset_id": asset_id,
            "image_url": f"/api/v1/assets/{asset_id}/content" if asset_id else "",
            "width": final_w,
            "height": final_h,
        }


webui_runner = WebUIRunner()
