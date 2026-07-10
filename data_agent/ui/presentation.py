"""UI presentation helpers: formatting, suggested actions, display utilities."""
from __future__ import annotations

from typing import Any

from data_agent.ui.security import safe_display_text


def suggested_quality_action(flag: dict[str, Any]) -> str:
    """Return a human-readable suggested action for a quality flag."""
    msg = str(flag.get("message", "")).lower()
    flag_id = str(flag.get("flag_id", ""))

    if "axis_confirmation_required" in msg or "axis" in flag_id.lower():
        return "Confirm axis metadata"
    if "model_unavailable" in msg or "fallback_used" in msg:
        return "Use local result or retry with configured model"
    if "low_confidence" in msg:
        return "Mark low confidence or rerun"
    if flag.get("requires_review"):
        return "Review before approval"
    return "No action required"


def format_quality_flag(flag: dict[str, Any]) -> dict[str, Any]:
    """Format a quality flag for display with redacted message and suggested action."""
    return {
        "flag_id": flag.get("flag_id", ""),
        "severity": flag.get("severity", "info"),
        "requires_review": flag.get("requires_review", False),
        "confidence": flag.get("confidence", 0.0),
        "message": safe_display_text(str(flag.get("message", ""))),
        "suggested_action": suggested_quality_action(flag),
    }


def format_model_output(output_json: dict[str, Any]) -> dict[str, Any]:
    """Extract displayable model-output fields."""
    if not isinstance(output_json, dict):
        return {}
    return {
        "text_blocks": output_json.get("text_blocks"),
        "detected_units": output_json.get("detected_units"),
        "axis_candidates": output_json.get("axis_candidates"),
        "visible_features": output_json.get("visible_features"),
        "factual_observations": output_json.get("factual_observations"),
        "interpretation_candidates": output_json.get("interpretation_candidates"),
        "method": output_json.get("method"),
        "note": output_json.get("note"),
    }


def cloud_mode_notice(mode: str) -> str:
    """Return a safety notice for cloud/auto modes, empty string for local."""
    if mode in ("cloud", "auto"):
        return "cloud/auto 模式可能会把选中的图片或文本发送到你配置的外部模型服务。敏感数据请使用 local 模式，或确认有权限后再使用。"
    return ""
