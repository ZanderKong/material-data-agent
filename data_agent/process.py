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
from .model_adapters.base import TaskContext, ModelResult
from .model_adapters.router import route_model_calls, get_fallback_chain
from .model_adapters.profiles import load_profiles, resolve_profile_env, is_profile_available
from .model_adapters.stubs import STUB_REGISTRY
from .model_adapters.openai_compatible import call_openai_compatible
from .model_adapters.redaction import sanitize_and_redact_model_result
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


def _get_profiles() -> dict:
    return load_profiles()


def _call_model_roles(
    task_dir: Path,
    conn,
    data_type: DataType,
    subtype: str,
    l1_obj: DataObject,
    run_short: str,
    model_mode: str,
    image_path: str = "",
) -> tuple[list[DataObject], list[ProcessingRun], list[QualityFlag]]:
    derived_objects: list[DataObject] = []
    model_runs: list[ProcessingRun] = []
    flags: list[QualityFlag] = []
    tid = l1_obj.task_id

    file_path = task_dir / "raw" / Path(l1_obj.data_schema.get("filename", ""))
    has_image = data_type in (DataType.CHART_IMAGE_INPUT, DataType.VISUAL_IMAGE)
    has_text = data_type == DataType.DESCRIPTIVE_OBSERVATION_TEXT

    ctx = TaskContext(
        task_id=tid,
        data_type=data_type.value,
        subtype=subtype,
        file_ext=file_path.suffix if file_path.exists() else "",
        file_size_bytes=file_path.stat().st_size if file_path.exists() else 0,
        has_image=has_image,
        has_text=has_text,
        model_mode=model_mode,
    )

    roles = route_model_calls(ctx)
    if not roles:
        return derived_objects, model_runs, flags

    profiles = _get_profiles()
    image_path_arg = str(file_path) if has_image and file_path.exists() else ""

    for role in roles:
        result = _execute_model_role(role, profiles, ctx, image_path_arg)
        if result is None:
            continue

        prefix = f"run_{run_short}__" if run_short else ""
        output_name = f"{prefix}model_result_{role}.json"
        output_path = task_dir / "derived" / output_name

        result_dict = result.model_dump(mode="json")
        result_dict = sanitize_and_redact_model_result(result_dict)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)

        model_derived = DataObject(
            task_id=tid,
            data_type=DataType.MODEL_RESULT,
            subtype=f"model_result_{role}",
            confidence=result.confidence,
            derived_from=[l1_obj.object_id],
            lifecycle=LifecycleLevel.L2,
            data_schema={
                "output_file": output_name,
                "role": role,
                "provider": result.provider,
                "model": result.model,
                "mode": result.mode,
                "fallback_used": result.fallback_used,
                "prompt_version": result.prompt_version,
            },
        )
        derived_objects.append(model_derived)

        model_run = ProcessingRun(
            task_id=tid,
            tool_name=f"model:{role}",
            tool_version="0.1.0",
            input_data_ids=[l1_obj.object_id],
            output_data_ids=[model_derived.object_id],
            parameters={
                "provider": result.provider,
                "model": result.model,
                "role": role,
                "mode": result.mode,
                "fallback_used": result.fallback_used,
            },
            status=ProcessingStatus.SUCCEEDED if result.success else ProcessingStatus.FAILED,
            warnings=result.warnings,
            errors=[result.error] if result.error else [],
        )
        model_runs.append(model_run)

        if result.fallback_used:
            flags.append(QualityFlag(
                task_id=tid,
                severity="warning",
                target_type="model_result",
                target_id=model_derived.object_id,
                message=f"fallback_used: Model role '{role}' used fallback from '{result.fallback_from}'.",
                evidence=str(result.warnings),
                requires_review=False,
                confidence=result.confidence,
            ))
        if not result.success:
            flags.append(QualityFlag(
                task_id=tid,
                severity="warning",
                target_type="model_result",
                target_id=model_derived.object_id,
                message=f"model_unavailable: {role} returned error: {result.error}",
                evidence=str(result.error),
                requires_review=False,
                confidence=0.0,
            ))
        if result.confidence < 0.5:
            flags.append(QualityFlag(
                task_id=tid,
                severity="info",
                target_type="model_result",
                target_id=model_derived.object_id,
                message=f"low_confidence_model_output: {role} confidence={result.confidence}.",
                evidence=str(result.output_json),
                requires_review=True,
                confidence=result.confidence,
            ))
        for w in result.warnings:
            if w == "model_output_excluded_from_conclusion":
                flags.append(QualityFlag(
                    task_id=tid,
                    severity="warning",
                    target_type="model_result",
                    target_id=model_derived.object_id,
                    message="model_output_excluded_from_conclusion: Forbidden output keys removed.",
                    requires_review=True,
                    confidence=0.5,
                ))

    return derived_objects, model_runs, flags


def _execute_model_role(
    role: str,
    profiles: dict,
    ctx: TaskContext,
    image_path: str = "",
) -> ModelResult | None:
    if ctx.model_mode == "local":
        stub_func = STUB_REGISTRY.get(role) or STUB_REGISTRY.get("local_stub")
        if stub_func:
            return stub_func(ctx)
        return None

    if ctx.model_mode == "cloud":
        if role in profiles and is_profile_available(profiles[role]):
            env = resolve_profile_env(profiles[role])
            return call_openai_compatible(profiles[role], ctx, env, image_path)
        result = ModelResult(
            success=False,
            role=role,
            provider="none",
            mode="cloud",
            error=f"Model profile '{role}' not configured or unavailable.",
            fallback_used=False,
        )
        return result

    if ctx.model_mode == "auto":
        if role in profiles and is_profile_available(profiles[role]):
            env = resolve_profile_env(profiles[role])
            result = call_openai_compatible(profiles[role], ctx, env, image_path)
            if result.success:
                return result
            fallback_chain = get_fallback_chain(role, profiles)
            fallback_result = result
            fallback_result.fallback_used = True
            fallback_result.fallback_from = role
            for fallback_role in fallback_chain:
                stub_func = STUB_REGISTRY.get(fallback_role)
                if stub_func:
                    fb = stub_func(ctx)
                    fb.fallback_from = role
                    fb.fallback_used = True
                    return fb
            return fallback_result
        fallback_chain = get_fallback_chain(role, profiles)
        for fallback_role in fallback_chain:
            stub_func = STUB_REGISTRY.get(fallback_role)
            if stub_func:
                result = stub_func(ctx)
                result.fallback_from = role
                result.fallback_used = True
                return result
        return None

    return None


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
            elif data_type in (DataType.VISUAL_IMAGE, DataType.DESCRIPTIVE_OBSERVATION_TEXT):
                run, derived_objects, flags = DISPATCH[data_type](l1_obj, task_dir, run_id, run_short, model_mode=model_mode)
            else:
                run, derived_objects, flags = DISPATCH[data_type](l1_obj, task_dir, run_id, run_short)

            image_path = str(file_path) if data_type in (DataType.CHART_IMAGE_INPUT, DataType.VISUAL_IMAGE) else ""
            model_derived, model_runs, model_flags = _call_model_roles(
                task_dir, conn, data_type, subtype, l1_obj, run_short, model_mode, image_path
            )

            all_old_l2: list[dict] = list(old_l2_info)
            for md in model_derived:
                old_model_info = _get_existing_l2_by_subtype(conn, tid, md.subtype)
                all_old_l2.extend(old_model_info)

            insert_processing_run(conn, run)
            append_processing_run(task_dir, run)

            all_derived = list(derived_objects) + list(model_derived)
            all_flags = list(flags) + list(model_flags)

            run_id_by_output_id: dict[str, str] = {}
            for oid in run.output_data_ids:
                run_id_by_output_id[oid] = run.run_id
            for mr in model_runs:
                for oid in mr.output_data_ids:
                    run_id_by_output_id[oid] = mr.run_id

            for derived in all_derived:
                insert_data_object(conn, derived)
                rel_run_id = run_id_by_output_id.get(derived.object_id, run.run_id)
                rel = Relationship(
                    task_id=tid,
                    rel_type=RelationshipType.DERIVED_FROM,
                    source_id=l1_obj.object_id,
                    target_id=derived.object_id,
                    metadata={"run_id": rel_run_id},
                )
                insert_relationship(conn, rel)
                append_relationship(task_dir, rel)

            for mr in model_runs:
                insert_processing_run(conn, mr)
                append_processing_run(task_dir, mr)

            if all_old_l2:
                _write_replacement_relationships(conn, task_dir, tid, all_derived, all_old_l2)

            for flag in all_flags:
                insert_quality_flag(conn, flag)
                append_quality_flag(task_dir, flag)

            manifest.run_ids = manifest.run_ids or []
            manifest.run_ids.append(run.run_id)
            for mr in model_runs:
                manifest.run_ids.append(mr.run_id)
            manifest.object_ids = manifest.object_ids or []
            if l1_obj.object_id not in manifest.object_ids:
                manifest.object_ids.append(l1_obj.object_id)
            for d in all_derived:
                manifest.object_ids.append(d.object_id)
            for f in all_flags:
                manifest.flag_ids = manifest.flag_ids or []
                manifest.flag_ids.append(f.flag_id)

            for d in all_derived:
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
            if old_info.get("subtype") != new_obj.subtype:
                continue
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
