"""Exercise real multipart serialization for ComfyUI asset transfers (#105)."""

from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.runners.comfy_runner import ComfyUIClient


@pytest.mark.asyncio
@pytest.mark.parametrize("host,port", [("127.0.0.1", 8188), ("engine.example", 9000)])
@pytest.mark.parametrize("method,suffix,mime", [
    ("upload_image", ".jpg", "image/jpeg"),
    ("upload_mask", ".png", "image/png"),
])
async def test_upload_preserves_bytes_and_uses_engine_reference(
    tmp_path: Path, host: str, port: int, method: str, suffix: str, mime: str,
) -> None:
    source = tmp_path / f"original{suffix}"
    content = b"\x00\xff\x80source-or-mask-bytes\r\n"
    source.write_bytes(content)
    requests: list[httpx.Request] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert str(request.url) == f"http://{host}:{port}/upload/image"
        body = await request.aread()
        message = BytesParser(policy=policy.default).parsebytes(
            f"Content-Type: {request.headers['content-type']}\r\n\r\n".encode() + body
        )
        parts = {
            part.get_param("name", header="content-disposition"): part
            for part in message.iter_parts()
        }
        assert parts["image"].get_filename() == source.name
        assert parts["image"].get_content_type() == mime
        assert parts["image"].get_payload(decode=True) == content
        assert parts["subfolder"].get_payload(decode=True) == b"berry_assets"
        assert parts["type"].get_payload(decode=True) == b"input"
        assert parts["overwrite"].get_payload(decode=True) == b"false"
        return httpx.Response(200, json={
            "name": "renamed (1).png", "subfolder": "engine/subfolder", "type": "input",
        })

    client = ComfyUIClient(host=host, port=port)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        client._client = transport
        result = await getattr(client, method)(str(source), subfolder="berry_assets")
    assert len(requests) == 1
    assert result == {"name": "renamed (1).png", "subfolder": "engine/subfolder", "type": "input"}
    assert source.read_bytes() == content


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    {}, {"name": ""}, {"name": None}, {"name": 12},
    {"name": "x.png", "subfolder": None},
    {"name": "x.png", "type": "output"}, [],
])
async def test_invalid_upload_reference_is_rejected(tmp_path: Path, response: Any) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"data")
    client = ComfyUIClient()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response))
    ) as transport:
        client._client = transport
        with pytest.raises(RuntimeError, match="unexpected response"):
            await client.upload_image(str(source))


@pytest.mark.asyncio
async def test_upload_defaults_and_explicit_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"data")

    async def handle(request: httpx.Request) -> httpx.Response:
        assert b'\r\n\r\ntrue\r\n' in await request.aread()
        return httpx.Response(200, json={"name": "renamed.png"})

    client = ComfyUIClient()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        client._client = transport
        result = await client.upload_image(str(source), subfolder="berry_assets", overwrite=True)
    assert result == {"name": "renamed.png", "subfolder": "berry_assets", "type": "input"}


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["upload_image", "upload_mask"])
async def test_missing_file_does_not_upload(tmp_path: Path, method: str) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        pytest.fail("Missing files must not send HTTP requests")

    client = ComfyUIClient()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        client._client = transport
        with pytest.raises(FileNotFoundError, match="not found"):
            await getattr(client, method)(str(tmp_path / "missing.png"))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "connection"])
async def test_upload_reports_failure(tmp_path: Path, failure: str) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"data")

    def handle(request: httpx.Request) -> httpx.Response:
        if failure == "connection":
            raise httpx.ConnectError("Connection refused", request=request)
        return httpx.Response(500)

    client = ComfyUIClient()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        client._client = transport
        with pytest.raises(RuntimeError, match="500|Connection refused"):
            await client.upload_mask(str(source))
