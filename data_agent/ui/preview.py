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


def preview_csv(path: Path, max_rows: int = 50) -> str | None:
    if not path.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_csv(path, nrows=max_rows)
        return df.to_csv(index=False)
    except Exception:
        try:
            text = path.read_text(encoding="utf-8")
            lines = text.strip().split("\n")
            return "\n".join(lines[:max_rows + 1])
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

    top_fields = {
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
        "warnings": data.get("warnings", []),
        "error": data.get("error", ""),
        "output_json": data.get("output_json", {}),
    }

    output = data.get("output_json", {})
    if isinstance(output, dict):
        top_fields["requires_review"] = output.get("requires_review", False)
        top_fields["ocr_unavailable"] = output.get("ocr_unavailable", False)
        top_fields["vision_unavailable"] = output.get("vision_unavailable", False)
        top_fields["text_blocks"] = output.get("text_blocks")
        top_fields["detected_units"] = output.get("detected_units")
        top_fields["axis_candidates"] = output.get("axis_candidates")
        top_fields["image_kind"] = output.get("image_kind")
        top_fields["visible_features"] = output.get("visible_features")
        top_fields["uncertainties"] = output.get("uncertainties")
        top_fields["factual_observations"] = output.get("factual_observations")
        top_fields["interpretation_candidates"] = output.get("interpretation_candidates")
        top_fields["method"] = output.get("method")
        top_fields["note"] = output.get("note")

    return top_fields
