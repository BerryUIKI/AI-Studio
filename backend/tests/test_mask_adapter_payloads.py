"""Known painted regions retain their meaning at the cloud adapter boundary."""

import base64
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from app.runners.creative_runner import CreativeRunner, resolve_execution_plan
from app.schemas.creative import CreativeActionRequest


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["fal_ai", "openai"])
async def test_cloud_payload_edits_known_region(provider: str, tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    mask = tmp_path / "mask.png"
    Image.new("RGB", (8, 6), "red").save(source)
    painted = Image.new("RGBA", (8, 6), (255, 255, 255, 0))
    painted.putpixel((3, 2), (255, 255, 255, 255))
    painted.save(mask)
    request = CreativeActionRequest(action="inpaint", engine_id=provider)
    with patch("app.runners.creative_runner.credentials_manager.get_key", return_value="fixture-key"), patch(
        "app.runners.creative_runner.asset_store.save_image_from_url", new=AsyncMock(return_value=SimpleNamespace(id="output", width=8, height=6))
    ), patch("app.runners.creative_runner._call_fal_ai_action", new=AsyncMock(return_value="https://fixture/output.png")) as fal, patch(
        "app.runners.creative_runner._call_openai_inpaint", new=AsyncMock(return_value="https://fixture/output.png")
    ) as openai:
        await CreativeRunner()._run_cloud(request, resolve_execution_plan(request), source, mask)
        if provider == "fal_ai":
            encoded = base64.b64decode(fal.call_args.kwargs["mask_b64"])
            with Image.open(BytesIO(encoded)) as actual:
                assert actual.size == (8, 6)
                assert actual.mode == "L"
                assert actual.getpixel((3, 2)) == 255
                assert actual.getpixel((0, 0)) == 0
        else:
            with Image.open(BytesIO(openai.call_args.args[2])) as actual:
                assert actual.size == (8, 6)
                assert actual.getpixel((3, 2))[3] == 0
                assert actual.getpixel((0, 0))[3] == 255


@pytest.mark.asyncio
async def test_misaligned_cloud_mask_blocks_dispatch(tmp_path: Path) -> None:
    source, mask = tmp_path / "source.png", tmp_path / "mask.png"
    Image.new("RGB", (8, 6)).save(source)
    Image.new("RGBA", (4, 3)).save(mask)
    records = {
        "source": SimpleNamespace(content_hash="source", width=8, height=6, path=source),
        "mask": SimpleNamespace(content_hash="mask", path=mask),
    }
    request = CreativeActionRequest(action="inpaint", engine_id="fal_ai", input_image_id="source", mask_image_id="mask")
    runner = CreativeRunner()
    with patch("app.runners.creative_runner.asset_store.get_asset", new=AsyncMock(side_effect=lambda key: records[key])), patch(
        "app.runners.creative_runner.asset_store.get_absolute_path", side_effect=lambda record: record.path
    ), patch.object(runner, "_run_cloud", new=AsyncMock()) as dispatch:
        result = await runner.execute(request)
    assert not result.success
    assert "do not match" in result.error_message
    dispatch.assert_not_called()
