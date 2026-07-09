"""Read-only helpers to read workspace/tasks/manifest/logs/derived."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..package import (
    load_manifest,
    get_processing_runs,
    get_quality_flags,
    get_relationships,
    get_review_records,
)
from ..model_adapters.profiles import load_profiles, list_profile_status, is_profile_available


def _safe_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"_error": f"Invalid JSON: {path.name}"}


def read_workspace_summary(ws: Path) -> dict[str, Any]:
    tasks_dir = ws / "tasks"
    db_path = ws / "agent.sqlite"
    summary: dict[str, Any] = {
        "exists": ws.exists(),
        "has_db": db_path.exists(),
        "has_tasks_dir": tasks_dir.exists(),
        "task_count": 0,
        "status_counts": {},
    }
    if not tasks_dir.exists():
        return summary

    count = 0
    for d in sorted(tasks_dir.iterdir()):
        if d.is_dir() and d.name.startswith("task_"):
            count += 1
            manifest = _safe_json(d / "manifest.json")
            if isinstance(manifest, dict):
                st = manifest.get("status", "unknown")
                summary["status_counts"][st] = summary["status_counts"].get(st, 0) + 1
    summary["task_count"] = count
    summary["workspace_path"] = str(ws.resolve())
    return summary


def read_task_list(ws: Path) -> list[dict[str, Any]]:
    tasks_dir = ws / "tasks"
    if not tasks_dir.exists():
        return []
    result = []
    for d in sorted(tasks_dir.iterdir()):
        if d.is_dir() and d.name.startswith("task_"):
            manifest = load_manifest(d)
            if manifest is None:
                result.append({
                    "task_id": d.name, "status": "missing_manifest",
                    "input_files": [], "run_count": 0, "flag_count": 0,
                    "review_count": 0, "derived_count": 0, "raw_count": 0,
                })
                continue
            raw_dir = d / "raw"
            derived_dir = d / "derived"
            flags = get_quality_flags(d)
            reviews = get_review_records(d)
            runs = get_processing_runs(d)
            result.append({
                "task_id": d.name,
                "status": manifest.status,
                "input_files": manifest.input_files,
                "run_count": len(manifest.run_ids or []),
                "flag_count": len(manifest.flag_ids or []),
                "review_count": len(manifest.review_ids or []),
                "derived_count": len(list(derived_dir.glob("*"))) if derived_dir.exists() else 0,
                "raw_count": len(list(raw_dir.glob("*"))) if raw_dir.exists() else 0,
                "requires_review_count": sum(1 for f in flags if f.get("requires_review")),
                "manifest": manifest,
                "task_dir": str(d),
            })
    return result


def read_raw_files(task_dir: Path) -> list[dict[str, Any]]:
    raw_dir = task_dir / "raw"
    if not raw_dir.exists():
        return []
    result = []
    for f in sorted(raw_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            result.append({
                "name": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "suffix": f.suffix.lower(),
            })
    return result


def read_derived_files(task_dir: Path) -> list[dict[str, Any]]:
    derived_dir = task_dir / "derived"
    if not derived_dir.exists():
        return []
    result = []
    for f in sorted(derived_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            suffix = f.suffix.lower()
            is_model_result = "model_result" in f.name
            result.append({
                "name": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "suffix": suffix,
                "is_model_result": is_model_result,
            })
    return result


def read_processing_runs(task_dir: Path) -> list[dict[str, Any]]:
    return get_processing_runs(task_dir)


def read_quality_flags(task_dir: Path) -> list[dict[str, Any]]:
    return get_quality_flags(task_dir)


def read_relationships(task_dir: Path) -> list[dict[str, Any]]:
    return get_relationships(task_dir)


def read_review_records(task_dir: Path) -> list[dict[str, Any]]:
    return get_review_records(task_dir)


def read_model_profiles() -> list[dict[str, Any]]:
    profiles = load_profiles()
    if not profiles:
        return []
    result = []
    for name, profile in profiles.items():
        status = list_profile_status(profile, show_values=False)
        result.append({
            "name": name,
            "role": status.get("role", ""),
            "provider": status.get("provider", ""),
            "base_url": status.get("base_url", ""),
            "api_key": status.get("api_key", ""),
            "model": status.get("model", ""),
            "available": is_profile_available(profile),
            "supports_vision": profile.supports_vision,
            "supports_json": profile.supports_json,
            "timeout_seconds": profile.timeout_seconds,
            "cost_tier": profile.cost_tier,
        })
    return result


def read_task_manifest(task_dir: Path) -> dict[str, Any] | None:
    manifest = load_manifest(task_dir)
    if manifest is None:
        return None
    return manifest.model_dump()
