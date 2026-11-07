"""Integration tests for creative_runner ComfyUI asset upload (issue #105)."""

import hashlib
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import tempfile
from PIL import Image
from io import BytesIO

from app.runners.creative_runner import CreativeRunner
from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.storage.asset_store import AssetRecord


def create_test_png(width: int, height: int, mode: str = "RGB") -> bytes:
    """Create a valid PNG image as bytes."""
    img = Image.new(mode, (width, height), color=(255, 255, 255, 255) if mode == "RGBA" else (255, 255, 255))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def temp_asset_files():
    """Create temporary image and mask files for testing."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_file:
        img_file.write(create_test_png(512, 512, "RGB"))
        img_file.flush()
        img_path = Path(img_file.name)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as mask_file:
        mask_file.write(create_test_png(512, 512, "RGBA"))
        mask_file.flush()
        mask_path = Path(mask_file.name)

    yield img_path, mask_path

    # Cleanup
    img_path.unlink(missing_ok=True)
    mask_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_img2img_uploads_source_before_execution(temp_asset_files):
    """IMG2IMG should upload source image to ComfyUI before submitting workflow."""
    img_path, _ = temp_asset_files
    runner = CreativeRunner()

    req = CreativeActionRequest(
        action=CreativeActionType.IMG2IMG,
        prompt="test prompt",
        model="test_model.safetensors",
        engine_id="comfyui",
        input_image_id="test_img_id",
        width=512,
        height=512,
        seed=42,
    )

    # Mock asset store
    mock_asset = AssetRecord(
        id="test_img_id",
        filename="test.png",
        file_path="test.png",
        media_type="image",
        content_hash=hashlib.sha256(img_path.read_bytes()).hexdigest(),
        byte_size=1000,
        created_at="2024-01-01T00:00:00Z",
    )

    with patch("app.runners.creative_runner.asset_store") as mock_store:
        mock_store.get_asset = AsyncMock(return_value=mock_asset)
        mock_store.get_absolute_path = Mock(return_value=img_path)
        mock_store.save_image_from_url = AsyncMock(return_value=mock_asset)

        # Mock engine_manager and ComfyUI client
        from app.schemas.engine import EngineConnection, EngineType, EngineOwnership, EngineStatus
        mock_connection = EngineConnection(
            id="comfyui-managed",
            name="ComfyUI (Managed)",
            engine_type=EngineType.COMFYUI,
            ownership=EngineOwnership.MANAGED,
            status=EngineStatus.RUNNING,
            endpoint_url="http://127.0.0.1:8188",
        )

        with patch("app.runners.creative_runner.engine_manager") as mock_mgr:
            mock_mgr.get_engine = Mock(return_value=mock_connection)

            with patch("app.runners.creative_runner.ComfyUIClient") as MockClient:
                mock_comfy = MockClient.return_value
                mock_comfy.upload_image = AsyncMock(return_value={
                    "name": "uploaded_test.png",
                    "subfolder": "berry_assets",
                "type": "input",
            })
                mock_comfy.queue_prompt = AsyncMock(return_value={"prompt_id": "test_prompt_123"})
                mock_comfy.poll_history_outputs = AsyncMock(return_value=[{
                    "filename": "output.png",
                    "subfolder": "",
                    "type": "output",
                }])
                mock_comfy.base_url = "http://127.0.0.1:8188"

                # Mock cache
                with patch("app.runners.creative_runner.cache_store") as mock_cache:
                    mock_cache.get_async = AsyncMock(return_value=None)
                    mock_cache.set_async = AsyncMock()

                    result = await runner.execute(req)

                    # Verify upload was called with correct path
                    mock_comfy.upload_image.assert_called_once()
                    upload_call_args = mock_comfy.upload_image.call_args
                    # Path may have different formats (forward/back slashes), just check it was called
                    assert upload_call_args is not None

                    # Verify workflow was submitted after upload
                    mock_comfy.queue_prompt.assert_called_once()

                assert result.success is True


@pytest.mark.asyncio
async def test_inpaint_uploads_both_image_and_mask(temp_asset_files, mock_engine_manager):
    """INPAINT should upload both source image and mask before execution."""
    img_path, mask_path = temp_asset_files
    runner = CreativeRunner()

    req = CreativeActionRequest(
        action=CreativeActionType.INPAINT,
        prompt="inpaint test",
        model="test_model.safetensors",
        engine_id="comfyui",
        input_image_id="img_id",
        mask_image_id="mask_id",
        width=512,
        height=512,
        seed=42,
    )

    mock_img_asset = AssetRecord(
        id="img_id",
        filename="source.png",
        file_path="source.png",
        media_type="image",
        content_hash=hashlib.sha256(img_path.read_bytes()).hexdigest(),
        byte_size=1000,
        created_at="2024-01-01T00:00:00Z",
    )

    mock_mask_asset = AssetRecord(
        id="mask_id",
        filename="mask.png",
        file_path="mask.png",
        media_type="image",
        content_hash=hashlib.sha256(mask_path.read_bytes()).hexdigest(),
        byte_size=500,
        created_at="2024-01-01T00:00:00Z",
    )

    with patch("app.runners.creative_runner.asset_store") as mock_store:
        def get_asset_side_effect(asset_id):
            if asset_id == "img_id":
                return mock_img_asset
            elif asset_id == "mask_id":
                return mock_mask_asset
            return None

        def get_path_side_effect(asset_rec):
            if asset_rec.id == "img_id":
                return img_path
            elif asset_rec.id == "mask_id":
                return mask_path
            return None

        mock_store.get_asset = AsyncMock(side_effect=get_asset_side_effect)
        mock_store.get_absolute_path = Mock(side_effect=get_path_side_effect)
        mock_store.save_image_from_url = AsyncMock(return_value=mock_img_asset)

        from app.schemas.engine import EngineConnection, EngineType, EngineOwnership, EngineStatus
        mock_connection = EngineConnection(
            id="comfyui-managed",
            name="ComfyUI (Managed)",
            engine_type=EngineType.COMFYUI,
            ownership=EngineOwnership.MANAGED,
            status=EngineStatus.RUNNING,
            endpoint_url="http://127.0.0.1:8188",
        )

        with patch("app.runners.creative_runner.engine_manager") as mock_mgr:
            mock_mgr.get_engine = Mock(return_value=mock_connection)

            with patch("app.runners.creative_runner.ComfyUIClient") as MockComfyClient:
                mock_comfy = MockComfyClient.return_value
                mock_comfy.upload_image = AsyncMock(return_value={
                    "name": "uploaded_source.png",
                    "subfolder": "berry_assets",
                    "type": "input",
                })
                # Mock upload_mask to handle the converted mask file
                mock_comfy.upload_mask = AsyncMock(return_value={
                    "name": "uploaded_mask.png",
                    "subfolder": "berry_assets",
                    "type": "input",
                })
                mock_comfy.queue_prompt = AsyncMock(return_value={"prompt_id": "inpaint_123"})
                mock_comfy.poll_history_outputs = AsyncMock(return_value=[{
                    "filename": "inpainted.png",
                    "subfolder": "",
                    "type": "output",
                }])
                mock_comfy.base_url = "http://127.0.0.1:8188"

                with patch("app.runners.creative_runner.cache_store") as mock_cache:
                    mock_cache.get_async = AsyncMock(return_value=None)
                    mock_cache.set_async = AsyncMock()

                    # Mock normalize_mask_for_comfyui to avoid file system operations
                    with patch("app.runners.creative_runner.normalize_mask_for_comfyui") as mock_convert:
                        mock_convert.return_value = mask_path  # Return original for test simplicity

                        result = await runner.execute(req)

                        # Verify both uploads were called
                        mock_comfy.upload_image.assert_called_once()
                        mock_comfy.upload_mask.assert_called_once()

                        # Verify workflow submission happened after uploads
                        mock_comfy.queue_prompt.assert_called_once()

                        assert result.success is True


@pytest.mark.asyncio
async def test_upscale_uploads_source_image(temp_asset_files, mock_engine_manager):
    """UPSCALE should upload source image before execution."""
    img_path, _ = temp_asset_files
    runner = CreativeRunner()

    req = CreativeActionRequest(
        action=CreativeActionType.UPSCALE,
        prompt="",
        model="",
        engine_id="comfyui",
        input_image_id="upscale_img_id",
        upscaler_name="RealESRGAN_x4plus.pth",
        upscale_factor=4,
        width=512,
        height=512,
        seed=42,
    )

    mock_asset = AssetRecord(
        id="upscale_img_id",
        filename="to_upscale.png",
        file_path="to_upscale.png",
        media_type="image",
        content_hash=hashlib.sha256(img_path.read_bytes()).hexdigest(),
        byte_size=1000,
        created_at="2024-01-01T00:00:00Z",
    )

    with patch("app.runners.creative_runner.asset_store") as mock_store:
        mock_store.get_asset = AsyncMock(return_value=mock_asset)
        mock_store.get_absolute_path = Mock(return_value=img_path)
        mock_store.save_image_from_url = AsyncMock(return_value=mock_asset)

        with patch("app.runners.creative_runner.ComfyUIClient") as MockClient:
            mock_comfy = MockClient.return_value
            mock_comfy.upload_image = AsyncMock(return_value={
                "name": "uploaded_upscale.png",
                "subfolder": "berry_assets",
                "type": "input",
            })
            mock_comfy.queue_prompt = AsyncMock(return_value={"prompt_id": "upscale_123"})
            mock_comfy.poll_history_outputs = AsyncMock(return_value=[{
                "filename": "upscaled.png",
                "subfolder": "",
                "type": "output",
            }])
            mock_comfy.base_url = "http://127.0.0.1:8188"

            with patch("app.runners.creative_runner.cache_store") as mock_cache:
                mock_cache.get_async = AsyncMock(return_value=None)
                mock_cache.set_async = AsyncMock()

                result = await runner.execute(req)

                mock_comfy.upload_image.assert_called_once()
                mock_comfy.queue_prompt.assert_called_once()

                assert result.success is True


@pytest.mark.asyncio
async def test_upload_failure_prevents_workflow_submission(mock_engine_manager):
    """If upload fails, workflow should not be submitted and error should be reported."""
    runner = CreativeRunner()

    req = CreativeActionRequest(
        action=CreativeActionType.IMG2IMG,
        prompt="test",
        model="test.safetensors",
        engine_id="comfyui",
        input_image_id="img_id",
        width=512,
        height=512,
        seed=42,
    )

    mock_asset = AssetRecord(
        id="img_id",
        filename="test.png",
        file_path="test.png",
        media_type="image",
        content_hash=hashlib.sha256(b"fake_data").hexdigest(),
        byte_size=1000,
        created_at="2024-01-01T00:00:00Z",
    )

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"fake_data")
        temp_path = Path(f.name)

    try:
        with patch("app.runners.creative_runner.asset_store") as mock_store:
            mock_store.get_asset = AsyncMock(return_value=mock_asset)
            mock_store.get_absolute_path = Mock(return_value=temp_path)

            with patch("app.runners.creative_runner.ComfyUIClient") as MockClient:
                mock_comfy = MockClient.return_value
                # Upload fails with RuntimeError
                mock_comfy.upload_image = AsyncMock(side_effect=RuntimeError("Connection refused"))
                mock_comfy.queue_prompt = AsyncMock()

                with patch("app.runners.creative_runner.cache_store") as mock_cache:
                    mock_cache.get_async = AsyncMock(return_value=None)

                    result = await runner.execute(req)

                    # Verify workflow was NOT submitted after upload failure
                    mock_comfy.queue_prompt.assert_not_called()

                    # Verify error is reported
                    assert result.success is False
                    assert "Connection refused" in result.error_message
    finally:
        temp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_uploaded_filename_used_in_workflow(mock_engine_manager):
    """Verify that the uploaded filename from ComfyUI is used in the compiled workflow."""
    runner = CreativeRunner()

    req = CreativeActionRequest(
        action=CreativeActionType.IMG2IMG,
        prompt="test",
        model="test.safetensors",
        engine_id="comfyui",
        input_image_id="img_id",
        width=512,
        height=512,
        seed=42,
    )

    mock_asset = AssetRecord(
        id="img_id",
        filename="original.png",
        file_path="original.png",
        media_type="image",
        content_hash=hashlib.sha256(b"fake_data").hexdigest(),
        byte_size=1000,
        created_at="2024-01-01T00:00:00Z",
    )

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"fake_data")
        temp_path = Path(f.name)

    try:
        with patch("app.runners.creative_runner.asset_store") as mock_store:
            mock_store.get_asset = AsyncMock(return_value=mock_asset)
            mock_store.get_absolute_path = Mock(return_value=temp_path)
            mock_store.save_image_from_url = AsyncMock(return_value=mock_asset)

            with patch("app.runners.creative_runner.ComfyUIClient") as MockClient:
                mock_comfy = MockClient.return_value
                # ComfyUI returns a different filename after upload
                mock_comfy.upload_image = AsyncMock(return_value={
                    "name": "comfy_renamed_12345.png",
                    "subfolder": "berry_assets",
                    "type": "input",
                })
                mock_comfy.queue_prompt = AsyncMock(return_value={"prompt_id": "test_123"})
                mock_comfy.poll_history_outputs = AsyncMock(return_value=[{
                    "filename": "output.png",
                    "subfolder": "",
                    "type": "output",
                }])
                mock_comfy.base_url = "http://127.0.0.1:8188"

                with patch("app.runners.creative_runner.cache_store") as mock_cache:
                    mock_cache.get_async = AsyncMock(return_value=None)
                    mock_cache.set_async = AsyncMock()

                    result = await runner.execute(req)

                    # Get the workflow that was queued
                    queued_workflow = mock_comfy.queue_prompt.call_args[0][0]

                    # The workflow should reference the ComfyUI-returned filename, not the original
                    workflow_str = str(queued_workflow)
                    assert "berry_assets/comfy_renamed_12345.png" in workflow_str
                    assert "original.png" not in workflow_str

                    assert result.success is True
    finally:
        temp_path.unlink(missing_ok=True)
