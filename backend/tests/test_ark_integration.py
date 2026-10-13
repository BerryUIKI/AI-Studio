"""Product integration contracts, with no paid provider requests."""

from pathlib import Path
from unittest.mock import patch

import pytest
from app.runtime.credentials import CredentialManager
from app.schemas.cloud import CloudProviderId


@pytest.mark.parametrize("action", ["txt2img", "img2img"])
def test_ark_plan_overrides_stale_local_engine(action: str) -> None:
    from app.runners.creative_runner import resolve_execution_plan
    from app.runners.volcengine_runner import SEEDREAM_MODEL
    from app.schemas.creative import CreativeActionRequest

    plan = resolve_execution_plan(
        CreativeActionRequest(
            action=action, connection_id="volcengine", model=SEEDREAM_MODEL
        )
    )
    assert plan.engine == "cloud" and plan.provider_id == "volcengine"
    assert plan.target_model == SEEDREAM_MODEL


@pytest.mark.parametrize(
    "action,model",
    [
        ("inpaint", "doubao-seedream-4-0-250828"),
        ("upscale", "doubao-seedream-4-0-250828"),
        ("txt2img", "other"),
    ],
)
def test_ark_plan_rejects_unsupported_actions_and_model(
    action: str, model: str
) -> None:
    from app.runners.creative_runner import resolve_execution_plan
    from app.schemas.creative import CreativeActionRequest

    with pytest.raises(ValueError):
        resolve_execution_plan(
            CreativeActionRequest(
                action=action, connection_id="volcengine", model=model
            )
        )


@pytest.mark.asyncio
async def test_ark_ignores_unapplied_controls_but_invalidates_variations_and_source() -> (
    None
):
    from app.core.creative_identity import creative_execution_identity
    from app.runners.creative_runner import (
        compute_creative_cache_hash,
        resolve_execution_plan,
    )
    from app.runners.volcengine_runner import SEEDREAM_MODEL
    from app.schemas.creative import CreativeActionRequest

    request = CreativeActionRequest(
        action="txt2img", connection_id="volcengine", model=SEEDREAM_MODEL, seed=42
    )
    identity = await creative_execution_identity(resolve_execution_plan(request), None)
    assert identity["model"] == SEEDREAM_MODEL and identity["model_revision"] is None
    first = compute_creative_cache_hash(
        request, "volcengine", "source-a", execution_identity=identity
    )
    request.negative_prompt, request.steps, request.cfg_scale, request.denoise = (
        "ignored",
        99,
        50,
        0.1,
    )
    assert (
        compute_creative_cache_hash(
            request, "volcengine", "source-a", execution_identity=identity
        )
        == first
    )
    request.seed += 1
    assert (
        compute_creative_cache_hash(
            request, "volcengine", "source-a", execution_identity=identity
        )
        != first
    )
    request.seed -= 1
    assert (
        compute_creative_cache_hash(
            request, "volcengine", "source-b", execution_identity=identity
        )
        != first
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["txt2img", "img2img"])
async def test_ark_adopts_actual_media_and_reuses_persistent_cache(
    tmp_path: Path, action: str
) -> None:
    import base64
    import io
    from unittest.mock import AsyncMock

    from app.core.cache import CacheStore
    from app.runners.creative_runner import CreativeRunner
    from app.runners.volcengine_runner import SEEDREAM_MODEL, ArkImage
    from app.schemas.creative import CreativeActionRequest
    from app.storage.asset_store import AssetStore
    from app.storage.db import DatabaseManager
    from app.storage.task_store import TaskStore
    from PIL import Image

    manager = DatabaseManager(tmp_path / "fixture.db")
    assets = AssetStore(manager=manager, base_dir=tmp_path)
    image = io.BytesIO()
    Image.new("RGB", (96, 72), "blue").save(image, "JPEG")
    data = image.getvalue()
    source = (
        await assets.save_bytes(data, filename="source.jpg")
        if action == "img2img"
        else None
    )
    output_buffer = io.BytesIO()
    Image.new("RGB", (96, 72), "red").save(output_buffer, "JPEG")
    request = CreativeActionRequest(
        action=action,
        connection_id="volcengine",
        model=SEEDREAM_MODEL,
        prompt="fixture",
        seed=41,
        input_image_id=source.id if source else None,
        aspect_ratio="16:9",
    )
    dispatch = AsyncMock(
        return_value=ArkImage(
            url=None,
            content=output_buffer.getvalue(),
            requested_model=SEEDREAM_MODEL,
            effective_model=None,
            request_id="fixture-request",
        )
    )

    def bindings(cache: CacheStore) -> list:
        return [
            patch("app.runners.creative_runner.asset_store", assets),
            patch("app.runners.creative_runner.cache_store", cache),
            patch("app.runners.creative_runner.task_store", TaskStore(manager)),
            patch("app.runners.creative_runner.request_ark_image", dispatch),
            patch(
                "app.runners.creative_runner.credentials_manager.get_key",
                return_value="fixture-key",
            ),
        ]

    from contextlib import ExitStack

    with ExitStack() as stack:
        for binding in bindings(CacheStore(manager, assets)):
            stack.enter_context(binding)
        first = await CreativeRunner().execute(request)
        assert first.success and not first.is_cached
        assert (first.width, first.height, first.mime_type, first.extension) == (
            96,
            72,
            "image/jpeg",
            ".jpg",
        )
        assert (
            first.provenance.seed is None
            and first.provenance.steps is None
            and first.provenance.cfg_scale is None
        )
        assert first.provenance.parameters["variation_nonce"] == 41
        assert first.provenance.parameters["response_model"] is None
        assert dispatch.await_args.kwargs["width"] == 2560
        assert dispatch.await_args.kwargs["height"] == 1440
        if source:
            encoded = dispatch.await_args.kwargs["image_data_uri"]
            assert encoded.startswith("data:image/png;base64,")
            with Image.open(
                io.BytesIO(base64.b64decode(encoded.split(",", 1)[1]))
            ) as reference:
                assert reference.size == (96, 72)
        await manager.close()
    with ExitStack() as stack:
        for binding in bindings(CacheStore(manager, assets)):
            stack.enter_context(binding)
        cached = await CreativeRunner().execute(request)
        assert cached.success and cached.is_cached and cached.asset_id == first.asset_id
        assert dispatch.await_count == 1
        output = await assets.get_asset(first.asset_id)
        assets.get_absolute_path(output).unlink()
        repaired = await CreativeRunner().execute(request)
        assert repaired.success and not repaired.is_cached
        assert dispatch.await_count == 2


@pytest.mark.asyncio
async def test_explicit_invalid_ark_size_fails_before_cache_or_dispatch() -> None:
    from unittest.mock import AsyncMock

    from app.runners.creative_runner import CreativeRunner
    from app.runners.volcengine_runner import SEEDREAM_MODEL
    from app.schemas.creative import CreativeActionRequest

    request = CreativeActionRequest(
        action="txt2img",
        model=SEEDREAM_MODEL,
        connection_id="volcengine",
        width=512,
        height=512,
    )
    with (
        patch(
            "app.runners.creative_runner.request_ark_image", new=AsyncMock()
        ) as dispatch,
        patch(
            "app.runners.creative_runner.cache_store.get_async", new=AsyncMock()
        ) as cache,
    ):
        result = await CreativeRunner().execute(request)
    assert not result.success and "921600" in result.error_message
    dispatch.assert_not_called()
    cache.assert_not_called()


def test_ark_catalog_only_advertises_supported_actions(tmp_path: Path) -> None:
    manager = CredentialManager(tmp_path)
    manager._memory_creds["volcengine"] = "fixture-secret-credential"
    provider = next(
        item
        for item in manager.list_providers()
        if item.id == CloudProviderId.VOLCENGINE
    )
    assert provider.is_configured
    assert provider.capabilities == ["txt2img", "img2img"]
    assert set(provider.action_models) == set(provider.capabilities)
    assert "fixture-secret-credential" not in provider.model_dump_json()
    assert not provider.key_test_supported


@pytest.mark.asyncio
async def test_ark_key_test_does_not_send_a_paid_request(tmp_path: Path) -> None:
    with patch(
        "app.runtime.credentials.httpx.AsyncClient",
        side_effect=AssertionError("Unexpected network check"),
    ):
        result = await CredentialManager(tmp_path).test_key(
            CloudProviderId.VOLCENGINE, "fixture-key"
        )
    assert not result.valid and result.status_code is None
    assert "may incur charges" in result.message
