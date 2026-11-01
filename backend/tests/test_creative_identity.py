"""Creative cache keys follow the execution target and its actual contents."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.creative_identity import creative_execution_identity
from app.runners.creative_runner import CreativeRunner, compute_creative_cache_hash, resolve_execution_plan
from app.schemas.creative import CreativeActionRequest
from app.schemas.engine import EngineConnection


def test_explicit_cloud_connection_overrides_stale_local_selection() -> None:
    request = CreativeActionRequest(action="txt2img", prompt="fixture", model="flux-schnell",
                                    engine_id="comfyui-managed", connection_id="fal_ai")
    plan = resolve_execution_plan(request)
    assert plan.engine == "cloud"
    assert plan.provider_id == "fal_ai"


@pytest.mark.asyncio
async def test_local_model_bytes_endpoint_and_runtime_change_cache_identity(tmp_path: Path) -> None:
    model = tmp_path / "same.safetensors"
    model.write_bytes(b"first model")
    connection = EngineConnection(id="fixture", name="Fixture", engine_type="comfyui",
                                  ownership="external", endpoint_url="http://first:8188",
                                  status="running", version="revision-one")
    request = CreativeActionRequest(action="txt2img", prompt="fixture", model=model.name,
                                    connection_id=connection.id, seed=42)
    with patch("app.runners.creative_runner.engine_manager.get_engine", return_value=connection), patch(
        "app.core.workflow_spec.model_store.scan_all_roots_async", new_callable=AsyncMock, return_value=[SimpleNamespace(file_path=str(model))]
    ):
        plan = resolve_execution_plan(request)

        async def key() -> str:
            identity = await creative_execution_identity(plan, connection)
            return compute_creative_cache_hash(request, connection.id, execution_identity=identity)

        first = await key()
        assert await key() == first
        model.write_bytes(b"other model")
        replaced = await key()
        assert replaced != first
        connection.endpoint_url = "http://second:8188"
        moved = await key()
        assert moved != replaced
        connection.version = "revision-two"
        assert await key() != moved


@pytest.mark.asyncio
async def test_cloud_identity_describes_adapter_target_without_invented_weight_revision() -> None:
    request = CreativeActionRequest(action="txt2img", prompt="fixture", model="requested-alias",
                                    connection_id="siliconflow", seed=42)
    identity = await creative_execution_identity(resolve_execution_plan(request), None)
    assert identity["model"] == "stabilityai/stable-diffusion-xl-base-1.0"
    assert identity["model_revision"] is None
    assert len(identity["adapter_revision"]) == 64


@pytest.mark.asyncio
async def test_unverified_local_model_never_reads_or_writes_cache() -> None:
    connection = EngineConnection(id="fixture", name="Fixture", engine_type="comfyui",
                                  ownership="external", endpoint_url="http://fixture:8188", status="running")
    request = CreativeActionRequest(action="txt2img", prompt="fixture", model="unknown.safetensors",
                                    connection_id=connection.id, seed=42)
    with patch("app.runners.creative_runner.engine_manager.get_engine", return_value=connection), patch(
        "app.core.creative_identity.local_model_identity", new=AsyncMock(return_value="unverified:unknown.safetensors")
    ), patch("app.runners.creative_runner.cache_store") as cache, patch(
        "app.runners.creative_runner.asset_store.get_asset", new=AsyncMock(return_value=None)
    ), patch.object(CreativeRunner, "_run_comfy", new=AsyncMock(return_value={
        "asset_id": "fixture-output", "image_url": "/api/v1/assets/fixture-output/content"
    })) as dispatch:
        result = await CreativeRunner().execute(request)
        assert result.success
        dispatch.assert_awaited_once()
        cache.get_async.assert_not_called()
        cache.set_async.assert_not_called()
