"""Evidence package validation: structure, manifest, run, relationship, and checksum checks.

Does not modify manifest, SQLite, raw, derived, quality flags, relationships, or reviews.
"""
from __future__ import annotations

import hashlib
import json
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
# Strict readers – do NOT use _read_json_list because it hides invalid JSON
# ---------------------------------------------------------------------------

def _strict_read_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON object file strictly. Returns None on missing, dict on success.

    Raises ValueError for invalid JSON or wrong top-level type (not dict).
    """
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}: {path}")
    return data


def _strict_read_json_list(path: Path) -> list[dict[str, Any]] | None:
    """Read a JSON list file strictly. Returns None on missing, list on success.

    Raises ValueError for invalid JSON or wrong top-level type (not list).
    """
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON list, got {type(data).__name__}: {path}")
    return data


def _safe_resolve(task_dir: Path, sub_path: str) -> Path | None:
    """Resolve a relative path under a task directory safely.

    Returns None for absolute paths, .. traversal, or result outside task_dir.
    """
    candidate = (task_dir / sub_path).resolve()
    if not str(candidate).startswith(str(task_dir.resolve())):
        return None
    return candidate


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Check collector
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


def _resolve_data_file(td: Path, rel_path: str) -> Path | None:
    """Resolve a data_schema file path relative to task_dir.

    Tries derived/ first, then task_dir root.
    """
    fp_str = str(rel_path)
    resolved = _safe_resolve(td / "derived", fp_str)
    if resolved is not None and resolved.exists():
        return resolved
    resolved = _safe_resolve(td, fp_str)
    if resolved is not None and resolved.exists():
        return resolved
    return None


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def _check_structure(td: Path, c: _Collector) -> None:
    required = ["manifest.json", ("dir", "raw"), ("dir", "derived"), ("dir", "logs"), ("dir", "reviews")]
    for r in required:
        if isinstance(r, tuple):
            p = td / r[1]
            if p.is_dir():
                c.add(f"dir_{r[1]}", "pass", f"Directory '{r[1]}' exists")
            else:
                c.add(f"dir_{r[1]}", "error", f"Required directory '{r[1]}' is missing")
        else:
            p = td / r
            if p.exists():
                c.add(f"file_{r}", "pass", f"File '{r}' exists")
            else:
                c.add(f"file_{r}", "error", f"Required file '{r}' is missing")


def _check_manifest_references(td: Path, manifest: dict[str, Any], c: _Collector) -> None:
    raw_dir = td / "raw"
    for fn in manifest.get("input_files", []) or []:
        if not fn:
            c.add("manifest_input_empty_id", "error", "manifest.input_files contains an empty file name")
            continue
        if not (raw_dir / fn).exists():
            c.add("manifest_input_missing", "error", f"Raw file '{fn}' referenced in manifest not found")

    for dp in manifest.get("derived_files", []) or []:
        resolved = _safe_resolve(td, dp)
        if resolved is None:
            c.add("manifest_derived_bad_path", "error", f"Derived file path rejected: {dp}")
        elif not resolved.exists():
            c.add("manifest_derived_missing", "error", f"Derived file '{dp}' referenced in manifest not found")


def _check_id_lists(td: Path, manifest: dict[str, Any], c: _Collector) -> None:
    def _validate_id_presence(list_name: str, log_path: Path, expected_ids: list[str], id_key: str):
        if not expected_ids:
            return
        seen: set[str] = set()
        for eid in expected_ids:
            if not eid or not isinstance(eid, str):
                c.add(f"manifest_{list_name}_empty_id", "error", f"manifest.{list_name} contains empty or non-string ID")
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
            if expected_ids:
                c.add(f"{list_name}_missing_file", "error", f"manifest.{list_name} has IDs but {log_path.name} is missing")
            return

        existing_ids = {str(item.get(id_key, "")) for item in data}
        for eid in seen:
            if eid not in existing_ids:
                c.add(f"{list_name}_id_not_found", "error", f"ID '{eid}' in manifest.{list_name} not found in {log_path.name}")

    _validate_id_presence("run_ids", td / "logs" / "processing_runs.json", manifest.get("run_ids", []) or [], "run_id")
    _validate_id_presence("flag_ids", td / "logs" / "quality_flags.json", manifest.get("flag_ids", []) or [], "flag_id")
    _validate_id_presence("review_ids", td / "reviews" / "review_records.json", manifest.get("review_ids", []) or [], "review_id")


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
        if not rid:
            c.add("runs_empty_id", "error", "Processing run has empty run_id")
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
                    if key in ("model",) and params.get("provider", "").startswith("local"):
                        c.add(f"runs_model_empty_{key}", "warn", f"Run {rid} model key '{key}' is empty (local provider)")
                    else:
                        c.add(f"runs_model_empty_{key}", "error", f"Run {rid} model key '{key}' is empty")


def _check_data_objects(td: Path, ws: Path, c: _Collector) -> None:
    db_path = get_db_path(ws)
    if not db_path.exists():
        c.add("registry_db_missing", "warn", "agent.sqlite not found; registry-level checks skipped")
        return

    conn = None
    try:
        conn = get_conn(ws)
        objs = get_data_objects_by_task(conn, td.name)
        for obj in objs:
            oid = obj["object_id"]
            lifecycle = obj["lifecycle"]
            data_type = obj["data_type"]
            derived_from = obj["derived_from"]
            data_schema = obj["data_schema"]

            if lifecycle in ("L2", "l2"):
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
                    c.add(f"dataobj_{oid}_no_output", "error", f"Model-result object {oid} missing output_file in data_schema")
                else:
                    out_path = _resolve_data_file(td, str(output_file))
                    if out_path is None:
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
                    if resolved is None:
                        c.add(f"dataobj_{oid}_schema_file_missing", "error", f"Data-schema file '{fp}' for object {oid} not found under derived/")
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

    known_ids: set[str] = set()
    for sub in ("raw", "derived"):
        sd = td / sub
        if sd.is_dir():
            for f in sd.iterdir():
                if f.is_file():
                    known_ids.add(f.name)
    try:
        runs = _strict_read_json_list(td / "logs" / "processing_runs.json")
        if runs:
            for r in runs:
                rid = r.get("run_id", "")
                if rid:
                    known_ids.add(rid)
    except (ValueError, json.JSONDecodeError):
        pass

    seen_rel_ids: set[str] = set()
    replaces_map: dict[str, str] = {}   # source -> target
    replaced_by_map: dict[str, str] = {}  # target -> source

    for rel in rels:
        rid = rel.get("rel_id", "")
        rtype = rel.get("rel_type", "")
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        meta = rel.get("metadata", {}) or {}

        if not rid:
            c.add("rels_empty_id", "error", "Relationship has empty rel_id")
        elif rid in seen_rel_ids:
            c.add("rels_duplicate_id", "error", f"Duplicate rel_id: {rid}")
        seen_rel_ids.add(rid)

        if rtype == "derived_from":
            if not src or not tgt:
                c.add("rels_derived_from_empty", "error", "derived_from has empty source or target")
            run_id = meta.get("run_id", "")
            if run_id and run_id not in known_ids:
                c.add("rels_derived_from_run_missing", "warn", f"derived_from run_id '{run_id}' not found in processing_runs")

        if rtype == "replaces":
            replaces_map[src] = tgt
            if src == tgt:
                c.add("rels_self_replace", "error", f"replaces has same source and target: {src}")

        if rtype == "replaced_by":
            replaced_by_map[tgt] = src
            if src == tgt:
                c.add("rels_self_replaced_by", "error", f"replaced_by has same source and target: {src}")

    for src, tgt in replaces_map.items():
        rep = replaced_by_map.get(tgt, "")
        if rep != src:
            c.add("rels_replaces_no_reciprocal", "warn", f"replaces {src} -> {tgt} missing reciprocal replaced_by")


def _check_raw_checksum(td: Path, ws: Path, c: _Collector) -> None:
    db_path = get_db_path(ws)
    if not db_path.exists():
        c.add("checksum_db_missing", "warn", "agent.sqlite not found; checksum checks skipped")
        return

    conn = None
    try:
        conn = get_conn(ws)
        files = get_files_by_task(conn, td.name)
        for frow in files:
            stored = frow["stored_path"]
            expected_checksum = frow["checksum_sha256"]
            if not stored or not expected_checksum:
                c.add("checksum_missing_data", "warn", f"File record {frow['file_id']} missing stored_path or checksum")
                continue
            sp = Path(stored)
            if not sp.exists():
                c.add("checksum_file_missing", "warn", f"Stored file not found: {stored}")
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
        _check_id_lists(td, manifest, c)

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
        _write_validation_reports(td, result)

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


def _write_validation_reports(td: Path, result: ValidationResult) -> None:
    try:
        json_data = result.model_dump()
    except Exception:
        return

    json_path = td / "logs" / "package_validation_result.json"
    md_path = td / "logs" / "package_validation_report.md"

    tmp_json = json_path.with_suffix(json_path.suffix + ".tmp")
    tmp_md = md_path.with_suffix(md_path.suffix + ".tmp")

    try:
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        tmp_json.replace(json_path)
        result.result_path = str(json_path.resolve())
    except OSError:
        pass

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
                lines.append(f"- {e}")
        else:
            lines.append("None")
        lines.append("")
        lines.append("## Warnings")
        if result.warnings:
            for w in result.warnings:
                lines.append(f"- {w}")
        else:
            lines.append("None")
        lines.append("")
        lines.append("## Checks")
        lines.append("")
        lines.append("| Check | Status | Message |")
        lines.append("|-------|--------|---------|")
        for ch in result.checks:
            lines.append(f"| {ch.name} | {ch.status} | {ch.message} |")
        lines.append("")
        lines.append("---")
        lines.append("*Validation checks evidence integrity, not scientific correctness.*")

        with open(tmp_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        tmp_md.replace(md_path)
        result.report_path = str(md_path.resolve())
    except OSError:
        pass
