"""Bounded, decoded image adoption without forwarding provider credentials."""

import io
from urllib.parse import urlsplit

import httpx
from PIL import Image

from app.core.media_validator import validate_and_inspect_media
from app.core.workers import run_blocking
from app.schemas.project import AssetRecord
from app.storage.asset_store import AssetStore

MAX_OUTPUT_BYTES = 50 * 1024 * 1024


def _inspect_image(content: bytes) -> tuple[int, int, str]:
    mime, _, _ = validate_and_inspect_media(content)
    if mime not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        raise ValueError("Provider output must be a supported image")
    with Image.open(io.BytesIO(content)) as image:
        image.verify()
    with Image.open(io.BytesIO(content)) as image:
        image.load()
        return image.width, image.height, mime


async def adopt_cloud_image(
    *,
    store: AssetStore,
    url: str | None = None,
    content: bytes | None = None,
    project_id: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> AssetRecord:
    """Download at most one output, fully decode it, then publish managed bytes."""
    if (url is None) == (content is None):
        raise ValueError("Exactly one image output source is required")
    if url is not None:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError(
                "Provider image URL must use HTTPS without embedded credentials"
            )
        if client is None:
            async with httpx.AsyncClient(timeout=60, follow_redirects=False) as owned:
                return await adopt_cloud_image(
                    store=store, url=url, project_id=project_id, client=owned
                )
        try:
            async with client.stream("GET", url, follow_redirects=False) as response:
                if response.status_code != 200:
                    raise ValueError(
                        f"Provider output download failed (HTTP {response.status_code})"
                    )
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(chunks) + len(chunk) > MAX_OUTPUT_BYTES:
                        raise ValueError("Provider output exceeds the image byte limit")
                    chunks.extend(chunk)
                content = bytes(chunks)
        except httpx.RequestError:
            raise ValueError(
                "Provider output could not be downloaded; no output was adopted"
            ) from None
    if not content or len(content) > MAX_OUTPUT_BYTES:
        raise ValueError("Provider output is empty or exceeds the image byte limit")
    try:
        width, height, mime = await run_blocking(_inspect_image, content)
    except Exception:
        raise ValueError(
            "Provider returned an undecodable image; no output was adopted"
        ) from None
    extension = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }[mime]
    return await store.save_bytes(
        content,
        filename=f"cloud_output{extension}",
        media_type="image",
        project_id=project_id,
        width=width,
        height=height,
    )
