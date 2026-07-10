"""Sample index: chunked CSV reads, dual observation shapes, two-pass conservative linker."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from data_agent.package import load_manifest


class RelatedTask(BaseModel):
    task_id: str
    data_type: str
    source: str
    confidence: float


class SampleEntry(BaseModel):
    sample_id: str
    batch_id: str = ""
    related_tasks: list[RelatedTask] = Field(default_factory=list)
    available_data: list[str] = Field(default_factory=list)


class SampleIndexResult(BaseModel):
    schema_version: str = "sample_index_v1"
    generated_at: str
    samples: list[SampleEntry] = Field(default_factory=list)
    unlinked_tasks: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _clean_id(val: Any) -> str | None:
    """Clean a single sample_id or batch_id value."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s.lower() in ("nan", "na", "none", ""):
        return None
    return s


def _read_csv_ids(path: Path, target_cols: list[str]) -> list[dict[str, str]]:
    """Read sample_id and batch_id columns using chunked CSV reads."""
    results: list[dict[str, str]] = []
    try:
        header = pd.read_csv(path, nrows=0)
    except Exception:
        return results
    cols_lower = {c.lower(): c for c in header.columns}
    usecols = [c for c in header.columns if c.lower() in target_cols]
    if not usecols or "sample_id" not in cols_lower:
        return results

    sid_col = cols_lower["sample_id"]
    bid_col = cols_lower.get("batch_id", cols_lower.get("batchid", None))

    try:
        for chunk in pd.read_csv(path, usecols=usecols, chunksize=5000):
            for _, row in chunk.iterrows():
                sid = _clean_id(row.get(sid_col))
                if sid is None:
                    continue
                bid = ""
                if bid_col:
                    bv = _clean_id(row.get(bid_col))
                    if bv is not None:
                        bid = bv
                results.append({"sample_id": sid, "batch_id": bid})
    except Exception:
        pass
    return results


def _extract_observation_ids(td: Path) -> list[dict[str, str]]:
    """Extract sample IDs from structured observation files in derived/.

    Supports both local processor output (data.extracted_details.sample_ids)
    and model-wrapper output (data.output_json.extracted_details.sample_ids).
    """
    derived = td / "derived"
    results = []
    if not derived.is_dir():
        return results
    for f in sorted(derived.iterdir()):
        if not f.is_file() or "structured_observation" not in f.name.lower():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            results.append(None)  # marker for warning
            continue
        if not isinstance(data, dict):
            results.append(None)
            continue

        ids: list[str] = []
        # Shape 1: local processor
        ed = data.get("extracted_details", {})
        if isinstance(ed, dict):
            ids_raw = ed.get("sample_ids", [])
            if isinstance(ids_raw, list):
                for x in ids_raw:
                    if isinstance(x, str) and x.strip():
                        ids.append(x.strip())
        # Shape 2: model wrapper
        output = data.get("output_json", {})
        if isinstance(output, dict):
            ed2 = output.get("extracted_details", {})
            if isinstance(ed2, dict):
                ids_raw2 = ed2.get("sample_ids", [])
                if isinstance(ids_raw2, list):
                    for x in ids_raw2:
                        if isinstance(x, str) and x.strip() and x.strip() not in ids:
                            ids.append(x.strip())
            # Also accept direct sample_ids
            direct = output.get("sample_ids", [])
            if isinstance(direct, list):
                for x in direct:
                    if isinstance(x, str) and x.strip() and x.strip() not in ids:
                        ids.append(x.strip())

        for sid in ids:
            results.append({"sample_id": sid, "batch_id": ""})
    return results


def _task_data_type(td: Path) -> str:
    manifest = load_manifest(td)
    raw_dir = td / "raw"
    if raw_dir.is_dir():
        for rf in sorted(raw_dir.iterdir()):
            if not rf.is_file():
                continue
            s = rf.suffix.lower()
            name = rf.name.lower()
            if s == ".csv":
                if "metadata" in name:
                    return "sample_metadata"
                if any(kw in name for kw in ("spectral", "ftir", "uvvis", "wavenumber", "raman")):
                    return "raw_spectral"
                return "raw_numeric"
            if s in (".png", ".jpg", ".jpeg", ".webp"):
                if "chart" in name:
                    return "chart_image_input"
                if any(kw in name for kw in ("surface", "photo", "microscope", "sem", "tem")):
                    return "visual_image"
            if s in (".txt", ".md"):
                return "descriptive_observation_text"
    return "unknown"


def build_sample_index(workspace: Path) -> SampleIndexResult:
    tasks_dir = workspace / "tasks"
    warnings: list[str] = []
    entries_by_key: dict[tuple[str, str], list[RelatedTask]] = {}
    unlinked: list[dict[str, Any]] = []

    if not tasks_dir.is_dir():
        result = SampleIndexResult(
            generated_at=datetime.now(timezone.utc).isoformat(),
            warnings=["No tasks directory found"],
        )
        _atomic_write(workspace, result)
        return result

    # Pass 1: explicit IDs from metadata CSV (1.0) and numeric/spectral CSV (0.95)
    tasks_with_csv: set[str] = set()
    for d in sorted(tasks_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith("task_"):
            continue
        tid = d.name
        dtype = _task_data_type(d)
        raw_dir = d / "raw"

        csv_entries: list[tuple[dict[str, str], float, str]] = []
        if raw_dir.is_dir():
            for rf in sorted(raw_dir.iterdir()):
                if not rf.is_file() or rf.suffix.lower() != ".csv":
                    continue
                tasks_with_csv.add(tid)
                is_metadata = "metadata" in rf.name.lower()
                conf = 1.0 if is_metadata else 0.95
                source = "metadata_csv" if is_metadata else "numeric_spectral_csv"
                for entry in _read_csv_ids(rf, ["sample_id", "batch_id"]):
                    csv_entries.append((entry, conf, source))

        if not csv_entries:
            continue

        for entry, conf, source in csv_entries:
            key = (entry["sample_id"], entry.get("batch_id", ""))
            entries_by_key.setdefault(key, []).append(RelatedTask(task_id=tid, data_type=dtype, source=source, confidence=conf))

    # Pass 2: observation IDs link to exactly one explicit sample
    for d in sorted(tasks_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith("task_"):
            continue
        tid = d.name
        dtype = _task_data_type(d)

        obs_entries = _extract_observation_ids(d)
        has_bad_json = any(e is None for e in obs_entries)
        obs_entries = [e for e in obs_entries if e is not None]

        if has_bad_json:
            unlinked.append({"task_id": tid, "data_type": dtype, "reason": "invalid_structured_observation_json", "candidate_ids": []})

            if not obs_entries:
                if not has_bad_json and not _csv_entries_found(d):
                    unlinked.append({"task_id": tid, "data_type": dtype, "reason": "no_sample_id_found", "candidate_ids": []})
            continue

        for entry in obs_entries:
            sid = entry["sample_id"]
            # Observation doesn't carry batch – find exact match
            matching_keys = [k for k in entries_by_key if k[0] == sid]
            if len(matching_keys) == 1:
                key = matching_keys[0]
                entries_by_key.setdefault(key, []).append(RelatedTask(task_id=tid, data_type=dtype, source="structured_observation", confidence=0.8))
            elif len(matching_keys) > 1:
                unlinked.append({"task_id": tid, "data_type": dtype, "reason": "ambiguous_batch_for_observation_id", "candidate_ids": [sid]})
            else:
                unlinked.append({"task_id": tid, "data_type": dtype, "reason": "observation_no_explicit_match", "candidate_ids": [sid]})

    # Final pass: unlinked tasks with no IDs at all
    all_task_ids = {d.name for d in tasks_dir.iterdir() if d.is_dir() and d.name.startswith("task_")}
    linked_task_ids = {rt.task_id for tasks in entries_by_key.values() for rt in tasks}
    already_unlinked = {u["task_id"] for u in unlinked}
    for tid in sorted(all_task_ids):
        if tid in linked_task_ids or tid in already_unlinked:
            continue
        dtype = _task_data_type(tasks_dir / tid)
        if tid in tasks_with_csv:
            unlinked.append({"task_id": tid, "data_type": dtype, "reason": "csv_without_sample_id", "candidate_ids": []})
        else:
            unlinked.append({"task_id": tid, "data_type": dtype, "reason": "no_sample_id_found", "candidate_ids": []})
    sid_map: dict[str, list[str]] = {}
    for (sid, bid) in entries_by_key:
        sid_map.setdefault(sid, []).append(bid)
    for sid, bids in sid_map.items():
        if len(bids) > 1:
            warnings.append(f"Sample '{sid}' has multiple batch IDs: {', '.join(b for b in bids if b)}")

    # Build sample entries
    samples: list[SampleEntry] = []
    for (sid, bid), tasks in sorted(entries_by_key.items(), key=lambda x: (x[0][0], x[0][1])):
        tasks.sort(key=lambda t: (t.task_id, t.source, -t.confidence))
        data_types = sorted(set(t.data_type for t in tasks))
        samples.append(SampleEntry(sample_id=sid, batch_id=bid, related_tasks=tasks, available_data=data_types))

    unlinked.sort(key=lambda u: u["task_id"])
    for u in unlinked:
        u["candidate_ids"] = sorted(set(u.get("candidate_ids", [])))

    result = SampleIndexResult(
        generated_at=datetime.now(timezone.utc).isoformat(),
        samples=samples,
        unlinked_tasks=unlinked,
        warnings=warnings,
    )

    try:
        _atomic_write(workspace, result)
    except OSError as e:
        result.warnings.append(f"Failed to write sample_index.json: {e}")
        raise

    return result


def _csv_entries_found(td: Path) -> bool:
    raw_dir = td / "raw"
    if not raw_dir.is_dir():
        return False
    for rf in raw_dir.iterdir():
        if rf.is_file() and rf.suffix.lower() == ".csv":
            if _read_csv_ids(rf, ["sample_id"]):
                return True
    return False


def _atomic_write(workspace: Path, result: SampleIndexResult) -> None:
    idx_path = workspace / "sample_index.json"
    tmp = idx_path.with_suffix(idx_path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
        tmp.replace(idx_path)
    except OSError:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def load_sample_index(workspace: Path) -> SampleIndexResult | None:
    idx_path = workspace / "sample_index.json"
    if not idx_path.exists():
        return None
    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SampleIndexResult(**data)
    except (json.JSONDecodeError, FileNotFoundError, Exception):
        return None
