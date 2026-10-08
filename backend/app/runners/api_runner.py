"""
Cloud API execution driver.

Supports OpenAI-compatible LLM endpoints (DeepSeek, GPT-4o, etc.),
image generation APIs (Fal.ai / SiliconFlow / OpenAI Images),
and the output.preview presentation card runner.

Reads credentials from environment variables or from node-level params.
Never hardcodes secrets.
"""

import asyncio
import os
import time
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from app.schemas.events import (
    NodeErrorEvent,
    NodeOutputEvent,
    NodeProgressEvent,
    NodeStatusEvent,
    WorkflowEvent,
)
from app.storage.asset_store import asset_store


class APIRunnerError(Exception):
    """Raised when a cloud API call fails unrecoverably."""


_shared_client: Optional[httpx.AsyncClient] = None


def get_shared_client(timeout: float = 120.0) -> httpx.AsyncClient:
    """Return a shared persistent httpx client to prevent socket exhaustion."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(timeout=timeout)
    return _shared_client


async def close_shared_client() -> None:
    """Close shared HTTP client."""
    global _shared_client
    if _shared_client and not _shared_client.is_closed:
        await _shared_client.aclose()
        _shared_client = None


# ---------------------------------------------------------------------------
# LLM Execution (OpenAI-compatible)
# ---------------------------------------------------------------------------

async def run_llm_node(
    node_id: str,
    inputs: Dict[str, Any],
    params: Dict[str, Any],
) -> AsyncGenerator[WorkflowEvent, None]:
    """
    Execute a text.llm node against an OpenAI-compatible endpoint.
    Yields real-time streaming events.
    """
    yield NodeStatusEvent(node_id=node_id, status="running")
    yield NodeProgressEvent(node_id=node_id, progress=0.1, message="Sending prompt to LLM...")

    prompt: str = inputs.get("prompt", "")
    system_prompt: str = inputs.get("system_prompt", "You are a helpful creative assistant.")
    model: str = params.get("model", "deepseek-chat")
    temperature: float = float(params.get("temperature", 0.7))

    # Resolve base_url & api_key: params first, then env vars
    base_url: str = params.get("base_url") or os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    api_key: str = params.get("api_key") or os.environ.get("LLM_API_KEY", "")

    # Route common model names to their canonical base URLs
    if not params.get("base_url"):
        if model.startswith("gpt-") or model.startswith("o1"):
            base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com")
            api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        yield NodeErrorEvent(
            node_id=node_id,
            message="No API key configured. Set LLM_API_KEY in environment or provide api_key in node params.",
        )
        return

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "stream": False,
    }

    try:
        yield NodeProgressEvent(node_id=node_id, progress=0.3, message=f"Waiting for {model} response...")
        client = get_shared_client(timeout=60.0)
        response = await client.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        result_text: str = data["choices"][0]["message"]["content"]
        yield NodeProgressEvent(node_id=node_id, progress=0.95, message="Processing response...")
        yield NodeOutputEvent(node_id=node_id, output={"result": result_text})
        yield NodeStatusEvent(node_id=node_id, status="completed")

    except httpx.HTTPStatusError as e:
        yield NodeErrorEvent(node_id=node_id, message=f"API HTTP error {e.response.status_code}: {e.response.text[:200]}")
        yield NodeStatusEvent(node_id=node_id, status="error")
    except Exception as e:
        yield NodeErrorEvent(node_id=node_id, message=f"Unexpected error: {str(e)}")
        yield NodeStatusEvent(node_id=node_id, status="error")


# ---------------------------------------------------------------------------
# Image Generation Execution
# ---------------------------------------------------------------------------

async def run_image_gen_node(
    node_id: str,
    inputs: Dict[str, Any],
    params: Dict[str, Any],
) -> AsyncGenerator[WorkflowEvent, None]:
    """
    Execute an image.generate node against a cloud image API.

    Supports:
    - Fal.ai (fal-ai/flux/schnell, fal-ai/flux/dev, fal-ai/stable-diffusion-xl)
    - SiliconFlow (stabilityai/stable-diffusion-3-5-large-turbo, etc.)
    - OpenAI DALL-E 3 (dall-e-3)
    """
    yield NodeStatusEvent(node_id=node_id, status="running")
    yield NodeProgressEvent(node_id=node_id, progress=0.05, message="Preparing image generation request...")

    prompt: str = inputs.get("prompt", "")
    model: str = params.get("model", "flux-schnell")
    aspect_ratio: str = params.get("aspect_ratio", "1:1")

    # Map aspect ratios to pixel dimensions for APIs that use width/height
    ASPECT_TO_SIZE = {
        "1:1": (1024, 1024),
        "16:9": (1344, 768),
        "9:16": (768, 1344),
        "4:3": (1152, 896),
        "3:4": (896, 1152),
    }
    width, height = ASPECT_TO_SIZE.get(aspect_ratio, (1024, 1024))

    api_key: str = params.get("api_key") or os.environ.get("IMAGE_API_KEY", "")

    # Route by model to the appropriate provider
    if model in ("flux-schnell", "flux-dev"):
        yield NodeProgressEvent(node_id=node_id, progress=0.2, message="Routing to Fal.ai FLUX API...")
        image_url = await _call_fal_ai(model, prompt, width, height, api_key)

    elif model == "dall-e-3":
        yield NodeProgressEvent(node_id=node_id, progress=0.2, message="Routing to OpenAI DALL-E 3 API...")
        oai_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        image_url = await _call_openai_images(prompt, oai_key)

    elif model == "sdxl-turbo":
        yield NodeProgressEvent(node_id=node_id, progress=0.2, message="Routing to SiliconFlow SDXL API...")
        sf_key = api_key or os.environ.get("SILICONFLOW_API_KEY", "")
        image_url = await _call_siliconflow(prompt, width, height, sf_key)

    else:
        yield NodeErrorEvent(node_id=node_id, message=f"Unknown image model: '{model}'")
        yield NodeStatusEvent(node_id=node_id, status="error")
        return

    if image_url is None:
        yield NodeErrorEvent(node_id=node_id, message="Image generation returned no URL. Check API key and quota.")
        yield NodeStatusEvent(node_id=node_id, status="error")
        return

    yield NodeProgressEvent(node_id=node_id, progress=0.8, message="Persisting cloud image into managed storage...")
    output_dict: Dict[str, Any] = {"image": image_url}
    try:
        asset = await asset_store.save_image_from_url(image_url)
        output_dict = {
            "image": f"/api/v1/assets/{asset.id}/content",
            "asset_id": asset.id,
            "content_hash": asset.content_hash,
            "remote_url": image_url,
        }
    except Exception:
        # Fall back to remote URL if download fails (e.g. offline mock or local test)
        pass

    yield NodeProgressEvent(node_id=node_id, progress=1.0, message="Image generation completed.")
    yield NodeOutputEvent(node_id=node_id, output=output_dict)
    yield NodeStatusEvent(node_id=node_id, status="completed")


async def _call_fal_ai(model: str, prompt: str, width: int, height: int, api_key: str) -> str | None:
    model_id = "fal-ai/flux/schnell" if model == "flux-schnell" else "fal-ai/flux/dev"
    if not api_key:
        raise APIRunnerError("FAL_KEY / IMAGE_API_KEY not set for Fal.ai")
    client = get_shared_client(timeout=120.0)
    response = await client.post(
        f"https://fal.run/{model_id}",
        headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
        json={"prompt": prompt, "image_size": {"width": width, "height": height}},
    )
    response.raise_for_status()
    data = response.json()
    images = data.get("images", [])
    return images[0]["url"] if images else None


async def _call_openai_images(prompt: str, api_key: str) -> str | None:
    if not api_key:
        raise APIRunnerError("OPENAI_API_KEY not set for DALL-E")
    client = get_shared_client(timeout=90.0)
    response = await client.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1024x1024"},
    )
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["url"] if data.get("data") else None


async def _call_siliconflow(prompt: str, width: int, height: int, api_key: str) -> str | None:
    if not api_key:
        raise APIRunnerError("SILICONFLOW_API_KEY / IMAGE_API_KEY not set for SiliconFlow")
    client = get_shared_client(timeout=120.0)
    response = await client.post(
        "https://api.siliconflow.cn/v1/images/generations",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "stabilityai/stable-diffusion-xl-base-1.0",
            "prompt": prompt,
            "n": 1,
            "size": f"{width}x{height}",
        },
    )
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["url"] if data.get("data") else None


async def _call_openai_inpaint(
    prompt: str, image_bytes: bytes, mask_bytes: bytes, api_key: str
) -> str | None:
    if not api_key:
        raise APIRunnerError("OPENAI_API_KEY not set for OpenAI inpainting")
    client = get_shared_client(timeout=120.0)
    files = {
        "image": ("image.png", image_bytes, "image/png"),
        "mask": ("mask.png", mask_bytes, "image/png"),
    }
    data = {
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
    }
    response = await client.post(
        "https://api.openai.com/v1/images/edits",
        headers={"Authorization": f"Bearer {api_key}"},
        files=files,
        data=data,
    )
    response.raise_for_status()
    resp_data = response.json()
    return resp_data["data"][0]["url"] if resp_data.get("data") else None


async def _call_fal_ai_action(
    action: str,
    prompt: str,
    api_key: str,
    width: int = 1024,
    height: int = 1024,
    image_b64: Optional[str] = None,
    mask_b64: Optional[str] = None,
    denoise: float = 0.75,
    upscale_factor: float = 2.0,
) -> str | None:
    if not api_key:
        raise APIRunnerError("FAL_KEY / IMAGE_API_KEY not set for Fal.ai")

    headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
    client = get_shared_client(timeout=120.0)
    if action == "inpaint":
        if not image_b64 or not mask_b64:
            raise ValueError("Image and mask required for Fal.ai inpainting")
        endpoint = "https://fal.run/fal-ai/flux-general/inpainting"
        payload = {
            "prompt": prompt,
            "image_url": f"data:image/png;base64,{image_b64}",
            "mask_url": f"data:image/png;base64,{mask_b64}",
        }
    elif action == "upscale":
        if not image_b64:
            raise ValueError("Image required for Fal.ai upscaling")
        endpoint = "https://fal.run/fal-ai/clarity-upscaler"
        payload = {
            "image_url": f"data:image/png;base64,{image_b64}",
            "scale": int(upscale_factor),
        }
    elif action == "img2img":
        if not image_b64:
            raise ValueError("Image required for Fal.ai img2img")
        endpoint = "https://fal.run/fal-ai/flux/dev/image-to-image"
        payload = {
            "prompt": prompt,
            "image_url": f"data:image/png;base64,{image_b64}",
            "strength": max(0.1, min(1.0, 1.0 - denoise)),
        }
    else:
        endpoint = "https://fal.run/fal-ai/flux/schnell"
        payload = {"prompt": prompt, "image_size": {"width": width, "height": height}}

    response = await client.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    if "image" in data and isinstance(data["image"], dict):
        return data["image"].get("url")
    images = data.get("images", [])
    return images[0]["url"] if images else None


async def _call_fal_ai_video(
    action: str,
    prompt: str,
    api_key: str,
    image_b64: Optional[str] = None,
    fps: int = 16,
    num_frames: int = 25,
    motion_bucket_id: int = 127,
) -> str | None:
    """Call Fal.ai video endpoints (Fast SVD for img2video, Luma/Kling for txt2video)."""
    if not api_key:
        raise APIRunnerError("FAL_KEY / IMAGE_API_KEY not set for Fal.ai video")

    headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
    client = get_shared_client(timeout=180.0)
    if action == "img2video":
        if not image_b64:
            raise ValueError("Source image required for Fal.ai img2video")
        endpoint = "https://fal.run/fal-ai/fast-svd/image-to-video"
        payload = {
            "image_url": f"data:image/png;base64,{image_b64}",
            "motion_bucket_id": motion_bucket_id,
            "fps": fps,
            "cond_aug": 0.02,
            "steps": 25,
        }
    else:  # txt2video
        endpoint = "https://fal.run/fal-ai/luma-dream-machine"
        payload = {
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "loop": False,
        }

    response = await client.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    if "video" in data and isinstance(data["video"], dict):
        return data["video"].get("url")
    return data.get("video_url") or data.get("url")


async def _call_siliconflow_video(
    action: str,
    prompt: str,
    api_key: str,
    image_b64: Optional[str] = None,
) -> str | None:
    """Call SiliconFlow video generation endpoints (CogVideoX) with async status polling."""
    if not api_key:
        raise APIRunnerError("SILICONFLOW_API_KEY not set for SiliconFlow video")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    client = get_shared_client(timeout=180.0)
    endpoint = "https://api.siliconflow.cn/v1/video/submit"
    payload: Dict[str, Any] = {
        "model": "THUDM/CogVideoX-5b",
        "prompt": prompt,
    }
    if action == "img2video" and image_b64:
        payload["image"] = f"data:image/png;base64,{image_b64}"

    response = await client.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()

    # Check if direct video URL is already present in response
    if "uri" in data and isinstance(data["uri"], str) and (data["uri"].startswith("http") or data["uri"].startswith("blob")):
        return data["uri"]
    if "data" in data and isinstance(data["data"], dict) and data["data"].get("url"):
        return data["data"].get("url")
    if data.get("url") and isinstance(data["url"], str) and data["url"].startswith("http"):
        return data["url"]

    # If asynchronous job was submitted, poll job status
    job_id = (
        data.get("requestId")
        or data.get("jobId")
        or data.get("id")
        or (data.get("data", {}).get("id") if isinstance(data.get("data"), dict) else None)
    )
    if not job_id:
        # Fallback to whatever URL/URI field is provided if not a recognized job ID
        return data.get("uri") or data.get("url")

    from app.storage.task_store import record_remote_job
    await record_remote_job(str(job_id))
    poll_endpoint = "https://api.siliconflow.cn/v1/video/status"
    start_poll = time.time()
    poll_timeout = 180.0

    while time.time() - start_poll < poll_timeout:
        await asyncio.sleep(2.0)
        status_resp = await client.post(
            poll_endpoint,
            headers=headers,
            json={"requestId": job_id},
        )
        if status_resp.status_code in (400, 404):
            status_resp = await client.get(
                f"{poll_endpoint}?requestId={job_id}",
                headers=headers,
            )

        if not status_resp.is_success:
            continue

        status_data = status_resp.json()
        status = str(
            status_data.get("status")
            or (status_data.get("data", {}).get("status") if isinstance(status_data.get("data"), dict) else "")
        ).lower()

        if status in ("succeed", "succeeded", "success", "completed"):
            results = status_data.get("results") or status_data.get("data", {})
            if isinstance(results, dict):
                videos = results.get("videos")
                if isinstance(videos, list) and len(videos) > 0 and isinstance(videos[0], dict):
                    return videos[0].get("url")
                return results.get("url") or results.get("video_url")
            elif isinstance(results, list) and len(results) > 0 and isinstance(results[0], dict):
                return results[0].get("url")
            return status_data.get("url")
        elif status in ("failed", "error"):
            reason = status_data.get("reason") or status_data.get("message") or "Video generation task failed"
            raise APIRunnerError(f"SiliconFlow video generation failed: {reason}")

    raise APIRunnerError("SiliconFlow video generation timed out after 180 seconds")



# ---------------------------------------------------------------------------
# Input node: passthrough (no API call needed)
# ---------------------------------------------------------------------------

async def run_input_text_node(
    node_id: str,
    params: Dict[str, Any],
) -> AsyncGenerator[WorkflowEvent, None]:
    """Passthrough for static text input nodes — no API cost."""
    yield NodeStatusEvent(node_id=node_id, status="running")
    value: str = params.get("value", "")
    yield NodeOutputEvent(node_id=node_id, output={"text": value})
    yield NodeStatusEvent(node_id=node_id, status="completed")


# ---------------------------------------------------------------------------
# Preview node: display media input card
# ---------------------------------------------------------------------------

async def run_preview_node(
    node_id: str,
    inputs: Dict[str, Any],
    params: Dict[str, Any],
) -> AsyncGenerator[WorkflowEvent, None]:
    """Presentation card handler for output.preview nodes."""
    yield NodeStatusEvent(node_id=node_id, status="running")
    media = inputs.get("media") or inputs.get("image") or inputs.get("text") or inputs.get("result")
    output: Dict[str, Any] = {}
    if isinstance(media, str):
        if media.startswith("http://") or media.startswith("https://") or media.startswith("/api/v1/assets/"):
            output["image"] = media
        else:
            output["result"] = media
    elif isinstance(media, dict):
        output.update(media)
    elif media is not None:
        output["result"] = str(media)

    yield NodeOutputEvent(node_id=node_id, output=output)
    yield NodeStatusEvent(node_id=node_id, status="completed")


# ---------------------------------------------------------------------------
# Runner dispatch table
# ---------------------------------------------------------------------------

NODE_RUNNERS = {
    "input.text": run_input_text_node,
    "text.llm": run_llm_node,
    "image.generate": run_image_gen_node,
    "output.preview": run_preview_node,
}
