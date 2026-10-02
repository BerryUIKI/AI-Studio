"""
Creative Action Runner.

High-level dispatcher for primary canvas actions (txt2img, img2img, inpaint, upscale).
Coordinates execution across ComfyUI, Stable Diffusion WebUI, and Cloud APIs,
enforcing deterministic caching, provenance tracking, and content-addressable storage.
"""

import asyncio
import base64
import hashlib
import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.cache import cache_store
from app.runners.api_runner import (
    _call_fal_ai,
    _call_fal_ai_action,
    _call_fal_ai_video,
    _call_openai_images,
    _call_openai_inpaint,
    _call_siliconflow,
    _call_siliconflow_video,
)
from app.runners.comfy_runner import comfy_client
from app.runners.macro_compiler import (
    ASPECT_RATIO_DIMENSIONS,
    build_comfy_img2img_graph,
    build_comfy_img2video_graph,
    build_comfy_inpaint_graph,
    build_comfy_txt2img_graph,
    build_comfy_txt2video_graph,
    build_comfy_upscale_graph,
)
from app.runners.webui_runner import WebUIRunner
from app.runtime.credentials import credentials_manager
from app.schemas.cloud import CloudProviderId
from app.schemas.creative import (
    CreativeActionRequest,
    CreativeActionResult,
    CreativeActionType,
    GenerationProvenance,
)
from app.storage.asset_store import asset_store

logger = logging.getLogger(__name__)


def compute_creative_cache_hash(req: CreativeActionRequest, input_hash: str = "", mask_hash: str = "") -> str:
    """Compute deterministic semantic cache hash for a creative action."""
    canonical_payload = {
        "action": req.action.value,
        "prompt": req.prompt.strip(),
        "negative_prompt": req.negative_prompt.strip(),
        "model": req.model,
        "engine_id": req.engine_id,
        "width": req.width,
        "height": req.height,
        "steps": req.steps,
        "cfg_scale": req.cfg_scale,
        "seed": req.seed,
        "denoise": req.denoise,
        "input_hash": input_hash,
        "mask_hash": mask_hash,
        "upscale_factor": req.upscale_factor,
        "upscaler_name": req.upscaler_name,
        "fps": req.fps,
        "num_frames": req.num_frames,
        "motion_bucket_id": req.motion_bucket_id,
        "duration_seconds": req.duration_seconds,
    }
    raw = json.dumps(canonical_payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CreativeRunner:
    """Coordinates canvas-level image generation, inpainting, and upscaling."""

    def __init__(self) -> None:
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.active_cancellations: Dict[str, asyncio.Event] = {}

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel an active creative task and signal cancellation to engines."""
        cancel_event = self.active_cancellations.get(task_id)
        task_info = self.active_tasks.get(task_id, {})
        engine_id = task_info.get("engine", "")

        if cancel_event:
            cancel_event.set()

        interrupted = False
        disclaimer = None

        is_cloud = "cloud" in engine_id or engine_id in ("fal_ai", "fal", "siliconflow", "silicon", "openai")
        if "comfy" in engine_id:
            interrupted = await comfy_client.interrupt()
        elif "webui" in engine_id:
            runner = WebUIRunner()
            interrupted = await runner.interrupt()
        elif is_cloud:
            disclaimer = (
                "Cloud cancellation requested locally. Note: external cloud providers "
                "may continue asynchronous inference or incur compute charges."
            )

        return {
            "task_id": task_id,
            "status": "cancelled",
            "engine_interrupted": interrupted,
            "disclaimer": disclaimer,
        }

    async def execute(self, req: CreativeActionRequest) -> CreativeActionResult:
        task_id = f"task_{int(time.time() * 1000)}"
        start_time = time.monotonic()
        cancel_event = asyncio.Event()

        # Resolve aspect ratio dimensions if default 512
        if req.aspect_ratio in ASPECT_RATIO_DIMENSIONS:
            req.width, req.height = ASPECT_RATIO_DIMENSIONS[req.aspect_ratio]

        # Resolve randomized seed if -1
        actual_seed = req.seed if req.seed >= 0 else random.randint(1, 2147483647)
        req.seed = actual_seed

        # Retrieve content hashes of input/mask assets if supplied
        input_hash = ""
        mask_hash = ""
        input_file_path: Optional[Path] = None
        mask_file_path: Optional[Path] = None

        if req.input_image_id:
            rec = await asset_store.get_asset(req.input_image_id)
            if rec:
                input_hash = rec.content_hash
                input_file_path = asset_store.get_absolute_path(rec)

        if req.mask_image_id:
            m_rec = await asset_store.get_asset(req.mask_image_id)
            if m_rec:
                mask_hash = m_rec.content_hash
                mask_file_path = asset_store.get_absolute_path(m_rec)

        # Check deterministic cache
        cache_key = compute_creative_cache_hash(req, input_hash, mask_hash)
        cached_result = await cache_store.get_async(cache_key)
        is_video = req.action in (CreativeActionType.TXT2VIDEO, CreativeActionType.IMG2VIDEO)

        if cached_result:
            return CreativeActionResult(
                success=True,
                task_id=task_id,
                asset_id=cached_result.get("asset_id"),
                image_url=cached_result.get("image_url") if not is_video else None,
                video_url=cached_result.get("video_url") or (cached_result.get("image_url") if is_video else None),
                width=cached_result.get("width", req.width),
                height=cached_result.get("height", req.height),
                duration_seconds=cached_result.get("duration_seconds", req.duration_seconds if is_video else None),
                fps=cached_result.get("fps", req.fps if is_video else None),
                provenance=GenerationProvenance.model_validate(cached_result["provenance"]),
                is_cached=True,
            )

        # Register active task
        self.active_tasks[task_id] = {
            "action": req.action.value,
            "engine": req.engine_id,
            "start_time": time.time(),
        }
        self.active_cancellations[task_id] = cancel_event

        # Dispatch based on engine
        try:
            is_cloud = "cloud" in req.engine_id or req.engine_id in ("fal_ai", "fal", "siliconflow", "silicon", "openai")
            if "webui" in req.engine_id:
                if is_video:
                    raise ValueError("WebUI engine currently does not support native video generation. Use ComfyUI or Cloud.")
                runner = WebUIRunner()
                action_data = await runner.execute_action(req)
                asset_id = action_data["asset_id"]
                image_url = action_data["image_url"]
                out_w = action_data.get("width", req.width)
                out_h = action_data.get("height", req.height)
            elif "comfy" in req.engine_id:
                action_data = await self._run_comfy(req, input_file_path, mask_file_path)
                asset_id = action_data["asset_id"]
                image_url = action_data["image_url"]
                out_w = action_data.get("width", req.width)
                out_h = action_data.get("height", req.height)
            elif is_cloud:
                action_data = await self._run_cloud(req, input_file_path, mask_file_path)
                asset_id = action_data["asset_id"]
                image_url = action_data["image_url"]
                out_w = action_data.get("width", req.width)
                out_h = action_data.get("height", req.height)
            else:
                # Default to ComfyUI fallback
                action_data = await self._run_comfy(req, input_file_path, mask_file_path)
                asset_id = action_data["asset_id"]
                image_url = action_data["image_url"]
                out_w = action_data.get("width", req.width)
                out_h = action_data.get("height", req.height)

            if cancel_event.is_set():
                return CreativeActionResult(
                    success=False,
                    task_id=task_id,
                    error_message="Task cancelled by user.",
                    width=req.width,
                    height=req.height,
                )

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

            provenance = GenerationProvenance(
                action=req.action,
                prompt=req.prompt,
                negative_prompt=req.negative_prompt,
                model=req.model,
                engine_id=req.engine_id,
                seed=req.seed,
                steps=req.steps,
                cfg_scale=req.cfg_scale,
                dimensions=f"{out_w}x{out_h}",
                created_at=datetime.now(timezone.utc).isoformat(),
                source_asset_id=req.input_image_id,
                mask_asset_id=req.mask_image_id,
                execution_time_ms=elapsed_ms,
                fps=req.fps if is_video else None,
                num_frames=req.num_frames if is_video else None,
                duration_seconds=req.duration_seconds if is_video else None,
                motion_bucket_id=req.motion_bucket_id if is_video else None,
            )

            result = CreativeActionResult(
                success=True,
                task_id=task_id,
                asset_id=asset_id,
                image_url=image_url if not is_video else None,
                video_url=image_url if is_video else None,
                width=out_w,
                height=out_h,
                duration_seconds=req.duration_seconds if is_video else None,
                fps=req.fps if is_video else None,
                provenance=provenance,
                is_cached=False,
            )

            # Store in cache
            cache_payload = {
                "asset_id": asset_id,
                "image_url": image_url if not is_video else None,
                "video_url": image_url if is_video else None,
                "width": out_w,
                "height": out_h,
                "duration_seconds": req.duration_seconds if is_video else None,
                "fps": req.fps if is_video else None,
                "provenance": provenance.model_dump(),
            }
            await cache_store.set_async(cache_key, cache_payload)

            return result

        except Exception as e:
            logger.error(f"Creative action {req.action} failed: {e}")
            return CreativeActionResult(
                success=False,
                task_id=task_id,
                error_message=str(e),
                width=req.width,
                height=req.height,
            )
        finally:
            self.active_tasks.pop(task_id, None)
            self.active_cancellations.pop(task_id, None)

    async def _run_comfy(
        self,
        req: CreativeActionRequest,
        input_file: Optional[Path],
        mask_file: Optional[Path],
    ) -> Dict[str, Any]:
        """Compile and submit ComfyUI macro graph."""
        if req.action == CreativeActionType.TXT2IMG:
            prompt_graph = build_comfy_txt2img_graph(
                prompt=req.prompt,
                negative_prompt=req.negative_prompt,
                checkpoint=req.model,
                steps=req.steps,
                cfg=req.cfg_scale,
                aspect_ratio=req.aspect_ratio,
                seed=req.seed,
            )
        elif req.action == CreativeActionType.IMG2IMG:
            if not input_file:
                raise ValueError("Source image required for img2img")
            prompt_graph = build_comfy_img2img_graph(
                prompt=req.prompt,
                image_filename=input_file.name,
                negative_prompt=req.negative_prompt,
                checkpoint=req.model,
                steps=req.steps,
                cfg=req.cfg_scale,
                denoise=req.denoise,
                seed=req.seed,
            )
        elif req.action == CreativeActionType.INPAINT:
            if not input_file or not mask_file:
                raise ValueError("Source image and mask required for inpaint")
            prompt_graph = build_comfy_inpaint_graph(
                prompt=req.prompt,
                image_filename=input_file.name,
                mask_filename=mask_file.name,
                negative_prompt=req.negative_prompt,
                checkpoint=req.model,
                steps=req.steps,
                cfg=req.cfg_scale,
                denoise=req.denoise,
                seed=req.seed,
            )
        elif req.action == CreativeActionType.UPSCALE:
            if not input_file:
                raise ValueError("Source image required for upscale")
            prompt_graph = build_comfy_upscale_graph(
                image_filename=input_file.name,
                upscaler_model=req.upscaler_name or "RealESRGAN_x4plus.pth",
            )
        elif req.action == CreativeActionType.IMG2VIDEO:
            if not input_file:
                raise ValueError("Source image required for ComfyUI img2video")
            prompt_graph = build_comfy_img2video_graph(
                image_filename=input_file.name,
                checkpoint=req.model if "svd" in req.model.lower() else "svd_xt.safetensors",
                width=req.width,
                height=req.height,
                video_frames=req.num_frames,
                fps=req.fps,
                motion_bucket_id=req.motion_bucket_id,
                seed=req.seed,
                steps=req.steps,
                cfg=req.cfg_scale,
            )
        elif req.action == CreativeActionType.TXT2VIDEO:
            prompt_graph = build_comfy_txt2video_graph(
                prompt=req.prompt,
                negative_prompt=req.negative_prompt,
                checkpoint=req.model,
                width=req.width,
                height=req.height,
                video_frames=req.num_frames,
                fps=req.fps,
                seed=req.seed,
                steps=req.steps,
                cfg=req.cfg_scale,
            )
        else:
            raise ValueError(f"Unsupported action: {req.action}")

        # Queue prompt and poll history
        prompt_res = await comfy_client.queue_prompt(prompt_graph)
        prompt_id = prompt_res.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"Failed to queue ComfyUI prompt: {prompt_res}")

        outputs = await comfy_client.poll_history_outputs(prompt_id)
        if not outputs:
            raise RuntimeError("ComfyUI finished with no output media")

        first_img = outputs[0]
        # Download and store in local asset store
        filename = first_img.get("filename")
        subfolder = first_img.get("subfolder", "")
        img_type = first_img.get("type", "output")
        view_url = f"{comfy_client.base_url}/view?filename={filename}&subfolder={subfolder}&type={img_type}"

        is_video = req.action in (CreativeActionType.TXT2VIDEO, CreativeActionType.IMG2VIDEO)
        if is_video:
            asset = await asset_store.save_media_from_url(view_url, filename=filename or "comfy_video.webp", media_type="video")
        else:
            asset = await asset_store.save_image_from_url(view_url, filename=filename or "comfy_output.png")

        return {
            "asset_id": asset.id,
            "image_url": f"/api/v1/assets/{asset.id}/content",
            "width": req.width,
            "height": req.height,
        }

    async def _run_cloud(
        self,
        req: CreativeActionRequest,
        input_file: Optional[Path] = None,
        mask_file: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Dispatch creative action to cloud API using BYOK key."""
        model = req.model.lower()
        image_b64: Optional[str] = None
        mask_b64: Optional[str] = None
        image_bytes: Optional[bytes] = None
        mask_bytes: Optional[bytes] = None

        if input_file and input_file.is_file():
            image_bytes = input_file.read_bytes()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        if mask_file and mask_file.is_file():
            mask_bytes = mask_file.read_bytes()
            mask_b64 = base64.b64encode(mask_bytes).decode("utf-8")

        out_w = req.width
        out_h = req.height

        if req.action == CreativeActionType.INPAINT:
            if not image_bytes or not mask_bytes:
                raise ValueError("Source image and mask are required for cloud inpainting.")

            if "openai" in req.engine_id or "dall-e" in model:
                key = credentials_manager.get_key(CloudProviderId.OPENAI)
                if not key:
                    raise RuntimeError("OpenAI API key missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_openai_inpaint(req.prompt, image_bytes, mask_bytes, key)
            else:
                key = credentials_manager.get_key(CloudProviderId.FAL)
                if not key:
                    raise RuntimeError(
                        "Fal.ai API key is required for cloud inpainting. "
                        "Configure Fal.ai or OpenAI in Cloud Settings (BYOK)."
                    )
                remote_url = await _call_fal_ai_action(
                    action="inpaint",
                    prompt=req.prompt,
                    api_key=key,
                    image_b64=image_b64,
                    mask_b64=mask_b64,
                )

        elif req.action == CreativeActionType.UPSCALE:
            if not image_b64:
                raise ValueError("Source image is required for cloud upscaling.")

            key = credentials_manager.get_key(CloudProviderId.FAL)
            if not key:
                raise RuntimeError(
                    "Cloud upscaling requires Fal.ai API key. "
                    "OpenAI DALL-E 3 does not offer an upscaling endpoint. "
                    "Please configure a Fal.ai BYOK key or use local ComfyUI/WebUI."
                )
            remote_url = await _call_fal_ai_action(
                action="upscale",
                prompt=req.prompt,
                api_key=key,
                image_b64=image_b64,
                upscale_factor=req.upscale_factor,
            )
            out_w = int(req.width * req.upscale_factor)
            out_h = int(req.height * req.upscale_factor)

        elif req.action == CreativeActionType.IMG2IMG:
            if not image_b64:
                raise ValueError("Source image is required for cloud image-to-image.")

            key = credentials_manager.get_key(CloudProviderId.FAL)
            if not key:
                raise RuntimeError(
                    "Cloud image-to-image currently requires Fal.ai (FLUX img2img). "
                    "Please configure a Fal.ai BYOK key or use local ComfyUI/WebUI."
                )
            remote_url = await _call_fal_ai_action(
                action="img2img",
                prompt=req.prompt,
                api_key=key,
                image_b64=image_b64,
                denoise=req.denoise,
            )

        elif req.action == CreativeActionType.IMG2VIDEO:
            if not image_b64:
                raise ValueError("Source image is required for cloud img2video.")
            if req.engine_id in ("siliconflow", "silicon"):
                key_sf = credentials_manager.get_key(CloudProviderId.SILICONFLOW)
                if not key_sf:
                    raise RuntimeError("SiliconFlow API key missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_siliconflow_video(
                    action="img2video",
                    prompt=req.prompt,
                    api_key=key_sf,
                    image_b64=image_b64,
                )
            else:
                key_fal = credentials_manager.get_key(CloudProviderId.FAL)
                if not key_fal:
                    key_sf = credentials_manager.get_key(CloudProviderId.SILICONFLOW)
                    if key_sf:
                        remote_url = await _call_siliconflow_video(
                            action="img2video",
                            prompt=req.prompt,
                            api_key=key_sf,
                            image_b64=image_b64,
                        )
                    else:
                        raise RuntimeError(
                            "Cloud img2video requires a Fal.ai BYOK key (Fast SVD) or SiliconFlow key (CogVideoX). "
                            "Configure Fal.ai or SiliconFlow in Cloud Providers or use local ComfyUI."
                        )
                else:
                    remote_url = await _call_fal_ai_video(
                        action="img2video",
                        prompt=req.prompt,
                        api_key=key_fal,
                        image_b64=image_b64,
                        fps=req.fps,
                        num_frames=req.num_frames,
                        motion_bucket_id=req.motion_bucket_id,
                    )

        elif req.action == CreativeActionType.TXT2VIDEO:
            if req.engine_id in ("siliconflow", "silicon"):
                key_sf = credentials_manager.get_key(CloudProviderId.SILICONFLOW)
                if not key_sf:
                    raise RuntimeError("SiliconFlow API key missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_siliconflow_video(
                    action="txt2video",
                    prompt=req.prompt,
                    api_key=key_sf,
                )
            elif req.engine_id in ("fal_ai", "fal"):
                key_fal = credentials_manager.get_key(CloudProviderId.FAL)
                if not key_fal:
                    raise RuntimeError("Fal.ai API key missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_fal_ai_video(
                    action="txt2video",
                    prompt=req.prompt,
                    api_key=key_fal,
                    fps=req.fps,
                    num_frames=req.num_frames,
                )
            else:
                key_fal = credentials_manager.get_key(CloudProviderId.FAL)
                if key_fal:
                    remote_url = await _call_fal_ai_video(
                        action="txt2video",
                        prompt=req.prompt,
                        api_key=key_fal,
                        fps=req.fps,
                        num_frames=req.num_frames,
                    )
                else:
                    key_sf = credentials_manager.get_key(CloudProviderId.SILICONFLOW)
                    if not key_sf:
                        raise RuntimeError(
                            "No cloud API key configured for video generation. "
                            "Configure a Fal.ai or SiliconFlow BYOK key in Cloud Settings."
                        )
                    remote_url = await _call_siliconflow_video(
                        action="txt2video",
                        prompt=req.prompt,
                        api_key=key_sf,
                    )

        else:
            # TXT2IMG
            if "flux" in model or req.engine_id == "cloud_fal":
                provider_id = CloudProviderId.FAL
                key = credentials_manager.get_key(provider_id)
                if not key:
                    raise RuntimeError("Fal.ai API key is missing. Configure it in Cloud Providers (BYOK).")
                target_model = "flux-schnell" if "schnell" in model else "flux-dev"
                remote_url = await _call_fal_ai(target_model, req.prompt, req.width, req.height, key)
            elif "dall-e" in model or "openai" in req.engine_id:
                provider_id = CloudProviderId.OPENAI
                key = credentials_manager.get_key(provider_id)
                if not key:
                    raise RuntimeError("OpenAI API key is missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_openai_images(req.prompt, key)
            else:
                provider_id = CloudProviderId.SILICONFLOW
                key = credentials_manager.get_key(provider_id)
                if not key:
                    key = credentials_manager.get_key(CloudProviderId.FAL)
                    if key:
                        remote_url = await _call_fal_ai("flux-schnell", req.prompt, req.width, req.height, key)
                    else:
                        raise RuntimeError("No cloud provider API key configured. Please set up a BYOK key in Cloud Settings.")
                else:
                    remote_url = await _call_siliconflow(req.prompt, req.width, req.height, key)

        if not remote_url:
            raise RuntimeError(f"Cloud provider returned no media URL for action {req.action}.")

        is_video = req.action in (CreativeActionType.TXT2VIDEO, CreativeActionType.IMG2VIDEO)
        if is_video:
            asset = await asset_store.save_media_from_url(remote_url, filename="cloud_video.mp4", media_type="video")
        else:
            asset = await asset_store.save_image_from_url(remote_url, filename="cloud_output.png")

        return {
            "asset_id": asset.id,
            "image_url": f"/api/v1/assets/{asset.id}/content",
            "width": out_w,
            "height": out_h,
        }


creative_runner = CreativeRunner()
