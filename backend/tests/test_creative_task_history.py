"""Creative execution writes real task records for both success and failure."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.runners.creative_runner import CreativeRunner
from app.schemas.creative import CreativeActionRequest
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore, record_remote_job


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
async def test_creative_records_survive_reopen(fail: bool, tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "history.db")
    store = TaskStore(manager)
    runner = CreativeRunner()
    request = CreativeActionRequest(action="txt2img", engine_id="fal_ai", project_id="project", seed=42)

    async def dispatch(*args: object) -> dict:
        await record_remote_job("fixture-job")
        if fail:
            raise RuntimeError("provider unavailable")
        return {"asset_id": "output", "image_url": "/api/v1/assets/output/content", "width": 32, "height": 24}

    try:
        with patch("app.runners.creative_runner.task_store", store), patch.object(runner, "_run_cloud", side_effect=dispatch), patch(
            "app.runners.creative_runner.cache_store.get_async", new=AsyncMock(return_value=None)
        ), patch("app.runners.creative_runner.cache_store.set_async", new=AsyncMock()), patch(
            "app.runners.creative_runner.asset_store.get_asset", new=AsyncMock(return_value=SimpleNamespace(width=32, height=24))
        ):
            result = await runner.execute(request)
        await manager.close()
        task = (await store.list_tasks(project_id="project"))[0]
        assert task.id == result.task_id
        assert task.status == ("failed" if fail else "succeeded")
        assert task.params["seed"] == 42
        assert task.params["width"] == 1024
        assert request.width == 512
        assert task.metadata["provider_job_id"] == "fixture-job"
        assert task.metadata["engine"] == "cloud"
        assert task.error == ("provider unavailable" if fail else None)
        assert (await store.get_run(task.run_id)).status == task.status
        if not fail:
            assert task.outputs["asset_id"] == "output"
            assert task.outputs["provenance"]["provider_id"] == "fal_ai"
    finally:
        await manager.close()
