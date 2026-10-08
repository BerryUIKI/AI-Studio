"""Tests for unified provider resolution and execution plan enforcement (Issue #110)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.runners.creative_runner import (
    CreativeRunner,
    compute_creative_cache_hash,
    resolve_effective_provider,
    resolve_execution_plan,
)
from app.runtime.credentials import credentials_manager
from app.schemas.cloud import CloudProviderId
from app.schemas.creative import (
    CreativeActionRequest,
    CreativeActionResult,
    CreativeActionType,
    CreativeExecutionPlan,
)


def test_resolve_execution_plan_fal_sdxl_turbo():
    """Verify fal_ai engine selection resolves to fal_ai provider, never switching to siliconflow."""
    req = CreativeActionRequest(
        action=CreativeActionType.TXT2IMG,
        prompt="A serene cyberpunk lakeside",
        model="sdxl-turbo",
        engine_id="fal_ai",
    )
    plan = resolve_execution_plan(req)
    assert plan.engine == "cloud"
    assert plan.provider_id == "fal_ai"
    assert plan.action == CreativeActionType.TXT2IMG

    # Effective provider must strictly match plan provider_id
    assert resolve_effective_provider(req) == plan.provider_id


def test_resolve_execution_plan_comfy_and_webui():
    """Verify local engines resolve consistently."""
    req_comfy = CreativeActionRequest(
        action=CreativeActionType.TXT2IMG,
        prompt="test prompt",
        engine_id="managed_comfyui",
    )
    plan_comfy = resolve_execution_plan(req_comfy)
    assert plan_comfy.engine == "comfyui"
    assert plan_comfy.provider_id == "comfyui"

    req_webui = CreativeActionRequest(
        action=CreativeActionType.TXT2IMG,
        prompt="test prompt",
        engine_id="managed_webui",
    )
    plan_webui = resolve_execution_plan(req_webui)
    assert plan_webui.engine == "webui"
    assert plan_webui.provider_id == "webui"


def test_resolve_execution_plan_rejects_unsupported_actions():
    """Verify unsupported provider/action combinations raise early clear errors."""
    # WebUI does not support video
    req_webui_vid = CreativeActionRequest(
        action=CreativeActionType.TXT2VIDEO,
        prompt="ocean waves",
        engine_id="managed_webui",
    )
    with pytest.raises(ValueError, match="WebUI engine currently does not support native video"):
        resolve_execution_plan(req_webui_vid)

    # SiliconFlow does not support upscale or img2img
    req_sf_upscale = CreativeActionRequest(
        action=CreativeActionType.UPSCALE,
        prompt="",
        engine_id="siliconflow",
    )
    with pytest.raises(ValueError, match="SiliconFlow does not support upscale"):
        resolve_execution_plan(req_sf_upscale)

    # OpenAI does not support upscale or video
    req_oai_video = CreativeActionRequest(
        action=CreativeActionType.TXT2VIDEO,
        prompt="floating lanterns",
        engine_id="openai",
    )
    with pytest.raises(ValueError, match="OpenAI does not support txt2video"):
        resolve_execution_plan(req_oai_video)


@pytest.mark.asyncio
async def test_dispatch_uses_resolved_plan_without_switching():
    """Verify dispatch strictly calls the planned provider and fails if key is missing rather than falling back."""
    runner = CreativeRunner()
    req = CreativeActionRequest(
        action=CreativeActionType.TXT2IMG,
        prompt="Cyberpunk street in rain",
        model="sdxl-turbo",
        engine_id="fal_ai",
    )

    # When Fal key is missing, execute must fail with Fal error, never switch to SiliconFlow even if SiliconFlow key is present
    with patch.object(credentials_manager, "get_key", side_effect=lambda pid: "sf-key-123" if pid == CloudProviderId.SILICONFLOW else None):
        res = await runner.execute(req)
        assert res.success is False
        assert "Fal.ai API key is missing" in (res.error_message or "")


@pytest.mark.asyncio
async def test_cache_key_and_provenance_reflect_resolved_provider():
    """Verify that semantic cache hashing and provenance record the resolved provider_id."""
    runner = CreativeRunner()
    req = CreativeActionRequest(
        action=CreativeActionType.TXT2IMG,
        prompt="Ethereal space lotus",
        model="sdxl-turbo",
        engine_id="fal_ai",
        seed=42,
    )

    # 1. Cache key uses resolved provider
    plan = resolve_execution_plan(req)
    cache_key = compute_creative_cache_hash(req, connection_id="comfyui-managed", provider_id=plan.provider_id)
    assert cache_key == compute_creative_cache_hash(req, connection_id="comfyui-managed")

    # 2. Execution records provenance.provider_id
    with patch.object(credentials_manager, "get_key", return_value="fake-fal-key"), \
         patch("app.runners.creative_runner._call_fal_ai", new_callable=AsyncMock) as mock_fal, \
         patch("app.runners.creative_runner.asset_store.save_image_from_url", new_callable=AsyncMock) as mock_save:
        mock_fal.return_value = "https://fal.media/files/lotus.png"
        mock_asset = MagicMock()
        mock_asset.id = "asset_lotus_123"
        mock_asset.content_hash = "hash_lotus_123"
        mock_save.return_value = mock_asset

        result = await runner.execute(req)
        assert result.success is True
        assert result.provenance is not None
        assert result.provenance.provider_id == "fal_ai"
        assert result.provenance.engine_id == "fal_ai"
        mock_fal.assert_called_once_with("sdxl-turbo", "Ethereal space lotus", 1024, 1024, "fake-fal-key")
        assert req.width == 512  # Execution resolves a snapshot without mutating the submission.
