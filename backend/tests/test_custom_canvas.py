"""Real task, worker, media and cache integration; all provider responses are fixtures."""

import base64
import io
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from app.core.cache import CacheStore
from app.core.creative_tasks import CreativeTaskService
from app.core.custom_provider_service import CustomProviderService
from app.runners.creative_runner import CreativeRunner, resolve_execution_plan
from app.runtime.credentials import CredentialManager
from app.schemas.creative import CreativeActionRequest
from app.schemas.custom_provider import CustomProviderSpec
from app.storage.asset_store import AssetStore
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore
from PIL import Image

JS = "async function execute(input,ctx){const r=await ctx.request({body:{model:input.model,image:input.input_image}});return {type:'image',value:{b64_json:r.data[0].b64_json},reported_model:'fixture-response-model'}}"
PY = "async def execute(input,ctx):\n    r=await ctx.request({'body':{'model':input['model'],'image':input['input_image']}})\n    return {'type':'image','value':{'b64_json':r['data'][0]['b64_json']},'reported_model':'fixture-response-model'}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,source", [("rest", ""), ("javascript", JS), ("python", PY)]
)
@pytest.mark.parametrize("action", ["txt2img", "img2img"])
async def test_custom_canvas_adopts_bytes_persists_replays_and_invalidates(
    tmp_path: Path, mode: str, source: str, action: str
) -> None:
    manager = DatabaseManager(tmp_path / "fixture.db")
    assets = AssetStore(manager=manager, base_dir=tmp_path)
    tasks = TaskStore(manager)
    credentials = CredentialManager(tmp_path)
    credentials.set_key("custom-fixture", "synthetic-fixture-credential")
    service = CustomProviderService(credentials)
    spec = CustomProviderSpec(
        id="custom-fixture",
        name="Fixture",
        endpoint="https://fixture.invalid",
        models=["fixture-model"],
        actions=["txt2img", "img2img"],
        mode=mode,
        source=source,
        result_path="data.0.b64_json",
        response_format="b64_json",
        body_template={"model": "{{model}}", "image": "{{input_image}}"},
    )
    service.registry.save(spec, approve_execution=True)
    image = io.BytesIO()
    Image.new("RGB", (96, 72), "blue").save(image, "JPEG")
    reference = (
        await assets.save_bytes(image.getvalue(), filename="reference.jpg")
        if action == "img2img"
        else None
    )
    image = io.BytesIO()
    Image.new("RGB", (96, 72), "red").save(image, "JPEG")
    calls = []

    async def response(broker, operation):
        calls.append(operation)
        return {"data": [{"b64_json": base64.b64encode(image.getvalue()).decode()}]}

    request = CreativeActionRequest(
        action=action,
        connection_id=spec.id,
        model="fixture-model",
        prompt="Fixture",
        seed=41,
        input_image_id=reference.id if reference else None,
    )

    def bindings():
        return [
            patch("app.runners.creative_runner.asset_store", assets),
            patch(
                "app.runners.creative_runner.cache_store", CacheStore(manager, assets)
            ),
            patch("app.runners.creative_runner.task_store", tasks),
            patch("app.runners.creative_runner.credentials_manager", credentials),
            patch("app.core.provider_broker.ProviderBroker.request", response),
            patch(
                "app.core.provider_broker.httpx.AsyncClient",
                side_effect=AssertionError("Live HTTP forbidden"),
            ),
        ]

    with ExitStack() as stack:
        for binding in bindings():
            stack.enter_context(binding)
        first = await CreativeRunner().execute(request)
        assert first.success, first.error_message
        assert (first.width, first.height, first.mime_type, first.extension) == (
            96,
            72,
            "image/jpeg",
            ".jpg",
        )
        assert first.provenance.model == "fixture-model"
        assert (
            first.provenance.seed is None
            and first.provenance.steps is None
            and first.provenance.cfg_scale is None
        )
        assert first.provenance.parameters["variation_nonce"] == 41
        assert "synthetic-fixture-credential" not in first.model_dump_json()
        if reference:
            assert calls[0]["body"]["image"].startswith("data:image/png;base64,")
        task = await tasks.get_task(first.task_id)
        assert (
            task.status == "succeeded"
            and task.metadata["execution_identity"]["custom_execution"][
                "provider_revision"
            ]
            == spec.revision
        )
        await manager.close()
        # Reopen the same database and cache, as after application restart.
        replay = await CreativeRunner().execute(request)
        assert (
            replay.is_cached and replay.asset_id == first.asset_id and len(calls) == 1
        )
        output = await assets.get_asset(first.asset_id)
        assets.get_absolute_path(output).unlink()
        repaired = await CreativeRunner().execute(request)
        assert repaired.success and not repaired.is_cached and len(calls) == 2
        credentials.set_key(spec.id, "synthetic-replacement-credential")
        replaced_key = await CreativeRunner().execute(request)
        assert replaced_key.success and not replaced_key.is_cached and len(calls) == 3
        service.registry.save(
            spec.model_copy(update={"endpoint": "https://changed.invalid"}),
            approve_execution=True,
        )
        changed = await CreativeRunner().execute(request)
        assert changed.success and not changed.is_cached and len(calls) == 4


@pytest.mark.asyncio
async def test_queued_custom_task_pins_descriptor_before_execution(
    tmp_path: Path,
) -> None:
    credentials = CredentialManager(tmp_path)
    service = CustomProviderService(credentials)
    spec = CustomProviderSpec(
        id="custom-pinned",
        name="Fixture",
        endpoint="https://fixture.invalid",
        models=["fixture"],
        actions=["txt2img"],
        auth="none",
    )
    service.registry.save(spec)
    manager = DatabaseManager(tmp_path / "tasks.db")
    scheduler = CreativeTaskService(TaskStore(manager))
    request = CreativeActionRequest(
        action="txt2img", connection_id=spec.id, model="fixture"
    )

    async def execute(pinned, task_id):
        assert pinned.provider_revision == spec.revision
        service.registry.save(
            spec.model_copy(update={"endpoint": "https://changed.invalid"})
        )
        with pytest.raises(ValueError, match="changed"):
            resolve_execution_plan(pinned)
        from app.schemas.creative import CreativeActionResult

        return CreativeActionResult(
            success=False,
            task_id=task_id,
            error_message="Fixture refused stale configuration",
        )

    with patch("app.runners.creative_runner.credentials_manager", credentials):
        result = await scheduler.execute_and_wait(request, execute)
    assert not result.success and "stale" in result.error_message


def test_custom_plan_rejects_unknown_platform_model_and_action(tmp_path: Path) -> None:
    credentials = CredentialManager(tmp_path)
    service = CustomProviderService(credentials)
    spec = CustomProviderSpec(
        id="custom-limited",
        name="Fixture",
        endpoint="https://fixture.invalid",
        models=["fixture"],
        actions=["txt2img"],
        auth="none",
    )
    service.registry.save(spec)
    with patch("app.runners.creative_runner.credentials_manager", credentials):
        for model, action in [("other", "txt2img"), ("fixture", "inpaint")]:
            with pytest.raises(ValueError, match="model or action"):
                resolve_execution_plan(
                    CreativeActionRequest(
                        action=action, model=model, connection_id=spec.id
                    )
                )
