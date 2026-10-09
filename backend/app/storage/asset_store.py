"""Content-addressable asset storage for durable generated media."""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple
import httpx

from app.schemas.project import AssetRecord
from app.storage.db import DatabaseManager, db_manager, get_default_data_dir
from app.core.media_validator import inspect_media_metadata
from app.core.workers import run_blocking


def _metadata_for_bytes(data: bytes) -> dict[str, Any]:
    try:
        return inspect_media_metadata(data)
    except Exception:
        # Legacy non-media records remain readable without fabricated MIME metadata.
        return {}


def _metadata_for_file(path: Path) -> dict[str, Any]:
    try:
        return _metadata_for_bytes(path.read_bytes())
    except OSError:
        return {}


def _dimensions_for_file(path: Path, filename: str) -> Tuple[Optional[int], Optional[int]]:
    return _inspect_media_dimensions(path.read_bytes(), filename)


def _inspect_media_dimensions(data: bytes, filename: str) -> Tuple[Optional[int], Optional[int]]:
    """Inspect media bytes to detect true pixel dimensions."""
    try:
        from app.core.media_validator import validate_and_inspect_media
        _, w, h = validate_and_inspect_media(data, filename)
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass

    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(data)) as img:
            return img.width, img.height
    except Exception:
        pass

    return None, None


class AssetStore:
    """Manages physical files and metadata for media assets."""

    def __init__(self, manager: DatabaseManager = db_manager, base_dir: Optional[Path] = None) -> None:
        self.manager = manager
        self._base_dir = base_dir

    @property
    def assets_dir(self) -> Path:
        if self._base_dir:
            d = self._base_dir / "assets"
        else:
            d = get_default_data_dir() / "assets"
        return d

    def _persist_bytes(self, data: bytes, content_hash: str, extension: str) -> str:
        target_path = self.assets_dir / content_hash[:2] / f"{content_hash}{extension}"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if not target_path.exists():
            target_path.write_bytes(data)
        return str(target_path.relative_to(self.assets_dir))

    async def save_bytes(
        self,
        data: bytes,
        filename: str,
        media_type: str = "image",
        project_id: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> AssetRecord:
        content_hash = await run_blocking(lambda: hashlib.sha256(data).hexdigest())
        byte_size = len(data)
        media_metadata = await run_blocking(_metadata_for_bytes, data)

        # Content-addressable subfolder structure: assets/{hash[:2]}/{hash}{ext}
        ext = Path(filename).suffix or (".mp4" if media_type == "video" else ".png")
        if media_metadata:
            ext = str(media_metadata["extension"])
            filename = f"{Path(filename).stem}{ext}"
        elif media_type == "video":
            if data[:4] == b"\x1a\x45\xdf\xa3":
                ext = ".webm"
            elif len(data) >= 8 and data[4:8] in (b"ftyp", b"moov", b"wide", b"mdat"):
                ext = ".mp4"
            elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                ext = ".webp"
            if Path(filename).suffix != ext:
                filename = f"{Path(filename).stem}{ext}"

        rel_path = await run_blocking(self._persist_bytes, data, content_hash, ext)

        # Decode actual dimensions if not provided
        if width is None or height is None or width <= 0 or height <= 0:
            detected_w, detected_h = await run_blocking(_inspect_media_dimensions, data, filename)
            width = width or detected_w
            height = height or detected_h

        asset_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        conn = await self.manager.get_connection()
        await conn.execute(
            """
            INSERT INTO assets (id, project_id, filename, file_path, media_type, content_hash, byte_size, width, height, created_at, media_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (asset_id, project_id, filename, rel_path, media_type, content_hash, byte_size, width, height, now, json.dumps(media_metadata)),
        )
        await conn.commit()

        return AssetRecord(
            **media_metadata,
            id=asset_id,
            project_id=project_id,
            filename=filename,
            file_path=rel_path,
            media_type=media_type,
            content_hash=content_hash,
            byte_size=byte_size,
            width=width,
            height=height,
            file_exists=True,
            created_at=now,
        )

    async def save_image_from_url(
        self,
        url: str,
        filename: Optional[str] = None,
        project_id: Optional[str] = None,
        timeout: float = 30.0,
    ) -> AssetRecord:
        """Download remote image and persist into managed asset store."""
        return await self.save_media_from_url(url, filename=filename, media_type="image", project_id=project_id, timeout=timeout)

    async def save_media_from_url(
        self,
        url: str,
        filename: Optional[str] = None,
        media_type: str = "image",
        project_id: Optional[str] = None,
        timeout: float = 60.0,
    ) -> AssetRecord:
        """Download remote image or video and persist into managed asset store."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.content

        default_ext = ".mp4" if "video" in media_type else ".png"
        name = filename or Path(url.split("?")[0]).name or f"media_{uuid.uuid4().hex[:8]}{default_ext}"
        return await self.save_bytes(data=data, filename=name, media_type=media_type, project_id=project_id)

    async def get_asset(self, asset_id: str) -> Optional[AssetRecord]:
        conn = await self.manager.get_connection()
        async with conn.execute(
            """
            SELECT id, project_id, filename, file_path, media_type, content_hash, byte_size, width, height, created_at, media_json
            FROM assets WHERE id = ?
            """,
            (asset_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            w = row["width"]
            h = row["height"]
            if (w is None or h is None) and row["media_type"] == "image":
                disk_file = self.assets_dir / row["file_path"]
                if disk_file.is_file():
                    det_w, det_h = await run_blocking(_dimensions_for_file, disk_file, row["filename"])
                    if det_w and det_h:
                        w, h = det_w, det_h
                        await conn.execute("UPDATE assets SET width = ?, height = ? WHERE id = ?", (w, h, row["id"]))
                        await conn.commit()

            disk_file = self.assets_dir / row["file_path"]
            file_exists = disk_file.is_file()
            metadata = json.loads(row["media_json"] or "{}")
            if not metadata and file_exists:
                metadata = await run_blocking(_metadata_for_file, disk_file)
                if metadata:
                    await conn.execute("UPDATE assets SET media_json = ? WHERE id = ?", (json.dumps(metadata), asset_id))
                    await conn.commit()

            return AssetRecord(
                **metadata,
                id=row["id"],
                project_id=row["project_id"],
                filename=row["filename"],
                file_path=row["file_path"],
                media_type=row["media_type"],
                content_hash=row["content_hash"],
                byte_size=row["byte_size"],
                width=w,
                height=h,
                file_exists=file_exists,
                created_at=row["created_at"],
            )

    async def get_asset_by_hash(self, content_hash: str) -> Optional[AssetRecord]:
        conn = await self.manager.get_connection()
        async with conn.execute(
            """
            SELECT id, project_id, filename, file_path, media_type, content_hash, byte_size, width, height, created_at, media_json
            FROM assets WHERE content_hash = ? ORDER BY created_at DESC LIMIT 1
            """,
            (content_hash,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            w = row["width"]
            h = row["height"]
            if (w is None or h is None) and row["media_type"] == "image":
                disk_file = self.assets_dir / row["file_path"]
                if disk_file.is_file():
                    det_w, det_h = await run_blocking(_dimensions_for_file, disk_file, row["filename"])
                    if det_w and det_h:
                        w, h = det_w, det_h
                        await conn.execute("UPDATE assets SET width = ?, height = ? WHERE id = ?", (w, h, row["id"]))
                        await conn.commit()

            disk_file = self.assets_dir / row["file_path"]
            file_exists = disk_file.is_file()

            return AssetRecord(
                **json.loads(row["media_json"] or "{}"),
                id=row["id"],
                project_id=row["project_id"],
                filename=row["filename"],
                file_path=row["file_path"],
                media_type=row["media_type"],
                content_hash=row["content_hash"],
                byte_size=row["byte_size"],
                width=w,
                height=h,
                file_exists=file_exists,
                created_at=row["created_at"],
            )

    def get_absolute_path(self, asset: AssetRecord) -> Path:
        return self.assets_dir / asset.file_path

    async def list_assets(self, project_id: Optional[str] = None) -> List[AssetRecord]:
        conn = await self.manager.get_connection()
        if project_id:
            query = "SELECT * FROM assets WHERE project_id = ? ORDER BY created_at DESC"
            params = (project_id,)
        else:
            query = "SELECT * FROM assets ORDER BY created_at DESC"
            params = ()

        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [
                AssetRecord(
                    **json.loads(row["media_json"] or "{}"),
                    id=row["id"],
                    project_id=row["project_id"],
                    filename=row["filename"],
                    file_path=row["file_path"],
                    media_type=row["media_type"],
                    content_hash=row["content_hash"],
                    byte_size=row["byte_size"],
                    width=row["width"],
                    height=row["height"],
                    file_exists=(self.assets_dir / row["file_path"]).is_file(),
                    created_at=row["created_at"],
                )
                for row in rows
            ]


asset_store = AssetStore()
