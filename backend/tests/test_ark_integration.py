"""Product integration contracts, with no paid provider requests."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.runtime.credentials import CredentialManager
from app.schemas.cloud import CloudProviderId


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
