"""Evidence package validation: strict path safety, manifest ID checks, relationship integrity, checksum, atomic reports."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from data_agent.config import get_db_path
from data_agent.db import (
    get_files_by_task,
    get_data_objects_by_task,
    get_conn,
)
from data_agent.package import load_manifest
from data_agent.ui.security import safe_display_text


ValidationStatus = Literal["pass", "warn", "error"]


class ValidationCheck(BaseModel):
    name: str
    status: ValidationStatus
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    task_id: str
    status: ValidationStatus
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: list[ValidationCheck] = Field(default_factory=list)
    report_path: str = ""
    result_path: str = ""
    validated_at: str


# ---------------------------------------------------------------------------
# Strict readers
# ---------------------------------------------------------------------------

def _strict_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}: {path}")
    return data


def _strict_read_json_list(path: Path) -> list[dict[str, Any]] | None:
    """Read a JSON list file strictly.

    Returns None when file is missing. Raises ValueError for invalid JSON,
    wrong top-level type, or any item that is not a dict.
    """
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON list, got {type(data).__name__}: {path}")
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Item {i} in {path.name} is not a dict: {type(item).__name__}")
    return data


def _safe_resolve(task_dir: Path, sub_path: str) -> Path | None:
    """Resolve a relative path under a task directory safely.

    Rejects:
    - Absolute paths, even if inside task_dir.
    - Any explicit '..' component.
    - Empty sub_path when a file is required.

    Returns None when containment fails. Accepts paths under symlinked ancestors
    (e.g. macOS /tmp -> /private/tmp) by normalizing both sides.
    """
    if not sub_path or sub_path.isspace():
        return None
    candidate = Path(sub_path)
    if candidate.is_absolute():
        return None
    if ".." in candidate.parts:
        return None
    try:
        root_resolved = task_dir.resolve()
        full = (task_dir / sub_path).resolve()
        full.relative_to(root_resolved)
        return full
    except (ValueError, OSError):
        return None


def _resolve_manifest_raw(task_dir: Path, filename: str) -> Path | None:
    """Resolve a manifest.input_files entry under task_dir/raw/. Rejects symlinks."""
    if not filename or ".." in filename or Path(filename).is_absolute():
        return None
    raw_dir = task_dir / "raw"
    candidate = raw_dir / filename
    if candidate.is_symlink():
        return None
    return _safe_resolve(raw_dir, filename)


def _resolve_manifest_derived(task_dir: Path, rel_path: str) -> Path | None:
    """Resolve a manifest.derived_files entry under task_dir."""
    return _safe_resolve(task_dir, rel_path)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_data_file(td: Path, rel_path: str) -> Path | None:
    """Resolve a data_schema file path: tries derived/ first, then task_dir root."""
    fp_str = str(rel_path)
    resolved = _safe_resolve(td / "derived", fp_str)
    if resolved is not None and resolved.is_file():
        return resolved
    resolved = _safe_resolve(td, fp_str)
    if resolved is not None and resolved.is_file():
        return resolved
    return None


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class _Collector:
    def __init__(self):
        self.checks: list[ValidationCheck] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def add(self, name: str, status: ValidationStatus, message: str, details: dict[str, Any] | None = None):
        check = ValidationCheck(name=name, status=status, message=message, details=details or {})
        self.checks.append(check)
        if status == "error":
            self.errors.append(message)
        elif status == "warn":
            self.warnings.append(message)

    def overall(self) -> ValidationStatus:
        if self.errors:
            return "error"
        if self.warnings:
            return "warn"
        return "pass"


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check_structure(td: Path, c: _Collector) -> None:
    for name in ("manifest.json",):
        if not (td / name).is_file():
            c.add("manifest_missing_file", "error", f"Required file '{name}' does not exist or is not a regular file")
    for name in ("raw", "derived", "logs", "reviews"):
        p = td / name
        if p.is_dir():
            c.add(f"dir_{name}", "pass", f"Directory '{name}' exists")
        else:
            c.add(f"dir_{name}", "error", f"Required directory '{name}' is missing")


def _check_manifest_references(td: Path, manifest: dict[str, Any], c: _Collector) -> None:
    for fn in manifest.get("input_files", []) or []:
        if not fn or not isinstance(fn, str):
            c.add("manifest_input_empty_id", "error", "manifest.input_files contains empty or non-string file name")
            continue
        resolved = _resolve_manifest_raw(td, fn)
        if resolved is None:
            c.add("manifest_input_rejected", "error", f"Input file path rejected (unsafe): {fn}")
        elif not resolved.is_file():
            c.add("manifest_input_missing", "error", f"Raw file '{fn}' referenced in manifest not found")
        elif resolved.is_symlink():
            c.add("manifest_input_symlink", "error", f"Raw file '{fn}' is a symlink, not valid evidence")

    for dp in manifest.get("derived_files", []) or []:
        if not dp or not isinstance(dp, str):
            c.add("manifest_derived_empty", "error", "manifest.derived_files contains empty or non-string entry")
            continue
        resolved = _resolve_manifest_derived(td, dp)
        if resolved is None:
            c.add("manifest_derived_rejected", "error", f"Derived path rejected (unsafe): {dp}")
        elif not resolved.is_file():
            c.add("manifest_derived_missing", "error", f"Derived file '{dp}' referenced in manifest not found")


def _check_id_lists(td: Path, ws: Path, manifest: dict[str, Any], c: _Collector) -> None:
    def _validate_ids(list_name: str, log_path: Path, expected: list, id_key: str):
        if not expected:
            # Even if manifest list is empty, validate the file when present
            try:
                data = _strict_read_json_list(log_path)
            except (ValueError, json.JSONDecodeError) as ex:
                c.add(f"{list_name}_invalid_file", "error", f"Cannot read {log_path.name}: {ex}")
            return

        seen: set[str] = set()
        for eid in expected:
            if not eid or not isinstance(eid, str):
                c.add(f"manifest_{list_name}_empty", "error", f"manifest.{list_name} contains empty or non-string ID")
                continue
            if eid in seen:
                c.add(f"manifest_{list_name}_duplicate", "error", f"Duplicate ID '{eid}' in manifest.{list_name}")
                continue
            seen.add(eid)

        try:
            data = _strict_read_json_list(log_path)
        except (ValueError, json.JSONDecodeError) as ex:
            c.add(f"{list_name}_read_error", "error", f"Cannot read {log_path.name}: {ex}")
            return

        if data is None:
            c.add(f"{list_name}_missing_file", "error", f"manifest.{list_name} has IDs but {log_path.name} is missing")
            return

        existing_ids = {str(item.get(id_key, "")) for item in data}
        for eid in seen:
            if eid not in existing_ids:
                c.add(f"{list_name}_id_not_found", "error", f"ID '{eid}' in manifest.{list_name} not found in {log_path.name}")

    _validate_ids("run_ids", td / "logs" / "processing_runs.json", manifest.get("run_ids", []) or [], "run_id")
    _validate_ids("flag_ids", td / "logs" / "quality_flags.json", manifest.get("flag_ids", []) or [], "flag_id")
    _validate_ids("review_ids", td / "reviews" / "review_records.json", manifest.get("review_ids", []) or [], "review_id")

    # Object ID validation against SQLite
    obj_ids = manifest.get("object_ids", []) or []
    if obj_ids:
        seen_obj: set[str] = set()
        for oid in obj_ids:
            if not oid or not isinstance(oid, str):
                c.add("manifest_objectids_empty", "error", "manifest.object_ids contains empty or non-string ID")
            elif oid in seen_obj:
                c.add("manifest_objectids_duplicate", "error", f"Duplicate object ID: {oid}")
            seen_obj.add(oid)

        db_path = get_db_path(ws)
        if db_path.exists():
            conn = None
            try:
                conn = get_conn(ws)
                db_objects = get_data_objects_by_task(conn, td.name)
                db_ids = {str(row["object_id"]) for row in db_objects}
                for oid in seen_obj:
                    if oid not in db_ids:
                        c.add("objectid_not_in_db", "error", f"Object ID '{oid}' in manifest not found in SQLite data_objects")
            except Exception as ex:
                c.add("objectid_db_read_error", "error", f"Error reading object IDs from SQLite: {ex}")
            finally:
                if conn:
                    conn.close()
        else:
            c.add("objectid_no_db", "warn", "agent.sqlite not found; object-ID registry checks skipped")


def _check_processing_runs(td: Path, ws: Path, c: _Collector) -> None:
    try:
        runs = _strict_read_json_list(td / "logs" / "processing_runs.json")
    except (ValueError, json.JSONDecodeError) as ex:
        c.add("runs_invalid_json", "error", f"processing_runs.json invalid: {ex}")
        return
    if runs is None:
        return

    valid_statuses = {"pending", "running", "succeeded", "failed", "deprecated"}
    seen_ids: set[str] = set()
    for run in runs:
        rid = run.get("run_id", "")
        if not rid or not isinstance(rid, str):
            c.add("runs_empty_id", "error", "Processing run has empty or non-string run_id")
            continue
        if rid in seen_ids:
            c.add("runs_duplicate_id", "error", f"Duplicate run_id: {rid}")
        seen_ids.add(rid)

        tool = run.get("tool_name", "")
        status = run.get("status", "")
        has_created = run.get("created_at") or run.get("started_at")

        if not tool:
            c.add("runs_missing_tool", "error", f"Run {rid} missing tool_name")
        if not status:
            c.add("runs_missing_status", "error", f"Run {rid} missing status")
        elif status not in valid_statuses:
            c.add("runs_invalid_status", "error", f"Run {rid} has unknown status: {status}")
        if not has_created:
            c.add("runs_missing_timestamp", "error", f"Run {rid} missing created_at or started_at")

        if isinstance(tool, str) and tool.startswith("model:"):
            params = run.get("parameters", {}) or {}
            for key in ("provider", "model", "mode"):
                if key not in params:
                    c.add("runs_model_missing_key", "error", f"Run {rid} model run missing '{key}' in parameters")
                elif not params[key]:
                    if key in ("model",) and str(params.get("provider", "")).startswith("local"):
                        c.add(f"runs_model_empty_{key}", "warn", f"Run {rid} model key '{key}' is empty (local provider)")
                    else:
                        c.add(f"runs_model_empty_{key}", "error", f"Run {rid} model key '{key}' is empty")


def _check_data_objects(td: Path, ws: Path, c: _Collector) -> None:
    db_path = get_db_path(ws)
    if not db_path.exists():
        c.add("registry_db_missing", "warn", "agent.sqlite not found; registry-level object checks skipped")
        return

    conn = None
    try:
        conn = get_conn(ws)
        objs = get_data_objects_by_task(conn, td.name)
        for obj in objs:
            oid = obj["object_id"]
            lifecycle = str(obj["lifecycle"]).upper()
            data_type = obj["data_type"]
            derived_from = obj["derived_from"]
            data_schema = obj["data_schema"]

            if lifecycle == "L2":
                df = json.loads(derived_from) if isinstance(derived_from, str) else derived_from
                if isinstance(df, list) and not df:
                    c.add(f"dataobj_{oid}_no_derived_from", "error", f"L2 object {oid} has empty derived_from")

            if isinstance(data_schema, str):
                try:
                    data_schema = json.loads(data_schema)
                except json.JSONDecodeError:
                    data_schema = {}
            schema = data_schema if isinstance(data_schema, dict) else {}

            if data_type == "model_result":
                output_file = schema.get("output_file", "")
                if not output_file:
                    c.add(f"dataobj_{oid}_no_output", "error", f"Model-result object {oid} missing output_file")
                else:
                    out_path = _resolve_data_file(td, str(output_file))
                    if out_path is None or not out_path.is_file():
                        c.add(f"dataobj_{oid}_output_missing", "error", f"Model-result output file '{output_file}' not found")
                    else:
                        try:
                            with open(out_path, "r", encoding="utf-8") as f:
                                mr = json.load(f)
                            for field in ("success", "role", "provider", "mode", "output_json", "schema_version", "prompt_version"):
                                if field not in mr:
                                    c.add(f"dataobj_{oid}_mr_missing_{field}", "error", f"Model-result missing '{field}'")
                        except json.JSONDecodeError:
                            c.add(f"dataobj_{oid}_mr_invalid", "error", f"Model-result JSON invalid: {output_file}")

            for key in ("output_file", "plot_png", "reconstructed_plot", "clean_csv"):
                fp = schema.get(key, "")
                if fp:
                    resolved = _resolve_data_file(td, str(fp))
                    if resolved is None or not resolved.is_file():
                        c.add(f"dataobj_{oid}_schema_file_missing", "error", f"Data-schema file '{fp}' not found under derived/")
    except Exception as ex:
        c.add("registry_read_error", "error", f"Error reading agent.sqlite: {ex}")
    finally:
        if conn:
            conn.close()


def _check_relationships(td: Path, ws: Path, c: _Collector) -> None:
    try:
        rels = _strict_read_json_list(td / "logs" / "relationships.json")
    except (ValueError, json.JSONDecodeError) as ex:
        c.add("rels_invalid_json", "error", f"relationships.json invalid: {ex}")
        return
    if rels is None:
        return

    # Build registries from DB when available
    db_path = get_db_path(ws)
    l2_subtypes: dict[str, str] = {}     # object_id -> subtype
    run_ids: set[str] = set()
    run_tools: dict[str, str] = {}        # run_id -> tool_name
    if db_path.exists():
        conn = None
        try:
            conn = get_conn(ws)
            for obj in get_data_objects_by_task(conn, td.name):
                l2_subtypes[str(obj["object_id"])] = str(obj["subtype"])
            for row in conn.execute("SELECT run_id, tool_name FROM processing_runs WHERE task_id = ?", (td.name,)).fetchall():
                run_ids.add(str(row["run_id"]))
                run_tools[str(row["run_id"])] = str(row["tool_name"])
        except Exception:
            pass
        finally:
            if conn:
                conn.close()
    else:
        c.add("rels_no_db", "warn", "agent.sqlite not found; relationship endpoint traceability checks skipped")

    seen_rel_ids: set[str] = set()
    replaces_pairs: set[tuple[str, str]] = set()
    replaced_by_pairs: set[tuple[str, str]] = set()

    for rel in rels:
        rid = rel.get("rel_id", "")
        rtype = rel.get("rel_type", "")
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        meta = rel.get("metadata", {}) or {}

        if not rid or not isinstance(rid, str):
            c.add("rels_empty_id", "error", "Relationship has empty or non-string rel_id")
        elif rid in seen_rel_ids:
            c.add("rels_duplicate_id", "error", f"Duplicate rel_id: {rid}")
        seen_rel_ids.add(rid)

        if not rtype or not src or not tgt:
            c.add("rels_missing_field", "error", f"Relationship {rid} missing type/source/target")
            continue

        if rtype == "derived_from":
            if db_path.exists():
                if src not in l2_subtypes and tgt not in l2_subtypes:
                    c.add("rels_derived_from_unknown", "error", f"derived_from {rid} endpoints not found in registry")
            run_id = meta.get("run_id", "")
            if run_id:
                if run_id not in run_ids:
                    c.add("rels_derived_from_run_missing", "error", f"derived_from run_id '{run_id}' not found in processing_runs")
                elif tgt in l2_subtypes:
                    tool = run_tools.get(run_id, "")
                    if tool and not tool.startswith("model:") and any("model_result" in k for k in [l2_subtypes.get(tgt, "")]):
                        c.add("rels_model_result_non_model_run", "error", f"model_result derived_from {rid} run '{run_id}' is not a model:* run")

        if rtype == "replaces":
            if src == tgt:
                c.add("rels_self_replace", "error", f"replaces self-reference: {src}")
            else:
                replaces_pairs.add((src, tgt))
                if db_path.exists():
                    if src in l2_subtypes and tgt in l2_subtypes:
                        if l2_subtypes[src] != l2_subtypes[tgt]:
                            c.add("rels_replaces_subtype_mismatch", "error", f"replaces {src} (subtype={l2_subtypes[src]}) and {tgt} (subtype={l2_subtypes[tgt]}) differ")

        if rtype == "replaced_by":
            if src == tgt:
                c.add("rels_self_replaced_by", "error", f"replaced_by self-reference: {src}")
            else:
                replaced_by_pairs.add((src, tgt))

    # Reciprocal check: every (replaces new, old) must have (replaced_by old, new)
    for (new_obj, old_obj) in replaces_pairs:
        if (old_obj, new_obj) not in replaced_by_pairs:
            c.add("rels_replaces_no_reciprocal", "error", f"replaces {new_obj} -> {old_obj} missing reciprocal replaced_by")

    for (old_obj, new_obj) in replaced_by_pairs:
        if (new_obj, old_obj) not in replaces_pairs:
            c.add("rels_replaced_by_no_reciprocal", "error", f"replaced_by {old_obj} -> {new_obj} missing reciprocal replaces")

    # Check: same subtype L2 objects with multiple entries must have replacement evidence
    if db_path.exists():
        subtype_objs: dict[str, list[str]] = {}
        for oid, st in l2_subtypes.items():
            if st:
                subtype_objs.setdefault(st, []).append(oid)
        for st, oids in subtype_objs.items():
            if len(oids) > 1:
                has_replacement = any(
                    (a, b) in replaces_pairs or (b, a) in replaces_pairs
                    for i, a in enumerate(oids) for b in oids[i + 1:]
                )
                if not has_replacement:
                    c.add("rels_rerun_no_evidence", "error", f"Multiple L2 objects of subtype '{st}' without replacement evidence")


def _check_raw_checksum(td: Path, ws: Path, c: _Collector) -> None:
    db_path = get_db_path(ws)
    if not db_path.exists():
        c.add("checksum_db_missing", "warn", "agent.sqlite not found; checksum checks skipped")
        return

    raw_dir = td / "raw"
    conn = None
    try:
        conn = get_conn(ws)
        files = get_files_by_task(conn, td.name)
        for frow in files:
            lifecycle = str(frow["lifecycle"]).upper()
            if lifecycle != "L1":
                continue
            stored = frow["stored_path"]
            expected_checksum = frow["checksum_sha256"]
            if not stored or not expected_checksum:
                c.add("checksum_missing_data", "warn", f"File record {frow['file_id']} missing stored_path or checksum")
                continue

            sp = Path(stored)
            # Only check L1 files under this task's raw/
            try:
                sp.resolve().relative_to(raw_dir.resolve())
            except (ValueError, OSError):
                c.add("checksum_outside_raw", "error", f"L1 file record {frow['file_id']} stored_path '{stored}' is outside task raw/")
                continue

            if not sp.is_file():
                c.add("checksum_file_missing", "warn", f"Stored L1 file not found: {stored}")
                continue

            computed = _sha256_file(sp)
            if computed != expected_checksum:
                c.add("checksum_mismatch", "error", f"Checksum mismatch for {frow['original_name']}: expected {expected_checksum[:16]}..., got {computed[:16]}...")
    except Exception as ex:
        c.add("checksum_read_error", "error", f"Error during checksum verification: {ex}")
    finally:
        if conn:
            conn.close()


def _check_quality_flags(td: Path, c: _Collector) -> None:
    try:
        flags = _strict_read_json_list(td / "logs" / "quality_flags.json")
    except (ValueError, json.JSONDecodeError) as ex:
        c.add("flags_invalid_json", "error", f"quality_flags.json invalid: {ex}")
        return
    if flags is None:
        return

    for flag in flags:
        if flag.get("requires_review"):
            c.add("flags_requires_review", "warn", "Quality flag requires_review=True")
        msg = str(flag.get("message", ""))
        for token in ("model_unavailable", "fallback_used", "low_confidence"):
            if token in msg.lower():
                c.add("flags_risk_token", "warn", f"Quality flag contains risk token '{token}'")


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------

def _write_validation_reports(td: Path, result: ValidationResult) -> bool:
    """Write validation JSON and Markdown reports atomically.

    Returns True when both artifacts are successfully written and paths
    set on the result. Returns False on any failure and adds report_write_failed.
    """
    try:
        json_data = result.model_dump()
    except Exception:
        json_data = {}

    json_path = td / "logs" / "package_validation_result.json"
    md_path = td / "logs" / "package_validation_report.md"

    tmp_json = json_path.with_suffix(json_path.suffix + ".tmp")
    tmp_md = md_path.with_suffix(md_path.suffix + ".tmp")

    json_ok = False
    md_ok = False

    try:
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        tmp_json.replace(json_path)
        result.result_path = str(json_path.resolve())
        json_ok = True
    except OSError as ex:
        result.checks.append(ValidationCheck(name="report_write_failed", status="error", message=f"JSON report write failed: {ex}"))
        result.errors.append(f"JSON report write failed: {ex}")
        if tmp_json.exists():
            tmp_json.unlink(missing_ok=True)

    try:
        lines = [
            f"# Package Validation Report",
            f"",
            f"- **Task**: {result.task_id}",
            f"- **Validated**: {result.validated_at}",
            f"- **Status**: {result.status.upper()}",
            f"",
            f"## Errors",
        ]
        if result.errors:
            for e in result.errors:
                lines.append(f"- {safe_display_text(str(e))}")
        else:
            lines.append("None")
        lines.append("")
        lines.append("## Warnings")
        if result.warnings:
            for w in result.warnings:
                lines.append(f"- {safe_display_text(str(w))}")
        else:
            lines.append("None")
        lines.append("")
        lines.append("## Checks")
        lines.append("")
        lines.append("| Check | Status | Message |")
        lines.append("|-------|--------|---------|")
        for ch in result.checks:
            lines.append(f"| {ch.name} | {ch.status} | {safe_display_text(ch.message)} |")
        lines.append("")
        lines.append("---")
        lines.append("*Validation checks evidence integrity, not scientific correctness.*")

        with open(tmp_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        tmp_md.replace(md_path)
        result.report_path = str(md_path.resolve())
        md_ok = True
    except OSError as ex:
        result.checks.append(ValidationCheck(name="report_write_failed", status="error", message=f"Markdown report write failed: {ex}"))
        result.errors.append(f"Markdown report write failed: {ex}")
        if tmp_md.exists():
            tmp_md.unlink(missing_ok=True)

    if not json_ok or not md_ok:
        result.status = "error"
        return False
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_task(workspace: Path, task_id: str, write_report: bool = True) -> ValidationResult:
    td = workspace / "tasks" / task_id
    c = _Collector()

    try:
        manifest_obj = load_manifest(td)
    except Exception:
        manifest_obj = None
    if manifest_obj is None:
        c.add("manifest_missing", "error", "manifest.json missing or unreadable")
    else:
        manifest = manifest_obj.model_dump() if hasattr(manifest_obj, "model_dump") else manifest_obj

    if td.is_dir():
        _check_structure(td, c)
    else:
        c.add("task_dir_missing", "error", f"Task directory not found: {td}")

    if manifest_obj is not None:
        _check_manifest_references(td, manifest, c)
        _check_id_lists(td, workspace, manifest, c)

    _check_processing_runs(td, workspace, c)
    _check_data_objects(td, workspace, c)
    _check_relationships(td, workspace, c)
    _check_raw_checksum(td, workspace, c)
    _check_quality_flags(td, c)

    result = ValidationResult(
        task_id=task_id,
        status=c.overall(),
        errors=c.errors,
        warnings=c.warnings,
        checks=c.checks,
        validated_at=datetime.now(timezone.utc).isoformat(),
    )

    if write_report:
        ok = _write_validation_reports(td, result)
        if not ok:
            pass  # result already has report_write_failed, status already set to error

    return result


def validate_all(workspace: Path, write_report: bool = True) -> list[ValidationResult]:
    tasks_dir = workspace / "tasks"
    if not tasks_dir.is_dir():
        return []
    results = []
    for d in sorted(tasks_dir.iterdir()):
        if d.is_dir() and d.name.startswith("task_"):
            results.append(validate_task(workspace, d.name, write_report))
    return results
