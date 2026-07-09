"""SQLite registry system for the data agent."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from .config import get_db_path
from .schemas import (
    FileRecord,
    DataObject,
    ProcessingRun,
    QualityFlag,
    ReviewRecord,
    Relationship,
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS files (
    file_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    original_name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mime_type TEXT DEFAULT '',
    lifecycle TEXT NOT NULL DEFAULT 'L0',
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_objects (
    object_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    data_type TEXT NOT NULL,
    subtype TEXT DEFAULT '',
    confidence REAL DEFAULT 1.0,
    file_ids TEXT DEFAULT '[]',
    derived_from TEXT DEFAULT '[]',
    data_schema TEXT DEFAULT '{}',
    lifecycle TEXT NOT NULL DEFAULT 'L1',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processing_runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    tool_name TEXT DEFAULT 'data_agent',
    tool_version TEXT DEFAULT '0.1.0',
    input_data_ids TEXT DEFAULT '[]',
    output_data_ids TEXT DEFAULT '[]',
    parameters TEXT DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    warnings TEXT DEFAULT '[]',
    errors TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quality_flags (
    flag_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    target_type TEXT DEFAULT '',
    target_id TEXT DEFAULT '',
    message TEXT DEFAULT '',
    evidence TEXT DEFAULT '',
    requires_review INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    reviewer TEXT DEFAULT '',
    action TEXT NOT NULL,
    target_type TEXT DEFAULT '',
    target_id TEXT DEFAULT '',
    before_value TEXT DEFAULT '',
    after_value TEXT DEFAULT '',
    comment TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relationships (
    rel_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    manifest_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_files_task ON files(task_id);
CREATE INDEX IF NOT EXISTS idx_data_objects_task ON data_objects(task_id);
CREATE INDEX IF NOT EXISTS idx_processing_runs_task ON processing_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_quality_flags_task ON quality_flags(task_id);
CREATE INDEX IF NOT EXISTS idx_reviews_task ON reviews(task_id);
CREATE INDEX IF NOT EXISTS idx_relationships_task ON relationships(task_id);
"""


def init_db(workspace: Path) -> sqlite3.Connection:
    db_path = get_db_path(workspace)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def get_conn(workspace: Path) -> sqlite3.Connection:
    db_path = get_db_path(workspace)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _to_json(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _from_json(s: str) -> object:
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return s


def insert_file(conn: sqlite3.Connection, record: FileRecord) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO files
           (file_id, task_id, original_name, stored_path, checksum_sha256,
            size_bytes, mime_type, lifecycle, registered_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.file_id,
            record.task_id,
            record.original_name,
            record.stored_path,
            record.checksum_sha256,
            record.size_bytes,
            record.mime_type,
            record.lifecycle.value,
            record.registered_at,
        ),
    )
    conn.commit()


def insert_data_object(conn: sqlite3.Connection, obj: DataObject) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO data_objects
           (object_id, task_id, data_type, subtype, confidence, file_ids,
            derived_from, data_schema, lifecycle, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            obj.object_id,
            obj.task_id,
            obj.data_type.value,
            obj.subtype,
            obj.confidence,
            json.dumps(obj.file_ids, ensure_ascii=False),
            json.dumps(obj.derived_from, ensure_ascii=False),
            json.dumps(obj.data_schema, ensure_ascii=False),
            obj.lifecycle.value,
            obj.created_at,
        ),
    )
    conn.commit()


def insert_processing_run(conn: sqlite3.Connection, run: ProcessingRun) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO processing_runs
           (run_id, task_id, tool_name, tool_version, input_data_ids,
            output_data_ids, parameters, status, warnings, errors, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run.run_id,
            run.task_id,
            run.tool_name,
            run.tool_version,
            json.dumps(run.input_data_ids, ensure_ascii=False),
            json.dumps(run.output_data_ids, ensure_ascii=False),
            json.dumps(run.parameters, ensure_ascii=False),
            run.status.value,
            json.dumps(run.warnings, ensure_ascii=False),
            json.dumps(run.errors, ensure_ascii=False),
            run.created_at,
        ),
    )
    conn.commit()


def insert_quality_flag(conn: sqlite3.Connection, flag: QualityFlag) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO quality_flags
           (flag_id, task_id, severity, target_type, target_id, message,
            evidence, requires_review, confidence, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            flag.flag_id,
            flag.task_id,
            flag.severity,
            flag.target_type,
            flag.target_id,
            flag.message,
            flag.evidence,
            1 if flag.requires_review else 0,
            flag.confidence,
            flag.created_at,
        ),
    )
    conn.commit()


def insert_relationship(conn: sqlite3.Connection, rel: Relationship) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO relationships
           (rel_id, task_id, rel_type, source_id, target_id, metadata, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            rel.rel_id,
            rel.task_id,
            rel.rel_type.value,
            rel.source_id,
            rel.target_id,
            json.dumps(rel.metadata, ensure_ascii=False),
            rel.created_at,
        ),
    )
    conn.commit()


def insert_review(conn: sqlite3.Connection, review: ReviewRecord) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO reviews
           (review_id, task_id, reviewer, action, target_type, target_id,
            before_value, after_value, comment, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            review.review_id,
            review.task_id,
            review.reviewer,
            review.action.value,
            review.target_type,
            review.target_id,
            review.before_value,
            review.after_value,
            review.comment,
            review.created_at,
        ),
    )
    conn.commit()


def insert_task(conn: sqlite3.Connection, task_id: str, manifest_json: str = "{}") -> None:
    from datetime import datetime, timezone

    conn.execute(
        "INSERT OR REPLACE INTO tasks (task_id, manifest_json, created_at) VALUES (?, ?, ?)",
        (task_id, manifest_json, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_task(conn: sqlite3.Connection, task_id: str) -> Optional[sqlite3.Row]:
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return row


def get_files_by_task(conn: sqlite3.Connection, task_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM files WHERE task_id = ?", (task_id,)).fetchall()


def get_data_objects_by_task(conn: sqlite3.Connection, task_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM data_objects WHERE task_id = ?", (task_id,)).fetchall()


def get_processing_runs_by_task(conn: sqlite3.Connection, task_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM processing_runs WHERE task_id = ?", (task_id,)).fetchall()


def get_quality_flags_by_task(conn: sqlite3.Connection, task_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM quality_flags WHERE task_id = ?", (task_id,)).fetchall()


def get_relationships_by_task(conn: sqlite3.Connection, task_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM relationships WHERE task_id = ?", (task_id,)).fetchall()


def get_reviews_by_task(conn: sqlite3.Connection, task_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,)).fetchall()
