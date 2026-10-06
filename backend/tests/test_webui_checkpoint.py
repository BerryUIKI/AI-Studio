"""
Tests for WebUI checkpoint validation, override_settings contract, and effective model provenance.

Verifies:
1. Validating and applying the selected checkpoint via WebUI supported API.
2. Distinct checkpoint requests produce distinct selection contracts.
3. Unavailable models fail before generation.
4. Effective model and revision identity are recorded in provenance and caching.
5. All creative image actions (txt2img, img2img, inpaint) enforce the model contract.
"""

import base64
import json
import uuid
import httpx
import pytest
from PIL import Image
from io import BytesIO

from app.runners.creative_runner import CreativeRunner
from app.runners.webui_runner import WebUIRunner
from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.storage.asset_store import asset_store


def create_dummy_png(width: int = 512, height: int = 512) -> bytes:
    """Create a valid PNG for testing."""
    img = Image.new("RGBA", (width, height), color=(255, 255, 255, 255))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


DUMMY_PNG_BYTES = create_dummy_png()
B64_DUMMY = base64.b64encode(DUMMY_PNG_BYTES).decode("utf-8")

AVAILABLE_MODELS = [
    {
        "title": "v1-5-pruned-emaonly.safetensors [6ce0161689]",
        "model_name": "v1-5-pruned-emaonly",
        "hash": "6ce0161689",
        "sha256": "6ce0161689b3853cac59637ab7460ab6ba5025054032e7ac659e720349b88648",
        "filename": "/models/v1-5-pruned-emaonly.safetensors",
    },
    {
        "title": "chosen-checkpoint.safetensors [a1b2c3d4e5]",
        "model_name": "chosen-checkpoint",
        "hash": "a1b2c3d4e5",
        "sha256": "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
        "filename": "/models/chosen-checkpoint.safetensors",
    },
    {
        "title": "sdxl-base-1.0.safetensors [31e35c80fc]",
        "model_name": "sdxl-base-1.0",
        "hash": "31e35c80fc",
        "sha256": "31e35c80fca3179299874724f40f188f5037a6833f74073d80e90214a1797e5c",
        "filename": "/models/sdxl-base-1.0.safetensors",
    },
]


@pytest.mark.asyncio
async def test_webui_txt2img_applies_chosen_checkpoint_via_mock_transport():
    """Verify WebUIRunner._run_txt2img applies override_settings and sd_model_checkpoint."""
    captured_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        if url_path == "/sdapi/v1/sd-models":
            return httpx.Response(200, json=AVAILABLE_MODELS)
        if url_path == "/sdapi/v1/txt2img":
            payload = json.loads(request.content.decode("utf-8"))
            captured_requests.append(payload)
            return httpx.Response(200, json={"images": [B64_DUMMY]})
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7860") as client:
        runner = WebUIRunner("http://127.0.0.1:7860")
        req = CreativeActionRequest(
            action=CreativeActionType.TXT2IMG,
            prompt="a fantasy castle",
            model="chosen-checkpoint.safetensors",
            seed=42,
        )
        res = await runner._run_txt2img(client, req)

        assert len(captured_requests) == 1
        captured = captured_requests[0]
        # Verify override_settings is established
        assert "override_settings" in captured
        assert (
            captured["override_settings"]["sd_model_checkpoint"]
            == "chosen-checkpoint.safetensors [a1b2c3d4e5]"
        )
        assert captured["sd_model_checkpoint"] == "chosen-checkpoint.safetensors [a1b2c3d4e5]"
        assert res["effective_model"] == "chosen-checkpoint.safetensors [a1b2c3d4e5]"
        assert res["model_revision"] == "a1b2c3d4e5"


@pytest.mark.asyncio
async def test_webui_two_distinct_checkpoints_produce_distinct_selection_contracts():
    """Verify two distinct checkpoints produce distinct override_settings."""
    captured_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        if url_path == "/sdapi/v1/sd-models":
            return httpx.Response(200, json=AVAILABLE_MODELS)
        if url_path == "/sdapi/v1/txt2img":
            payload = json.loads(request.content.decode("utf-8"))
            captured_requests.append(payload)
            return httpx.Response(200, json={"images": [B64_DUMMY]})
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7860") as client:
        runner = WebUIRunner("http://127.0.0.1:7860")

        # Checkpoint 1
        req1 = CreativeActionRequest(
            action=CreativeActionType.TXT2IMG,
            prompt="futuristic neon city",
            model="chosen-checkpoint.safetensors",
        )
        res1 = await runner._run_txt2img(client, req1)

        # Checkpoint 2
        req2 = CreativeActionRequest(
            action=CreativeActionType.TXT2IMG,
            prompt="vintage landscape",
            model="sdxl-base-1.0.safetensors",
        )
        res2 = await runner._run_txt2img(client, req2)

        assert len(captured_requests) == 2
        assert (
            captured_requests[0]["override_settings"]["sd_model_checkpoint"]
            == "chosen-checkpoint.safetensors [a1b2c3d4e5]"
        )
        assert (
            captured_requests[1]["override_settings"]["sd_model_checkpoint"]
            == "sdxl-base-1.0.safetensors [31e35c80fc]"
        )
        assert res1["effective_model"] != res2["effective_model"]
        assert res1["model_revision"] == "a1b2c3d4e5"
        assert res2["model_revision"] == "31e35c80fc"


@pytest.mark.asyncio
async def test_webui_unavailable_model_fails_before_generation():
    """Verify that requesting an unavailable checkpoint fails before any generation request."""
    generation_called = False

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal generation_called
        url_path = request.url.path
        if url_path == "/sdapi/v1/sd-models":
            return httpx.Response(200, json=AVAILABLE_MODELS)
        if url_path in ("/sdapi/v1/txt2img", "/sdapi/v1/img2img"):
            generation_called = True
            return httpx.Response(200, json={"images": [B64_DUMMY]})
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7860") as client:
        runner = WebUIRunner("http://127.0.0.1:7860")
        req = CreativeActionRequest(
            action=CreativeActionType.TXT2IMG,
            prompt="a mysterious alien world",
            model="nonexistent-model-xyz.safetensors",
        )

        with pytest.raises(ValueError) as exc_info:
            await runner._run_txt2img(client, req)

        assert "nonexistent-model-xyz.safetensors" in str(exc_info.value)
        assert not generation_called, "Generation endpoint should not be contacted for unavailable models"


@pytest.mark.asyncio
async def test_webui_img2img_and_inpaint_enforce_selected_checkpoint():
    """Verify img2img and inpaint also validate and send override_settings."""
    captured_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        if url_path == "/sdapi/v1/sd-models":
            return httpx.Response(200, json=AVAILABLE_MODELS)
        if url_path == "/sdapi/v1/img2img":
            payload = json.loads(request.content.decode("utf-8"))
            captured_requests.append(payload)
            return httpx.Response(200, json={"images": [B64_DUMMY]})
        return httpx.Response(404, json={"error": "not found"})

    dummy_asset = await asset_store.save_bytes(DUMMY_PNG_BYTES, filename="test_input.png")
    mask_asset = await asset_store.save_bytes(DUMMY_PNG_BYTES, filename="test_mask.png")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7860") as client:
        runner = WebUIRunner("http://127.0.0.1:7860")

        # 1. img2img
        req_i2i = CreativeActionRequest(
            action=CreativeActionType.IMG2IMG,
            prompt="oil painting rendition",
            model="chosen-checkpoint.safetensors",
            input_image_id=dummy_asset.id,
            denoise=0.5,
        )
        res_i2i = await runner._run_img2img(client, req_i2i)
        assert res_i2i["effective_model"] == "chosen-checkpoint.safetensors [a1b2c3d4e5]"
        assert res_i2i["model_revision"] == "a1b2c3d4e5"
        assert (
            captured_requests[0]["override_settings"]["sd_model_checkpoint"]
            == "chosen-checkpoint.safetensors [a1b2c3d4e5]"
        )

        # 2. inpaint
        req_inp = CreativeActionRequest(
            action=CreativeActionType.INPAINT,
            prompt="fix eyes",
            model="chosen-checkpoint.safetensors",
            input_image_id=dummy_asset.id,
            mask_image_id=mask_asset.id,
        )
        res_inp = await runner._run_inpaint(client, req_inp)
        assert res_inp["effective_model"] == "chosen-checkpoint.safetensors [a1b2c3d4e5]"
        assert (
            captured_requests[1]["override_settings"]["sd_model_checkpoint"]
            == "chosen-checkpoint.safetensors [a1b2c3d4e5]"
        )


@pytest.mark.asyncio
async def test_creative_runner_webui_provenance_and_caching(mock_engine_manager):
    """Verify CreativeRunner records effective model & revision identity and preserves them across cache hits."""
    runner = CreativeRunner()

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        if url_path == "/sdapi/v1/sd-models":
            return httpx.Response(200, json=AVAILABLE_MODELS)
        if url_path == "/sdapi/v1/txt2img":
            return httpx.Response(200, json={"images": [B64_DUMMY]})
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(mock_handler)

    # Monkeypatch execute_action in WebUIRunner to use mock transport client
    async def mock_execute_action(self, req: CreativeActionRequest):
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7860") as client:
            return await self._dispatch_action(client, req)

    from unittest.mock import patch
    with patch.object(WebUIRunner, "execute_action", mock_execute_action):
        req = CreativeActionRequest(
            action=CreativeActionType.TXT2IMG,
            prompt=f"enchanted forest {uuid.uuid4()}",
            model="chosen-checkpoint.safetensors",
            engine_id="managed_webui",
            seed=777,
        )

        # First run: uncached, should compute and capture provenance
        result1 = await runner.execute(req)
        assert result1.success is True
        assert result1.is_cached is False
        assert result1.provenance is not None
        assert result1.provenance.model == "chosen-checkpoint.safetensors [a1b2c3d4e5]"
        assert result1.provenance.model_revision == "a1b2c3d4e5"
        assert result1.provenance.model_hash == "a1b2c3d4e5"

        # Second run: cached, provenance with effective model and revision preserved
        result2 = await runner.execute(req)
        assert result2.success is True
        assert result2.is_cached is True
        assert result2.asset_id == result1.asset_id
        assert result2.provenance is not None
        assert result2.provenance.model == "chosen-checkpoint.safetensors [a1b2c3d4e5]"
        assert result2.provenance.model_revision == "a1b2c3d4e5"
        assert result2.provenance.model_hash == "a1b2c3d4e5"
