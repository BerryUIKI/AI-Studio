"""
Creative Action Runner.

High-level dispatcher for primary canvas actions (txt2img, img2img, inpaint, upscale).
Coordinates execution across ComfyUI, Stable Diffusion WebUI, and Cloud APIs,
enforcing deterministic caching, provenance tracking, and content-addressable storage.

Connection Routing (Issue #127):
- Resolves stable connection_id from request to engine endpoint
- Creates type-specific clients for each resolved connection
- Ensures all operations (upload, queue, poll, cancel) use the same connection
- Prevents cross-connection cache reuse
"""

import asyncio
import base64
import hashlib
import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from app.core.cache import cache_store
from app.core.task_registry import task_registry
from app.runtime.engine_manager import engine_manager
from app.schemas.engine import EngineConnection, EngineType, EngineOwnership
from app.runners.api_runner import (
    _call_fal_ai,
    _call_fal_ai_action,
    _call_fal_ai_video,
    _call_openai_images,
    _call_openai_inpaint,
    _call_siliconflow,
    _call_siliconflow_video,
)
from app.runners.comfy_runner import ComfyUIClient
from app.runners.macro_compiler import (
    ASPECT_RATIO_DIMENSIONS,
    build_comfy_img2img_graph,
    build_comfy_img2video_graph,
    build_comfy_inpaint_graph,
    build_comfy_txt2img_graph,
    build_comfy_txt2video_graph,
    build_comfy_upscale_graph,
)
from app.runners.mask_converter import (
    normalize_mask_for_comfyui,
    normalize_mask_for_openai,
    normalize_mask_for_webui,
    normalize_mask_for_fal_ai,
    validate_mask_dimensions,
)
from app.runners.webui_runner import WebUIRunner
from app.runtime.credentials import credentials_manager
from app.schemas.cloud import CloudProviderId
from app.schemas.creative import (
    CreativeActionRequest,
    CreativeActionResult,
    CreativeActionType,
    CreativeExecutionPlan,
    GenerationProvenance,
)
from app.storage.asset_store import asset_store
from app.storage.task_store import execution_task, task_store
from app.schemas.task import RunRecord, TaskRecord

logger = logging.getLogger(__name__)


def resolve_execution_plan(req: CreativeActionRequest) -> CreativeExecutionPlan:
    """Resolve a unified capability-checked execution plan for a creative action (Invariant #5).

    The resolved plan is the single source of truth for:
    1. Pre-execution dispatch
    2. Deterministic cache key hashing
    3. Provenance and UI disclosure
    """
    engine_id = (req.engine_id or "").lower()
    model = (req.model or "").lower()
    action = req.action

    if "webui" in engine_id:
        if action in (CreativeActionType.TXT2VIDEO, CreativeActionType.IMG2VIDEO):
            raise ValueError("WebUI engine currently does not support native video generation. Use ComfyUI or Cloud.")
        return CreativeExecutionPlan(
            engine="webui",
            provider_id="webui",
            target_model=req.model,
            action=action,
        )

    if "comfy" in engine_id:
        return CreativeExecutionPlan(
            engine="comfyui",
            provider_id="comfyui",
            target_model=req.model,
            action=action,
        )

    # Cloud Engine resolution
    # 1. Explicit cloud provider requested
    if engine_id in ("fal_ai", "fal", "cloud_fal"):
        target_model = req.model
        if action == CreativeActionType.TXT2IMG:
            target_model = "flux-schnell" if "schnell" in model else ("flux-dev" if "flux" in model else req.model)
        elif action == CreativeActionType.IMG2VIDEO:
            target_model = req.model if "svd" in model else "svd_xt"
        return CreativeExecutionPlan(
            engine="cloud",
            provider_id="fal_ai",
            target_model=target_model,
            action=action,
        )

    if engine_id in ("siliconflow", "silicon", "cloud_siliconflow"):
        if action in (CreativeActionType.UPSCALE, CreativeActionType.IMG2IMG):
            raise ValueError(
                f"SiliconFlow does not support {action.value}. Use Fal.ai or local ComfyUI/WebUI."
            )
        target_model = req.model
        if action == CreativeActionType.TXT2VIDEO:
            target_model = req.model if "cogvideo" in model else "CogVideoX-5b"
        elif action == CreativeActionType.IMG2VIDEO:
            target_model = req.model if "cogvideo" in model else "CogVideoX-5b-I2V"
        elif action == CreativeActionType.TXT2IMG:
            target_model = req.model or "stabilityai/stable-diffusion-xl-base-1.0"
        return CreativeExecutionPlan(
            engine="cloud",
            provider_id="siliconflow",
            target_model=target_model,
            action=action,
        )

    if engine_id in ("openai", "cloud_openai"):
        if action in (CreativeActionType.UPSCALE, CreativeActionType.IMG2IMG, CreativeActionType.TXT2VIDEO, CreativeActionType.IMG2VIDEO):
            raise ValueError(
                f"OpenAI does not support {action.value}. Use Fal.ai, SiliconFlow, or local ComfyUI."
            )
        target_model = req.model if "dall-e" in model else "dall-e-3"
        return CreativeExecutionPlan(
            engine="cloud",
            provider_id="openai",
            target_model=target_model,
            action=action,
        )

    # 2. Generic cloud engine (engine_id == "cloud", "cloud_default", etc.)
    if action == CreativeActionType.INPAINT:
        if "dall-e" in model:
            return CreativeExecutionPlan(engine="cloud", provider_id="openai", target_model=req.model, action=action)
        return CreativeExecutionPlan(engine="cloud", provider_id="fal_ai", target_model=req.model, action=action)

    if action in (CreativeActionType.UPSCALE, CreativeActionType.IMG2IMG):
        return CreativeExecutionPlan(engine="cloud", provider_id="fal_ai", target_model=req.model, action=action)

    if action == CreativeActionType.IMG2VIDEO:
        if not credentials_manager.get_key(CloudProviderId.FAL) and credentials_manager.get_key(CloudProviderId.SILICONFLOW):
            return CreativeExecutionPlan(engine="cloud", provider_id="siliconflow", target_model=req.model or "CogVideoX-5b-I2V", action=action)
        return CreativeExecutionPlan(engine="cloud", provider_id="fal_ai", target_model=req.model or "svd_xt", action=action)

    if action == CreativeActionType.TXT2VIDEO:
        if credentials_manager.get_key(CloudProviderId.FAL):
            return CreativeExecutionPlan(engine="cloud", provider_id="fal_ai", target_model=req.model or "fast-svd-lcm", action=action)
        if credentials_manager.get_key(CloudProviderId.SILICONFLOW):
            return CreativeExecutionPlan(engine="cloud", provider_id="siliconflow", target_model=req.model or "CogVideoX-5b", action=action)
        return CreativeExecutionPlan(engine="cloud", provider_id="fal_ai", target_model=req.model or "fast-svd-lcm", action=action)

    # TXT2IMG
    if "flux" in model:
        target_model = "flux-schnell" if "schnell" in model else "flux-dev"
        return CreativeExecutionPlan(engine="cloud", provider_id="fal_ai", target_model=target_model, action=action)
    if "dall-e" in model:
        return CreativeExecutionPlan(engine="cloud", provider_id="openai", target_model=req.model, action=action)
    if credentials_manager.get_key(CloudProviderId.SILICONFLOW):
        return CreativeExecutionPlan(engine="cloud", provider_id="siliconflow", target_model=req.model or "stabilityai/stable-diffusion-xl-base-1.0", action=action)
    if credentials_manager.get_key(CloudProviderId.FAL):
        return CreativeExecutionPlan(engine="cloud", provider_id="fal_ai", target_model="flux-schnell", action=action)
    return CreativeExecutionPlan(engine="cloud", provider_id="cloud_default", target_model=req.model, action=action)


def resolve_effective_provider(req: CreativeActionRequest) -> str:
    """Resolve the concrete provider identity that will execute this request (Invariant #5)."""
    return resolve_execution_plan(req).provider_id


def compute_creative_cache_hash(
    req: CreativeActionRequest,
    connection_id: str,
    input_hash: str = "",
    mask_hash: str = "",
    provider_id: Optional[str] = None,
) -> str:
    """Compute deterministic semantic cache hash for a creative action (Invariant #5).

    Cache version updated for Issue #127: connection routing.
    Results from different engine connections must not be reused.
    """
    effective_provider = provider_id or resolve_effective_provider(req)
    canonical_payload = {
        "action": req.action.value,
        "prompt": req.prompt.strip(),
        "negative_prompt": req.negative_prompt.strip(),
        "model": req.model,
        "connection_id": connection_id,  # Isolate by connection
        "provider_id": effective_provider,
        "runner_version": "0.4.0",  # Explicit grayscale cloud masks and dimension validation
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

    def _resolve_connection(
        self,
        connection_id: Optional[str],
        engine_id: Optional[str]
    ) -> EngineConnection:
        """
        Resolve stable engine connection from request (Issue #127).

        Resolution chain:
        1. Explicit connection_id from request (preferred)
        2. Map legacy engine_id to default managed connection
        3. Raise error if neither resolves

        Args:
            connection_id: Stable connection identifier (e.g., "comfyui-managed", "studio-a100")
            engine_id: Legacy engine identifier (deprecated)

        Returns:
            Resolved EngineConnection

        Raises:
            ValueError: If connection cannot be resolved or doesn't exist
        """
        # Priority 1: Explicit connection_id
        if connection_id:
            connection = engine_manager.get_engine(connection_id)
            if not connection:
                available = list(engine_manager.list_connections().keys())
                raise ValueError(
                    f"Engine connection '{connection_id}' not found. "
                    f"Available connections: {available}"
                )
            return connection

        # Priority 2: Legacy engine_id mapping
        if engine_id:
            logger.warning(
                f"Using legacy engine_id '{engine_id}' without connection_id. "
                f"Please migrate to explicit connection_id in future requests."
            )

            # Map legacy engine_id to default managed connections
            if engine_id in ("comfyui", "managed_comfyui"):
                connection = engine_manager.get_engine("comfyui-managed")
                if connection:
                    return connection
            elif engine_id in ("webui", "managed_webui"):
                connection = engine_manager.get_engine("webui-managed")
                if connection:
                    return connection

            # If mapped connection doesn't exist, fall through to error

        # Priority 3: No valid identifier provided
        raise ValueError(
            "No connection_id or engine_id provided in request. "
            "Please specify connection_id for proper engine routing."
        )

    def _create_client(self, connection: EngineConnection):
        """
        Create type-specific client for resolved connection (Issue #127).

        Args:
            connection: Resolved engine connection

        Returns:
            ComfyUIClient or WebUIRunner configured for this connection

        Raises:
            ValueError: If engine type is unsupported
        """
        if connection.engine_type == EngineType.COMFYUI:
            # Parse connection endpoint_url to extract host/port
            parsed = urlparse(connection.endpoint_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 8188

            # Create client with full configured URL (not reconstructed)
            return ComfyUIClient(host=host, port=port, base_url=connection.endpoint_url)

        elif connection.engine_type == EngineType.WEBUI:
            # WebUIRunner uses full endpoint URL
            return WebUIRunner(endpoint_url=connection.endpoint_url)

        else:
            raise ValueError(
                f"Unsupported engine type '{connection.engine_type}' "
                f"for connection '{connection.id}'"
            )

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel an active creative task and signal cancellation to engines (Issue #127)."""
        cancel_event = self.active_cancellations.get(task_id)
        task_info = self.active_tasks.get(task_id, {})

        if cancel_event:
            cancel_event.set()

        # Cloud task cancellation disclaimer
        engine_id = task_info.get("engine", "")
        is_cloud = "cloud" in engine_id or engine_id in ("fal_ai", "fal", "siliconflow", "silicon", "openai")
        disclaimer = ("External cloud providers may continue work and incur charges; remote cancellation is not confirmed."
                      if is_cloud else "This engine has no task-scoped active abort; awaiting the actual outcome to avoid interrupting other jobs.")

        return {
            "task_id": task_id,
            "status": "cancel-requested",
            "engine_interrupted": False,
            "disclaimer": disclaimer,
        }

    async def execute(self, req: CreativeActionRequest, task_id: Optional[str] = None) -> CreativeActionResult:
        """Snapshot and persist every outcome, including cached and preflight failures."""
        req = req.model_copy(deep=True)
        task_id = task_id or f"task_{uuid.uuid4()}"
        if await task_store.get_run(task_id) is None:
            await task_store.create_run(RunRecord(id=task_id, project_id=req.project_id, request=req.model_dump()))
        task = TaskRecord(id=task_id, run_id=task_id, node_id="canvas", node_type=req.action.value,
                          params=req.model_dump(), inputs={"source_asset_id": req.input_image_id, "mask_asset_id": req.mask_image_id})
        await task_store.save_task(task)
        task.status = "running"
        await task_store.save_task(task)
        await task_store.finish_run(task_id, "running")
        context_token = execution_task.set((task_store, task))
        try:
            result = await self._execute(req, task_id, task)
            task.params = req.model_dump()
            task.outputs = result.model_dump()
            task.error = result.error_message
            task.status = "cached" if result.is_cached else ("succeeded" if result.success else "failed")
            if result.error_message == "Task cancelled by user.":
                task.status = "cancelled"
            if result.provenance:
                task.metadata.update({"engine": "cloud" if result.provenance.provider_id not in ("comfyui", "webui") else result.provenance.provider_id,
                                      "provider_id": result.provenance.provider_id, "connection_id": result.provenance.connection_id})
            return result
        except BaseException as error:
            task.status = "interrupted" if isinstance(error, asyncio.CancelledError) else "failed"
            task.error = str(error) or "Execution interrupted"
            raise
        finally:
            execution_task.reset(context_token)
            await task_store.save_task(task)
            await task_store.finish_run(task_id, task.status)

    async def _execute(self, req: CreativeActionRequest, task_id: str, persisted: TaskRecord) -> CreativeActionResult:
        start_time = time.monotonic()
        cancel_event = task_registry.get_cancel_event(task_id) or asyncio.Event()
        is_video = req.action in (CreativeActionType.TXT2VIDEO, CreativeActionType.IMG2VIDEO)

        source_dependent_actions = (
            CreativeActionType.UPSCALE,
            CreativeActionType.IMG2IMG,
            CreativeActionType.INPAINT,
            CreativeActionType.IMG2VIDEO,
        )

        # Resolve aspect ratio dimensions for generation actions without a source image.
        # Prevent generation aspect-ratio defaults from overwriting dimensions for source-dependent editing actions.
        if req.action not in source_dependent_actions:
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
        source_width: Optional[int] = None
        source_height: Optional[int] = None

        if req.input_image_id:
            rec = await asset_store.get_asset(req.input_image_id)
            if rec:
                input_hash = rec.content_hash
                input_file_path = asset_store.get_absolute_path(rec)
                source_width = rec.width
                source_height = rec.height

        # Inspect disk file if source width/height were not in record
        if input_file_path and input_file_path.is_file() and (not source_width or not source_height):
            try:
                from PIL import Image
                with Image.open(input_file_path) as im:
                    source_width, source_height = im.size
            except Exception:
                pass

        if req.action == CreativeActionType.UPSCALE:
            if source_width and source_height:
                req.width = source_width
                req.height = source_height
        elif req.action in (CreativeActionType.IMG2IMG, CreativeActionType.INPAINT):
            if source_width and source_height and (not req.width or not req.height or (req.width == 512 and req.height == 512)):
                req.width = source_width
                req.height = source_height

        if req.mask_image_id:
            m_rec = await asset_store.get_asset(req.mask_image_id)
            if m_rec:
                mask_hash = m_rec.content_hash
                mask_file_path = asset_store.get_absolute_path(m_rec)

        # Validate required source assets for asset-dependent actions
        if req.action in (CreativeActionType.IMG2IMG, CreativeActionType.UPSCALE, CreativeActionType.IMG2VIDEO):
            if not input_file_path or not input_file_path.is_file():
                return CreativeActionResult(
                    success=False,
                    task_id=task_id,
                    error_message=f"Source image required (source image is required for {req.action.value}).",
                    width=req.width,
                    height=req.height,
                )
        elif req.action == CreativeActionType.INPAINT:
            if not input_file_path or not input_file_path.is_file() or not mask_file_path or not mask_file_path.is_file():
                return CreativeActionResult(
                    success=False,
                    task_id=task_id,
                    error_message="Source image and mask required for inpainting.",
                    width=req.width,
                    height=req.height,
                )

        if req.action == CreativeActionType.INPAINT:
            try:
                if not source_width or not source_height:
                    raise ValueError("Source image dimensions could not be decoded.")
                await asyncio.to_thread(validate_mask_dimensions, mask_file_path, source_width, source_height)
            except (OSError, ValueError) as error:
                return CreativeActionResult(success=False, task_id=task_id, error_message=str(error))

        try:
            # 1. Resolve unified execution plan before cache check & dispatch
            plan = resolve_execution_plan(req)
            persisted.params = req.model_dump()
            persisted.metadata = {"engine": plan.engine, "provider_id": plan.provider_id, "model": plan.target_model}
            await task_store.save_task(persisted)

            # 2. Resolve connection for local engine execution (Issue #127)
            connection = None
            connection_id = None
            if plan.engine in ("comfyui", "webui"):
                connection = self._resolve_connection(req.connection_id, req.engine_id)
                connection_id = connection.id
                logger.info(f"[{task_id}] Resolved connection: {connection_id} ({connection.endpoint_url})")
            else:
                # Cloud execution - use provider_id as connection_id
                connection_id = plan.provider_id

        except Exception as e:
            return CreativeActionResult(
                success=False,
                task_id=task_id,
                error_message=str(e),
                width=req.width,
                height=req.height,
            )

        # Check deterministic cache with connection_id (Issue #127)
        cache_key = compute_creative_cache_hash(req, connection_id, input_hash, mask_hash, provider_id=plan.provider_id)
        cached_result = await cache_store.get_async(cache_key)

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

        # Register active task with connection_id (Issue #127)
        self.active_tasks[task_id] = {
            "action": req.action.value,
            "engine": plan.engine,
            "provider_id": plan.provider_id,
            "connection_id": connection_id,
            "start_time": time.time(),
        }
        self.active_cancellations[task_id] = cancel_event
        task_registry.register_task(
            task_id=task_id,
            task_type="creative_action",
            cancel_event=cancel_event,
            metadata={
                "action": req.action.value,
                "engine": plan.engine,
                "provider_id": plan.provider_id,
                "connection_id": connection_id,
                "start_time": time.time(),
            },
        )

        # Dispatch based on plan.engine with resolved connection (Issue #127)
        try:
            if plan.engine == "webui":
                if is_video:
                    raise ValueError("WebUI engine currently does not support native video generation. Use ComfyUI or Cloud.")
                runner = self._create_client(connection)
                action_data = await runner.execute_action(req)
                asset_id = action_data["asset_id"]
                image_url = action_data["image_url"]
                out_w = action_data.get("width", req.width)
                out_h = action_data.get("height", req.height)
            elif plan.engine == "comfyui":
                comfy_client = self._create_client(connection)
                action_data = await self._run_comfy(req, comfy_client, input_file_path, mask_file_path)
                asset_id = action_data["asset_id"]
                image_url = action_data["image_url"]
                out_w = action_data.get("width", req.width)
                out_h = action_data.get("height", req.height)
            elif plan.engine == "cloud":
                action_data = await self._run_cloud(req, plan, input_file_path, mask_file_path)
                asset_id = action_data["asset_id"]
                image_url = action_data["image_url"]
                out_w = action_data.get("width", req.width)
                out_h = action_data.get("height", req.height)
            else:
                raise ValueError(f"Unknown engine in plan: {plan.engine}")

            # Derive result dimensions from decoded output file if available
            asset_record = await asset_store.get_asset(asset_id)
            if asset_record:
                rec_w = getattr(asset_record, "width", None)
                rec_h = getattr(asset_record, "height", None)
                if isinstance(rec_w, int) and isinstance(rec_h, int):
                    out_w = rec_w
                    out_h = rec_h

            if cancel_event.is_set():
                persisted.metadata["cancel_requested"] = True
                persisted.metadata["cancellation_outcome"] = "Execution completed before cancellation could be confirmed."

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

            effective_model = action_data.get("effective_model") or plan.target_model
            model_hash = action_data.get("model_hash") or action_data.get("model_revision")

            provenance = GenerationProvenance(
                action=req.action,
                prompt=req.prompt,
                negative_prompt=req.negative_prompt,
                model=effective_model,
                model_revision=model_hash,
                model_hash=model_hash,
                connection_id=connection_id,  # Issue #127
                engine_id=req.engine_id,  # Legacy field
                provider_id=plan.provider_id,
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
            task_registry.unregister_task(task_id)

    async def _run_comfy(
        self,
        req: CreativeActionRequest,
        comfy_client: ComfyUIClient,  # Issue #127: Accept resolved client
        input_file: Optional[Path],
        mask_file: Optional[Path],
    ) -> Dict[str, Any]:
        """Compile and submit ComfyUI macro graph, uploading required assets first (Issue #127)."""
        # Upload source image and mask to ComfyUI's input directory if needed
        uploaded_image_name: Optional[str] = None
        uploaded_mask_name: Optional[str] = None
        converted_mask_path: Optional[Path] = None

        if input_file and input_file.is_file():
            try:
                upload_result = await comfy_client.upload_image(str(input_file), subfolder="berry_assets")
                uploaded_image_name = upload_result["name"]
                # Include subfolder in the filename if ComfyUI expects it
                if upload_result.get("subfolder"):
                    uploaded_image_name = f"{upload_result['subfolder']}/{uploaded_image_name}"
                logger.debug(f"Uploaded source image to ComfyUI: {uploaded_image_name}")
            except Exception as upload_err:
                raise RuntimeError(f"Failed to transfer source image to ComfyUI: {upload_err}") from upload_err

        if mask_file and mask_file.is_file():
            try:
                # Validate and convert mask for ComfyUI (Issue #106)
                # ComfyUI LoadImage MASK output = 1 - alpha, requiring inversion
                if input_file:
                    from PIL import Image
                    source_img = Image.open(input_file)
                    validate_mask_dimensions(mask_file, source_img.width, source_img.height)

                converted_mask_path = await asyncio.to_thread(normalize_mask_for_comfyui, mask_file)
                mask_result = await comfy_client.upload_mask(str(converted_mask_path), subfolder="berry_assets")
                uploaded_mask_name = mask_result["name"]
                if mask_result.get("subfolder"):
                    uploaded_mask_name = f"{mask_result['subfolder']}/{uploaded_mask_name}"
                logger.debug(f"Uploaded converted mask to ComfyUI: {uploaded_mask_name}")
            except Exception as upload_err:
                raise RuntimeError(f"Failed to transfer mask to ComfyUI: {upload_err}") from upload_err
            finally:
                # Clean up temporary converted mask
                if converted_mask_path and converted_mask_path.exists():
                    try:
                        converted_mask_path.unlink()
                    except Exception:
                        pass

        # Build workflow graphs using uploaded filenames
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
            if not uploaded_image_name:
                raise ValueError("Source image upload failed for img2img")
            prompt_graph = build_comfy_img2img_graph(
                prompt=req.prompt,
                image_filename=uploaded_image_name,
                negative_prompt=req.negative_prompt,
                checkpoint=req.model,
                steps=req.steps,
                cfg=req.cfg_scale,
                denoise=req.denoise,
                seed=req.seed,
            )
        elif req.action == CreativeActionType.INPAINT:
            if not uploaded_image_name or not uploaded_mask_name:
                raise ValueError("Source image and mask upload required for inpaint")
            prompt_graph = build_comfy_inpaint_graph(
                prompt=req.prompt,
                image_filename=uploaded_image_name,
                mask_filename=uploaded_mask_name,
                negative_prompt=req.negative_prompt,
                checkpoint=req.model,
                steps=req.steps,
                cfg=req.cfg_scale,
                denoise=req.denoise,
                seed=req.seed,
            )
        elif req.action == CreativeActionType.UPSCALE:
            if not uploaded_image_name:
                raise ValueError("Source image upload failed for upscale")
            prompt_graph = build_comfy_upscale_graph(
                image_filename=uploaded_image_name,
                upscaler_model=req.upscaler_name or "RealESRGAN_x4plus.pth",
                upscale_factor=req.upscale_factor,
                source_width=req.width,
                source_height=req.height,
            )
        elif req.action == CreativeActionType.IMG2VIDEO:
            if not uploaded_image_name:
                raise ValueError("Source image upload failed for ComfyUI img2video")
            prompt_graph = build_comfy_img2video_graph(
                image_filename=uploaded_image_name,
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

        asset_w = getattr(asset, "width", None)
        asset_h = getattr(asset, "height", None)
        asset_id = getattr(asset, "id", None)
        return {
            "asset_id": asset_id,
            "image_url": f"/api/v1/assets/{asset_id}/content" if asset_id else "",
            "width": asset_w if isinstance(asset_w, int) else req.width,
            "height": asset_h if isinstance(asset_h, int) else req.height,
        }

    async def _run_cloud(
        self,
        req: CreativeActionRequest,
        plan: CreativeExecutionPlan,
        input_file: Optional[Path] = None,
        mask_file: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Dispatch creative action to cloud API according to resolved plan using BYOK key."""
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
        remote_url: Optional[str] = None

        if req.action == CreativeActionType.INPAINT:
            if not image_bytes or not mask_bytes:
                raise ValueError("Source image and mask are required for cloud inpainting.")

            if plan.provider_id == "openai":
                key = credentials_manager.get_key(CloudProviderId.OPENAI)
                if not key:
                    raise RuntimeError("OpenAI API key missing. Configure it in Cloud Providers (BYOK).")
                # Convert mask for OpenAI (Issue #106): transparent = edit
                converted_mask_bytes = await asyncio.to_thread(normalize_mask_for_openai, mask_bytes)
                remote_url = await _call_openai_inpaint(req.prompt, image_bytes, converted_mask_bytes, key)
            elif plan.provider_id == "fal_ai":
                key = credentials_manager.get_key(CloudProviderId.FAL)
                if not key:
                    raise RuntimeError("Fal.ai API key is required for cloud inpainting. Configure it in Cloud Settings (BYOK).")
                # flux-general/inpainting consumes grayscale white=edit, black=protect.
                converted_mask_bytes = await asyncio.to_thread(normalize_mask_for_fal_ai, mask_bytes)
                converted_mask_b64 = base64.b64encode(converted_mask_bytes).decode("utf-8")
                remote_url = await _call_fal_ai_action(
                    action="inpaint",
                    prompt=req.prompt,
                    api_key=key,
                    image_b64=image_b64,
                    mask_b64=converted_mask_b64,
                )
            else:
                raise ValueError(f"Provider {plan.provider_id} does not support cloud inpainting.")

        elif req.action == CreativeActionType.UPSCALE:
            if not image_b64:
                raise ValueError("Source image is required for cloud upscaling.")

            if plan.provider_id == "fal_ai":
                key = credentials_manager.get_key(CloudProviderId.FAL)
                if not key:
                    raise RuntimeError("Cloud upscaling requires Fal.ai API key. Please configure a Fal.ai BYOK key.")
                remote_url = await _call_fal_ai_action(
                    action="upscale",
                    prompt=req.prompt,
                    api_key=key,
                    image_b64=image_b64,
                    upscale_factor=req.upscale_factor,
                )
                out_w = int(round(req.width * req.upscale_factor))
                out_h = int(round(req.height * req.upscale_factor))
            else:
                raise ValueError(f"Provider {plan.provider_id} does not support cloud upscaling.")

        elif req.action == CreativeActionType.IMG2IMG:
            if not image_b64:
                raise ValueError("Source image is required for cloud image-to-image.")

            if plan.provider_id == "fal_ai":
                key = credentials_manager.get_key(CloudProviderId.FAL)
                if not key:
                    raise RuntimeError("Cloud image-to-image requires Fal.ai BYOK key. Configure it in Cloud Settings.")
                remote_url = await _call_fal_ai_action(
                    action="img2img",
                    prompt=req.prompt,
                    api_key=key,
                    image_b64=image_b64,
                    denoise=req.denoise,
                )
            else:
                raise ValueError(f"Provider {plan.provider_id} does not support cloud img2img.")

        elif req.action == CreativeActionType.IMG2VIDEO:
            if not image_b64:
                raise ValueError("Source image is required for cloud img2video.")

            if plan.provider_id == "siliconflow":
                key_sf = credentials_manager.get_key(CloudProviderId.SILICONFLOW)
                if not key_sf:
                    raise RuntimeError("SiliconFlow API key missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_siliconflow_video(
                    action="img2video",
                    prompt=req.prompt,
                    api_key=key_sf,
                    image_b64=image_b64,
                )
            elif plan.provider_id == "fal_ai":
                key_fal = credentials_manager.get_key(CloudProviderId.FAL)
                if not key_fal:
                    raise RuntimeError("Fal.ai API key missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_fal_ai_video(
                    action="img2video",
                    prompt=req.prompt,
                    api_key=key_fal,
                    image_b64=image_b64,
                    fps=req.fps,
                    num_frames=req.num_frames,
                    motion_bucket_id=req.motion_bucket_id,
                )
            else:
                raise ValueError(f"Provider {plan.provider_id} does not support cloud img2video.")

        elif req.action == CreativeActionType.TXT2VIDEO:
            if plan.provider_id == "siliconflow":
                key_sf = credentials_manager.get_key(CloudProviderId.SILICONFLOW)
                if not key_sf:
                    raise RuntimeError("SiliconFlow API key missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_siliconflow_video(
                    action="txt2video",
                    prompt=req.prompt,
                    api_key=key_sf,
                )
            elif plan.provider_id == "fal_ai":
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
                raise ValueError(f"Provider {plan.provider_id} does not support cloud txt2video.")

        else:
            # TXT2IMG
            if plan.provider_id == "fal_ai":
                key = credentials_manager.get_key(CloudProviderId.FAL)
                if not key:
                    raise RuntimeError("Fal.ai API key is missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_fal_ai(plan.target_model, req.prompt, req.width, req.height, key)
            elif plan.provider_id == "openai":
                key = credentials_manager.get_key(CloudProviderId.OPENAI)
                if not key:
                    raise RuntimeError("OpenAI API key is missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_openai_images(req.prompt, key)
            elif plan.provider_id == "siliconflow":
                key = credentials_manager.get_key(CloudProviderId.SILICONFLOW)
                if not key:
                    raise RuntimeError("SiliconFlow API key is missing. Configure it in Cloud Providers (BYOK).")
                remote_url = await _call_siliconflow(req.prompt, req.width, req.height, key)
            else:
                raise RuntimeError("No cloud provider API key configured. Please set up a BYOK key in Cloud Settings.")

        if not remote_url:
            raise RuntimeError(f"Cloud provider returned no media URL for action {req.action}.")

        is_video = req.action in (CreativeActionType.TXT2VIDEO, CreativeActionType.IMG2VIDEO)
        if is_video:
            asset = await asset_store.save_media_from_url(remote_url, filename="cloud_video.mp4", media_type="video")
        else:
            asset = await asset_store.save_image_from_url(remote_url, filename="cloud_output.png")

        asset_w = getattr(asset, "width", None)
        asset_h = getattr(asset, "height", None)
        asset_id = getattr(asset, "id", None)
        return {
            "asset_id": asset_id,
            "image_url": f"/api/v1/assets/{asset_id}/content" if asset_id else "",
            "width": asset_w if isinstance(asset_w, int) else out_w,
            "height": asset_h if isinstance(asset_h, int) else out_h,
        }


creative_runner = CreativeRunner()
