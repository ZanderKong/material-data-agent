"""Action wrappers that call existing CLI backend functions with try/except."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from data_agent.db import init_db
from data_agent.ingest import ingest_inbox
from data_agent.process import process_all_tasks, process_single_task
from data_agent.reviews import write_review as _write_review
from data_agent.validation import validate_task
from data_agent.ui.security import safe_ui_error


def _safe_msg(exc: Exception) -> str:
    return safe_ui_error(str(exc))


def do_ingest(inbox_path: str, ws: Path) -> dict[str, Any]:
    inbox = Path(inbox_path).resolve()
    if not inbox.exists():
        return {"success": False, "task_count": 0, "message": f"Inbox not found: {inbox}", "task_ids": []}

    conn = None
    try:
        conn = init_db(ws)
        task_ids = ingest_inbox(inbox, ws, conn)
        return {
            "success": True,
            "task_count": len(task_ids),
            "message": f"Created {len(task_ids)} task(s)",
            "task_ids": task_ids,
        }
    except Exception as e:
        return {"success": False, "task_count": 0, "message": _safe_msg(e), "task_ids": []}
    finally:
        if conn is not None:
            conn.close()


def do_upload_ingest(uploaded_files: list[Any], ws: Path) -> dict[str, Any]:
    if not uploaded_files:
        return {"success": False, "task_count": 0, "message": "No files uploaded", "task_ids": []}

    import time
    ts = str(int(time.time() * 1000))
    tmp_inbox = ws / "_ui_uploads" / ts
    tmp_inbox.mkdir(parents=True, exist_ok=True)

    saved = []
    conn = None
    try:
        for uf in uploaded_files:
            dest = tmp_inbox / uf.name
            with open(dest, "wb") as f:
                f.write(uf.getbuffer())
            saved.append({"name": uf.name, "size": uf.size})

        conn = init_db(ws)
        task_ids = ingest_inbox(tmp_inbox, ws, conn)
        return {
            "success": True,
            "task_count": len(task_ids),
            "message": f"Uploaded and created {len(task_ids)} task(s)",
            "task_ids": task_ids,
            "uploaded": saved,
        }
    except Exception as e:
        return {"success": False, "task_count": 0, "message": _safe_msg(e), "task_ids": []}
    finally:
        if conn is not None:
            conn.close()
        shutil.rmtree(tmp_inbox, ignore_errors=True)


def do_process_all(ws: Path, model_mode: str = "local") -> dict[str, Any]:
    try:
        count = process_all_tasks(ws, model_mode)
        return {"success": True, "count": count, "message": f"Processed {count} task(s)"}
    except Exception as e:
        return {"success": False, "count": 0, "message": _safe_msg(e)}


def do_process_task(ws: Path, task_id: str, model_mode: str = "local") -> dict[str, Any]:
    try:
        ok = process_single_task(ws, task_id, model_mode)
        if ok:
            return {"success": True, "message": f"Task {task_id} processed successfully"}
        return {"success": False, "message": f"Task {task_id} processing returned False"}
    except Exception as e:
        return {"success": False, "message": _safe_msg(e)}


def do_review(
    ws: Path,
    task_id: str,
    action: str,
    reviewer: str = "",
    comment: str = "",
    target_type: str = "task",
    target_id: str = "",
) -> dict[str, Any]:
    if not reviewer.strip():
        return {"success": False, "message": "Reviewer name is required"}
    try:
        _write_review(ws, task_id, action, reviewer, comment, target_id, target_type)
        return {"success": True, "message": f"Review '{action}' recorded by {reviewer}"}
    except Exception as e:
        return {"success": False, "message": _safe_msg(e)}


def do_validate_package(ws: Path, task_id: str) -> dict[str, Any]:
    try:
        result = validate_task(ws, task_id, write_report=True)
        return result.model_dump()
    except Exception as e:
        return {"task_id": task_id, "status": "error", "errors": [_safe_msg(e)], "warnings": [], "checks": [], "report_path": "", "result_path": "", "validated_at": ""}
