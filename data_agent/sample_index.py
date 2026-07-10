"""Sample index: extracts sample IDs from task packages and builds a workspace-level index."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def _read_metadata_csv(path: Path) -> list[dict[str, str]]:
    """Extract sample_id/batch_id from a metadata CSV. Returns list of {sample_id, batch_id}."""
    import pandas as pd
    try:
        df = pd.read_csv(path, usecols=lambda c: c.lower() in ("sample_id", "sampleid", "sample id", "batch_id", "batchid"), nrows=10000)
    except Exception:
        return []
    df.columns = [c.strip().lower().replace(" ", "_").replace("sampleid", "sample_id").replace("batchid", "batch_id") for c in df.columns]
    results = []
    for _, row in df.iterrows():
        sid = str(row.get("sample_id", "")).strip()
        bid = str(row.get("batch_id", "")).strip()
        if sid and sid.lower() not in ("nan", "na", "none", ""):
            results.append({"sample_id": sid, "batch_id": bid if bid.lower() not in ("nan", "na", "none", "") else ""})
    return results


def _read_numeric_spectral_csv(path: Path) -> list[dict[str, str]]:
    """Extract sample_id/batch_id from a numeric or spectral CSV. Confidence 0.95."""
    import pandas as pd
    try:
        df = pd.read_csv(path, nrows=10000)
    except Exception:
        return []
    cols_lower = {c.lower().strip(): c for c in df.columns}
    results = []
    if "sample_id" in cols_lower:
        col = cols_lower["sample_id"]
        batch_col = cols_lower.get("batch_id", cols_lower.get("batchid", None))
        for _, row in df.iterrows():
            sid = str(row[col]).strip()
            if sid and sid.lower() not in ("nan", "na", "none", ""):
                bid = ""
                if batch_col:
                    bv = str(row[batch_col]).strip()
                    if bv.lower() not in ("nan", "na", "none", ""):
                        bid = bv
                results.append({"sample_id": sid, "batch_id": bid})
    return results


def _extract_from_structured_observation(td: Path) -> list[dict[str, str]]:
    """Read structured_observations JSON from derived/ for sample IDs. Confidence 0.8."""
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
            continue
        output = data.get("output_json", {}) if isinstance(data, dict) else {}
        if not isinstance(output, dict):
            output = {}
        ids = output.get("sample_ids", output.get("extracted_details", {}).get("sample_ids", [])) if isinstance(output, dict) else []
        if not ids:
            # Try reading from raw structured observation JSON directly
            try:
                ids = data.get("sample_ids", [])
            except (AttributeError, TypeError):
                ids = []
        for sid in ids:
            if isinstance(sid, str):
                results.append({"sample_id": sid, "batch_id": ""})
    return results


def _task_data_type(td: Path) -> str:
    """Infer the primary data type from manifest and derived files."""
    manifest = load_manifest(td)
    derived = td / "derived"
    raw_files = list((td / "raw").iterdir()) if (td / "raw").is_dir() else []

    if derived.is_dir():
        for f in derived.iterdir():
            if f.suffix == ".json" and "model_result" in f.name:
                return "model_result"
            if f.suffix == ".json" and "structured_observation" in f.name:
                return "structured_observation"

    for rf in raw_files:
        s = rf.suffix.lower()
        if s == ".csv":
            fname = rf.name.lower()
            if "metadata" in fname:
                return "sample_metadata"
            if "spectral" in fname or "ftir" in fname or "uvvis" in fname or "wavenumber" in fname:
                return "raw_spectral"
            return "raw_numeric"
        if s in (".png", ".jpg", ".jpeg", ".webp"):
            fname = rf.name.lower()
            if "chart" in fname:
                return "chart_image_input"
            if "surface" in fname or "photo" in fname or "microscope" in fname:
                return "visual_image"
        if s == ".txt":
            return "descriptive_observation_text"
    return "unknown"


def build_sample_index(workspace: Path) -> SampleIndexResult:
    tasks_dir = workspace / "tasks"
    warnings: list[str] = []
    entries_by_key: dict[tuple[str, str], SampleEntry] = {}
    unlinked: list[dict[str, Any]] = []

    if not tasks_dir.is_dir():
        return SampleIndexResult(
            generated_at=datetime.now(timezone.utc).isoformat(),
            warnings=["No tasks directory found"],
        )

    for d in sorted(tasks_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith("task_"):
            continue
        tid = d.name
        dtype = _task_data_type(d)
        candidates: list[tuple[dict[str, str], float, str]] = []

        # 1. Metadata CSV: confidence 1.0
        raw = d / "raw"
        if raw.is_dir():
            for rf in sorted(raw.iterdir()):
                if rf.suffix.lower() == ".csv" and "metadata" in rf.name.lower():
                    for entry in _read_metadata_csv(rf):
                        candidates.append((entry, 1.0, "metadata_csv"))
                    break

        # 2. Numeric/spectral CSV: confidence 0.95
        if raw.is_dir():
            for rf in sorted(raw.iterdir()):
                if rf.suffix.lower() != ".csv" or "metadata" in rf.name.lower():
                    continue
                for entry in _read_numeric_spectral_csv(rf):
                    # Don't duplicate explicit metadata entries
                    key = (entry["sample_id"], entry.get("batch_id", ""))
                    if not any((c[0]["sample_id"], c[0].get("batch_id", "")) == key for c in candidates):
                        candidates.append((entry, 0.95, "numeric_spectral_csv"))

        # 3. Structured observation JSON: confidence 0.8
        for entry in _extract_from_structured_observation(d):
            key = (entry["sample_id"], entry.get("batch_id", ""))
            if not any((c[0]["sample_id"], c[0].get("batch_id", "")) == key for c in candidates):
                candidates.append((entry, 0.8, "structured_observation"))

        # 4. Filename candidates: confidence 0.5, never auto-link
        if raw.is_dir():
            for rf in sorted(raw.iterdir()):
                fname = rf.name.lower()
                for ext in (".csv", ".txt", ".png", ".jpg"):
                    base = fname.replace(ext, "")
                    parts = base.split("_")
                    for p in parts:
                        if len(p) >= 2 and any(c.isalpha() for c in p) and any(c.isdigit() for c in p):
                            candidates.append(({"sample_id": p, "batch_id": ""}, 0.5, "filename_candidate"))
                            break
                    if len(candidates) > 0 and candidates[-1][2] == "filename_candidate":
                        break

        if not candidates:
            unlinked.append({"task_id": tid, "data_type": dtype, "reason": "no_sample_id_found", "candidate_ids": []})
            continue

        for entry, conf, source in candidates:
            sid = entry["sample_id"]
            bid = entry.get("batch_id", "")
            key = (sid, bid)

            if key in entries_by_key:
                sample = entries_by_key[key]
            elif conf >= 0.8:  # Only auto-link conf >= 0.8
                sample = SampleEntry(sample_id=sid, batch_id=bid)
                entries_by_key[key] = sample
            else:
                # Filename candidates: only link if an existing entry exists
                if key in entries_by_key:
                    pass  # fall through
                else:
                    unlinked.append({"task_id": tid, "data_type": dtype, "reason": "low_confidence_filename_candidate", "candidate_ids": [sid]})
                    continue

            sample.related_tasks.append(RelatedTask(task_id=tid, data_type=dtype, source=source, confidence=conf))
            if dtype not in sample.available_data:
                sample.available_data.append(dtype)

    # Detect same sample_id / different batch_id as warning
    sid_map: dict[str, list[tuple[str, str]]] = {}
    for (sid, bid) in entries_by_key:
        sid_map.setdefault(sid, []).append(bid)
    for sid, bids in sid_map.items():
        if len(bids) > 1:
            warnings.append(f"Sample '{sid}' has multiple batch IDs: {', '.join(b for b in bids if b)}")

    # Sort
    samples = sorted(entries_by_key.values(), key=lambda s: (s.sample_id, s.batch_id))
    for s in samples:
        s.related_tasks.sort(key=lambda t: (t.task_id, -t.confidence))
    unlinked.sort(key=lambda u: u["task_id"])

    result = SampleIndexResult(
        generated_at=datetime.now(timezone.utc).isoformat(),
        samples=samples,
        unlinked_tasks=unlinked,
        warnings=warnings,
    )

    # Write atomically
    idx_path = workspace / "sample_index.json"
    tmp = idx_path.with_suffix(idx_path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
        tmp.replace(idx_path)
    except OSError:
        pass

    return result


def load_sample_index(workspace: Path) -> SampleIndexResult | None:
    idx_path = workspace / "sample_index.json"
    if not idx_path.exists():
        return None
    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SampleIndexResult(**data)
    except (json.JSONDecodeError, FileNotFoundError):
        return None
