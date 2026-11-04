"""The agent must report how it answered and must never start a model mid-request."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.core.agent_service import AgentService
from app.schemas.agent import AgentChatRequest
from app.schemas.cloud import LLMConfig


def _service(credential_manager=None) -> AgentService:
    return AgentService(credential_manager=credential_manager)


def test_no_model_configured_reports_plain_heuristic():
    response = asyncio.run(_service().process_chat(AgentChatRequest(message="Create a cat")))

    assert response.agent_mode == "heuristic"
    # Nothing was attempted, so there is nothing to warn about.
    assert response.agent_notice is None


def test_failed_model_call_is_reported_as_a_fallback():
    credentials = MagicMock()
    credentials.get_llm_config.return_value = LLMConfig(
        provider="openai", model="gpt-4o", base_url="https://api.openai.invalid/v1",
        api_key="sk-test", enabled=True,
    )
    service = _service(credentials)
    service._process_with_llm = AsyncMock(side_effect=RuntimeError("connection refused"))

    response = asyncio.run(service.process_chat(AgentChatRequest(message="Create a cat")))

    assert response.agent_mode == "heuristic_fallback"
    assert response.agent_notice is not None
    assert "connection refused" in response.agent_notice
    # The user still gets a proposal; the notice only says how it was produced.
    assert response.proposal is not None


def test_unusable_model_reply_is_reported_as_a_fallback():
    credentials = MagicMock()
    credentials.get_llm_config.return_value = LLMConfig(
        provider="openai", model="gpt-4o", base_url="https://api.openai.invalid/v1",
        api_key="sk-test", enabled=True,
    )
    service = _service(credentials)
    service._process_with_llm = AsyncMock(return_value=None)

    response = asyncio.run(service.process_chat(AgentChatRequest(message="Create a cat")))

    assert response.agent_mode == "heuristic_fallback"
    assert "no usable reply" in (response.agent_notice or "")


def test_local_model_is_never_started_by_a_chat_request(monkeypatch):
    """Starting llama-server loads weights; a chat request must not wait for that."""
    started = []
    monkeypatch.setattr(
        "app.runtime.llama_server.llama_supervisor.llama_server_supervisor.start",
        lambda *args, **kwargs: started.append(args) or {},
    )
    monkeypatch.setattr(
        "app.runtime.llama_server.llama_supervisor.llama_server_supervisor.is_installed",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.runtime.llama_server.llama_supervisor.llama_server_supervisor.is_running",
        lambda: False,
    )
    credentials = MagicMock()
    credentials.get_llm_config.return_value = LLMConfig(
        provider="llama_server", model="qwen2.5.gguf",
        base_url="http://127.0.0.1:8080/v1", enabled=True,
    )
    service = _service(credentials)
    service._process_with_llm = AsyncMock(side_effect=RuntimeError("not running"))

    asyncio.run(service.process_chat(AgentChatRequest(message="Create a cat")))

    assert started == []
