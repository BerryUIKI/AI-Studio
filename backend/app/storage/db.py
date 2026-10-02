"""SQLite database connection and schema management."""

import os
import sys
from pathlib import Path
from typing import Optional
import aiosqlite


def get_default_data_dir() -> Path:
    """Return root application data directory for database and managed assets."""
    custom_dir = os.environ.get("BERRY_DATA_DIR") or os.environ.get("AI_WORKFLOW_DATA_DIR")
    if custom_dir:
        return Path(custom_dir).resolve()

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(local_app_data) / "BerryAIStudio"

    return Path.home() / ".berry-ai"


class DatabaseManager:
    """Manages SQLite connection lifecycle and schema migrations."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    def get_effective_db_path(self) -> Path | str:
        if self.db_path:
            return self.db_path
        data_dir = get_default_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "berry.db"

    async def get_connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            path = self.get_effective_db_path()
            if isinstance(path, Path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path_str = str(path)
            else:
                path_str = str(path)
            self._conn = await aiosqlite.connect(path_str)
            self._conn.row_factory = aiosqlite.Row
            await self._init_schema(self._conn)
        return self._conn

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _init_schema(self, conn: aiosqlite.Connection) -> None:
        """Create versioned tables if not existing."""
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA foreign_keys=ON;")

        await conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                canvas_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                media_type TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                byte_size INTEGER DEFAULT 0,
                width INTEGER,
                height INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_assets_hash ON assets(content_hash);
            CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);

            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                target_node_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                status TEXT NOT NULL,
                params_json TEXT,
                inputs_json TEXT,
                outputs_json TEXT,
                error_msg TEXT,
                created_at TEXT NOT NULL,
                finished_at TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);

            CREATE TABLE IF NOT EXISTS cache_entries (
                node_hash TEXT PRIMARY KEY,
                output_json TEXT NOT NULL,
                asset_ids_json TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        await conn.commit()


# Global database manager instance
db_manager = DatabaseManager()
