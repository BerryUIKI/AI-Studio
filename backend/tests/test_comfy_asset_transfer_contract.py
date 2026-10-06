"""Verify upload ordering, engine references, failure handling, and cache reuse."""

import json
import struct
import zlib
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.runners.comfy_runner import ComfyUIClient
from app.runners.creative_runner import CreativeRunner
from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.storage.asset_store import AssetRecord


@pytest.mark.asyncio
@pytest.mark.parametrize("action,fail_mask", [
    ("img2img", False), ("inpaint", False), ("upscale", False),
    ("img2video", False), ("inpaint", True),
])
async def test_upload_then_queue_and_cache_reuse(
    tmp_path: Path, action: str, fail_mask: bool,
) -> None:
    originals: dict[Path, bytes] = {}
    records: dict[str, AssetRecord] = {}
    for name in ("source", "mask"):
        path = tmp_path / f"{name}.png"
        def chunk(kind: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + bytes((255, 255, 255, 128)) * 8) * 8))
            + chunk(b"IEND", b"")
        )
        originals[path] = path.read_bytes()
        records[name] = AssetRecord(
            id=name, filename=path.name, file_path=path.name, media_type="image",
            content_hash=f"{name}-hash", byte_size=path.stat().st_size,
            created_at="2026-10-06T00:00:00Z",
        )
    events: list[str] = []
    cached: dict[str, Any] = {}

    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload/image":
            body = await request.aread()
            name = "mask" if b'filename="mask.png"' in body else "source"
            events.append(name)
            if name == "mask" and fail_mask:
                return httpx.Response(503)
            return httpx.Response(200, json={
                "name": f"{name} (1).png", "subfolder": "engine/folder", "type": "input",
            })
        assert request.url.path == "/prompt"
        events.append("queue")
        graph = json.loads(await request.aread())["prompt"]
        loaded = {
            node["inputs"]["image"] for node in graph.values()
            if node["class_type"] == "LoadImage"
        }
        expected = {"engine/folder/source (1).png"}
        if action == "inpaint":
            expected.add("engine/folder/mask (1).png")
        assert loaded == expected
        assert events == (["source", "mask", "queue"] if action == "inpaint" else ["source", "queue"])
        return httpx.Response(200, json={"prompt_id": "test-prompt"})

    async def save_cache(key: str, value: dict[str, Any]) -> None:
        cached[key] = value

    client = ComfyUIClient()
    client.poll_history_outputs = AsyncMock(return_value=[{"filename": "output.png", "type": "output"}])
    req = CreativeActionRequest(
        action=CreativeActionType(action), engine_id="comfyui", input_image_id="source",
        mask_image_id="mask" if action == "inpaint" else None, seed=42,
    )
    with (
        patch("app.runners.creative_runner.comfy_client", client),
        patch("app.runners.creative_runner.asset_store") as store,
        patch("app.runners.creative_runner.cache_store") as cache,
    ):
        store.get_asset = AsyncMock(side_effect=records.get)
        store.get_absolute_path = Mock(side_effect=lambda rec: tmp_path / rec.filename)
        store.save_image_from_url = AsyncMock(return_value=Mock(id="output"))
        store.save_media_from_url = AsyncMock(return_value=Mock(id="output"))
        cache.get_async = AsyncMock(side_effect=cached.get)
        cache.set_async = AsyncMock(side_effect=save_cache)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
            client._client = transport
            first = await CreativeRunner().execute(req)
            if fail_mask:
                assert not first.success
                assert "Failed to transfer mask" in first.error_message
                assert events == ["source", "mask"]
                cache.set_async.assert_not_awaited()
                client.poll_history_outputs.assert_not_awaited()
            else:
                assert first.success, first.error_message
                second = await CreativeRunner().execute(req)
                assert second.success and second.is_cached
                assert second.asset_id == first.asset_id
                assert events.count("source") == events.count("queue") == 1
                client.poll_history_outputs.assert_awaited_once()
    assert {path: path.read_bytes() for path in originals} == originals
