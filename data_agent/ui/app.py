"""Streamlit local UI for Material R&D Data Processing Agent."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from ..config import resolve_workspace
from .readers import (
    read_workspace_summary,
    read_task_list,
    read_task_manifest,
    read_raw_files,
    read_derived_files,
    read_processing_runs,
    read_quality_flags,
    read_relationships,
    read_review_records,
    read_model_profiles,
)
from .status import derive_display_status, status_display_name
from .preview import get_file_kind, preview_image, preview_csv, preview_json, preview_text, preview_model_result
from .actions import do_ingest, do_upload_ingest, do_process_all, do_process_task, do_review

st.set_page_config(page_title="Material Data Agent", layout="wide")


def _init_session():
    defaults = {
        "workspace_path": "./workspace",
        "selected_task_id": None,
        "task_list": [],
        "model_mode": "local",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_session()

st.title("Material R&D Data Processing Agent")


def _error_redacted(exc: Exception) -> str:
    msg = str(exc)
    return f"Error: {msg[:500]}"


# ---- Sidebar ----
with st.sidebar:
    st.header("Workspace")
    ws_input = st.text_input("Workspace path", value=st.session_state.workspace_path, key="ws_path_input")
    st.session_state.workspace_path = ws_input

    ws = Path(ws_input).resolve()

    summary = read_workspace_summary(ws)

    if not summary["has_tasks_dir"]:
        st.info("Not initialized. Use Ingest tab to create tasks.")
    else:
        st.metric("Tasks", summary["task_count"])
        if summary.get("status_counts"):
            st.caption("Status: " + ", ".join(f"{k}:{v}" for k, v in summary["status_counts"].items()))

    st.divider()

    st.session_state.model_mode = st.selectbox(
        "Model mode",
        ["local", "auto", "cloud"],
        index=["local", "auto", "cloud"].index(st.session_state.model_mode),
    )

    st.divider()

    if st.button("Refresh"):
        st.session_state.task_list = read_task_list(ws)
        st.rerun()


# ---- Tabs ----
tab_overview, tab_ingest, tab_tasks, tab_detail, tab_profiles, tab_help = st.tabs([
    "Overview", "Ingest", "Tasks", "Task Detail", "Model Profiles", "Help",
])

# ==== Tab: Overview ====
with tab_overview:
    st.subheader("Workspace Overview")
    st.code(str(ws.resolve()), language=None)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Path exists", "Yes" if ws.exists() else "No")
    with col2:
        st.metric("agent.sqlite", "Found" if (ws / "agent.sqlite").exists() else "Not found")
    with col3:
        st.metric("Tasks", summary["task_count"])

    if summary.get("status_counts"):
        st.subheader("Status Distribution")
        st.json(summary["status_counts"])


# ==== Tab: Ingest ====
with tab_ingest:
    st.subheader("Ingest Files")

    method = st.radio("Method", ["Inbox directory", "Upload files"], horizontal=True)

    if method == "Inbox directory":
        inbox_path = st.text_input("Inbox directory path", placeholder="/path/to/inbox")
        if st.button("Ingest Inbox", type="primary", disabled=not inbox_path):
            with st.spinner("Ingesting..."):
                result = do_ingest(inbox_path, ws)
            if result["success"]:
                st.success(f"{result['message']}. Task IDs: {', '.join(result['task_ids'])}")
                st.session_state.task_list = read_task_list(ws)
            else:
                st.error(result["message"])

    else:
        uploaded = st.file_uploader("Choose files", accept_multiple_files=True)
        if uploaded:
            st.write(f"{len(uploaded)} file(s) selected:")
            for uf in uploaded:
                st.text(f"  {uf.name} ({uf.size} bytes)")
        if st.button("Upload and Ingest", type="primary", disabled=not uploaded):
            with st.spinner("Uploading and ingesting..."):
                result = do_upload_ingest(uploaded, ws)
            if result["success"]:
                st.success(result["message"])
                st.session_state.task_list = read_task_list(ws)
            else:
                st.error(result["message"])


# ==== Tab: Tasks ====
with tab_tasks:
    st.subheader("Task List")

    if st.button("Load / Refresh Task List"):
        st.session_state.task_list = read_task_list(ws)
        st.rerun()

    tasks = st.session_state.task_list

    if not tasks:
        st.info("No tasks found. Use the Ingest tab to create tasks.")
    else:
        status_filter = st.multiselect(
            "Filter by display status",
            ["ingested", "processed", "needs_review", "reviewed", "returned_for_rerun", "failed_or_warning", "deprecated"],
            default=[],
        )
        only_needs = st.checkbox("Only show needs_review", value=False)

        rows_for_table: list[dict] = []
        for t in tasks:
            flags = read_quality_flags(Path(t["task_dir"]))
            reviews = read_review_records(Path(t["task_dir"]))
            runs = read_processing_runs(Path(t["task_dir"]))
            ds = derive_display_status(t["status"], runs, flags, reviews)

            if only_needs and ds != "needs_review":
                continue
            if status_filter and ds not in status_filter:
                continue

            rows_for_table.append({
                "": t["task_id"],
                "Task ID": t["task_id"],
                "Display Status": status_display_name(ds),
                "Input": ", ".join(t.get("input_files", [])),
                "Runs": t["run_count"],
                "Flags": t["flag_count"],
                "Reviews": t["review_count"],
            })

        if rows_for_table:
            st.dataframe(rows_for_table, use_container_width=True, hide_index=True,
                         column_order=["Task ID", "Display Status", "Input", "Runs", "Flags", "Reviews"])

        selected = st.selectbox(
            "Select task to view details",
            [t["task_id"] for t in tasks],
            index=None,
            placeholder="Choose a task...",
        )
        if selected:
            st.session_state.selected_task_id = selected


# ==== Tab: Task Detail ====
with tab_detail:
    tid = st.session_state.selected_task_id

    if not tid:
        st.info("Select a task in the Tasks tab to view details.")
    else:
        task_dir = ws / "tasks" / tid
        if not task_dir.exists():
            st.error(f"Task directory not found: {task_dir}")
        else:
            manifest = read_task_manifest(task_dir)
            raw_files = read_raw_files(task_dir)
            derived_files = read_derived_files(task_dir)
            runs = read_processing_runs(task_dir)
            flags = read_quality_flags(task_dir)
            rels = read_relationships(task_dir)
            reviews = read_review_records(task_dir)

            st.header(f"Task: {tid}")
            st.caption(f"Path: {task_dir}")

            st.subheader("Summary")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Status", manifest.get("status", "?") if manifest else "?")
            with c2:
                st.metric("Raw files", len(raw_files))
            with c3:
                st.metric("Derived files", len(derived_files))
            with c4:
                st.metric("Runs / Flags", f"{len(runs)} / {len(flags)}")

            # --- Raw Files ---
            with st.expander("Raw Files", expanded=False):
                if not raw_files:
                    st.caption("No raw files")
                for rf in raw_files:
                    rpath = Path(rf["path"])
                    st.text(f"{rf['name']} ({rf['size_bytes']} bytes, {rf['suffix']})")
                    kind = get_file_kind(rpath)
                    if kind == "image":
                        st.image(str(rpath), caption=rf["name"], width=400)
                    elif kind in ("csv", "text"):
                        content = preview_text(rpath) or ""
                        st.text_area("Content", content, height=120, key=f"raw_{rf['name']}")
                    elif kind == "json":
                        content = preview_json(rpath) or ""
                        st.code(content[:2000] or "(empty)", language="json")

            # --- Derived Files ---
            with st.expander("Derived Files", expanded=True):
                if not derived_files:
                    st.caption("No derived files")
                for df_info in derived_files:
                    dpath = Path(df_info["path"])
                    kind = get_file_kind(dpath)
                    label = f"{df_info['name']} ({df_info['size_bytes']} bytes)"
                    if kind == "model_result":
                        st.markdown(f"**{label}**")
                        data = preview_model_result(dpath)
                        if data:
                            if data.get("_error"):
                                st.error(data["_error"])
                            else:
                                c_success, c_role, c_conf, c_fb = st.columns(4)
                                with c_success:
                                    st.metric("Success", str(data.get("success")))
                                with c_role:
                                    st.metric("Role", str(data.get("role")))
                                with c_conf:
                                    st.metric("Confidence", f"{data.get('confidence', 0):.2f}")
                                with c_fb:
                                    st.metric("Fallback", "Yes" if data.get("fallback_used") else "No")
                                if data.get("error"):
                                    st.warning(f"Error: {data['error']}")
                                if data.get("warnings"):
                                    for w in data["warnings"]:
                                        st.caption(f"Warning: {w}")
                                st.json(data.get("output_json", {}))
                        st.divider()
                    elif kind == "image":
                        st.image(str(dpath), caption=label, width=400)
                    elif kind == "csv":
                        st.markdown(f"**{label}**")
                        content = preview_csv(dpath) or ""
                        st.text_area("Preview", content, height=200, key=f"derived_{df_info['name']}")
                    elif kind == "json":
                        st.markdown(f"**{label}**")
                        content = preview_json(dpath) or ""
                        st.code(content[:3000] or "(empty)", language="json")
                    else:
                        st.text(label)

            # --- Processing Runs ---
            with st.expander("Processing Runs", expanded=False):
                if not runs:
                    st.caption("No processing runs")
                else:
                    for run in runs:
                        is_model = str(run.get("tool_name", "")).startswith("model:")
                        label = f"{run.get('tool_name','?')} [{run.get('status','?')}]"
                        if is_model:
                            label = f"{label}"
                        st.text(label)
                        with st.expander("Details"):
                            st.json(run)

            # --- Quality Flags ---
            with st.expander("Quality Flags", expanded=False):
                if not flags:
                    st.caption("No quality flags")
                else:
                    for flag in flags:
                        requires = flag.get("requires_review", False)
                        icon = "Review" if requires else "Info"
                        severity = flag.get("severity", "info")
                        if requires:
                            st.warning(f"{icon}: {flag.get('message','')} (severity={severity}, confidence={flag.get('confidence',0):.2f})")
                        else:
                            st.info(f"{icon}: {flag.get('message','')} (severity={severity}, confidence={flag.get('confidence',0):.2f})")

            # --- Relationships ---
            with st.expander("Relationships", expanded=False):
                if not rels:
                    st.caption("No relationships")
                else:
                    st.dataframe([{
                        "type": r.get("rel_type", ""),
                        "source": r.get("source_id", "")[:20],
                        "target": r.get("target_id", "")[:20],
                    } for r in rels], use_container_width=True)

            # --- Review Records ---
            with st.expander("Review Records", expanded=False):
                if not reviews:
                    st.caption("No reviews")
                else:
                    for rev in reviews:
                        st.text(f"{rev.get('action','?')} by {rev.get('reviewer','?')} at {rev.get('created_at','')}")
                        if rev.get("comment"):
                            st.caption(f"Comment: {rev['comment']}")

            st.divider()

            # --- Actions ---
            st.subheader("Actions")

            col_process, col_review = st.columns(2)

            with col_process:
                st.markdown("**Process / Rerun**")
                process_mode = st.selectbox(
                    "Model mode",
                    ["local", "auto", "cloud"],
                    key="detail_model_mode",
                    index=["local", "auto", "cloud"].index(st.session_state.model_mode),
                )
                if st.button("Process / Rerun Task", key="btn_process_task"):
                    with st.spinner(f"Processing {tid}..."):
                        result = do_process_task(ws, tid, process_mode)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])

                if st.button("Process All Tasks", key="btn_process_all"):
                    with st.spinner(f"Processing all tasks..."):
                        result = do_process_all(ws, process_mode)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])

            with col_review:
                st.markdown("**Review**")
                review_action = st.selectbox(
                    "Action",
                    ["approve", "return_for_rerun", "mark_low_confidence", "deprecate"],
                    key="review_action",
                )
                reviewer = st.text_input("Reviewer", key="review_reviewer")
                comment = st.text_area("Comment", key="review_comment")

                if review_action == "deprecate":
                    confirm = st.checkbox("I confirm this will deprecate the current results", key="deprecate_confirm")
                else:
                    confirm = True

                if st.button("Submit Review", key="btn_review", disabled=not confirm):
                    with st.spinner("Recording review..."):
                        result = do_review(ws, tid, review_action, reviewer, comment)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])


# ==== Tab: Model Profiles ====
with tab_profiles:
    st.subheader("Model Profiles")

    profiles = read_model_profiles()
    if not profiles:
        st.info("No model_profiles.yaml found. Local mode will use stubs only. Auto/cloud will fallback or fail gracefully.")
    else:
        rows = []
        for p in profiles:
            rows.append({
                "Name": p["name"],
                "Role": p["role"],
                "Provider": p["provider"],
                "Base URL": p["base_url"],
                "API Key": p["api_key"],
                "Model": p["model"],
                "Available": "yes" if p["available"] else "no",
                "Vision": "yes" if p["supports_vision"] else "no",
                "JSON": "yes" if p["supports_json"] else "no",
                "Timeout": f"{p['timeout_seconds']}s",
                "Cost": p["cost_tier"],
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)


# ==== Tab: Help ====
with tab_help:
    st.subheader("Help & Marimo")

    st.markdown("""
### Quick Reference

**Model modes:**
- `local` — Zero network calls, uses local stubs only
- `cloud` — Calls configured cloud models directly
- `auto` — Tries cloud first, falls back to local stubs

**Lifecycle:**
- L0 → original file registration
- L1 → immutable archive copy in `raw/`
- L2 → derived processing results in `derived/`
- Rerun preserves old L2 and creates `replaces` relationships

**Model routing:**
- Raw numeric / spectral / metadata → no model calls
- Chart images → OCR + Vision
- Surface photos → Vision + OCR
- Observation text → Fast model
    """)

    st.divider()
    st.subheader("Marimo Review")

    if st.session_state.selected_task_id:
        tid = st.session_state.selected_task_id
    else:
        tid = "TASK_ID"

    ws_str = str(ws.resolve())
    cmd = f"python -m data_agent open --workspace {ws_str} --task {tid}"
    st.code(cmd, language="bash")

    cmd_print = cmd + " --print-command"
    st.code(cmd_print, language="bash")
    st.caption("Add --print-command to see the command without starting the server.")
