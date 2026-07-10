"""Evidence package export: ZIP generation with validation gate and review README."""
from __future__ import annotations

import json
import os
import shutil
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

    if output_path is None:
        exports_dir = workspace / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        output_path = exports_dir / f"{task_id}_export.zip"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Validate
    val_result = validate_task(workspace, task_id, write_report=True)
    result_json = td / "logs" / "package_validation_result.json"
    report_md = td / "logs" / "package_validation_report.md"

    if not result_json.exists() or not report_md.exists():
        return ExportResult(
            success=False, task_id=task_id,
            validation_status=val_result.status,
            errors=["Validation report generation failed"],
            message="Export failed: validation reports not available",
        )

    # 2. Generate readme
    try:
        readme = _generate_readme(td, task_id, val_result)
    except Exception:
        readme = f"# Review Package: {task_id}\n\nReadme generation failed.\n"

    # 3. Build ZIP
    warnings: list[str] = []
    if val_result.status == "error":
        warnings.append("EXPORTED WITH VALIDATION ERRORS")

    tmp_zip_path = None
    try:
        fd, tmp_zip_path = tempfile.mkstemp(suffix=".zip", dir=str(output_path.parent))
        os.close(fd)

        file_count = 0
        with zipfile.ZipFile(tmp_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write readme at root
            zf.writestr("README_for_review.md", readme)
            file_count += 1

            # Copy validation report to root too
            with open(report_md, "r", encoding="utf-8") as f:
                zf.writestr("package_validation_report.md", f.read())
            file_count += 1

            for sub in ("manifest.json", "raw", "derived", "logs", "reviews"):
                src = td / sub
                if not src.exists():
                    continue
                if src.is_file():
                    arcname = sub
                    zf.write(str(src), arcname)
                    file_count += 1
                elif src.is_dir():
                    for root, dirs, files in os.walk(str(src)):
                        for fn in files:
                            if fn.startswith("."):
                                continue
                            fp = Path(root) / fn
                            rel = fp.relative_to(td)
                            # Security: reject dangerous paths
                            if fp.is_symlink() or ".." in str(rel) or fp.resolve() != fp:
                                warnings.append(f"Skipped unsafe path: {rel}")
                                continue
                            zf.write(str(fp), str(rel))
                            file_count += 1

        # Atomic replace
        final = Path(tmp_zip_path)
        final.replace(output_path)

        base_msg = f"Exported {task_id} ({file_count} files)"
        if val_result.status == "error":
            status_msg = f"{base_msg} with validation errors"
        else:
            status_msg = base_msg

        return ExportResult(
            success=True,
            task_id=task_id,
            zip_path=str(output_path.resolve()),
            validation_status=val_result.status,
            file_count=file_count,
            warnings=warnings,
            message=status_msg,
        )
    except Exception as e:
        if tmp_zip_path and Path(tmp_zip_path).exists():
            Path(tmp_zip_path).unlink(missing_ok=True)
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
        f"# Review Package: {task_id}",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        f"**Validation Status**: {val_result.status.upper()}",
        "",
        "## Input Files",
    ]
    if manifest:
        for f in manifest.input_files:
            lines.append(f"- {f}")
    else:
        lines.append("*No manifest*")

    lines.append("")
    lines.append("## Derived Files")
    if manifest:
        for f in manifest.derived_files:
            lines.append(f"- {f}")
    else:
        lines.append("*No manifest*")

    lines.append("")
    lines.append("## Processing Runs")
    for r in runs:
        lines.append(f"- {r.get('tool_name', '?')} [{r.get('status', '?')}]")

    lines.append("")
    lines.append("## Quality Flags")
    for fq in flags:
        msg = safe_display_text(str(fq.get("message", "")))
        review_tag = " [REQUIRES REVIEW]" if fq.get("requires_review") else ""
        lines.append(f"- {fq.get('severity', 'info')}: {msg}{review_tag}")

    lines.append("")
    lines.append("## Reviews")
    for rev in reviews:
        lines.append(f"- {rev.get('action', '?')} by {rev.get('reviewer', '?')}")

    lines.append("")
    lines.append("## Validation")
    lines.append(f"Status: {val_result.status.upper()}")
    lines.append(f"Report: package_validation_report.md (also in logs/)")

    lines.append("")
    lines.append("---")
    lines.append("*model_result is model-assisted extraction, not a scientific conclusion.*")
    lines.append("*requires_review=True requires human confirmation.*")

    return "\n".join(lines)
