"""Verified uploads and safe content descriptors, independent of HTTP transport."""

import base64
import binascii
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.media_validator import sanitize_filename, validate_and_inspect_media
from app.core.workers import run_blocking
from app.schemas.project import AssetRecord
from app.storage.asset_store import AssetStore


@dataclass(frozen=True)
class AssetContent:
    path: Path
    mime_type: str
    filename: str
    disposition: Literal['inline', 'attachment']


@dataclass(frozen=True)
class AssetService:
    store: AssetStore

    async def upload(self, data: bytes, filename: str | None) -> AssetRecord:
        name = sanitize_filename(filename)
        mime, width, height = await run_blocking(validate_and_inspect_media, data, name)
        return await self.store.save_bytes(data, filename=name,
            media_type='video' if mime.startswith('video/') else 'image', width=width, height=height)

    async def upload_base64(self, content: str, filename: str) -> AssetRecord:
        try:
            data = base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError(f'Invalid base64 payload: {error}') from error
        return await self.upload(data, filename)

    async def get(self, asset_id: str) -> AssetRecord:
        record = await self.store.get_asset(asset_id)
        if record is None:
            raise LookupError('Asset not found')
        return record

    async def content(self, asset_id: str) -> AssetContent:
        record = await self.get(asset_id)
        path = self.store.get_absolute_path(record)
        if not await run_blocking(path.is_file):
            raise LookupError('Asset file missing on disk')
        safe_types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                      '.webp': 'image/webp', '.gif': 'image/gif', '.mp4': 'video/mp4', '.webm': 'video/webm'}
        mime = record.mime_type or safe_types.get(path.suffix.lower())
        name = f'{Path(record.filename).stem}{record.extension}' if record.extension else record.filename
        return AssetContent(path, mime or 'application/octet-stream', sanitize_filename(name),
                            'inline' if mime else 'attachment')
