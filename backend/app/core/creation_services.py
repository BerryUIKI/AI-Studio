"""Typed composition boundary shared by creative HTTP entry points."""

from dataclasses import dataclass

from app.core.creative_tasks import CreativeTaskService
from app.runners.creative_runner import CreativeRunner
from app.storage.task_store import TaskStore


@dataclass(frozen=True)
class CreationServices:
    tasks: TaskStore
    scheduler: CreativeTaskService
    runner: CreativeRunner
