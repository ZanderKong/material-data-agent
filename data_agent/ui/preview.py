"""File preview helpers for raw/derived/model_result content."""
from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any


def get_file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if "model_result" in name and suffix == ".json":
        return "model_result"
    if suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        return "image"
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        return "json"
    if suffix in (".txt", ".md", ".markdown"):
        return "text"
    return "other"


def preview_image(path: Path) -> str | None:
    if not path.exists():
        return None
    return str(path)


def _preview_csv_fallback(path: Path, max_rows: int = 50) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = []
            for i, line in enumerate(fh):
                if i > max_rows:
                    break
                lines.append(line.rstrip("\n"))
            return "\n".join(lines)
    except Exception:
        return None


def preview_csv(path: Path, max_rows: int = 50) -> str | None:
    if not path.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_csv(path, nrows=max_rows)
        return df.to_csv(index=False)
    except Exception:
        return _preview_csv_fallback(path, max_rows)


def preview_csv_dataframe(path: Path, max_rows: int = 50):
    """Return a pandas DataFrame for table display. Returns None if unreadable."""
    if not path.exists():
        return None
    try:
        import pandas as pd
        return pd.read_csv(path, nrows=max_rows)
    except Exception:
        return None


def preview_json(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps(data, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, FileNotFoundError):
        try:
            return path.read_text(encoding="utf-8")[:2000]
        except Exception:
            return None


def preview_text(path: Path, max_chars: int = 2000) -> str | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        if len(text) > max_chars:
            return text[:max_chars] + f"\n\n... (truncated, {len(text)} total chars)"
        return text
    except Exception:
        return None


def preview_model_result(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return {"_error": "Invalid JSON"}

    if not isinstance(data, dict):
        return {"_error": "Not a dict"}

    output = data.get("output_json", {})
    if not isinstance(output, dict):
        output = {}

    audit = {
        "role": data.get("role", ""),
        "provider": data.get("provider", ""),
        "model": data.get("model", ""),
        "mode": data.get("mode", ""),
        "success": data.get("success", False),
        "confidence": data.get("confidence", 0.0),
        "fallback_used": data.get("fallback_used", False),
        "fallback_from": data.get("fallback_from", ""),
        "latency_ms": data.get("latency_ms", 0),
        "token_usage": data.get("token_usage", {}),
        "schema_version": data.get("schema_version", ""),
        "prompt_version": data.get("prompt_version", ""),
        "input_metadata": data.get("input_metadata", {}),
    }

    risk = {
        "warnings": data.get("warnings", []),
        "error": data.get("error", ""),
        "requires_review": data.get("requires_review", output.get("requires_review", False)),
        "ocr_unavailable": output.get("ocr_unavailable", False),
        "vision_unavailable": output.get("vision_unavailable", False),
    }

    extracted = {
        "output_json": output,
        "text_blocks": output.get("text_blocks"),
        "detected_units": output.get("detected_units"),
        "axis_candidates": output.get("axis_candidates"),
        "visible_features": output.get("visible_features"),
        "factual_observations": output.get("factual_observations"),
        "interpretation_candidates": output.get("interpretation_candidates"),
        "image_kind": output.get("image_kind"),
        "method": output.get("method"),
        "note": output.get("note"),
    }

    raw = {
        "raw_text": data.get("raw_text", ""),
        "raw_response": data.get("raw_response", ""),
        "raw_response_redacted": data.get("raw_response_redacted", ""),
    }

    return {
        "audit": audit,
        "risk": risk,
        "extracted": extracted,
        "raw": raw,
    }


def select_raw_response(raw: dict[str, Any]) -> str:
    """Pick the first non-empty raw response with fallback order and type coercion.

    Order: raw_response_redacted → raw_text → raw_response
    Returns empty string when all are empty.
    """
    for key in ("raw_response_redacted", "raw_text", "raw_response"):
        value = raw.get(key)
        if value is not None and value != "":
            if isinstance(value, str):
                return value
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False, indent=2, default=str)
            return str(value)
    return ""
