"""Submissions survive restart without inventing a remote completion outcome."""

from pathlib import Path

import pytest

from app.schemas.task import RunRecord, TaskRecord
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore


@pytest.mark.asyncio
async def test_durable_history_and_restart_recovery(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "tasks.db")
    store = TaskStore(manager)
    try:
        for identity, status, engine in [("done", "succeeded", "cloud"), ("remote", "running", "cloud"), ("local", "running", "comfyui")]:
            await store.create_run(RunRecord(id=identity, project_id="project", request={"prompt": "hello", "api_key": "secret"}))
            await store.save_task(TaskRecord(id=identity, run_id=identity, node_id="canvas", node_type="txt2img", status=status,
                params={"seed": 42, "nested": {"token": "secret", "chroma_key": "green"}}, metadata={"engine": engine, "provider_job_id": "job-123"},
                outputs={"asset_id": "output"} if identity == "done" else {}))
            if identity == "done":
                await store.finish_run(identity, "succeeded")
        await manager.close()
        store = TaskStore(manager)
        assert await store.reconcile_interrupted() == 2
        history = {task.id: task for task in await store.list_tasks(project_id="project")}
        assert history["done"].status == "succeeded"
        assert history["done"].outputs["asset_id"] == "output"
        assert history["remote"].status == "outcome-unknown"
        assert history["local"].status == "interrupted"
        assert history["remote"].metadata["provider_job_id"] == "job-123"
        assert history["remote"].params["nested"] == {"chroma_key": "green"}
        assert await store.list_tasks(project_id="another") == []
        assert "api_key" not in (await store.get_run("remote")).request
    finally:
        await manager.close()
