"""Evidence package read and write for task directories."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .schemas import (
    TaskManifest,
    ProcessingRun,
    QualityFlag,
    Relationship,
    ReviewRecord,
)


def create_task_dir(task_dir: Path) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "raw").mkdir(exist_ok=True)
    (task_dir / "derived").mkdir(exist_ok=True)
    (task_dir / "logs").mkdir(exist_ok=True)
    (task_dir / "reviews").mkdir(exist_ok=True)


def write_manifest(task_dir: Path, manifest: TaskManifest) -> None:
    manifest.updated_at = datetime.now(timezone.utc).isoformat()
    path = task_dir / "manifest.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest.model_dump(), f, ensure_ascii=False, indent=2)


def load_manifest(task_dir: Path) -> Optional[TaskManifest]:
    path = task_dir / "manifest.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TaskManifest(**data)


def append_processing_run(task_dir: Path, run: ProcessingRun) -> None:
    path = task_dir / "logs" / "processing_runs.json"
    runs = _read_json_list(path)
    runs.append(run.model_dump())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(runs, f, ensure_ascii=False, indent=2)


def append_quality_flag(task_dir: Path, flag: QualityFlag) -> None:
    path = task_dir / "logs" / "quality_flags.json"
    flags = _read_json_list(path)
    flags.append(flag.model_dump())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(flags, f, ensure_ascii=False, indent=2)


def append_relationship(task_dir: Path, rel: Relationship) -> None:
    path = task_dir / "logs" / "relationships.json"
    rels = _read_json_list(path)
    rels.append(rel.model_dump())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rels, f, ensure_ascii=False, indent=2)


def append_review_record(task_dir: Path, review: ReviewRecord) -> None:
    path = task_dir / "reviews" / "review_records.json"
    reviews = _read_json_list(path)
    reviews.append(review.model_dump())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)


def get_processing_runs(task_dir: Path) -> list[dict]:
    path = task_dir / "logs" / "processing_runs.json"
    return _read_json_list(path)


def get_quality_flags(task_dir: Path) -> list[dict]:
    path = task_dir / "logs" / "quality_flags.json"
    return _read_json_list(path)


def get_relationships(task_dir: Path) -> list[dict]:
    path = task_dir / "logs" / "relationships.json"
    return _read_json_list(path)


def get_review_records(task_dir: Path) -> list[dict]:
    path = task_dir / "reviews" / "review_records.json"
    return _read_json_list(path)


def _read_json_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, FileNotFoundError):
        return []
