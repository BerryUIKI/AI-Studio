"""Agent context survives service restart and cannot cross project boundaries."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.agent_service import AgentService
from app.schemas.agent import AgentChatRequest, AgentChatMessage
from app.storage.conversation_store import ConversationStore
from app.storage.db import DatabaseManager


@pytest.mark.asyncio
async def test_followup_restores_prior_context_after_service_restart(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / 'agent.db')
    history = ConversationStore(manager)
    try:
        first = await AgentService(history_store=history).process_chat(AgentChatRequest(message='What can you do?'))
        service = AgentService(history_store=history)
        observed = []

        async def respond(req: AgentChatRequest):
            observed.extend(service.conversations[req.conversation_id])
            return await original(req)

        original = service._process_chat
        with patch.object(service, '_process_chat', side_effect=respond):
            second = await service.process_chat(AgentChatRequest(message='List models', conversation_id=first.conversation_id))
        assert second.conversation_id == first.conversation_id
        assert [message.role for message in observed] == ['user', 'assistant']
        assert observed[0].content == 'What can you do?'
        assert len(await history.load(first.conversation_id, None)) == 4
        assert service.conversations == {}
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_history_is_bounded_and_project_scoped(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / 'agent.db')
    history = ConversationStore(manager)
    try:
        await history.save('conversation', None, [AgentChatMessage(content=str(i)) for i in range(150)])
        assert len(await history.load('conversation', None)) == 100
        with pytest.raises(ValueError, match='different project'):
            await history.load('conversation', 'another-project')
        conn = await manager.get_connection()
        await conn.executemany(
            "INSERT INTO agent_conversations (id, messages_json, updated_at) VALUES (?, '[]', '2000-01-01')",
            [(str(index),) for index in range(205)],
        )
        await history.save('latest', None, [AgentChatMessage(content='fixture')])
        async with conn.execute('SELECT count(*) FROM agent_conversations') as cursor:
            assert (await cursor.fetchone())[0] == 200
        assert (await history.latest(None))['conversation_id'] == 'latest'
    finally:
        await manager.close()
