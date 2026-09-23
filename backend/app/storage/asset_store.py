"""Content-addressable asset storage for durable generated media."""

import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import httpx

from app.schemas.project import AssetRecord
from app.storage.db import DatabaseManager, db_manager, get_default_data_dir


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
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def save_bytes(
        self,
        data: bytes,
        filename: str,
        media_type: str = "image",
        project_id: Optional[str] = None,
    ) -> AssetRecord:
        content_hash = hashlib.sha256(data).hexdigest()
        byte_size = len(data)

        # Content-addressable subfolder structure: assets/{hash[:2]}/{hash}{ext}
        ext = Path(filename).suffix or ".png"
        subdir = self.assets_dir / content_hash[:2]
        subdir.mkdir(parents=True, exist_ok=True)
        target_path = subdir / f"{content_hash}{ext}"

        if not target_path.exists():
            target_path.write_bytes(data)

        asset_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        rel_path = str(target_path.relative_to(self.assets_dir))

        conn = await self.manager.get_connection()
        await conn.execute(
            """
            INSERT INTO assets (id, project_id, filename, file_path, media_type, content_hash, byte_size, width, height, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (asset_id, project_id, filename, rel_path, media_type, content_hash, byte_size, None, None, now),
        )
        await conn.commit()

        return AssetRecord(
            id=asset_id,
            project_id=project_id,
            filename=filename,
            file_path=rel_path,
            media_type=media_type,
            content_hash=content_hash,
            byte_size=byte_size,
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
            SELECT id, project_id, filename, file_path, media_type, content_hash, byte_size, width, height, created_at
            FROM assets WHERE id = ?
            """,
            (asset_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return AssetRecord(
                id=row["id"],
                project_id=row["project_id"],
                filename=row["filename"],
                file_path=row["file_path"],
                media_type=row["media_type"],
                content_hash=row["content_hash"],
                byte_size=row["byte_size"],
                width=row["width"],
                height=row["height"],
                created_at=row["created_at"],
            )

    async def get_asset_by_hash(self, content_hash: str) -> Optional[AssetRecord]:
        conn = await self.manager.get_connection()
        async with conn.execute(
            """
            SELECT id, project_id, filename, file_path, media_type, content_hash, byte_size, width, height, created_at
            FROM assets WHERE content_hash = ? ORDER BY created_at DESC LIMIT 1
            """,
            (content_hash,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return AssetRecord(
                id=row["id"],
                project_id=row["project_id"],
                filename=row["filename"],
                file_path=row["file_path"],
                media_type=row["media_type"],
                content_hash=row["content_hash"],
                byte_size=row["byte_size"],
                width=row["width"],
                height=row["height"],
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
                    id=row["id"],
                    project_id=row["project_id"],
                    filename=row["filename"],
                    file_path=row["file_path"],
                    media_type=row["media_type"],
                    content_hash=row["content_hash"],
                    byte_size=row["byte_size"],
                    width=row["width"],
                    height=row["height"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]


asset_store = AssetStore()
