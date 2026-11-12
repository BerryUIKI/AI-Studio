import json
import logging
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app, credentials_manager
from app.runtime.credentials import CredentialManager, redact_key, _is_windows
from app.schemas.cloud import CloudProviderId, LLMConfig, SetLLMConfigRequest

client = TestClient(app)


def test_redact_key_helper():
    assert redact_key("") == ""
    assert redact_key("12345") == "****"
    assert redact_key("12345678") == "****"
    assert redact_key("sk-1234567890abcdef") == "sk-...cdef"


def test_credential_encryption_on_disk():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mgr = CredentialManager(data_dir=tmp_path)
        dummy_secret = "super-confidential-secret-key-xyz-987"
        mgr.set_key(CloudProviderId.OPENAI, dummy_secret)

        raw_file_content = mgr.creds_file.read_text(encoding="utf-8")
        if _is_windows():
            # In Windows, verify DPAPI encrypted envelope is used and raw secret is absent
            assert dummy_secret not in raw_file_content
            data = json.loads(raw_file_content)
            assert data.get("encrypted") is True
            assert data.get("format") == "dpapi"
            assert "data" in data

        # Reloading in another manager instance must recover the original secret
        mgr_reloaded = CredentialManager(data_dir=tmp_path)
        assert mgr_reloaded.get_key(CloudProviderId.OPENAI) == dummy_secret


def test_credential_legacy_plaintext_backward_compatibility():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        creds_file = tmp_path / "credentials.json"
        legacy_data = {
            "openai": "sk-legacy-unencrypted-key",
            "fal": "fal-legacy-key",
        }
        creds_file.write_text(json.dumps(legacy_data), encoding="utf-8")

        mgr = CredentialManager(data_dir=tmp_path)
        assert mgr.get_key(CloudProviderId.OPENAI) == "sk-legacy-unencrypted-key"
        assert mgr.get_key(CloudProviderId.FAL) == "fal-legacy-key"


def test_credential_save_failure_raises_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        mgr = CredentialManager(data_dir=tmp_path)
        with patch.object(Path, "write_text", side_effect=OSError("Disk full")):
            with pytest.raises(OSError, match="Failed to persist credentials"):
                mgr.set_key(CloudProviderId.OPENAI, "sk-test")


def test_llm_config_endpoints_redact_secrets():
    dummy_key = "sk-llm-secret-token-abcdef123456"
    stored_cfg = LLMConfig(
        provider="openai",
        model="gpt-4o",
        base_url="https://api.openai.com/v1",
        api_key=dummy_key,
        temperature=0.7,
        enabled=True,
    )

    with patch.object(credentials_manager, "get_llm_config", return_value=stored_cfg):
        resp = client.get("/api/v1/agent/llm/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_key"] != dummy_key
        assert data["api_key"] == redact_key(dummy_key)


def test_llm_config_set_preserves_existing_secret_when_redacted_or_empty():
    dummy_key = "sk-llm-secret-token-abcdef123456"
    existing_cfg = LLMConfig(
        provider="openai",
        model="gpt-4o",
        base_url="https://api.openai.com/v1",
        api_key=dummy_key,
        temperature=0.7,
        enabled=True,
    )

    saved_configs = []

    def mock_set_llm_config(cfg):
        saved_configs.append(cfg)

    with patch.object(credentials_manager, "get_llm_config", return_value=existing_cfg), \
         patch.object(credentials_manager, "set_llm_config", side_effect=mock_set_llm_config):
        # Case 1: user sends redacted key back
        req_payload = {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "api_key": redact_key(dummy_key),
            "temperature": 0.5,
            "enabled": True,
        }
        resp = client.post("/api/v1/agent/llm/config", json=req_payload)
        assert resp.status_code == 200
        assert len(saved_configs) == 1
        assert saved_configs[0].api_key == dummy_key
        assert saved_configs[0].model == "gpt-4o-mini"
        assert resp.json()["api_key"] == redact_key(dummy_key)

        # Case 2: user sends empty string key
        req_payload["api_key"] = ""
        resp = client.post("/api/v1/agent/llm/config", json=req_payload)
        assert resp.status_code == 200
        assert len(saved_configs) == 2
        assert saved_configs[1].api_key == dummy_key


def test_llm_config_set_persistence_error_returns_500():
    with patch.object(credentials_manager, "set_llm_config", side_effect=OSError("Read-only filesystem")):
        req_payload = {
            "provider": "openai",
            "model": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-new-key",
            "temperature": 0.7,
            "enabled": True,
        }
        resp = client.post("/api/v1/agent/llm/config", json=req_payload)
        assert resp.status_code == 500
        assert "Failed to persist LLM configuration" in resp.json()["detail"]


def test_non_windows_chmod_failure_raises(monkeypatch):
    """A chmod failure must abort the save instead of storing a world-readable secret file."""
    if not hasattr(os, "chmod"):
        pytest.skip("platform without os.chmod")
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("app.runtime.credentials._is_windows", lambda: False)

        mgr = CredentialManager(data_dir=Path(tmpdir))

        def broken_chmod(path, mode):
            raise OSError("Simulated chmod failure")

        monkeypatch.setattr(os, "chmod", broken_chmod)
        with pytest.raises(OSError, match="Failed to persist credentials"):
            mgr.set_key(CloudProviderId.OPENAI, "sk-nonwin-chmod-fail")


def test_non_windows_chmod_enforced_on_save(monkeypatch):
    """On non-Windows the saved credential file must end up with no group/other access."""
    if os.name == "nt":
        pytest.skip("0600 enforcement is a non-Windows behavior")
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = CredentialManager(data_dir=Path(tmpdir))
        mgr.set_key(CloudProviderId.OPENAI, "sk-nonwin-enforced")
        mode = mgr.creds_file.stat().st_mode
        assert (mode & 0o077) == 0
        # Reloading in another manager must recover the secret
        reloaded = CredentialManager(data_dir=Path(tmpdir))
        assert reloaded.get_key(CloudProviderId.OPENAI) == "sk-nonwin-enforced"


def test_save_failure_log_contains_no_secret(monkeypatch, caplog):
    """Persistence errors must log messages that never contain the secret itself."""
    with tempfile.TemporaryDirectory() as tmpdir:
        secret = "sk-log-leak-probe-9876543210abcdef"
        mgr = CredentialManager(data_dir=Path(tmpdir))
        with caplog.at_level(logging.ERROR, logger="app.runtime.credentials"):
            with patch.object(Path, "write_text", side_effect=OSError("Disk full")):
                with pytest.raises(OSError, match="Failed to persist credentials"):
                    mgr.set_key(CloudProviderId.OPENAI, secret)
        # The raised error is the actionable message; the log must exist but never echo the secret
        assert secret not in caplog.text
        assert any("Error saving credentials" in record.message for record in caplog.records)
