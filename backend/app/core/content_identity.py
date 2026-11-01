"""Port-aware identities use verified media bytes rather than mutable URLs."""

import asyncio
import base64
import hashlib
from pathlib import Path
import re
from typing import Any

import httpx

from app.core.cache import compute_content_hash
from app.core.media_validator import MAX_UPLOAD_BYTES
from app.schemas.node import DataType


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def managed_asset_identity(asset_id: str, store: Any = None) -> str:
    if store is None:
        from app.storage.asset_store import asset_store
        store = asset_store
    record = await store.get_asset(asset_id)
    if record is None:
        raise ValueError(f"Managed asset is missing: {asset_id}")
    try:
        identity = await asyncio.to_thread(hash_file, store.get_absolute_path(record))
    except OSError as error:
        raise ValueError(f"Managed asset file is unavailable: {asset_id}") from error
    if identity != record.content_hash:
        raise ValueError(f"Managed asset content changed or is corrupt: {asset_id}")
    return identity


async def port_content_identity(value: Any, port_type: DataType) -> str:
    if port_type in {DataType.STRING, DataType.JSON} or value is None:
        return compute_content_hash({"type": port_type.value, "value": value})
    if isinstance(value, dict) and isinstance(value.get("asset_id"), str):
        return await managed_asset_identity(value["asset_id"])
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    if not isinstance(value, str):
        raise ValueError(f"Unsupported {port_type.value} content reference")
    managed = re.fullmatch(r"/api/v1/assets/([^/?]+)/content(?:\?[^#]*)?", value)
    if managed:
        return await managed_asset_identity(managed.group(1))
    if value.startswith("data:") and ";base64," in value:
        data = base64.b64decode(value.split(";base64,", 1)[1], validate=True)
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("Inline media exceeds the managed media size limit")
        return hashlib.sha256(data).hexdigest()
    if value.startswith(("http://", "https://")):
        digest = hashlib.sha256()
        size = 0
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            async with client.stream("GET", value) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise ValueError("Remote media exceeds the managed media size limit")
                    digest.update(chunk)
        if size == 0:
            raise ValueError("Remote media is empty")
        return digest.hexdigest()
    raise ValueError("Media inputs must reference managed assets, inline bytes or an HTTP resource")
