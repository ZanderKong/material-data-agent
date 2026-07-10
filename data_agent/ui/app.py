"""Streamlit local UI for Material R&D Data Processing Agent."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

from data_agent.config import resolve_workspace
from data_agent.ui.readers import (
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
    read_validation_result,
    read_sample_index,
)
from data_agent.ui.status import derive_display_status, status_display_name
from data_agent.ui.preview import (
    get_file_kind, preview_image, preview_csv, preview_csv_dataframe,
    preview_json, preview_text, preview_model_result, select_raw_response,
)
from data_agent.ui.actions import do_ingest, do_upload_ingest, do_process_all, do_process_task, do_review, do_validate_package, do_export_package, do_index_samples
from data_agent.ui.security import safe_ui_error, safe_display_text
from data_agent.ui.presentation import format_quality_flag, format_model_output, cloud_mode_notice

st.set_page_config(page_title="Material Data Agent", layout="wide")


def _init_session():
    defaults = {
        "workspace_path": os.environ.get("DATA_AGENT_UI_WORKSPACE", "./workspace"),
        "selected_task_id": None,
        "task_list": [],
        "task_list_workspace": "",
        "model_mode": "local",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _auto_refresh_task_list(ws: Path):
    key = str(ws.resolve())
    if st.session_state.get("task_list_workspace") != key:
        st.session_state.task_list = read_task_list(ws)
        st.session_state.task_list_workspace = key


_init_session()

st.title("Material R&D Data Processing Agent")


def _error_redacted(exc: Exception) -> str:
    return safe_ui_error(exc)


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
    notice = cloud_mode_notice(st.session_state.model_mode)
    if notice:
        st.warning(notice)

    st.divider()

    if st.button("Refresh"):
        st.session_state.task_list = read_task_list(ws)
        st.session_state.task_list_workspace = str(ws.resolve())
        st.rerun()

_auto_refresh_task_list(ws)


# ---- Tabs ----
tab_overview, tab_ingest, tab_tasks, tab_detail, tab_samples, tab_profiles, tab_help = st.tabs([
    "Overview", "Ingest", "Tasks", "Task Detail", "Sample View", "Model Profiles", "Help",
])

# ==== Tab: Overview ====
with tab_overview:
    st.subheader("Material Data Agent")
    st.caption("材料研发数据处理与证据链复核工具")
    st.markdown("Traceable data ingestion, structured processing, model-assisted extraction, and evidence-package export for materials R&D.")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Tasks", summary["task_count"])
    with col2:
        st.metric("Runs", summary.get("run_count", 0))
    with col3:
        st.metric("Flags", summary.get("flag_count", 0))
    with col4:
        st.metric("Reviews", summary.get("review_count", 0))
    with col5:
        st.metric("Model Results", summary.get("model_result_count", 0))

    if summary.get("status_counts"):
        st.caption("Status: " + ", ".join(f"{k}:{v}" for k, v in summary["status_counts"].items()))

    st.divider()

    st.caption("Workflow: Upload → Ingest → Process → Review → Validate → Export")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
**Capabilities**
- Multi-format data ingest (CSV, images, observation text)
- Sample-metadata extraction from CSV headers
- Chart/visual image model-assisted analysis
- Quality-flag generation and evidence-chain tracking
- Package validation and export-ready ZIP
- Version-aware rerun with `replaces`/`replaced_by` relationships
""")
    with c2:
        st.markdown("""
**Getting Started**
1. **Ingest** tab: add demo inbox or upload files
2. **Tasks** tab: review auto-detected tasks
3. Select a task → **Task Detail** tab
4. Click **Process** (local mode for zero-network)
5. Review derived files, flags, model results
""")

    if summary.get("invalid_record_count", 0) > 0:
        st.warning(f"Warning: {summary['invalid_record_count']} task(s) have invalid or missing manifests")


# ==== Tab: Ingest ====
with tab_ingest:
    st.subheader("Ingest Files")
    st.info("推荐输入格式：CSV 文件首行为列标题，列名包含单位（如thickness_um），包含sample_id列。图像保留坐标轴和标尺。详细规范见 Help → Data Input Contract。", icon="")

    method = st.radio("Method", ["Inbox directory", "Upload files"], horizontal=True)

    if method == "Inbox directory":
        inbox_path = st.text_input("Inbox directory path", placeholder="/path/to/inbox")
        if st.button("Ingest Inbox", type="primary", disabled=not inbox_path):
            with st.spinner("Ingesting..."):
                result = do_ingest(inbox_path, ws)
            if result["success"]:
                st.success(f"{result['message']}. Task IDs: {', '.join(result['task_ids'])}")
                st.session_state.task_list = read_task_list(ws)
                st.session_state.task_list_workspace = str(ws.resolve())
            else:
                st.error(safe_ui_error(result["message"]))

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
                st.session_state.task_list_workspace = str(ws.resolve())
            else:
                st.error(safe_ui_error(result["message"]))


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
            st.error(safe_ui_error(f"Task directory not found: {task_dir}"))
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

            view_mode = st.radio("View", ["Basic", "Advanced"], horizontal=True, key=f"view_{tid}")

            # --- Raw Files ---
            if view_mode == "Advanced":
                with st.expander("Raw Files", expanded=False):
                    if not raw_files:
                        st.caption("No raw files")
                    for rf in raw_files:
                        rpath = Path(rf["path"])
                        st.text(f"{rf['name']} ({rf['size_bytes']} bytes, {rf['suffix']})")
                        kind = get_file_kind(rpath)
                        if kind == "image":
                            st.image(str(rpath), caption=rf["name"], width=400)
                        elif kind == "csv":
                            df = preview_csv_dataframe(rpath)
                            if df is not None:
                                st.dataframe(df, use_container_width=True, key=f"raw_{rf['name']}")
                                st.caption(f"Preview: first {len(df)} rows")
                            else:
                                content = preview_csv(rpath) or ""
                                st.text_area("Content", content, height=200, key=f"raw_{rf['name']}")
                        elif kind == "text":
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
                                st.error(safe_ui_error(data["_error"]))
                            else:
                                st.caption(":warning: model_result 是模型辅助提取结果，不是科研结论。")
                                st.caption(":warning: requires_review=True 时必须人工确认。")
                                st.caption(":warning: success=False 表示模型不可用、fallback 或 stub，不代表分析成功。")

                                audit = data.get("audit", {})
                                risk = data.get("risk", {})
                                extracted = data.get("extracted", {})
                                raw_data = data.get("raw", {})

                                with st.expander("Audit", expanded=True):
                                    col_a1, col_a2, col_a3 = st.columns(3)
                                    with col_a1:
                                        st.metric("Role", str(audit.get("role")))
                                        st.metric("Provider", str(audit.get("provider")))
                                        st.metric("Model", str(audit.get("model")))
                                    with col_a2:
                                        st.metric("Mode", str(audit.get("mode")))
                                        st.metric("Success", str(audit.get("success")))
                                        st.metric("Confidence", f"{audit.get('confidence', 0):.2f}")
                                    with col_a3:
                                        st.metric("Fallback", "Yes" if audit.get("fallback_used") else "No")
                                        st.metric("Fallback From", str(audit.get("fallback_from") or "-"))
                                        st.metric("Latency", f"{audit.get('latency_ms', 0)}ms")
                                    if audit.get("token_usage"):
                                        st.caption(f"Token usage: {audit['token_usage']}")
                                    if audit.get("schema_version"):
                                        st.caption(f"Schema: {audit['schema_version']}  |  Prompt: {audit['prompt_version']}")

                                with st.expander("Risk", expanded=False):
                                    if risk.get("error"):
                                        st.warning(f"Error: {safe_ui_error(risk['error'])}")
                                    if risk.get("warnings"):
                                        for w in risk["warnings"]:
                                            st.caption(f"Warning: {safe_ui_error(str(w))}")
                                    col_r1, col_r2, col_r3 = st.columns(3)
                                    with col_r1:
                                        st.metric("Requires Review", str(risk.get("requires_review")))
                                    with col_r2:
                                        st.metric("OCR Unavailable", str(risk.get("ocr_unavailable")))
                                    with col_r3:
                                        st.metric("Vision Unavailable", str(risk.get("vision_unavailable")))

                                with st.expander("Extracted Output", expanded=True):
                                    output_json = extracted.get("output_json", {})
                                    if output_json:
                                        st.json(output_json)
                                    else:
                                        st.caption("No extracted output")

                                with st.expander("Raw Response (redacted)", expanded=False):
                                    display_raw = safe_display_text(select_raw_response(raw_data))
                                    if display_raw:
                                        st.text_area("Raw", display_raw[:2000], height=150, key=f"raw_resp_{df_info['name']}")
                                    else:
                                        st.caption("No raw response available")
                        st.divider()
                    elif kind == "image":
                        st.image(str(dpath), caption=label, width=400)
                    elif kind == "csv":
                        st.markdown(f"**{label}**")
                        df = preview_csv_dataframe(dpath)
                        if df is not None:
                            st.dataframe(df, use_container_width=True, key=f"derived_{df_info['name']}")
                            st.caption(f"Preview: first {len(df)} rows")
                        else:
                            content = preview_csv(dpath) or ""
                            st.text_area("Preview", content, height=200, key=f"derived_{df_info['name']}")
                    elif kind == "json":
                        st.markdown(f"**{label}**")
                        content = preview_json(dpath) or ""
                        st.code(content[:3000] or "(empty)", language="json")
                    else:
                        st.text(label)

            # --- Processing Runs ---
            if view_mode == "Advanced":
                with st.expander("Processing Runs", expanded=False):
                    if not runs:
                        st.caption("No processing runs")
                    else:
                        for run in runs:
                            is_model = str(run.get("tool_name", "")).startswith("model:")
                            lbl = f"{run.get('tool_name','?')} [{run.get('status','?')}]"
                            st.text(lbl)
                            with st.expander("Details"):
                                st.json(run)

            # --- Quality Flags ---
            with st.expander("Quality Flags", expanded=False):
                if not flags:
                    st.caption("No quality flags")
                else:
                    for flag in flags:
                        fq = format_quality_flag(flag)
                        requires = fq["requires_review"]
                        icon = "Review" if requires else "Info"
                        severity = fq["severity"]
                        if requires:
                            st.warning(f"{icon}: {fq['message']} (severity={severity}, confidence={fq['confidence']:.2f})")
                        else:
                            st.info(f"{icon}: {fq['message']} (severity={severity}, confidence={fq['confidence']:.2f})")
                        st.caption(f"Suggested: {fq['suggested_action']}  |  Flag ID: {fq['flag_id']}")

            # --- Relationships ---
            if view_mode == "Advanced":
                with st.expander("Relationships", expanded=False):
                    if not rels:
                        st.caption("No relationships")
                    else:
                        st.dataframe([{
                            "rel_type": r.get("rel_type", ""),
                            "source_id": r.get("source_id", ""),
                            "target_id": r.get("target_id", ""),
                            "run_id": (r.get("metadata", {}) or {}).get("run_id", r.get("run_id", "")),
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
                st.caption("Rerun will create new L2 derived files. Old L2 files will be kept. Replacement relationships will be recorded as replaces/replaced_by. Raw files will not be modified.")
                process_mode = st.selectbox(
                    "Model mode",
                    ["local", "auto", "cloud"],
                    key="detail_model_mode",
                    index=["local", "auto", "cloud"].index(st.session_state.model_mode),
                )
                notice = cloud_mode_notice(process_mode)
                if notice:
                    st.warning(notice)
                if st.button("Process / Rerun Task", key="btn_process_task"):
                    with st.spinner(f"Processing {tid}..."):
                        result = do_process_task(ws, tid, process_mode)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(safe_ui_error(result["message"]))

                if st.button("Process All Tasks", key="btn_process_all"):
                    with st.spinner(f"Processing all tasks..."):
                        result = do_process_all(ws, process_mode)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(safe_ui_error(result["message"]))

            with col_review:
                st.markdown("**Review**")
                review_action = st.selectbox(
                    "Action",
                    ["approve", "return_for_rerun", "mark_low_confidence", "deprecate"],
                    key="review_action",
                )
                reviewer = st.text_input("Reviewer", key="review_reviewer")
                comment = st.text_area("Comment", key="review_comment")
                target_type = st.selectbox(
                    "Target type",
                    ["task", "quality_flag", "data_object", "derived_file"],
                    key="review_target_type",
                )
                target_id = st.text_input(
                    "Target ID (leave empty for current task)",
                    key="review_target_id",
                    placeholder="e.g. flag_001",
                )
                if flags:
                    flag_ids = [f.get("flag_id", "") for f in flags if f.get("flag_id")]
                    if flag_ids:
                        st.caption(f"Available flag IDs: {', '.join(flag_ids)}")

                if review_action == "deprecate":
                    confirm = st.checkbox("I confirm this will deprecate the current results", key="deprecate_confirm")
                else:
                    confirm = True

                if st.button("Submit Review", key="btn_review", disabled=not confirm):
                    with st.spinner("Recording review..."):
                        result = do_review(ws, tid, review_action, reviewer, comment, target_type, target_id)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(safe_ui_error(result["message"]))

            st.divider()

            st.subheader("Validate Package")
            if st.button("Validate Package", key="btn_validate"):
                with st.spinner("Validating..."):
                    val_result = do_validate_package(ws, tid)
                status_label = val_result.get("status", "pass").upper()
                if status_label == "PASS":
                    st.success(f"Status: {status_label}")
                elif status_label == "WARN":
                    st.warning(f"Status: {status_label}")
                else:
                    st.error(f"Status: {status_label}")
                if val_result.get("errors"):
                    for e in val_result["errors"]:
                        st.text(safe_display_text(str(e)))
                if val_result.get("warnings"):
                    for w in val_result["warnings"]:
                        st.caption(safe_display_text(str(w)))
                if val_result.get("report_path"):
                    st.caption(f"Report: {val_result['report_path']}")
                if val_result.get("validated_at"):
                    st.caption(f"Validated: {val_result['validated_at']}")

            st.divider()
            st.subheader("Export Review Package")
            if st.button("Export Review Package", key="btn_export"):
                with st.spinner("Exporting..."):
                    exp = do_export_package(ws, tid)
                if exp.get("success"):
                    if exp.get("validation_status") == "error":
                        st.warning("EXPORTED WITH VALIDATION ERRORS")
                    st.success(exp.get("message", ""))
                    if exp.get("zip_path"):
                        zip_path = Path(exp["zip_path"])
                        if zip_path.exists():
                            with open(zip_path, "rb") as zf:
                                st.download_button("Download ZIP", zf.read(), file_name=zip_path.name, mime="application/zip")
                else:
                    st.error(safe_ui_error(exp.get("message", "Export failed")))


# ==== Tab: Sample View ====
with tab_samples:
    st.subheader("Sample Index")

    if st.button("Rebuild Sample Index", key="btn_rebuild_index"):
        with st.spinner("Building..."):
            idx = do_index_samples(ws)
        st.success(f"Indexed {len(idx.get('samples', []))} samples, {len(idx.get('unlinked_tasks', []))} unlinked")
        st.rerun()

    idx_data = read_sample_index(ws)
    samples = idx_data.get("samples", [])
    unlinked = idx_data.get("unlinked_tasks", [])

    if not samples and not unlinked:
        st.info("No sample index found. Click 'Rebuild Sample Index' to generate one.")
    else:
        st.metric("Samples", len(samples))
        st.metric("Unlinked Tasks", len(unlinked))

        if idx_data.get("warnings"):
            for w in idx_data["warnings"]:
                st.warning(w)

        if unlinked:
            with st.expander(f"Unlinked Tasks ({len(unlinked)})", expanded=False):
                for u in unlinked:
                    st.text(f"{u.get('task_id', '?')}: {u.get('reason', '')} (type: {u.get('data_type', '?')})")

        if samples:
            batch_filter = st.selectbox("Batch filter", ["All"] + sorted(set(s.get("batch_id", "") for s in samples if s.get("batch_id"))))
            for s in samples:
                bid = s.get("batch_id", "")
                if batch_filter != "All" and bid != batch_filter:
                    continue
                with st.expander(f"{s['sample_id']}  {('Batch: ' + bid) if bid else ''}", expanded=False):
                    for rt in s.get("related_tasks", []):
                        st.caption(f"{rt['task_id']} — {rt['data_type']} (source: {rt['source']}, confidence: {rt['confidence']:.2f})")
                    st.caption(f"Available data: {', '.join(s.get('available_data', []))}")


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
### Data Input Contract

推荐输入格式参见项目文档 `docs/data_input_contract.md`。

核心要点：
- CSV 首行为列标题，列名包含单位（如 `thickness_um`, `wavenumber_cm-1`）
- 数值列为纯数字，缺失值用空白或 `NA`
- 图像保留坐标轴、图例、单位、标尺
- 观测文本区分事实和推测
- 不满足规范的数据会产生 `requires_review` 标记，不会静默失败
    """)

    st.divider()

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
