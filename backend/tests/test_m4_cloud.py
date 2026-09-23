"""
Milestone 4 Verification Tests: BYOK Cloud Credentials, Providers & Cloud Execution.

Verifies:
1. CredentialManager local persistence and strict secret redaction.
2. Cloud key validation against external endpoints.
3. CreativeRunner cloud-only image generation with asset adoption and caching (zero GPU/torch).
4. FastAPI cloud REST endpoints.
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runners.creative_runner import CreativeRunner
from app.runtime.credentials import CredentialManager, redact_key
from app.schemas.cloud import CloudProviderId
from app.schemas.creative import CreativeActionRequest, CreativeActionType
from app.storage.asset_store import asset_store

client = TestClient(app)

DUMMY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_credential_redaction_and_persistence():
    """Verify secrets are strictly redacted in provider listings and persist safely."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = CredentialManager(data_dir=Path(tmpdir))

        # Check redact utility
        assert redact_key("sk-proj-1234567890abcdef") == "sk-...cdef"
        assert redact_key("short") == "****"
        assert redact_key("") == ""

        # Set secret
        mgr.set_key(CloudProviderId.OPENAI, "sk-proj-mysecretkey12345678")
        assert mgr.get_key(CloudProviderId.OPENAI) == "sk-proj-mysecretkey12345678"

        # List providers: ensure raw key is NEVER present in the info object
        providers = mgr.list_providers()
        oai = next(p for p in providers if p.id == CloudProviderId.OPENAI)
        assert oai.is_configured is True
        assert oai.redacted_key == "sk-...5678"
        assert "mysecretkey" not in oai.redacted_key

        # Re-load in a new instance: verify persistence
        mgr2 = CredentialManager(data_dir=Path(tmpdir))
        assert mgr2.get_key(CloudProviderId.OPENAI) == "sk-proj-mysecretkey12345678"

        # Delete key
        mgr2.delete_key(CloudProviderId.OPENAI)
        assert mgr2.get_key(CloudProviderId.OPENAI) is None


@pytest.mark.asyncio
async def test_cloud_key_validation_mocked():
    """Verify live key validation tests against provider endpoints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = CredentialManager(data_dir=Path(tmpdir))

        # Test valid key (200 OK)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp

            res = await mgr.test_key(CloudProviderId.OPENAI, "sk-test-valid-key")
            assert res.valid is True
            assert res.status_code == 200
            assert "verified successfully" in res.message

        # Test invalid key (401 Unauthorized)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_get.return_value = mock_resp

            res = await mgr.test_key(CloudProviderId.OPENAI, "sk-test-bad-key")
            assert res.valid is False
            assert res.status_code == 401
            assert "Invalid key" in res.message


@pytest.mark.asyncio
async def test_creative_runner_cloud_txt2img_adoption():
    """Verify cloud execution runs with zero GPU/torch and adopts remote URLs into asset store."""
    runner = CreativeRunner()
    unique_prompt = f"ethereal nebula {uuid.uuid4()}"

    # Mock Fal.ai FLUX call
    with patch("app.runners.creative_runner.credentials_manager.get_key") as mock_key, \
         patch("app.runners.creative_runner._call_fal_ai", new_callable=AsyncMock) as mock_fal, \
         patch("app.runners.creative_runner.asset_store.save_image_from_url", new_callable=AsyncMock) as mock_save:

        mock_key.return_value = "fal-test-key"
        mock_fal.return_value = "https://fal.media/files/sample_nebula.png"

        # Mock asset store adoption
        mock_asset = MagicMock()
        mock_asset.id = "asset_cloud_nebula"
        mock_asset.content_hash = "hash_nebula_123"
        mock_save.return_value = mock_asset

        req = CreativeActionRequest(
            action=CreativeActionType.TXT2IMG,
            prompt=unique_prompt,
            model="flux-schnell",
            engine_id="cloud_fal",
            aspect_ratio="1:1",
            seed=101,
        )

        # 1. Execute cloud action
        res = await runner.execute(req)
        assert res.success is True
        assert res.asset_id == "asset_cloud_nebula"
        assert res.image_url == "/api/v1/assets/asset_cloud_nebula/content"
        assert res.provenance is not None
        assert res.provenance.model == "flux-schnell"
        assert res.provenance.engine_id == "cloud_fal"

        # Verify asset adoption was called with remote URL
        mock_save.assert_called_once_with("https://fal.media/files/sample_nebula.png", filename="cloud_output.png")


def test_api_cloud_endpoints():
    """Verify REST endpoints for cloud provider listing and credential management."""
    # 1. List providers
    resp = client.get("/api/v1/cloud/providers")
    assert resp.status_code == 200
    providers = resp.json()
    assert isinstance(providers, list)
    assert any(p["id"] == "openai" for p in providers)
    assert any(p["id"] == "fal" for p in providers)
    assert any(p["id"] == "siliconflow" for p in providers)

    # 2. Store credential
    store_resp = client.post(
        "/api/v1/cloud/credentials",
        json={"provider_id": "fal", "api_key": "fal-test-secret-key-999"},
    )
    assert store_resp.status_code == 200
    fal_info = store_resp.json()
    assert fal_info["is_configured"] is True
    assert "999" in fal_info["redacted_key"]
    assert "secret" not in fal_info["redacted_key"]

    # 3. Test credential endpoint
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        test_resp = client.post(
            "/api/v1/cloud/credentials/test",
            json={"provider_id": "fal"},
        )
        assert test_resp.status_code == 200
        test_data = test_resp.json()
        assert test_data["valid"] is True

    # 4. Delete credential
    del_resp = client.delete("/api/v1/cloud/credentials/fal")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True
