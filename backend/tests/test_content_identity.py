"""Mutable media URLs and corrupt cached files cannot establish reuse."""

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

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
