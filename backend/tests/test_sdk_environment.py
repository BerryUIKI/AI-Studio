"""Only explicitly trusted SDKs get their own dependency environment."""

from pathlib import Path

import pytest
from app.runners.adapter_executor import AdapterError, execute_adapter
from app.runtime.sdk_environment import (
    prepare_sdk_environment,
    sdk_dependency_revision,
    sdk_directory,
    sdk_module_paths,
    sdk_ready,
)
from app.schemas.custom_provider import CustomProviderRecord, CustomProviderSpec


@pytest.mark.asyncio
async def test_empty_sdk_environment_is_isolated_and_loads_only_its_fixture_module(
    tmp_path: Path,
) -> None:
    from unittest.mock import AsyncMock

    from app.core.workers import run_blocking

    spec = CustomProviderSpec(
        id="custom-sdk",
        name="Fixture SDK",
        endpoint="https://fixture.invalid",
        models=["model"],
        actions=["txt2img"],
        mode="python_sdk",
        source="fixture",
    )
    record = CustomProviderRecord(spec=spec)
    with pytest.raises(AdapterError, match="trust"):
        await prepare_sdk_environment(record, tmp_path)
    assert not sdk_directory(spec, tmp_path).exists()
    record.trusted_revision = spec.revision
    await prepare_sdk_environment(record, tmp_path)
    assert sdk_ready(spec, tmp_path)
    directory = Path(sdk_module_paths(spec, tmp_path)[0])
    assert directory.is_relative_to(tmp_path)
    await run_blocking(directory.mkdir, parents=True, exist_ok=True)
    await run_blocking(
        (directory / "fixture_sdk.py").write_text,
        "def value(): return 'isolated-sdk'",
        encoding="utf-8",
    )
    source = "def execute(input,ctx):\n    import fixture_sdk\n    return {'type':'string','value':fixture_sdk.value()}"
    result = await execute_adapter(
        language="python_sdk",
        source=source,
        inputs={},
        broker=AsyncMock(),
        module_paths=[str(directory)],
    )
    assert result.value == "isolated-sdk"
    before = await run_blocking(sdk_dependency_revision, spec, tmp_path)
    await run_blocking(
        (directory / "fixture_sdk.py").write_text,
        "def value(): return 'changed-sdk'",
        encoding="utf-8",
    )
    assert await run_blocking(sdk_dependency_revision, spec, tmp_path) != before
    changed = spec.model_copy(
        update={"requirements": "fixture-sdk==1.0 --hash=sha256:" + "a" * 64}
    )
    assert not sdk_ready(changed, tmp_path)
