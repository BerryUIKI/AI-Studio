"""Descriptors cannot escape storage or silently retain trust after edits."""

from pathlib import Path

import pytest
from app.runtime.custom_providers import CustomProviderRegistry
from app.schemas.custom_provider import CustomProviderSpec
from pydantic import ValidationError


def spec(**overrides: object) -> CustomProviderSpec:
    return CustomProviderSpec.model_validate(
        {
            "id": "custom-fixture",
            "name": "Fixture",
            "endpoint": "https://fixture.invalid/v1/images",
            "models": ["fixture-model"],
            "actions": ["txt2img"],
            **overrides,
        }
    )


def test_roundtrip_and_revision_trust(tmp_path: Path) -> None:
    registry = CustomProviderRegistry(tmp_path)
    first = spec(mode="python", source="async def execute(input, ctx): return input")
    saved = registry.save(first, approve_execution=True)
    assert saved.execution_trusted
    assert CustomProviderRegistry(tmp_path).get(first.id).spec == first
    changed = first.model_copy(update={"source": first.source + "\n# edited"})
    assert changed.revision != first.revision
    assert not registry.save(changed).execution_trusted
    assert registry.save(changed, approve_execution=True).execution_trusted
    registry.delete(first.id)
    assert registry.list() == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": "../escape"},
        {"endpoint": "https://user:secret@fixture.invalid"},
        {"endpoint": "https://fixture.invalid?api_key=secret"},
        {"endpoint": "http://remote.invalid"},
        {"models": ["", "model"]},
        {"requirements": "requests>=2"},
        {"requirements": "--index-url https://untrusted.invalid"},
    ],
)
def test_unsafe_or_unpinned_descriptors_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        spec(**overrides)


def test_loopback_development_and_hashed_dependency_manifest() -> None:
    manifest = "fixture-sdk==1.0 --hash=sha256:" + "a" * 64
    record = spec(endpoint="http://127.0.0.1:8032/generate", requirements=manifest)
    assert record.requirements == manifest
