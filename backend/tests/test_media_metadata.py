"""Managed media retain their real format even at extensionless content URLs."""

import io
from pathlib import Path

import pytest
from PIL import Image

from app.core.media_validator import normalize_source_png
from app.storage.asset_store import AssetStore
from app.storage.db import DatabaseManager


def image_bytes(format: str, animated: bool = False) -> bytes:
    output = io.BytesIO()
    first = Image.new("RGB", (8, 6), "red")
    second = Image.new("RGB", (8, 6), "blue")
    first.save(output, format=format, save_all=animated, append_images=[second] if animated else [], duration=100)
    first.close()
    second.close()
    return output.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize("format,mime,extension,animated", [
    ("JPEG", "image/jpeg", ".jpg", False), ("WEBP", "image/webp", ".webp", True),
    ("GIF", "image/gif", ".gif", True), ("MP4", "video/mp4", ".mp4", False),
])
async def test_metadata_survives_persistent_reopen(tmp_path: Path, format: str, mime: str,
                                                extension: str, animated: bool) -> None:
    manager = DatabaseManager(tmp_path / "media.db")
    store = AssetStore(manager, tmp_path)
    # This fixture establishes container MIME, not video decoding/codec compatibility.
    data = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42" if format == "MP4" else image_bytes(format, animated)
    try:
        asset = await store.save_bytes(data, "misleading.png", media_type="video" if animated else "image")
        assert asset.mime_type == mime
        assert asset.extension == extension
        assert asset.is_animated == animated
        assert asset.filename.endswith(extension)
        assert store.get_absolute_path(asset).read_bytes() == data
        await manager.close()
        restored = await store.get_asset(asset.id)
        assert restored.mime_type == mime
        assert restored.is_animated == animated
        assert (await store.list_assets())[0].extension == extension
    finally:
        await manager.close()


@pytest.mark.parametrize("format", ["JPEG", "WEBP", "GIF"])
def test_cloud_source_conversion_matches_declared_png_mime(format: str) -> None:
    normalized = normalize_source_png(image_bytes(format, format != "JPEG"))
    with Image.open(io.BytesIO(normalized)) as image:
        assert image.format == "PNG"
        assert image.size == (8, 6)
