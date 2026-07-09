"""Ingest: register files from inbox as tasks with L0 -> L1 lifecycle."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from .classify import classify_file
from .config import get_tasks_dir, get_next_task_id
from .db import insert_file, insert_data_object, insert_task, insert_relationship
from .package import create_task_dir, write_manifest, append_relationship
from .schemas import (
    DataObject,
    FileRecord,
    LifecycleLevel,
    Relationship,
    RelationshipType,
    TaskManifest,
)


def _checksum(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def ingest_inbox(inbox_dir: Path, workspace: Path, conn) -> list[str]:
    tasks_dir = get_tasks_dir(workspace)
    task_ids = []
    inbox = inbox_dir if inbox_dir.is_absolute() else inbox_dir.resolve()
    for file_path in sorted(inbox.iterdir()):
        if file_path.is_file() and not file_path.name.startswith("."):
            tid = _ingest_single_file(file_path, tasks_dir, conn)
            task_ids.append(tid)
    return task_ids


def _ingest_single_file(file_path: Path, tasks_dir: Path, conn) -> str:
    task_id = get_next_task_id(tasks_dir)
    task_dir = tasks_dir / task_id
    create_task_dir(task_dir)

    checksum = _checksum(file_path)
    size = file_path.stat().st_size
    raw_dest = task_dir / "raw" / file_path.name

    file_record_l0 = FileRecord(
        task_id=task_id,
        original_name=file_path.name,
        stored_path=str(file_path),
        checksum_sha256=checksum,
        size_bytes=size,
        mime_type=file_path.suffix.lower(),
        lifecycle=LifecycleLevel.L0,
    )
    insert_file(conn, file_record_l0)

    shutil.copy2(file_path, raw_dest)

    file_record_l1 = FileRecord(
        task_id=task_id,
        original_name=file_path.name,
        stored_path=str(raw_dest),
        checksum_sha256=checksum,
        size_bytes=size,
        mime_type=file_path.suffix.lower(),
        lifecycle=LifecycleLevel.L1,
    )
    insert_file(conn, file_record_l1)

    rel_l0_l1 = Relationship(
        task_id=task_id,
        rel_type=RelationshipType.DERIVED_FROM,
        source_id=file_record_l0.file_id,
        target_id=file_record_l1.file_id,
        metadata={"transition": "L0_to_L1"},
    )
    insert_relationship(conn, rel_l0_l1)
    append_relationship(task_dir, rel_l0_l1)

    data_type, subtype, conf, schema = classify_file(file_path)
    data_obj = DataObject(
        task_id=task_id,
        data_type=data_type,
        subtype=subtype,
        confidence=conf,
        file_ids=[file_record_l1.file_id],
        data_schema=schema,
        lifecycle=LifecycleLevel.L1,
    )
    insert_data_object(conn, data_obj)

    manifest = TaskManifest(
        task_id=task_id,
        status="ingested",
        input_files=[file_path.name],
        object_ids=[data_obj.object_id],
        run_ids=[],
        flag_ids=[],
        review_ids=[],
        derived_files=[],
    )
    write_manifest(task_dir, manifest)

    insert_task(conn, task_id, json.dumps(manifest.model_dump(), ensure_ascii=False))

    return task_id
