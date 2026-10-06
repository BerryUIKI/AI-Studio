"""Tests for ComfyUI asset upload functionality (issue #105)."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, mock_open
import httpx

from app.runners.comfy_runner import ComfyUIClient


@pytest.mark.asyncio
async def test_upload_image_success():
    """Upload image should post to /upload/image and return engine filename."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)

    mock_response_data = {
        "name": "berry_test_12345.png",
        "subfolder": "berry_assets",
        "type": "input",
    }
    mock_request = httpx.Request("POST", "http://127.0.0.1:8188/upload/image")
    mock_resp = httpx.Response(200, json=mock_response_data, request=mock_request)

    with patch("pathlib.Path.is_file", return_value=True):
        with patch("builtins.open", mock_open(read_data=b"fake_image_data")):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp

                result = await c.upload_image("/fake/path/test.png", subfolder="berry_assets")

                assert result["name"] == "berry_test_12345.png"
                assert result["subfolder"] == "berry_assets"
                assert result["type"] == "input"

                # Verify the POST was called with correct endpoint
                mock_post.assert_called_once()
                call_args = mock_post.call_args
                assert "/upload/image" in str(call_args)


@pytest.mark.asyncio
async def test_upload_image_file_not_found():
    """Upload should raise FileNotFoundError if source image doesn't exist."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)

    with patch("pathlib.Path.is_file", return_value=False):
        with pytest.raises(FileNotFoundError) as exc_info:
            await c.upload_image("/nonexistent/image.png")

        assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_upload_image_http_error():
    """Upload should raise RuntimeError with meaningful message on HTTP error."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)

    mock_resp = httpx.Response(500, json={"error": "Internal server error"})
    http_error = httpx.HTTPStatusError("Server error", request=Mock(), response=mock_resp)

    with patch("pathlib.Path.is_file", return_value=True):
        with patch("builtins.open", mock_open(read_data=b"fake_data")):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = http_error

                with pytest.raises(RuntimeError) as exc_info:
                    await c.upload_image("/fake/test.png")

                assert "ComfyUI upload failed" in str(exc_info.value)
                assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_image_missing_name_in_response():
    """Upload should raise RuntimeError if response lacks 'name' field."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)

    mock_request = httpx.Request("POST", "http://127.0.0.1:8188/upload/image")
    mock_resp = httpx.Response(200, json={"status": "ok"}, request=mock_request)  # Missing 'name'

    with patch("pathlib.Path.is_file", return_value=True):
        with patch("builtins.open", mock_open(read_data=b"fake_data")):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp

                with pytest.raises(RuntimeError) as exc_info:
                    await c.upload_image("/fake/test.png")

                assert "unexpected response" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_upload_mask_success():
    """Upload mask should post to /upload/mask and return engine filename."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)

    mock_response_data = {
        "name": "mask_12345.png",
        "subfolder": "berry_assets",
        "type": "input",
    }
    mock_request = httpx.Request("POST", "http://127.0.0.1:8188/upload/mask")
    mock_resp = httpx.Response(200, json=mock_response_data, request=mock_request)

    with patch("pathlib.Path.is_file", return_value=True):
        with patch("builtins.open", mock_open(read_data=b"fake_mask_data")):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp

                result = await c.upload_mask("/fake/mask.png", subfolder="berry_assets")

                assert result["name"] == "mask_12345.png"
                assert result["subfolder"] == "berry_assets"

                # Verify POST to /upload/mask
                mock_post.assert_called_once()
                call_args = mock_post.call_args
                assert "/upload/mask" in str(call_args)


@pytest.mark.asyncio
async def test_upload_mask_fallback_to_upload_image():
    """Upload mask should fall back to /upload/image if /upload/mask returns 404."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)

    # First call to /upload/mask returns 404
    mock_404_request = httpx.Request("POST", "http://127.0.0.1:8188/upload/mask")
    mock_404_resp = httpx.Response(404, json={"error": "Not found"}, request=mock_404_request)
    mask_error = httpx.HTTPStatusError("Not found", request=mock_404_request, response=mock_404_resp)

    # Second call to /upload/image succeeds
    mock_success_request = httpx.Request("POST", "http://127.0.0.1:8188/upload/image")
    mock_success_resp = httpx.Response(200, json={
        "name": "fallback_mask.png",
        "subfolder": "berry_assets",
        "type": "input",
    }, request=mock_success_request)

    with patch("pathlib.Path.is_file", return_value=True):
        with patch("builtins.open", mock_open(read_data=b"fake_mask")):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                # First call raises 404, second call succeeds
                mock_post.side_effect = [mask_error, mock_success_resp]

                result = await c.upload_mask("/fake/mask.png", subfolder="berry_assets")

                assert result["name"] == "fallback_mask.png"
                assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_upload_mask_file_not_found():
    """Upload mask should raise FileNotFoundError if mask file doesn't exist."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)

    with patch("pathlib.Path.is_file", return_value=False):
        with pytest.raises(FileNotFoundError) as exc_info:
            await c.upload_mask("/nonexistent/mask.png")

        assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_upload_handles_subfolder_correctly():
    """Upload should include subfolder in request data and handle it in response."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)

    mock_request = httpx.Request("POST", "http://127.0.0.1:8188/upload/image")
    mock_resp = httpx.Response(200, json={
        "name": "test.png",
        "subfolder": "custom_folder",
        "type": "input",
    }, request=mock_request)

    with patch("pathlib.Path.is_file", return_value=True):
        with patch("builtins.open", mock_open(read_data=b"data")):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp

                result = await c.upload_image("/fake/test.png", subfolder="custom_folder")

                assert result["subfolder"] == "custom_folder"

                # Check that subfolder was passed in the form data
                call_kwargs = mock_post.call_args.kwargs
                assert "data" in call_kwargs
                assert call_kwargs["data"]["subfolder"] == "custom_folder"


@pytest.mark.asyncio
async def test_upload_overwrite_parameter():
    """Upload should pass overwrite parameter correctly."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)

    mock_request = httpx.Request("POST", "http://127.0.0.1:8188/upload/image")
    mock_resp = httpx.Response(200, json={"name": "test.png", "subfolder": "", "type": "input"}, request=mock_request)

    with patch("pathlib.Path.is_file", return_value=True):
        with patch("builtins.open", mock_open(read_data=b"data")):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp

                await c.upload_image("/fake/test.png", overwrite=True)

                call_kwargs = mock_post.call_args.kwargs
                assert call_kwargs["data"]["overwrite"] == "true"


@pytest.mark.asyncio
async def test_upload_connection_error():
    """Upload should raise RuntimeError on connection failure."""
    c = ComfyUIClient(host="127.0.0.1", port=8188)

    with patch("pathlib.Path.is_file", return_value=True):
        with patch("builtins.open", mock_open(read_data=b"data")):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = httpx.ConnectError("Connection refused")

                with pytest.raises(RuntimeError) as exc_info:
                    await c.upload_image("/fake/test.png")

                assert "Failed to upload image to ComfyUI" in str(exc_info.value)
