"""Display status derivation for tasks - frontend-only, does not write to manifest."""
from __future__ import annotations

from typing import Any

from ..schemas import ReviewAction


def derive_display_status(
    manifest_status: str,
    runs: list[dict[str, Any]] | None = None,
    flags: list[dict[str, Any]] | None = None,
    reviews: list[dict[str, Any]] | None = None,
) -> str:
    runs = runs or []
    flags = flags or []
    reviews = reviews or []

    deprecate_reviews = [r for r in reviews if r.get("action") == ReviewAction.DEPRECATE.value]
    if deprecate_reviews:
        return "deprecated"

    return_rerun_reviews = [r for r in reviews if r.get("action") == ReviewAction.RETURN_FOR_RERUN.value]
    if return_rerun_reviews:
        return "returned_for_rerun"

    if not runs:
        return "ingested"

    has_failed = any(r.get("status") == "failed" for r in runs)
    has_model_unavailable = any(
        f.get("message", "").startswith("model_unavailable") for f in flags
    )

    needs_review_flags = [f for f in flags if f.get("requires_review")]
    if needs_review_flags:
        approved_reviews = [
            r for r in reviews if r.get("action") == ReviewAction.APPROVE.value
        ]
        if approved_reviews:
            return "reviewed"
        return "needs_review"

    if has_failed or has_model_unavailable:
        return "failed_or_warning"

    approved = [r for r in reviews if r.get("action") == ReviewAction.APPROVE.value]
    if approved:
        return "reviewed"

    return "processed"


_STATUS_DISPLAY: dict[str, str] = {
    "ingested": "Ingested",
    "processed": "Processed",
    "needs_review": "Needs Review",
    "reviewed": "Reviewed",
    "returned_for_rerun": "Returned for Rerun",
    "failed_or_warning": "Failed / Warning",
    "deprecated": "Deprecated",
}


def status_display_name(status: str) -> str:
    return _STATUS_DISPLAY.get(status, status)
