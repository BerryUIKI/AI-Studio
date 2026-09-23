"""
Milestone 3 Verification Tests: Creative Image Actions, Canvas Mappings & Provenance.

Verifies:
1. ComfyUI macro graph compilation for txt2img, img2img, inpaint, and upscale.
2. SD WebUI runner API mappings and base64 asset adoption.
3. High-level CreativeRunner caching, provenance tracking, and variant invalidation.
4. Canvas asset upload and content-addressable storage.
5. FastAPI creative REST endpoints.
"""

import base64
import io
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runners.creative_runner import CreativeRunner, compute_creative_cache_hash
from app.runners.macro_compiler import (
    build_comfy_img2img_graph,
    build_comfy_inpaint_graph,
    build_comfy_txt2img_graph,
    build_comfy_upscale_graph,
)
from app.runners.webui_runner import WebUIRunner
from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.storage.asset_store import asset_store

client = TestClient(app)

DUMMY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_comfy_macro_compiler_all_actions():
    """Verify macro compiler produces valid ComfyUI prompt graphs for all 4 image actions."""
    # 1. txt2img
    t2i = build_comfy_txt2img_graph(prompt="A cozy cottage", aspect_ratio="16:9")
    assert "4" in t2i and t2i["4"]["class_type"] == "CheckpointLoaderSimple"
    assert "3" in t2i and t2i["3"]["class_type"] == "KSampler"
    assert "9" in t2i and t2i["9"]["class_type"] == "SaveImage"
    assert t2i["5"]["inputs"]["width"] == 1344

    # 2. img2img
    i2i = build_comfy_img2img_graph(prompt="sunset oil painting", image_filename="input.png", denoise=0.6)
    assert "1" in i2i and i2i["1"]["class_type"] == "LoadImage"
    assert "2" in i2i and i2i["2"]["class_type"] == "VAEEncode"
    assert i2i["3"]["inputs"]["denoise"] == 0.6

    # 3. inpaint
    inp = build_comfy_inpaint_graph(
        prompt="red flower", image_filename="input.png", mask_filename="mask.png"
    )
    assert "5" in inp and inp["5"]["class_type"] == "VAEEncodeForInpaint"
    assert "2" in inp and inp["2"]["class_type"] == "LoadImage"

    # 4. upscale
    ups = build_comfy_upscale_graph(image_filename="input.png", upscaler_model="RealESRGAN_x4plus.pth")
    assert "2" in ups and ups["2"]["class_type"] == "UpscaleModelLoader"
    assert "3" in ups and ups["3"]["class_type"] == "ImageUpscaleWithModel"


@pytest.mark.asyncio
async def test_webui_runner_txt2img_and_upscale():
    """Verify SD WebUI runner dispatches requests and saves base64 images into asset store."""
    runner = WebUIRunner(endpoint_url="http://127.0.0.1:7860")
    b64_dummy = base64.b64encode(DUMMY_PNG_BYTES).decode("utf-8")

    # 1. Test txt2img
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"images": [b64_dummy]}
        mock_post.return_value = mock_resp

        req = CreativeActionRequest(
            action=CreativeActionType.TXT2IMG,
            prompt="futuristic city",
            engine_id="managed_webui",
            width=512,
            height=512,
        )
        res = await runner.execute_action(req)
        assert res["asset_id"] is not None
        assert res["image_url"].startswith("/api/v1/assets/")

        # Verify asset was actually written to disk
        asset = await asset_store.get_asset(res["asset_id"])
        assert asset is not None
        assert asset.byte_size > 0

    # 2. Test upscale
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"image": b64_dummy}
        mock_post.return_value = mock_resp

        upscale_req = CreativeActionRequest(
            action=CreativeActionType.UPSCALE,
            input_image_id=res["asset_id"],
            engine_id="managed_webui",
            upscale_factor=2.0,
            width=512,
            height=512,
        )
        ups_res = await runner.execute_action(upscale_req)
        assert ups_res["width"] == 1024
        assert ups_res["height"] == 1024


@pytest.mark.asyncio
async def test_creative_runner_caching_and_provenance():
    """Verify CreativeRunner attaches provenance and deterministically caches results."""
    runner = CreativeRunner()
    b64_dummy = base64.b64encode(DUMMY_PNG_BYTES).decode("utf-8")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"images": [b64_dummy]}
        mock_post.return_value = mock_resp

        unique_prompt = f"cyberpunk portrait {uuid.uuid4()}"
        req = CreativeActionRequest(
            action=CreativeActionType.TXT2IMG,
            prompt=unique_prompt,
            engine_id="managed_webui",
            seed=42,
            steps=25,
            aspect_ratio="1:1",
        )

        # 1. First execution: should compute and cache
        res1 = await runner.execute(req)
        assert res1.success is True
        assert res1.is_cached is False
        assert res1.provenance is not None
        assert res1.provenance.seed == 42
        assert res1.provenance.steps == 25
        assert res1.provenance.model == "v1-5-pruned-emaonly.safetensors"

        # 2. Second identical execution: should be a deterministic CACHE HIT
        res2 = await runner.execute(req)
        assert res2.success is True
        assert res2.is_cached is True
        assert res2.asset_id == res1.asset_id

        # 3. Changed seed (new variation): should NOT hit cache
        req_variant = req.model_copy(update={"seed": 43})
        res3 = await runner.execute(req_variant)
        assert res3.success is True
        assert res3.is_cached is False
        assert res3.provenance.seed == 43


def test_creative_asset_upload_endpoint():
    """Verify uploading an image to the canvas stores it as an asset record."""
    file_content = io.BytesIO(DUMMY_PNG_BYTES)
    resp = client.post(
        "/api/v1/creative/upload",
        files={"file": ("canvas_upload.png", file_content, "image/png")},
    )
    assert resp.status_code == 200
    asset_data = resp.json()
    assert "id" in asset_data
    assert asset_data["filename"] == "canvas_upload.png"
    assert asset_data["content_hash"] is not None

    # Test reading it back
    content_resp = client.get(f"/api/v1/assets/{asset_data['id']}/content")
    assert content_resp.status_code == 200
    assert len(content_resp.content) == len(DUMMY_PNG_BYTES)


def test_api_creative_execute_endpoint():
    """Verify FastAPI /api/v1/creative/execute endpoint."""
    b64_dummy = base64.b64encode(DUMMY_PNG_BYTES).decode("utf-8")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"images": [b64_dummy]}
        mock_post.return_value = mock_resp

        payload = {
            "action": "txt2img",
            "prompt": "serene mountain lake",
            "engine_id": "managed_webui",
            "aspect_ratio": "1:1",
            "steps": 20,
            "seed": 999,
        }
        resp = client.post("/api/v1/creative/execute", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "asset_id" in data
        assert "provenance" in data
        assert data["provenance"]["prompt"] == "serene mountain lake"
