"""Custom inpainting uses canonical alpha coverage and invalidates changed masks."""

import base64
import io
from pathlib import Path
from unittest.mock import patch

import pytest
from app.core.cache import CacheStore
from app.core.custom_provider_service import CustomProviderService
from app.runners.creative_runner import CreativeRunner
from app.runtime.credentials import CredentialManager
from app.schemas.creative import CreativeActionRequest
from app.schemas.custom_provider import CustomProviderSpec
from app.storage.asset_store import AssetStore
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore
from PIL import Image


@pytest.mark.asyncio
async def test_custom_mask_preserves_coverage_coordinates_and_cache_identity(
    tmp_path: Path,
) -> None:
    manager = DatabaseManager(tmp_path / "fixture.db")
    assets = AssetStore(manager=manager, base_dir=tmp_path)
    credentials = CredentialManager(tmp_path)
    spec = CustomProviderSpec(
        id="custom-inpaint",
        name="Fixture",
        endpoint="https://fixture.invalid",
        auth="none",
        models=["fixture"],
        actions=["inpaint"],
        response_format="b64_json",
        result_path="data.0.b64_json",
        body_template={"image": "{{input_image}}", "mask": "{{mask_image}}"},
    )
    CustomProviderService(credentials).registry.save(spec)
    buffer = io.BytesIO()
    Image.new("RGB", (96, 72), "blue").save(buffer, "JPEG")
    source = await assets.save_bytes(buffer.getvalue(), filename="source.jpg")
    mask = Image.new("RGBA", (96, 72), (255, 255, 255, 0))
    mask.putpixel((48, 36), (255, 255, 255, 128))
    mask.putpixel((49, 36), (255, 255, 255, 255))
    encoded = io.BytesIO()
    mask.save(encoded, "PNG")
    record = await assets.save_bytes(encoded.getvalue(), filename="mask.png")
    calls = []

    async def response(broker, operation):
        calls.append(operation)
        return {"data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode()}]}

    request = CreativeActionRequest(
        action="inpaint",
        connection_id=spec.id,
        model="fixture",
        seed=42,
        input_image_id=source.id,
        mask_image_id=record.id,
    )
    with (
        patch("app.runners.creative_runner.credentials_manager", credentials),
        patch("app.runners.creative_runner.asset_store", assets),
        patch("app.runners.creative_runner.cache_store", CacheStore(manager, assets)),
        patch("app.runners.creative_runner.task_store", TaskStore(manager)),
        patch("app.core.provider_broker.ProviderBroker.request", response),
    ):
        first = await CreativeRunner().execute(request)
        assert first.success, first.error_message
        with Image.open(
            io.BytesIO(base64.b64decode(calls[0]["body"]["mask"].split(",", 1)[1]))
        ) as normalized:
            assert normalized.size == (96, 72) and normalized.mode == "L"
            assert normalized.getpixel((0, 0)) == 0
            assert normalized.getpixel((48, 36)) == 128
            assert normalized.getpixel((49, 36)) == 255
        assert (await CreativeRunner().execute(request)).is_cached and len(calls) == 1
        mask.putpixel((48, 36), (255, 255, 255, 255))
        mask.save(assets.get_absolute_path(record), "PNG")
        changed = await CreativeRunner().execute(request)
        assert not changed.success and "corrupt" in changed.error_message and len(calls) == 1
        new_mask = io.BytesIO()
        mask.save(new_mask, "PNG")
        replacement = await assets.save_bytes(new_mask.getvalue(), filename="replacement-mask.png")
        request.mask_image_id = replacement.id
        changed = await CreativeRunner().execute(request)
        assert changed.success and not changed.is_cached and len(calls) == 2
