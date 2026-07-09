"""Unified processing orchestration: dispatch to appropriate processor by data type."""
from __future__ import annotations

import json
from pathlib import Path

from .classify import classify_file
from .db import get_conn, insert_data_object, insert_processing_run, insert_quality_flag, insert_relationship
from .package import (
    write_manifest,
    load_manifest,
    append_processing_run,
    append_quality_flag,
    append_relationship,
    get_processing_runs,
)
from .schemas import (
    DataObject,
    DataType,
    LifecycleLevel,
    ProcessingRun,
    ProcessingStatus,
    QualityFlag,
    Relationship,
    RelationshipType,
    TaskManifest,
)
from .processors.numeric import process_numeric
from .processors.spectral import process_spectral
from .processors.chart_image import process_chart_image
from .processors.observation_text import process_observation_text
from .processors.visual_image import process_visual_image
from .processors.metadata import process_metadata
from . import reports


DISPATCH = {
    DataType.RAW_NUMERIC: process_numeric,
    DataType.RAW_SPECTRAL: process_spectral,
    DataType.CHART_IMAGE_INPUT: process_chart_image,
    DataType.DESCRIPTIVE_OBSERVATION_TEXT: process_observation_text,
    DataType.VISUAL_IMAGE: process_visual_image,
    DataType.SAMPLE_METADATA: process_metadata,
}


def process_all_tasks(workspace: Path, model_mode: str = "local") -> int:
    tasks_dir = workspace / "tasks"
    if not tasks_dir.exists():
        return 0

    conn = get_conn(workspace)
    count = 0
    for task_dir in sorted(tasks_dir.iterdir()):
        if task_dir.is_dir() and task_dir.name.startswith("task_"):
            try:
                _process_task(task_dir, conn, model_mode)
                count += 1
            except Exception as e:
                print(f"  ERROR processing {task_dir.name}: {e}")
    conn.close()
    return count


def process_single_task(workspace: Path, task_id: str, model_mode: str = "local") -> bool:
    task_dir = workspace / "tasks" / task_id
    if not task_dir.exists():
        print(f"Task {task_id} not found at {task_dir}")
        return False

    conn = get_conn(workspace)
    try:
        _process_task(task_dir, conn, model_mode)
        return True
    except Exception as e:
        print(f"  ERROR processing {task_id}: {e}")
        return False
    finally:
        conn.close()


def _find_or_create_l1_obj(conn, tid: str, task_dir: Path, data_type: DataType, subtype: str, file_path: Path) -> DataObject | None:
    rows = conn.execute(
        "SELECT * FROM data_objects WHERE task_id = ? AND data_type = ?",
        (tid, data_type.value),
    ).fetchall()

    filename = file_path.name
    for row in rows:
        data_schema = json.loads(row["data_schema"]) if row["data_schema"] else {}
        if data_schema.get("filename") == filename:
            return DataObject(
                object_id=row["object_id"],
                task_id=row["task_id"],
                data_type=DataType(row["data_type"]),
                subtype=row["subtype"],
                confidence=row["confidence"],
                file_ids=json.loads(row["file_ids"]) if row["file_ids"] else [],
                derived_from=json.loads(row["derived_from"]) if row["derived_from"] else [],
                data_schema=data_schema,
                lifecycle=LifecycleLevel(row["lifecycle"]),
                created_at=row["created_at"],
            )

    data_type_r, subtype_r, conf, schema = classify_file(file_path)
    obj = DataObject(
        task_id=tid,
        data_type=data_type_r,
        subtype=subtype_r,
        confidence=conf,
        file_ids=[],
        data_schema=schema,
        lifecycle=LifecycleLevel.L1,
    )
    insert_data_object(conn, obj)
    return obj


def _get_l2_subtype(data_type: DataType, subtype: str) -> str:
    if data_type == DataType.RAW_NUMERIC:
        return "thickness_summary" if subtype == "thickness" else "resistance_summary"
    if data_type == DataType.RAW_SPECTRAL:
        return "ftir_peaks" if subtype == "FTIR" else "uvvis_peaks"
    if data_type == DataType.CHART_IMAGE_INPUT:
        return "chart_metadata"
    if data_type == DataType.DESCRIPTIVE_OBSERVATION_TEXT:
        return "observation_analysis"
    if data_type == DataType.VISUAL_IMAGE:
        return "visual_metadata"
    if data_type == DataType.SAMPLE_METADATA:
        return "metadata_index"
    return subtype


def _process_task(task_dir: Path, conn, model_mode: str) -> None:
    manifest = load_manifest(task_dir)
    if not manifest:
        return

    tid = task_dir.name

    raw_dir = task_dir / "raw"
    for file_path in sorted(raw_dir.iterdir()):
        if file_path.is_file() and not file_path.name.startswith("."):
            data_type, subtype, conf, schema = classify_file(file_path)

            if data_type not in DISPATCH or DISPATCH[data_type] is None:
                continue

            run_id = ProcessingRun(task_id=tid).run_id
            run_short = run_id[:8]

            l1_obj = _find_or_create_l1_obj(conn, tid, task_dir, data_type, subtype, file_path)
            if l1_obj is None:
                continue

            l2_subtype = _get_l2_subtype(data_type, subtype)
            old_l2_info = _get_existing_l2_by_subtype(conn, tid, l2_subtype)

            if data_type == DataType.CHART_IMAGE_INPUT:
                run, derived_objects, flags = DISPATCH[data_type](l1_obj, task_dir, run_id, run_short, model_mode=model_mode)
            else:
                run, derived_objects, flags = DISPATCH[data_type](l1_obj, task_dir, run_id, run_short)

            insert_processing_run(conn, run)
            append_processing_run(task_dir, run)

            for derived in derived_objects:
                insert_data_object(conn, derived)
                rel = Relationship(
                    task_id=tid,
                    rel_type=RelationshipType.DERIVED_FROM,
                    source_id=l1_obj.object_id,
                    target_id=derived.object_id,
                    metadata={"run_id": run.run_id},
                )
                insert_relationship(conn, rel)
                append_relationship(task_dir, rel)

            if old_l2_info:
                _write_replacement_relationships(conn, task_dir, tid, derived_objects, old_l2_info)

            for flag in flags:
                insert_quality_flag(conn, flag)
                append_quality_flag(task_dir, flag)

            manifest.run_ids = manifest.run_ids or []
            manifest.run_ids.append(run.run_id)
            manifest.object_ids = manifest.object_ids or []
            if l1_obj.object_id not in manifest.object_ids:
                manifest.object_ids.append(l1_obj.object_id)
            for d in derived_objects:
                manifest.object_ids.append(d.object_id)
            for f in flags:
                manifest.flag_ids = manifest.flag_ids or []
                manifest.flag_ids.append(f.flag_id)

            for d in derived_objects:
                output_file = d.data_schema.get("output_file", "")
                if output_file:
                    manifest.derived_files.append(f"derived/{output_file}")

    manifest.status = "processed"
    write_manifest(task_dir, manifest)

    reports.generate_processing_report(task_dir)


def _get_existing_l2_ids(conn, tid: str) -> list[str]:
    rows = conn.execute(
        "SELECT object_id FROM data_objects WHERE task_id = ? AND lifecycle = 'L2'",
        (tid,),
    ).fetchall()
    return [r["object_id"] for r in rows]


def _get_existing_l2_by_subtype(conn, tid: str, subtype: str) -> list[dict]:
    rows = conn.execute(
        "SELECT object_id, subtype, lifecycle FROM data_objects WHERE task_id = ? AND lifecycle = 'L2' AND subtype = ?",
        (tid, subtype),
    ).fetchall()
    return [dict(r) for r in rows]


def _write_replacement_relationships(conn, task_dir: Path, tid: str, new_l2_objects: list[DataObject], old_l2_info: list[dict]) -> None:
    for new_obj in new_l2_objects:
        for old_info in old_l2_info:
            old_id = old_info["object_id"]
            rel_replaces = Relationship(
                task_id=tid,
                rel_type=RelationshipType.REPLACES,
                source_id=new_obj.object_id,
                target_id=old_id,
                metadata={"note": "new_run_supersedes_previous"},
            )
            insert_relationship(conn, rel_replaces)
            append_relationship(task_dir, rel_replaces)

            rel_replaced = Relationship(
                task_id=tid,
                rel_type=RelationshipType.REPLACED_BY,
                source_id=old_id,
                target_id=new_obj.object_id,
                metadata={"note": "previous_run_superseded_by_new"},
            )
            insert_relationship(conn, rel_replaced)
            append_relationship(task_dir, rel_replaced)
