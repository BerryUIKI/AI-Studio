"""ASGI cleanup must close SQLite even when the host or scheduler fails."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from app.main import app, lifespan
from app.storage.db import DatabaseManager


def test_collection_isolates_singleton_credentials_and_default_data() -> None:
    from app.runtime.credentials import credentials_manager
    from app.storage.db import get_default_data_dir

    test_root = Path(__file__).resolve().parents[2] / ".cache" / "backend-tests"
    assert credentials_manager.creds_file.is_relative_to(test_root)
    assert get_default_data_dir().is_relative_to(test_root)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "consumer", "scheduler"])
async def test_lifespan_closes_database_on_every_exit(
    tmp_path: Path, failure: str | None
) -> None:
    manager = DatabaseManager(tmp_path / "owned.db")
    workflow_stop = AsyncMock(
        side_effect=RuntimeError("fixture shutdown") if failure == "scheduler" else None
    )
    creative_stop = AsyncMock()
    with (
        patch("app.main.db_manager", manager),
        patch("app.main.task_store.reconcile_interrupted", new=AsyncMock()),
        patch(
            "app.main.cache_store.reconcile_orphan_references_async", new=AsyncMock()
        ),
        patch("app.main.llama_server_supervisor.is_installed", return_value=False),
        patch("app.main.llama_server_supervisor.is_running", return_value=False),
        patch(
            "app.main.model_store.scan_all_roots_async", new=AsyncMock(return_value=[])
        ),
        patch("app.main.workflow_runs.shutdown", new=workflow_stop),
        patch("app.main.creative_tasks.shutdown", new=creative_stop),
    ):
        try:
            try:
                async with lifespan(app):
                    await manager.get_connection()
                    if failure == "consumer":
                        raise RuntimeError("fixture consumer")
            except RuntimeError:
                if failure is None:
                    raise
            assert manager._conn is None
            workflow_stop.assert_awaited_once()
            creative_stop.assert_awaited_once()
        finally:
            await manager.close()
