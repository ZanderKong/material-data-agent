"""Workspace configuration management."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_WORKSPACE = "workspace"
DEFAULT_DB_NAME = "agent.sqlite"
DEFAULT_TASKS_DIR = "tasks"


def resolve_workspace(workspace_path: str | None = None) -> Path:
    if workspace_path:
        p = Path(workspace_path)
    else:
        p = Path(DEFAULT_WORKSPACE)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_db_path(workspace: Path) -> Path:
    return workspace / DEFAULT_DB_NAME


def get_tasks_dir(workspace: Path) -> Path:
    tasks_dir = workspace / DEFAULT_TASKS_DIR
    tasks_dir.mkdir(parents=True, exist_ok=True)
    return tasks_dir


def get_next_task_id(tasks_dir: Path) -> str:
    existing = sorted(
        [int(d.name.split("_")[1]) for d in tasks_dir.iterdir() if d.is_dir() and d.name.startswith("task_")]
    )
    next_id = existing[-1] + 1 if existing else 1
    return f"task_{next_id:04d}"
