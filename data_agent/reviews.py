"""Review recording and rerun management."""
from __future__ import annotations

from pathlib import Path

from .db import get_conn, insert_review
from .package import append_review_record, load_manifest, write_manifest
from .schemas import ReviewAction, ReviewRecord


def write_review(
    workspace: Path,
    task_id: str,
    action: str,
    reviewer: str,
    comment: str = "",
    target_id: str = "",
    target_type: str = "task",
) -> ReviewRecord:
    action_enum = ReviewAction(action)
    task_dir = workspace / "tasks" / task_id

    review = ReviewRecord(
        task_id=task_id,
        reviewer=reviewer,
        action=action_enum,
        target_type=target_type if target_id else "task",
        target_id=target_id or task_id,
        comment=comment,
    )

    conn = get_conn(workspace)
    insert_review(conn, review)
    conn.close()

    append_review_record(task_dir, review)

    manifest = load_manifest(task_dir)
    if manifest:
        manifest.review_ids = manifest.review_ids or []
        manifest.review_ids.append(review.review_id)
        if action_enum == ReviewAction.APPROVE:
            manifest.status = "approved"
        elif action_enum == ReviewAction.DEPRECATE:
            manifest.status = "deprecated"
        elif action_enum == ReviewAction.RETURN_FOR_RERUN:
            manifest.status = "rerun_requested"
        elif action_enum == ReviewAction.MARK_LOW_CONFIDENCE:
            manifest.status = "low_confidence"
        write_manifest(task_dir, manifest)

    return review
