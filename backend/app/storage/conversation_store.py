"""Bounded project-linked Agent history. Credentials never enter transcripts."""

import json
from datetime import datetime, timezone

from app.schemas.agent import AgentChatMessage
from app.storage.db import DatabaseManager, db_manager
from app.storage.task_store import redact_submission


class ConversationStore:
    def __init__(self, manager: DatabaseManager = db_manager) -> None:
        self.manager = manager

    async def latest(self, project_id: str | None) -> dict[str, object] | None:
        conn = await self.manager.get_connection()
        async with conn.execute(
            "SELECT id, messages_json FROM agent_conversations WHERE project_id IS ? ORDER BY updated_at DESC, id LIMIT 1",
            (project_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return {"conversation_id": row["id"], "messages": json.loads(row["messages_json"])}

    async def load(self, conversation_id: str, project_id: str | None) -> list[AgentChatMessage]:
        conn = await self.manager.get_connection()
        async with conn.execute(
            "SELECT project_id, messages_json FROM agent_conversations WHERE id = ?",
            (conversation_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return []
        if row["project_id"] != project_id:
            raise ValueError("Conversation belongs to a different project.")
        return [AgentChatMessage.model_validate(message) for message in json.loads(row["messages_json"])]

    async def save(self, conversation_id: str, project_id: str | None, messages: list[AgentChatMessage]) -> None:
        conn = await self.manager.get_connection()
        await conn.execute(
            """INSERT INTO agent_conversations (id, project_id, messages_json, updated_at)
               VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET
               messages_json = excluded.messages_json, updated_at = excluded.updated_at""",
            (conversation_id, project_id,
             json.dumps(redact_submission([message.model_dump() for message in messages[-100:]])),
             datetime.now(timezone.utc).isoformat()),
        )
        # Retain the 200 most recently used conversations globally, with at most
        # 100 messages each. Project deletion removes its transcripts as well.
        await conn.execute(
            """DELETE FROM agent_conversations WHERE id NOT IN
               (SELECT id FROM agent_conversations ORDER BY updated_at DESC, id LIMIT 200)"""
        )
        await conn.commit()


conversation_store = ConversationStore()
