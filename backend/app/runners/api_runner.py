"""
Cloud API execution driver.

Supports OpenAI-compatible LLM endpoints (DeepSeek, GPT-4o, etc.),
image generation APIs (Fal.ai / SiliconFlow / OpenAI Images),
and the output.preview presentation card runner.

Reads credentials from environment variables or from node-level params.
Never hardcodes secrets.
"""

import os
import time
from typing import Any, AsyncGenerator, Dict

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
        async with httpx.AsyncClient(timeout=60.0) as client:
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
    async with httpx.AsyncClient(timeout=120.0) as client:
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
    async with httpx.AsyncClient(timeout=90.0) as client:
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
    async with httpx.AsyncClient(timeout=120.0) as client:
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
