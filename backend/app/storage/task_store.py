"""Durable submissions and task transitions, with conservative restart recovery."""

import json
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from app.schemas.task import RunRecord, TaskRecord, TaskStatus
from app.storage.db import DatabaseManager, db_manager

TERMINAL_STATUSES = {"cached", "succeeded", "failed", "cancelled", "interrupted", "outcome-unknown"}
SECRET_FIELDS = {"api_key", "apikey", "access_token", "token", "authorization", "password", "secret"}


def redact_submission(value: Any) -> Any:
    """Retain semantic parameters while excluding inline secrets from history."""
    if isinstance(value, dict):
        return {key: redact_submission(item) for key, item in value.items() if key.lower() not in SECRET_FIELDS}
    if isinstance(value, list):
        return [redact_submission(item) for item in value]
    return value


class TaskStore:
    def __init__(self, manager: DatabaseManager = db_manager) -> None:
        self.manager = manager

    async def create_run(self, run: RunRecord) -> None:
        conn = await self.manager.get_connection()
        await conn.execute(
            "INSERT INTO runs (id, project_id, target_node_id, status, created_at, request_json) VALUES (?, ?, ?, ?, ?, ?)",
            (run.id, run.project_id, run.target_node_id, run.status, run.created_at, json.dumps(redact_submission(run.request))),
        )
        await conn.commit()

    async def get_run(self, run_id: str) -> RunRecord | None:
        conn = await self.manager.get_connection()
        async with conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return RunRecord(**{key: row[key] for key in ("id", "project_id", "target_node_id", "status", "created_at", "finished_at")}, request=json.loads(row["request_json"] or "{}"))

    async def finish_run(self, run_id: str, status: TaskStatus) -> None:
        conn = await self.manager.get_connection()
        finished = datetime.now(timezone.utc).isoformat() if status in TERMINAL_STATUSES else None
        await conn.execute("UPDATE runs SET status = ?, finished_at = ? WHERE id = ?", (status, finished, run_id))
        await conn.commit()

    async def save_task(self, task: TaskRecord) -> None:
        conn = await self.manager.get_connection()
        if task.status in TERMINAL_STATUSES and task.finished_at is None:
            task.finished_at = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """INSERT INTO tasks (id, run_id, node_id, node_type, status, params_json, inputs_json,
               outputs_json, error_msg, created_at, finished_at, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET status=excluded.status, params_json=excluded.params_json,
               inputs_json=excluded.inputs_json, outputs_json=excluded.outputs_json, error_msg=excluded.error_msg,
               finished_at=excluded.finished_at, metadata_json=excluded.metadata_json""",
            (task.id, task.run_id, task.node_id, task.node_type, task.status, json.dumps(redact_submission(task.params)),
             json.dumps(redact_submission(task.inputs)), json.dumps(redact_submission(task.outputs)), task.error,
             task.created_at, task.finished_at, json.dumps(redact_submission(task.metadata))),
        )
        await conn.commit()

    async def list_tasks(self, project_id: str | None = None, run_id: str | None = None) -> list[TaskRecord]:
        conn = await self.manager.get_connection()
        async with conn.execute(
            """SELECT tasks.*, runs.project_id FROM tasks JOIN runs ON tasks.run_id = runs.id
               WHERE (? IS NULL OR runs.project_id = ?) AND (? IS NULL OR runs.id = ?)
               ORDER BY tasks.created_at DESC, tasks.id LIMIT 200""",
            (project_id, project_id, run_id, run_id),
        ) as cursor:
            rows = await cursor.fetchall()
        return [TaskRecord(
            **{key: row[key] for key in ("id", "run_id", "node_id", "node_type", "status", "created_at", "finished_at", "project_id")},
            params=json.loads(row["params_json"] or "{}"), inputs=json.loads(row["inputs_json"] or "{}"),
            outputs=json.loads(row["outputs_json"] or "{}"), error=row["error_msg"], metadata=json.loads(row["metadata_json"] or "{}"),
        ) for row in rows]

    async def get_task(self, task_id: str) -> TaskRecord | None:
        conn = await self.manager.get_connection()
        async with conn.execute("SELECT tasks.*, runs.project_id FROM tasks JOIN runs ON tasks.run_id = runs.id WHERE tasks.id = ?", (task_id,)) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return TaskRecord(
            **{key: row[key] for key in ("id", "run_id", "node_id", "node_type", "status", "created_at", "finished_at", "project_id")},
            params=json.loads(row["params_json"] or "{}"), inputs=json.loads(row["inputs_json"] or "{}"),
            outputs=json.loads(row["outputs_json"] or "{}"), error=row["error_msg"], metadata=json.loads(row["metadata_json"] or "{}"),
        )

    async def request_cancel(self, task_id: str) -> bool:
        """Do not overwrite a terminal result when cancellation races completion."""
        conn = await self.manager.get_connection()
        cursor = await conn.execute(
            """UPDATE tasks SET status = 'cancel-requested',
               metadata_json = json_set(COALESCE(metadata_json, '{}'), '$.cancel_requested', json('true'))
               WHERE id = ? AND status IN ('queued', 'running', 'cancel-requested')""", (task_id,),
        )
        await conn.execute(
            """UPDATE runs SET status = 'cancel-requested' WHERE id = (SELECT run_id FROM tasks WHERE id = ?)
               AND status IN ('queued', 'running', 'cancel-requested')""", (task_id,),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def reconcile_interrupted(self) -> int:
        """Never automatically resubmit uncertain remote work at duplicate cost."""
        conn = await self.manager.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        cursor = await conn.execute(
            """UPDATE tasks SET status = CASE WHEN json_extract(metadata_json, '$.engine') = 'cloud'
               THEN 'outcome-unknown' ELSE 'interrupted' END, finished_at = ?,
               error_msg = 'Application stopped before completion was recorded. Check the provider or engine before retrying.'
               WHERE status IN ('queued', 'running', 'cancel-requested')""", (now,),
        )
        await conn.execute(
            """UPDATE runs SET status = CASE WHEN EXISTS (SELECT 1 FROM tasks WHERE tasks.run_id = runs.id
               AND tasks.status = 'outcome-unknown') THEN 'outcome-unknown' ELSE 'interrupted' END,
               finished_at = ? WHERE status IN ('queued', 'running', 'cancel-requested')""", (now,),
        )
        await conn.commit()
        return cursor.rowcount

    async def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        conn = await self.manager.get_connection()
        await conn.execute(
            """INSERT INTO workflow_events (run_id, sequence, event_json)
               SELECT ?, COALESCE(MAX(sequence), 0) + 1, ? FROM workflow_events WHERE run_id = ?""",
            (run_id, json.dumps(redact_submission({**event, "run_id": run_id})), run_id),
        )
        await conn.commit()

    async def get_events(self, run_id: str, after_sequence: int = 0) -> list[dict[str, Any]]:
        conn = await self.manager.get_connection()
        async with conn.execute(
            "SELECT sequence, event_json FROM workflow_events WHERE run_id = ? AND sequence > ? ORDER BY sequence LIMIT 500",
            (run_id, after_sequence),
        ) as cursor:
            rows = await cursor.fetchall()
        return [{**json.loads(row["event_json"]), "sequence": row["sequence"]} for row in rows]


task_store = TaskStore()
execution_task: ContextVar[tuple[TaskStore, TaskRecord] | None] = ContextVar("execution_task", default=None)


async def record_remote_job(job_id: str) -> None:
    """Persist a provider-owned job identifier before starting to poll it."""
    context = execution_task.get()
    if context:
        store, task = context
        task.metadata["provider_job_id"] = job_id
        await store.save_task(task)
