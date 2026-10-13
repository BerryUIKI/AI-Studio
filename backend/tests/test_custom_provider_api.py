"""Custom platform CRUD and protected credential references without inference."""

from pathlib import Path
from unittest.mock import patch

import pytest
from app.main import app
from app.runtime.credentials import CredentialManager
from app.schemas.cloud import CloudProviderId
from fastapi.testclient import TestClient


def test_platform_crud_credentials_catalog_and_delete(tmp_path: Path) -> None:
    manager = CredentialManager(tmp_path)
    body = {
        "spec": {
            "id": "custom-fixture",
            "name": "Fixture",
            "endpoint": "https://fixture.invalid/generate",
            "models": ["model"],
            "actions": ["txt2img"],
            "mode": "python",
            "source": "async def execute(input, ctx): return input",
        }
    }
    with (
        patch("app.main.credentials_manager", manager),
        patch("app.api.custom_providers.credentials_manager", manager),
    ):
        client = TestClient(app)
        assert client.put("/api/v1/custom-providers", json=body).status_code == 200
        rows = client.get("/api/v1/custom-providers").json()
        assert (
            not rows[0]["execution_trusted"] and len(rows[0]["spec"]["revision"]) == 64
        )
        result = client.post(
            "/api/v1/cloud/credentials",
            json={
                "provider_id": "custom-fixture",
                "api_key": "fixture-secret-credential",
            },
        )
        assert result.status_code == 200
        assert "fixture-secret-credential" not in result.text
        assert not result.json()["is_configured"]
        body["approve_execution"] = True
        assert client.put("/api/v1/custom-providers", json=body).json()[
            "execution_trusted"
        ]
        catalog = client.get("/api/v1/cloud/providers").json()
        assert next(item for item in catalog if item["id"] == "custom-fixture")[
            "is_configured"
        ]
        assert (
            client.post(
                "/api/v1/cloud/credentials/test", json={"provider_id": "custom-fixture"}
            ).json()["valid"]
            is False
        )
        assert (
            client.delete("/api/v1/custom-providers/custom-fixture").status_code == 200
        )
        assert manager.get_key("custom-fixture") is None
        assert client.get("/api/v1/custom-providers").json() == []
        assert (
            client.post(
                "/api/v1/cloud/credentials",
                json={"provider_id": "custom-missing", "api_key": "fixture"},
            ).status_code
            == 404
        )


def test_failed_credential_save_keeps_existing_key_and_revision(tmp_path: Path) -> None:
    manager = CredentialManager(tmp_path)
    manager.set_key(CloudProviderId.OPENAI, "old-fixture")
    revision = manager.key_revision(CloudProviderId.OPENAI)
    with patch.object(manager, "_save", side_effect=OSError("fixture disk failure")):
        with pytest.raises(OSError):
            manager.set_key(CloudProviderId.OPENAI, "replacement-fixture")
        assert manager.get_key(CloudProviderId.OPENAI) == "old-fixture"
        assert manager.key_revision(CloudProviderId.OPENAI) == revision
        with pytest.raises(OSError):
            manager.delete_key(CloudProviderId.OPENAI)
        assert manager.get_key(CloudProviderId.OPENAI) == "old-fixture"


@pytest.mark.parametrize("identifier", [123, "../secret", "llm_config"])
def test_invalid_credential_identifier_is_validation_error(identifier: object) -> None:
    assert (
        TestClient(app)
        .post(
            "/api/v1/cloud/credentials",
            json={"provider_id": identifier, "api_key": "fixture"},
        )
        .status_code
        == 422
    )
