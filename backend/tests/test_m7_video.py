"""Tests for M7 Video Generation: Schemas, Caching, Macro Compilers, and Execution."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runners.creative_runner import compute_creative_cache_hash, creative_runner
from app.runners.macro_compiler import (
    build_comfy_img2video_graph,
    build_comfy_txt2video_graph,
)
from app.schemas.creative import (
    CreativeActionRequest,
    CreativeActionResult,
    CreativeActionType,
    GenerationProvenance,
)
from app.storage.asset_store import asset_store


@pytest.fixture
def client():
    return TestClient(app)


def test_video_schemas():
    """Verify video action schemas and default parameters."""
    req = CreativeActionRequest(
        action=CreativeActionType.TXT2VIDEO,
        prompt="A soaring eagle over a snowy mountain range",
        fps=16,
        num_frames=25,
        motion_bucket_id=127,
        duration_seconds=3.0,
    )
    assert req.action == CreativeActionType.TXT2VIDEO
    assert req.fps == 16
    assert req.num_frames == 25
    assert req.motion_bucket_id == 127
    assert req.duration_seconds == 3.0

    res = CreativeActionResult(
        success=True,
        task_id="task_123",
        video_url="/api/v1/assets/asset_video_1/content",
        width=1024,
        height=576,
        duration_seconds=3.0,
        fps=16,
    )
    assert res.video_url == "/api/v1/assets/asset_video_1/content"
    assert res.image_url is None
    assert res.duration_seconds == 3.0
    assert res.fps == 16


def test_video_cache_hashing():
    """Verify deterministic cache hashing incorporates video-specific parameters."""
    req1 = CreativeActionRequest(
        action=CreativeActionType.IMG2VIDEO,
        prompt="Ocean waves gently breaking on sandy beach",
        model="svd_xt.safetensors",
        fps=16,
        num_frames=25,
        motion_bucket_id=127,
        duration_seconds=2.5,
    )
    req2 = CreativeActionRequest(
        action=CreativeActionType.IMG2VIDEO,
        prompt="Ocean waves gently breaking on sandy beach",
        model="svd_xt.safetensors",
        fps=16,
        num_frames=25,
        motion_bucket_id=127,
        duration_seconds=2.5,
    )
    # Identical requests produce identical hash
    hash1 = compute_creative_cache_hash(req1, input_hash="sha256_input_abc")
    hash2 = compute_creative_cache_hash(req2, input_hash="sha256_input_abc")
    assert hash1 == hash2

    # Changing fps changes hash
    req_diff_fps = req1.model_copy(update={"fps": 24})
    assert compute_creative_cache_hash(req_diff_fps, input_hash="sha256_input_abc") != hash1

    # Changing motion bucket changes hash
    req_diff_motion = req1.model_copy(update={"motion_bucket_id": 200})
    assert compute_creative_cache_hash(req_diff_motion, input_hash="sha256_input_abc") != hash1

    # Changing num_frames changes hash
    req_diff_frames = req1.model_copy(update={"num_frames": 16})
    assert compute_creative_cache_hash(req_diff_frames, input_hash="sha256_input_abc") != hash1


def test_comfy_img2video_macro_graph():
    """Verify SVD image-to-video macro graph construction."""
    graph = build_comfy_img2video_graph(
        image_filename="source_portrait.png",
        checkpoint="svd_xt.safetensors",
        width=1024,
        height=576,
        video_frames=25,
        fps=16,
        motion_bucket_id=127,
        seed=42,
    )

    assert "1" in graph
    assert graph["1"]["class_type"] == "ImageOnlyCheckpointLoader"
    assert graph["1"]["inputs"]["ckpt_name"] == "svd_xt.safetensors"

    assert "2" in graph
    assert graph["2"]["class_type"] == "LoadImage"
    assert graph["2"]["inputs"]["image"] == "source_portrait.png"

    assert "3" in graph
    assert graph["3"]["class_type"] == "SVD_img2vid_Conditioning"
    assert graph["3"]["inputs"]["video_frames"] == 25
    assert graph["3"]["inputs"]["fps"] == 16
    assert graph["3"]["inputs"]["motion_bucket_id"] == 127

    assert "4" in graph
    assert graph["4"]["class_type"] == "KSampler"
    assert graph["4"]["inputs"]["seed"] == 42

    assert "6" in graph
    assert graph["6"]["class_type"] == "SaveAnimatedWEBP"
    assert graph["6"]["inputs"]["fps"] == 16


def test_comfy_txt2video_macro_graph():
    """Verify AnimateDiff text-to-video macro graph construction."""
    graph = build_comfy_txt2video_graph(
        prompt="Neon hologram dancer in rain",
        negative_prompt="blurry",
        checkpoint="v1-5-pruned-emaonly.safetensors",
        animatediff_model="mm_sd_v15_v2.ckpt",
        width=512,
        height=512,
        video_frames=16,
        fps=8,
        seed=100,
    )

    assert "1" in graph
    assert graph["1"]["class_type"] == "CheckpointLoaderSimple"

    assert "2" in graph
    assert graph["2"]["class_type"] == "AnimateDiffLoaderWithContext"
    assert graph["2"]["inputs"]["model_name"] == "mm_sd_v15_v2.ckpt"

    assert "3" in graph
    assert graph["3"]["class_type"] == "CLIPTextEncode"
    assert graph["3"]["inputs"]["text"] == "Neon hologram dancer in rain"

    assert "5" in graph
    assert graph["5"]["class_type"] == "EmptyLatentImage"
    assert graph["5"]["inputs"]["batch_size"] == 16

    assert "6" in graph
    assert graph["6"]["class_type"] == "KSampler"
    assert graph["6"]["inputs"]["seed"] == 100

    assert "8" in graph
    assert graph["8"]["class_type"] == "SaveAnimatedWEBP"
    assert graph["8"]["inputs"]["fps"] == 8


@pytest.mark.asyncio
async def test_cloud_video_execution(client):
    """Verify execution of cloud text-to-video via REST API with mocked provider."""
    mock_url = "https://fal.media/files/monkey/sample_generated_video.mp4"

    with patch("app.runners.creative_runner.credentials_manager.get_key", return_value="fake_fal_key"), \
         patch("app.runners.creative_runner._call_fal_ai_video", new=AsyncMock(return_value=mock_url)), \
         patch("app.storage.asset_store.asset_store.save_media_from_url") as mock_save:

        class MockAsset:
            id = "mock_video_asset_id_999"
            file_path = "mock/path.mp4"
            media_type = "video"
            filename = "cloud_video.mp4"

        mock_save.return_value = MockAsset()

        payload = {
            "action": "txt2video",
            "prompt": "Hyperlapse of clouds over Tokyo skyline at dusk",
            "engine_id": "cloud",
            "fps": 16,
            "num_frames": 25,
            "duration_seconds": 3.0,
            "seed": 9999,
        }

        resp = client.post("/api/v1/creative/execute", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["success"] is True
        assert data["video_url"] == "/api/v1/assets/mock_video_asset_id_999/content"
        assert data["fps"] == 16
        assert data["duration_seconds"] == 3.0
        assert data["provenance"]["action"] == "txt2video"
        assert data["provenance"]["fps"] == 16


def test_webui_rejection_for_video(client):
    """Verify WebUI rejects video generation requests with an actionable error message."""
    payload = {
        "action": "txt2video",
        "prompt": "Underwater coral reef with bioluminescent fish",
        "engine_id": "managed_webui",
    }
    resp = client.post("/api/v1/creative/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "WebUI engine currently does not support native video generation" in data["error_message"]


def test_img2video_missing_source_image(client):
    """Verify img2video errors if no input image is provided."""
    payload = {
        "action": "img2video",
        "prompt": "Animate camera moving forward",
        "engine_id": "managed_comfyui",
    }
    resp = client.post("/api/v1/creative/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "Source image required" in data["error_message"]
