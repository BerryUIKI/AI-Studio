"""Durable project and canvas storage management."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.project import Project, ProjectCreate, ProjectUpdate
from app.storage.db import DatabaseManager, db_manager


class ProjectStore:
    """Provides asynchronous CRUD for user projects and canvases."""

    def __init__(self, manager: DatabaseManager = db_manager) -> None:
        self.manager = manager

    async def create_project(self, data: ProjectCreate) -> Project:
        conn = await self.manager.get_connection()
        proj_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        version = data.version or 1
        canvas = data.canvas if data.canvas is not None else {
            "version": version,
            "nodes": [],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }
        if isinstance(canvas, dict) and "version" not in canvas:
            canvas["version"] = version

        await conn.execute(
            """
            INSERT INTO projects (id, name, version, canvas_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (proj_id, data.name, version, json.dumps(canvas), now, now),
        )
        await conn.commit()
        return Project(
            id=proj_id,
            name=data.name,
            version=version,
            canvas=canvas,
            created_at=now,
            updated_at=now,
        )

    async def get_project(self, project_id: str) -> Optional[Project]:
        conn = await self.manager.get_connection()
        async with conn.execute(
            "SELECT id, name, version, canvas_json, created_at, updated_at FROM projects WHERE id = ?",
            (project_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            canvas_dict = json.loads(row["canvas_json"])
            version_val = row["version"] if "version" in row.keys() and row["version"] is not None else 1
            if isinstance(canvas_dict, dict) and "version" not in canvas_dict:
                canvas_dict["version"] = version_val
            return Project(
                id=row["id"],
                name=row["name"],
                version=version_val,
                canvas=canvas_dict,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    async def list_projects(self) -> List[Project]:
        conn = await self.manager.get_connection()
        async with conn.execute(
            "SELECT id, name, version, canvas_json, created_at, updated_at FROM projects ORDER BY updated_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                canvas_dict = json.loads(row["canvas_json"])
                version_val = row["version"] if "version" in row.keys() and row["version"] is not None else 1
                if isinstance(canvas_dict, dict) and "version" not in canvas_dict:
                    canvas_dict["version"] = version_val
                result.append(
                    Project(
                        id=row["id"],
                        name=row["name"],
                        version=version_val,
                        canvas=canvas_dict,
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                )
            return result

    async def update_project(self, project_id: str, update: ProjectUpdate) -> Optional[Project]:
        conn = await self.manager.get_connection()
        existing = await self.get_project(project_id)
        if not existing:
            return None

        new_name = update.name if update.name is not None else existing.name
        new_version = update.version if update.version is not None else existing.version
        new_canvas = update.canvas if update.canvas is not None else existing.canvas
        if isinstance(new_canvas, dict) and "version" not in new_canvas:
            new_canvas["version"] = new_version
        now = datetime.now(timezone.utc).isoformat()

        await conn.execute(
            """
            UPDATE projects
            SET name = ?, version = ?, canvas_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_name, new_version, json.dumps(new_canvas), now, project_id),
        )
        await conn.commit()

        return Project(
            id=project_id,
            name=new_name,
            version=new_version,
            canvas=new_canvas,
            created_at=existing.created_at,
            updated_at=now,
        )

    async def delete_project(self, project_id: str) -> bool:
        conn = await self.manager.get_connection()
        cursor = await conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await conn.commit()
        return cursor.rowcount > 0


project_store = ProjectStore()
