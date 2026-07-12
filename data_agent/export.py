"""Evidence package export: safe ZIP with validation gate, preflight, and review README."""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from data_agent.package import load_manifest, get_processing_runs, get_quality_flags, get_review_records
from data_agent.ui.security import safe_display_text
from data_agent.validation import validate_task


class ExportResult(BaseModel):
    success: bool
    task_id: str
    zip_path: str = ""
    validation_status: Literal["pass", "warn", "error"] = "pass"
    file_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    message: str


def export_task(
    workspace: Path,
    task_id: str,
    output_path: Path | None = None,
) -> ExportResult:
    td = workspace / "tasks" / task_id
    if not td.is_dir():
        return ExportResult(
            success=False, task_id=task_id,
            errors=[f"Task directory not found: {td}"],
            message="Export failed: task directory not found",
        )

    # Reject output inside task
    if output_path is not None:
        try:
            out_resolved = output_path.resolve()
            td_resolved = td.resolve()
            out_resolved.relative_to(td_resolved)
            return ExportResult(
                success=False, task_id=task_id,
                errors=["Output path must not be inside the task directory"],
                message="Export failed: output inside task directory",
            )
        except (ValueError, OSError):
            pass  # OK, outside task

    if output_path is None:
        exports_dir = workspace / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        output_path = exports_dir / f"{task_id}_export.zip"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.is_symlink():
        return ExportResult(
            success=False, task_id=task_id,
            errors=["Output path is a symlink"],
            message="Export failed: output path is a symlink",
        )

    # 1. Validate
    val_result = validate_task(workspace, task_id, write_report=True)

    # Check for report_write_failed
    for ch in val_result.checks:
        if ch.name == "report_write_failed":
            return ExportResult(
                success=False, task_id=task_id,
                validation_status=val_result.status,
                errors=["Validation report generation failed (report_write_failed)"],
                message="Export failed: validation reports could not be written",
            )

    marker_path = td / "logs" / "package_validation_incomplete.json"
    if marker_path.exists():
        return ExportResult(
            success=False, task_id=task_id,
            validation_status="error",
            errors=["Validation incomplete marker present; rerun validation"],
            message="Export failed: validation did not complete",
        )

    result_json_path = td / "logs" / "package_validation_result.json"
    report_md_path = td / "logs" / "package_validation_report.md"
    expected_json_resolved = str(result_json_path.resolve())
    expected_md_resolved = str(report_md_path.resolve())

    if not val_result.result_path or not val_result.report_path:
        return ExportResult(
            success=False, task_id=task_id,
            validation_status=val_result.status,
            errors=["Validation report paths are blank"],
            message="Export failed: validation report paths not set",
        )
    if val_result.result_path != expected_json_resolved:
        return ExportResult(
            success=False, task_id=task_id,
            validation_status=val_result.status,
            errors=["Validation result_path does not match expected report location"],
            message="Export failed: validation report path mismatch",
        )
    if val_result.report_path != expected_md_resolved:
        return ExportResult(
            success=False, task_id=task_id,
            validation_status=val_result.status,
            errors=["Validation report_path does not match expected report location"],
            message="Export failed: validation report path mismatch",
        )

    if not result_json_path.is_file() or not report_md_path.is_file():
        return ExportResult(
            success=False, task_id=task_id,
            validation_status=val_result.status,
            errors=["Validation report artifacts missing after write"],
            message="Export failed: validation reports not found",
        )

    try:
        with open(result_json_path, "r", encoding="utf-8") as f:
            persisted = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ExportResult(
            success=False, task_id=task_id,
            validation_status=val_result.status,
            errors=["Cannot read persisted validation JSON"],
            message="Export failed: persisted validation JSON unreadable",
        )
    if not isinstance(persisted, dict):
        return ExportResult(
            success=False, task_id=task_id,
            validation_status=val_result.status,
            errors=["Persisted validation JSON is not a dict"],
            message="Export failed: persisted validation JSON format invalid",
        )
    for field in ("task_id", "validated_at", "status", "result_path", "report_path"):
        persisted_val = str(persisted.get(field, ""))
        current_val = str(getattr(val_result, field, ""))
        if persisted_val != current_val:
            return ExportResult(
                success=False, task_id=task_id,
                validation_status=val_result.status,
                errors=[safe_display_text(f"Persisted validation {field} mismatch: {persisted_val} != {current_val}")],
                message="Export failed: persisted validation report does not match current result",
            )

    # 2. Generate README
    try:
        readme = _generate_readme(td, task_id, val_result)
    except Exception as e:
        return ExportResult(
            success=False, task_id=task_id,
            validation_status=val_result.status,
            errors=[safe_display_text(f"README generation failed: {e}")],
            message="Export failed: README generation failed",
        )

    # 3. Preflight archive file list
    td_resolved = td.resolve()
    output_resolved = output_path.resolve()
    tmp_path = None

    def _collect_files():
        items: list[tuple[str, Path]] = []
        # README and validation report at root
        items.append(("README_for_review.md", None))
        items.append(("package_validation_report.md", None))

        for sub in ("manifest.json", "raw", "derived", "logs", "reviews"):
            src = td / sub
            if src.is_symlink():
                return None, f"Symlink in package: {sub}"
            if not src.exists():
                continue
            if src.is_file():
                items.append((sub, src))
            elif src.is_dir():
                for root, dirnames, files in os.walk(str(src), followlinks=False):
                    for d in dirnames:
                        dpath = Path(root) / d
                        if dpath.is_symlink():
                            return None, f"Directory symlink in package: {dpath}"
                    for fn in files:
                        if fn.startswith("."):
                            continue
                        fp_raw = Path(root) / fn
                        if fp_raw.is_symlink():
                            return None, f"Symlink in package: {fp_raw}"
                        fp = fp_raw.resolve()
                        if not fp.is_file():
                            return None, f"Non-regular file in package: {fp_raw}"
                        rel = str(fp_raw.relative_to(td))
                        if ".." in rel:
                            return None, f"Path traversal in package: {rel}"
                        if fp == output_resolved:
                            continue
                        items.append((rel, fp))
        # Ensure directory entries
        for dirname in ("raw/", "derived/", "logs/", "reviews/"):
            items.append((dirname, None))
        return items, None

    items, preflight_err = _collect_files()
    if preflight_err is not None:
        return ExportResult(
            success=False, task_id=task_id,
            validation_status=val_result.status,
            errors=[preflight_err],
            message=f"Export failed: {preflight_err}",
        )

    # 4. Build ZIP
    warnings: list[str] = []
    if val_result.status == "error":
        warnings.append("EXPORTED WITH VALIDATION ERRORS")

    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".zip", dir=str(output_path.parent))
        os.close(fd)

        file_count = 0
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for arcname, src_path in items:
                if arcname == "README_for_review.md":
                    zf.writestr(arcname, readme)
                    file_count += 1
                elif arcname == "package_validation_report.md":
                    with open(report_md_path, "r", encoding="utf-8") as f:
                        zf.writestr(arcname, f.read())
                    file_count += 1
                elif src_path is not None and src_path.is_file():
                    zf.write(str(src_path), arcname)
                    file_count += 1
                elif src_path is None:
                    zf.writestr(arcname, "")

        Path(tmp_path).replace(output_path)

        base_msg = f"Exported {task_id} ({file_count} files)"
        if val_result.status == "error":
            status_msg = f"{base_msg} with validation errors"
        else:
            status_msg = base_msg

        return ExportResult(
            success=True,
            task_id=task_id,
            zip_path=str(output_resolved),
            validation_status=val_result.status,
            file_count=file_count,
            warnings=warnings,
            message=status_msg,
        )
    except Exception as e:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink(missing_ok=True)
        return ExportResult(
            success=False, task_id=task_id,
            errors=[safe_display_text(str(e))],
            message="Export failed",
        )


def _generate_readme(td: Path, task_id: str, val_result: Any) -> str:
    manifest = load_manifest(td)
    runs = get_processing_runs(td)
    flags = get_quality_flags(td)
    reviews = get_review_records(td)

    lines = [
        f"# Review Package: {safe_display_text(task_id)}",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        f"**Validation Status**: {val_result.status.upper()}",
        "",
        "## Input Files",
    ]
    if manifest:
        for f in manifest.input_files:
            lines.append(f"- {safe_display_text(str(f))}")
    else:
        lines.append("*No manifest*")

    lines.append("")
    lines.append("## Derived Files")
    if manifest:
        for f in manifest.derived_files:
            lines.append(f"- {safe_display_text(str(f))}")
    else:
        lines.append("*No manifest*")

    lines.append("")
    lines.append("## Processing Runs")
    for r in runs:
        tool = safe_display_text(str(r.get("tool_name", "?")))
        status = safe_display_text(str(r.get("status", "?")))
        lines.append(f"- {tool} [{status}]")

    lines.append("")
    lines.append("## Quality Flags")
    for fq in flags:
        msg = safe_display_text(str(fq.get("message", "")))
        review_tag = " [REQUIRES REVIEW]" if fq.get("requires_review") else ""
        lines.append(f"- {safe_display_text(str(fq.get('severity', 'info')))}: {msg}{review_tag}")

    lines.append("")
    lines.append("## Reviews")
    for rev in reviews:
        action = safe_display_text(str(rev.get("action", "?")))
        reviewer = safe_display_text(str(rev.get("reviewer", "?")))
        lines.append(f"- {action} by {reviewer}")

    lines.append("")
    lines.append("## Validation")
    lines.append(f"Status: {val_result.status.upper()}")
    lines.append(f"Report: package_validation_report.md (also in logs/)")

    lines.append("")
    lines.append("---")
    lines.append("*model_result is model-assisted extraction, not a scientific conclusion.*")
    lines.append("*requires_review=True requires human confirmation.*")

    return "\n".join(lines)
