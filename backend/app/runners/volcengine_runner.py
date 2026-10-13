"""Single-image Ark REST calls with explicit models and redacted failures."""

import base64
import binascii
from dataclasses import dataclass
import re
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

ARK_IMAGE_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
SEEDREAM_MODEL = "doubao-seedream-4-0-250828"
MAX_IMAGE_BYTES = 50 * 1024 * 1024


class ArkError(RuntimeError):
    """An actionable failure containing no credentials or raw provider response."""


class _Image(BaseModel):
    url: str | None = None
    b64_json: str | None = Field(default=None, max_length=MAX_IMAGE_BYTES * 4 // 3 + 4)


class _Response(BaseModel):
    data: list[_Image] = Field(min_length=1, max_length=1)
    model: str | None = None


@dataclass(frozen=True)
class ArkImage:
    url: str | None
    content: bytes | None
    requested_model: str
    effective_model: str | None
    request_id: str | None


def _identifier(value: str | None, credential: str) -> str | None:
    if not value or credential in value or value.lower().startswith(("ark-", "sk-", "bearer")):
        return None
    return value if re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) else None


async def request_ark_image(
    *, prompt: str, model: str, width: int, height: int, api_key: str,
    image_data_uri: str | None = None,
    response_format: Literal["url", "b64_json"] = "url",
    client: httpx.AsyncClient | None = None,
) -> ArkImage:
    """Send one inference POST; never retry or substitute a model automatically."""
    if not api_key:
        raise ArkError("Ark API key is missing. Configure Volcengine Ark in Cloud Settings.")
    if model != SEEDREAM_MODEL:
        raise ArkError("This Ark adapter supports the explicitly selected Seedream 4.0 model only.")
    if width <= 0 or height <= 0 or not 921600 <= width * height <= 16777216 or not 1 / 16 <= width / height <= 16:
        raise ArkError("Seedream output must contain 921600–16777216 pixels with aspect ratio 1:16–16:1.")
    payload: dict[str, object] = {
        "model": model, "prompt": prompt, "size": f"{width}x{height}",
        "sequential_image_generation": "disabled", "response_format": response_format,
        "stream": False, "watermark": True,
    }
    if image_data_uri:
        payload["image"] = image_data_uri
    if client is None:
        async with httpx.AsyncClient(timeout=180.0, follow_redirects=False) as owned:
            return await request_ark_image(prompt=prompt, model=model, width=width, height=height,
                api_key=api_key, image_data_uri=image_data_uri, response_format=response_format, client=owned)
    try:
        response = await client.post(ARK_IMAGE_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}"}, json=payload, follow_redirects=False)
    except httpx.RequestError:
        raise ArkError("Ark connection interrupted; the remote outcome is unknown. Check provider history before an explicit retry.") from None
    if response.status_code != 200:
        code = None
        try:
            error = response.json().get("error", {})
            if isinstance(error, dict) and isinstance(error.get("code"), str):
                code = _identifier(error["code"], api_key)
        except (ValueError, AttributeError):
            pass
        diagnostic = f"; code {code}" if code else ""
        raise ArkError(f"Ark image request failed (HTTP {response.status_code}{diagnostic}). Check authentication, model access, quota and supported parameters.")
    try:
        body = _Response.model_validate(response.json())
        image = body.data[0]
        content = None
        if response_format == "b64_json":
            if not image.b64_json:
                raise ValueError("Missing base64 output")
            content = base64.b64decode(image.b64_json, validate=True)
            if not content or len(content) > MAX_IMAGE_BYTES:
                raise ValueError("Invalid output size")
        elif not image.url or not image.url.startswith("https://"):
            raise ValueError("Missing HTTPS output")
    except (ValueError, ValidationError, binascii.Error):
        raise ArkError("Ark returned an invalid single-image response; no output was adopted.") from None
    return ArkImage(url=image.url if response_format == "url" else None, content=content,
        requested_model=model, effective_model=_identifier(body.model, api_key),
        request_id=_identifier(response.headers.get("x-request-id") or response.headers.get("x-tt-logid"), api_key))
