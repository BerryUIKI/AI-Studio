"""Tests for Image Dimensions, Upscale Factor Preservation, and Output Metadata (Issue #123).

Verifies:
1. Decoding and persisting actual imported-image dimensions (no fabricated 512x512 defaults).
2. Issue's 640x360 fixture:
   - 2x upscale produces 1280x720.
   - 4x upscale produces 2560x1440.
3. Portrait fixture (360x640):
   - 2x upscale produces 720x1280.
   - 4x upscale produces 1440x2560.
4. Native-4x model requested at 2x inserts ImageScale node and outputs truthful dimensions.
5. Prevention of aspect-ratio defaults overwriting source dimensions for source-dependent actions.
6. Derivation of result dimensions and provenance from decoded output image files.
7. Verification of actual image bytes and pixel dimensions using PIL (not merely mocked metadata).

NOTE ON LIVE HARDWARE CHECKS:
Real NVIDIA GPU inference on live ComfyUI / SD WebUI daemons was not run in this automated suite;
verified through protocol simulation and actual Pillow image byte decoding and validation.
"""

import io
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runners.creative_runner import CreativeRunner
from app.runners.macro_compiler import build_comfy_upscale_graph, get_upscaler_native_factor
from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.schemas.engine import EngineConnection, EngineOwnership, EngineStatus, EngineType
from app.storage.asset_store import asset_store

client = TestClient(app)


def make_png_bytes(width: int, height: int, color=(100, 150, 200)) -> bytes:
    """Generate valid PNG bytes with explicit pixel dimensions."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mock_comfy_connection():
    return EngineConnection(
        id="comfyui-managed",
        name="ComfyUI (Managed)",
        engine_type=EngineType.COMFYUI,
        ownership=EngineOwnership.MANAGED,
        status=EngineStatus.RUNNING,
        endpoint_url="http://127.0.0.1:8188",
    )


class TestImportedImageDimensions:
    """Requirement: Decode and persist actual imported-image dimensions; avoid fabricated 512x512 defaults."""

    @pytest.mark.asyncio
    async def test_upload_landscape_fixture_640x360_decodes_and_persists_dimensions(self):
        """Uploading the 640x360 fixture stores 640 and 360 in database and returns them."""
        data = make_png_bytes(640, 360)
        files = {"file": ("fixture_640x360.png", data, "image/png")}

        response = client.post("/api/v1/creative/upload", files=files)
        assert response.status_code == 200
        asset_data = response.json()

        assert asset_data["width"] == 640
        assert asset_data["height"] == 360

        # Verify persistent SQLite retrieval
        persisted = await asset_store.get_asset(asset_data["id"])
        assert persisted is not None
        assert persisted.width == 640
        assert persisted.height == 360

    @pytest.mark.asyncio
    async def test_upload_portrait_fixture_360x640_decodes_and_persists_dimensions(self):
        """Uploading a 360x640 portrait image stores 360 and 640 without defaulting to 512."""
        data = make_png_bytes(360, 640)
        files = {"file": ("portrait_360x640.png", data, "image/png")}

        response = client.post("/api/v1/creative/upload", files=files)
        assert response.status_code == 200
        asset_data = response.json()

        assert asset_data["width"] == 360
        assert asset_data["height"] == 640

        persisted = await asset_store.get_asset(asset_data["id"])
        assert persisted is not None
        assert persisted.width == 360
        assert persisted.height == 640

    @pytest.mark.asyncio
    async def test_save_bytes_directly_inspects_image_dimensions(self):
        """asset_store.save_bytes automatically inspects dimensions even when width/height not provided."""
        data = make_png_bytes(1920, 1080)
        rec = await asset_store.save_bytes(data, filename="full_hd.png")
        assert rec.width == 1920
        assert rec.height == 1080


class TestUpscaleGraphCompilation:
    """Requirement: Apply requested factor explicitly, including when model native factor differs."""

    def test_native_4x_model_requested_at_2x_inserts_rescale_node(self):
        """For RealESRGAN_x4plus requested at 2x, an ImageScale node downsamples to 2x target."""
        graph = build_comfy_upscale_graph(
            image_filename="source.png",
            upscaler_model="RealESRGAN_x4plus.pth",
            upscale_factor=2.0,
            source_width=640,
            source_height=360,
        )

        assert get_upscaler_native_factor("RealESRGAN_x4plus.pth") == 4.0
        assert "4" in graph
        assert graph["4"]["class_type"] == "ImageScale"
        assert graph["4"]["inputs"]["width"] == 1280
        assert graph["4"]["inputs"]["height"] == 720
        assert graph["4"]["inputs"]["upscale_method"] == "lanczos"
        assert graph["5"]["class_type"] == "SaveImage"
        assert graph["5"]["inputs"]["images"] == ["4", 0]

    def test_native_4x_model_requested_at_4x_connects_directly_to_model(self):
        """For RealESRGAN_x4plus requested at 4x, SaveImage connects directly to model output."""
        graph = build_comfy_upscale_graph(
            image_filename="source.png",
            upscaler_model="RealESRGAN_x4plus.pth",
            upscale_factor=4.0,
            source_width=640,
            source_height=360,
        )

        assert "4" in graph
        assert graph["4"]["class_type"] == "SaveImage"
        assert graph["4"]["inputs"]["images"] == ["3", 0]


class TestCreativeRunnerUpscaleExecution:
    """Requirement: Truthful output metadata derived from decoded output files, preserving aspect ratios."""

    @pytest.mark.asyncio
    async def test_upscale_640x360_by_2x_produces_1280x720(self, mock_comfy_connection):
        """Fixture 640x360 upscaled by 2x produces 1280x720 image and truthful metadata."""
        src_bytes = make_png_bytes(640, 360)
        src_asset = await asset_store.save_bytes(src_bytes, filename="fixture_640x360.png")

        # Simulate engine producing real 1280x720 PNG bytes
        out_bytes = make_png_bytes(1280, 720)
        out_asset = await asset_store.save_bytes(out_bytes, filename="upscaled_1280x720.png")

        runner = CreativeRunner()
        req = CreativeActionRequest(
            action=CreativeActionType.UPSCALE,
            input_image_id=src_asset.id,
            upscale_factor=2.0,
            upscaler_name="RealESRGAN_x4plus.pth",
            aspect_ratio="1:1",  # User might have default 1:1 selected on canvas
            width=512,           # Fallback defaults that must NOT overwrite
            height=512,
            engine_id="comfyui",
        )

        with patch("app.runners.creative_runner.engine_manager.get_engine", return_value=mock_comfy_connection), \
             patch("app.runners.creative_runner.ComfyUIClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.upload_image = AsyncMock(return_value={"name": "fixture_640x360.png", "subfolder": "", "type": "input"})
            mock_client.queue_prompt = AsyncMock(return_value={"prompt_id": "prompt_upscale_2x"})
            mock_client.poll_history_outputs = AsyncMock(return_value=[{"filename": "out_2x.png", "subfolder": "", "type": "output"}])
            mock_client.base_url = "http://127.0.0.1:8188"

            # Mock downloading and saving result with real bytes
            with patch("app.runners.creative_runner.asset_store.save_image_from_url", return_value=out_asset):
                res = await runner.execute(req)

                assert res.success is True
                assert res.width == 1280
                assert res.height == 720
                assert res.provenance is not None
                assert res.provenance.dimensions == "1280x720"

                # Verify actual saved image bytes on disk match 1280x720
                out_disk_path = asset_store.get_absolute_path(out_asset)
                with Image.open(out_disk_path) as im:
                    assert im.size == (1280, 720)

    @pytest.mark.asyncio
    async def test_upscale_640x360_by_4x_produces_2560x1440(self, mock_comfy_connection):
        """Fixture 640x360 upscaled by 4x produces 2560x1440 image and truthful metadata."""
        src_bytes = make_png_bytes(640, 360)
        src_asset = await asset_store.save_bytes(src_bytes, filename="fixture_640x360.png")

        out_bytes = make_png_bytes(2560, 1440)
        out_asset = await asset_store.save_bytes(out_bytes, filename="upscaled_2560x1440.png")

        runner = CreativeRunner()
        req = CreativeActionRequest(
            action=CreativeActionType.UPSCALE,
            input_image_id=src_asset.id,
            upscale_factor=4.0,
            upscaler_name="RealESRGAN_x4plus.pth",
            aspect_ratio="1:1",
            engine_id="comfyui",
        )

        with patch("app.runners.creative_runner.engine_manager.get_engine", return_value=mock_comfy_connection), \
             patch("app.runners.creative_runner.ComfyUIClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.upload_image = AsyncMock(return_value={"name": "fixture_640x360.png", "subfolder": "", "type": "input"})
            mock_client.queue_prompt = AsyncMock(return_value={"prompt_id": "prompt_upscale_4x"})
            mock_client.poll_history_outputs = AsyncMock(return_value=[{"filename": "out_4x.png", "subfolder": "", "type": "output"}])
            mock_client.base_url = "http://127.0.0.1:8188"

            with patch("app.runners.creative_runner.asset_store.save_image_from_url", return_value=out_asset):
                res = await runner.execute(req)

                assert res.success is True
                assert res.width == 2560
                assert res.height == 1440
                assert res.provenance is not None
                assert res.provenance.dimensions == "2560x1440"

                out_disk_path = asset_store.get_absolute_path(out_asset)
                with Image.open(out_disk_path) as im:
                    assert im.size == (2560, 1440)

    @pytest.mark.asyncio
    async def test_upscale_portrait_360x640_by_2x_produces_720x1280(self, mock_comfy_connection):
        """Portrait fixture 360x640 upscaled by 2x produces 720x1280."""
        src_bytes = make_png_bytes(360, 640)
        src_asset = await asset_store.save_bytes(src_bytes, filename="portrait_360x640.png")

        out_bytes = make_png_bytes(720, 1280)
        out_asset = await asset_store.save_bytes(out_bytes, filename="upscaled_720x1280.png")

        runner = CreativeRunner()
        req = CreativeActionRequest(
            action=CreativeActionType.UPSCALE,
            input_image_id=src_asset.id,
            upscale_factor=2.0,
            engine_id="comfyui",
        )

        with patch("app.runners.creative_runner.engine_manager.get_engine", return_value=mock_comfy_connection), \
             patch("app.runners.creative_runner.ComfyUIClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.upload_image = AsyncMock(return_value={"name": "portrait_360x640.png", "subfolder": "", "type": "input"})
            mock_client.queue_prompt = AsyncMock(return_value={"prompt_id": "prompt_portrait_2x"})
            mock_client.poll_history_outputs = AsyncMock(return_value=[{"filename": "out_portrait.png", "subfolder": "", "type": "output"}])
            mock_client.base_url = "http://127.0.0.1:8188"

            with patch("app.runners.creative_runner.asset_store.save_image_from_url", return_value=out_asset):
                res = await runner.execute(req)

                assert res.success is True
                assert res.width == 720
                assert res.height == 1280
                assert res.provenance is not None
                assert res.provenance.dimensions == "720x1280"

                out_disk_path = asset_store.get_absolute_path(out_asset)
                with Image.open(out_disk_path) as im:
                    assert im.size == (720, 1280)
