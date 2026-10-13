"""Mutable media URLs and corrupt cached files cannot establish reuse."""

import asyncio
import hashlib
import io
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from PIL import Image

from app.core.cache import CacheStore
from app.core.content_identity import port_content_identity
from app.schemas.node import DataType
from app.storage.asset_store import AssetStore
from app.storage.db import DatabaseManager


@pytest.mark.asyncio
async def test_stable_remote_url_tracks_bytes_and_port_type() -> None:
    content = b"first content"

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    with patch("app.core.content_identity.httpx.AsyncClient", return_value=client):
        first = await port_content_identity("https://fixture.test/stable.png", DataType.IMAGE)
    content = b"changed content"
    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    with patch("app.core.content_identity.httpx.AsyncClient", return_value=client):
        changed = await port_content_identity("https://fixture.test/stable.png", DataType.IMAGE)
    text = await port_content_identity("https://fixture.test/stable.png", DataType.STRING)
    assert first != changed
    assert text not in {first, changed}


@pytest.mark.asyncio
async def test_corrupt_output_invalidates_persistent_cache(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "cache.db")
    assets = AssetStore(manager=manager, base_dir=tmp_path)
    cache = CacheStore(manager, assets)
    try:
        asset = await assets.save_bytes(b"first content", "fixture.png", media_type="image")
        await cache.set_async("node", {"image": f"/api/v1/assets/{asset.id}/content"})
        assert await cache.get_async("node") is not None
        assets.get_absolute_path(asset).write_bytes(b"changed content")
        cache.clear()
        assert await cache.get_async("node") is None
        assert not await cache.has_async("node")
        await cache.set_async("remote", {"image": "https://fixture.test/expired.png"})
        assert await cache.get_async("remote") is None
    finally:
        await manager.close()


def test_valid_owned_content_is_reused_without_replacement(tmp_path: Path) -> None:
    assets = AssetStore(base_dir=tmp_path)
    data = b"owned content"
    identity = hashlib.sha256(data).hexdigest()
    relative = assets._persist_bytes(data, identity, ".png")
    with patch("app.storage.asset_store.os.replace", side_effect=AssertionError("Valid bytes must be reused")):
        assert assets._persist_bytes(data, identity, ".png") == relative


def test_failed_publication_keeps_old_bytes_and_removes_staging(tmp_path: Path) -> None:
    assets = AssetStore(base_dir=tmp_path)
    data = b"owned content"
    identity = hashlib.sha256(data).hexdigest()
    relative = assets._persist_bytes(data, identity, ".png")
    path = assets.assets_dir / relative
    path.write_bytes(b"corrupt")
    with patch("app.storage.asset_store.os.replace", side_effect=OSError("Disk publication failed")):
        with pytest.raises(OSError, match="Disk publication failed"):
            assets._persist_bytes(data, identity, ".png")
    assert path.read_bytes() == b"corrupt"
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.asyncio
async def test_concurrent_owned_writes_publish_complete_content(tmp_path: Path) -> None:
    assets = AssetStore(base_dir=tmp_path)
    data = b"owned content" * 100000
    identity = hashlib.sha256(data).hexdigest()
    stores = [AssetStore(base_dir=tmp_path) for _ in range(8)]
    results = await asyncio.gather(
        *(asyncio.to_thread(store._persist_bytes, data, identity, ".png") for store in stores)
    )
    assert len(set(results)) == 1
    path = assets.assets_dir / results[0]
    assert path.read_bytes() == data
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.asyncio
async def test_retry_restores_corrupt_content_addressed_output(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "retry.db")
    assets = AssetStore(manager=manager, base_dir=tmp_path)
    cache = CacheStore(manager, assets)
    buffer = io.BytesIO()
    with Image.new("RGB", (11, 7), "red") as image:
        image.save(buffer, "PNG")
    data = buffer.getvalue()
    try:
        original = await assets.save_bytes(data, "original.png")
        original_url = f"/api/v1/assets/{original.id}/content"
        await cache.set_async("node", {"image": original_url})
        path = assets.get_absolute_path(original)
        path.write_bytes(b"corrupted output")
        assert await cache.get_async("node") is None

        retried = await assets.save_bytes(data, "retry.png")
        assert assets.get_absolute_path(retried) == path
        assert path.read_bytes() == data
        await cache.set_async("node", {"image": f"/api/v1/assets/{retried.id}/content"})
        await manager.close()
        cache.clear()
        assert await cache.has_async("node")
        # Repair also makes the older immutable asset reference accessible again.
        assert await cache.validate_output_assets({"image": original_url})
    finally:
        await manager.close()
