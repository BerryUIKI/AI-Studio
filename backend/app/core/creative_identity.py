"""Cache and provenance describe the adapter and model actually dispatched."""

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from app.core.content_identity import hash_file
from app.core.workflow_spec import local_model_identity
from app.schemas.creative import CreativeActionType, CreativeExecutionPlan
from app.schemas.engine import EngineConnection


def adapter_identity() -> str:
    runners = Path(__file__).resolve().parent.parent / "runners"
    digest = hashlib.sha256()
    for name in ("creative_runner.py", "api_runner.py", "comfy_runner.py", "webui_runner.py", "macro_compiler.py", "mask_converter.py"):
        digest.update(hash_file(runners / name).encode())
    return digest.hexdigest()


async def creative_execution_identity(plan: CreativeExecutionPlan, connection: EngineConnection | None) -> dict[str, Any]:
    identity: dict[str, Any] = {"adapter_revision": await asyncio.to_thread(adapter_identity), "model": plan.target_model}
    if connection:
        identity.update({"endpoint": connection.endpoint_url, "runtime_revision": connection.version,
                         "model_revision": await local_model_identity(plan.target_model)})
        return identity
    action = plan.action
    provider = plan.provider_id
    if provider == "fal_ai":
        models = {CreativeActionType.INPAINT: "fal-ai/flux-general/inpainting",
                  CreativeActionType.IMG2IMG: "fal-ai/flux/dev/image-to-image",
                  CreativeActionType.UPSCALE: "fal-ai/clarity-upscaler",
                  CreativeActionType.IMG2VIDEO: "fal-ai/fast-svd/image-to-video",
                  CreativeActionType.TXT2VIDEO: "fal-ai/luma-dream-machine"}
        model = models.get(action, "fal-ai/flux/schnell" if plan.target_model == "flux-schnell" else "fal-ai/flux/dev")
        identity.update({"endpoint": f"https://fal.run/{model}", "model": model})
    elif provider == "siliconflow":
        video = action in {CreativeActionType.IMG2VIDEO, CreativeActionType.TXT2VIDEO}
        identity.update({"endpoint": "https://api.siliconflow.cn/v1/video/submit" if video else "https://api.siliconflow.cn/v1/images/generations",
                         "model": "THUDM/CogVideoX-5b" if video else "stabilityai/stable-diffusion-xl-base-1.0"})
    elif provider == "openai":
        edit = action == CreativeActionType.INPAINT
        identity.update({"endpoint": "https://api.openai.com/v1/images/edits" if edit else "https://api.openai.com/v1/images/generations",
                         "model": "provider-default" if edit else "dall-e-3"})
    identity["model_revision"] = None  # The adapter does not obtain remote weight revisions.
    return identity
