"""Malformed or redirected provider outputs must not reach durable storage."""

import io
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image

from app.core.cloud_media import adopt_cloud_image


@pytest.mark.asyncio
async def test_download_decodes_actual_jpeg_and_omits_authentication() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (31, 17), "red").save(buffer, format="JPEG")
    store = AsyncMock()

    def transport(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(
            200, content=buffer.getvalue(), headers={"content-type": "image/png"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        await adopt_cloud_image(
            store=store,
            url="https://fixture.invalid/output.png",
            client=client,
            project_id="project",
        )
    assert store.save_bytes.await_args.kwargs == {
        "filename": "cloud_output.jpg",
        "media_type": "image",
        "project_id": "project",
        "width": 31,
        "height": 17,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content", [b"<html>error</html>", b"\x89PNG\r\n\x1a\ntruncated", b""]
)
async def test_invalid_content_never_publishes_an_asset(content: bytes) -> None:
    store = AsyncMock()
    with pytest.raises(ValueError):
        await adopt_cloud_image(store=store, content=content)
    store.save_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_redirect_is_rejected_without_followup_or_storage() -> None:
    store = AsyncMock()
    calls: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            302, headers={"location": "https://unrelated.invalid/output"}
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(transport), follow_redirects=True
    ) as client:
        with pytest.raises(ValueError, match="HTTP 302"):
            await adopt_cloud_image(
                store=store, url="https://fixture.invalid/output", client=client
            )
    assert len(calls) == 1
    store.save_bytes.assert_not_called()
