"""Common broker fixtures and approval checks for all supported calling-code forms."""

from pathlib import Path
from unittest.mock import patch

import pytest
from app.core.custom_provider_service import CustomProviderService
from app.runners.adapter_executor import AdapterError
from app.runtime.credentials import CredentialManager
from app.schemas.custom_provider import CustomProviderSpec

JS = "async function execute(input,ctx){const r=await ctx.request({body:{model:input.model}});return {type:'image',value:{url:r.data[0].url}}}"
PY = "async def execute(input,ctx):\n    r=await ctx.request({'body':{'model':input['model']}})\n    return {'type':'image','value':{'url':r['data'][0]['url']}}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,source", [("rest", ""), ("javascript", JS), ("python", PY)]
)
async def test_three_forms_normalize_fixture_without_http(
    tmp_path: Path, mode: str, source: str
) -> None:
    service = CustomProviderService(CredentialManager(tmp_path))
    spec = CustomProviderSpec(
        id="custom-fixture",
        name="Fixture",
        endpoint="https://fixture.invalid",
        models=["model"],
        actions=["txt2img"],
        mode=mode,
        source=source,
    )
    service.registry.save(spec, approve_execution=True)
    with patch(
        "app.core.provider_broker.httpx.AsyncClient",
        side_effect=AssertionError("Unexpected live HTTP"),
    ):
        output, count = await service.execute(
            spec.id,
            {"model": "model", "prompt": "fixture", "width": 1024, "height": 1024},
            fixture={"data": [{"url": "https://fixture.invalid/image.jpg"}]},
        )
    assert output.value == {"url": "https://fixture.invalid/image.jpg"} and count == 1


@pytest.mark.asyncio
async def test_unapproved_code_or_wrong_model_never_executes(tmp_path: Path) -> None:
    service = CustomProviderService(CredentialManager(tmp_path))
    spec = CustomProviderSpec(
        id="custom-fixture",
        name="Fixture",
        endpoint="https://fixture.invalid",
        models=["model"],
        actions=["txt2img"],
        mode="python",
        source=PY,
    )
    service.registry.save(spec)
    with pytest.raises(AdapterError, match="approve"):
        await service.execute(spec.id, {"model": "model"}, fixture={})
    with pytest.raises(AdapterError, match="model or action"):
        await service.execute(spec.id, {"model": "other"}, fixture={})


@pytest.mark.asyncio
async def test_descriptor_and_key_changes_refuse_stale_execution(
    tmp_path: Path,
) -> None:
    service = CustomProviderService(CredentialManager(tmp_path))
    spec = CustomProviderSpec(
        id="custom-revisions",
        name="Fixture",
        endpoint="https://fixture.invalid",
        models=["model"],
        actions=["txt2img"],
        auth="none",
    )
    service.registry.save(spec)
    inputs = {"model": "model", "prompt": "fixture", "width": 64, "height": 64}
    _, identity, _ = service.snapshot(spec.id, inputs)
    await service.execute(
        spec.id,
        inputs,
        fixture={"data": [{"url": "https://fixture.invalid/a.jpg"}]},
        expected_identity=identity,
    )
    service.credentials.set_key(spec.id, "synthetic-key-revision-one")
    with pytest.raises(AdapterError, match="changed"):
        await service.execute(spec.id, inputs, fixture={}, expected_identity=identity)
    _, updated, _ = service.snapshot(spec.id, inputs)
    assert updated != identity and "synthetic-key-revision-one" not in str(updated)
    service.registry.save(spec.model_copy(update={"endpoint": "https://other.invalid"}))
    with pytest.raises(AdapterError, match="changed"):
        await service.execute(spec.id, inputs, fixture={}, expected_identity=updated)
