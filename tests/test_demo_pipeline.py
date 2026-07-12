"""End-to-end integration test using the demo data."""
import shutil
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from data_agent.ingest import ingest_inbox
from data_agent.process import process_all_tasks, process_single_task
from data_agent.reviews import write_review
from data_agent.db import init_db, get_conn
from data_agent.config import get_tasks_dir
from data_agent.package import load_manifest


@pytest.fixture(scope="module")
def workspace(demo_inbox):
    if not demo_inbox:
        pytest.skip("DATA_AGENT_DEMO_INBOX is not configured; optional demo integration tests skipped.")
    tmp = tempfile.mkdtemp()
    ws = Path(tmp)
    conn = init_db(ws)
    ingest_inbox(demo_inbox, ws, conn)
    conn.close()
    process_all_tasks(ws, "local")
    yield ws
    shutil.rmtree(tmp)


def test_nine_tasks_registered(workspace):
    tasks_dir = get_tasks_dir(workspace)
    tasks = [d.name for d in tasks_dir.iterdir() if d.is_dir() and d.name.startswith("task_")]
    assert len(tasks) == 9, f"Expected 9 tasks, got {len(tasks)}"


def test_raw_copies_are_l1(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        raw_dir = task_dir / "raw"
        assert raw_dir.exists(), f"raw/ missing in {task_dir.name}"
        files = list(raw_dir.glob("*"))
        assert len(files) > 0, f"No raw files in {task_dir.name}"


def test_each_task_has_manifest(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        manifest = load_manifest(task_dir)
        assert manifest is not None, f"manifest.json missing in {task_dir.name}"


def test_thickness_quality_flags(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        raw_files = list((task_dir / "raw").glob("sample_thickness*"))
        if not raw_files:
            continue
        flags_path = task_dir / "logs" / "quality_flags.json"
        assert flags_path.exists(), "quality_flags.json missing for thickness task"
        with open(flags_path) as f:
            flags = json.load(f)
        messages = " ".join([fl.get("message", "") for fl in flags])
        assert "missing" in messages.lower() or "Missing" in messages, f"No missing flag in {task_dir.name}"
        assert "9999" in messages or "outlier" in messages.lower(), f"No outlier flag in {task_dir.name}"


def test_thickness_summary_stats(workspace):
    import pandas as pd
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        raw_files = list((task_dir / "raw").glob("sample_thickness*"))
        if not raw_files:
            continue
        csv_files = list((task_dir / "derived").glob("*thickness_summary*"))
        assert len(csv_files) > 0, f"thickness summary not found in {task_dir.name}"
        df = pd.read_csv(csv_files[0])
        a01 = df[df["sample_id"] == "A01"]
        a02 = df[df["sample_id"] == "A02"]
        assert int(a01["missing_count"].iloc[0]) == 1, f"A01 missing_count != 1"
        assert int(a02["outlier_count"].iloc[0]) == 1, f"A02 outlier_count != 1"


def test_resistance_unit_conversion(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        raw_files = list((task_dir / "raw").glob("sample_resistance*"))
        if not raw_files:
            continue
        flags_path = task_dir / "logs" / "quality_flags.json"
        with open(flags_path) as f:
            flags = json.load(f)
        messages = " ".join([fl.get("message", "") for fl in flags])
        assert "kOhm" in messages, f"Unit conversion not recorded in {task_dir.name}"


def test_observation_interpretation_candidate(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        raw_files = list((task_dir / "raw").glob("observation*"))
        if not raw_files:
            continue
        output_paths = list((task_dir / "derived").glob("*structured_observations*"))
        assert len(output_paths) > 0, f"structured_observations.json missing in {task_dir.name}"
        output_path = output_paths[0]
        with open(output_path) as f:
            data = json.load(f)
        interpretations = data.get("interpretation_candidates", [])
        assert len(interpretations) > 0, f"No interpretation_candidates found in {task_dir.name}"
        assert any("可能是" in i for i in interpretations), f"可能是 not in interpretation_candidates"


def test_ftir_peaks(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        raw_files = list((task_dir / "raw").glob("sample_ftir_raw*"))
        if not raw_files:
            continue
        peak_tables = list((task_dir / "derived").glob("*ftir_peak_table*"))
        assert len(peak_tables) > 0, "ftir_peak_table.csv missing"
        reconstructed_files = list((task_dir / "derived").glob("*ftir_reconstructed*"))
        assert len(reconstructed_files) > 0, "ftir_reconstructed.png missing"


def test_uvvis_peaks(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        raw_files = list((task_dir / "raw").glob("sample_uvvis_raw*"))
        if not raw_files:
            continue
        peak_tables = list((task_dir / "derived").glob("*uvvis_peak_table*"))
        assert len(peak_tables) > 0, "uvvis_peak_table.csv missing"
        reconstructed_files = list((task_dir / "derived").glob("*uvvis_reconstructed*"))
        assert len(reconstructed_files) > 0, "uvvis_reconstructed.png missing"


def test_chart_images_have_metadata(workspace):
    chart_tasks_found = 0
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        raw_files = list((task_dir / "raw").glob("*chart*"))
        if not raw_files:
            continue
        chart_tasks_found += 1
        meta_paths = list((task_dir / "derived").glob("*chart_metadata*"))
        assert len(meta_paths) > 0, f"chart_metadata.json missing in {task_dir.name}"
    assert chart_tasks_found == 2, f"Expected 2 chart tasks, got {chart_tasks_found}"


def test_metadata_has_run_and_l2(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        raw_files = list((task_dir / "raw").glob("sample_metadata*"))
        if not raw_files:
            continue
        manifest = json.loads((task_dir / "manifest.json").read_text())
        assert len(manifest.get("run_ids", [])) >= 1, f"metadata task has no runs"
        assert len(manifest.get("derived_files", [])) >= 1, f"metadata task has no derived files"
        index_files = list((task_dir / "derived").glob("*metadata_index*"))
        assert len(index_files) >= 1, f"metadata_index.json not found"


def test_visual_image_has_manual_review_flag(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        raw_files = list((task_dir / "raw").glob("sample_surface*"))
        if not raw_files:
            continue
        flags_path = task_dir / "logs" / "quality_flags.json"
        with open(flags_path) as f:
            flags = json.load(f)
        messages = " ".join([fl.get("message", "") for fl in flags])
        has_manual = "manual" in messages.lower() or "Manual" in messages
        assert has_manual, f"Missing manual review flag in {task_dir.name}"


def test_review_write(workspace):
    task_dirs = sorted((workspace / "tasks").iterdir())
    assert len(task_dirs) > 0
    first_task = task_dirs[0].name
    review = write_review(workspace, first_task, "approve", "ZQ", "integration test")
    review_path = workspace / "tasks" / first_task / "reviews" / "review_records.json"
    assert review_path.exists(), "review_records.json not created"
    with open(review_path) as f:
        records = json.load(f)
    assert len(records) > 0


def test_processing_report_exists(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        report_path = task_dir / "logs" / "processing_report.md"
        assert report_path.exists(), f"processing_report.md missing in {task_dir.name}"


def test_no_causal_conclusion_in_reports(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        report_path = task_dir / "logs" / "processing_report.md"
        if report_path.exists():
            text = report_path.read_text(encoding="utf-8")
            assert "结论" not in text, f"Found 结论 in report {task_dir.name}"
            assert "添加剂提高" not in text, f"Found causal claim in report {task_dir.name}"


def test_manifest_derived_files_exist(workspace):
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        manifest = json.loads((task_dir / "manifest.json").read_text())
        for df_path in manifest.get("derived_files", []):
            full_path = task_dir / df_path
            assert full_path.exists(), f"manifest derived_file not found: {full_path} in {task_dir.name}"


def test_run_output_ids_in_data_objects(workspace):
    db_path = workspace / "agent.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT run_id, output_data_ids FROM processing_runs WHERE status = 'succeeded'").fetchall()
    for r in rows:
        output_ids = json.loads(r["output_data_ids"]) if r["output_data_ids"] else []
        for oid in output_ids:
            obj_row = conn.execute("SELECT object_id FROM data_objects WHERE object_id = ?", (oid,)).fetchone()
            assert obj_row is not None, f"output_data_ids {oid} not found in data_objects for run {r['run_id']}"
    conn.close()


def test_l2_has_derived_from(workspace):
    db_path = workspace / "agent.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    l2_rows = conn.execute("SELECT object_id, task_id FROM data_objects WHERE lifecycle = 'L2'").fetchall()
    for l2 in l2_rows:
        rel_row = conn.execute(
            "SELECT rel_id FROM relationships WHERE target_id = ? AND rel_type = 'derived_from'",
            (l2["object_id"],),
        ).fetchone()
        assert rel_row is not None, f"L2 object {l2['object_id']} has no derived_from relationship"
    conn.close()


def test_relationships_json_vs_db(workspace):
    db_path = workspace / "agent.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    for task_dir in (workspace / "tasks").iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        tid = task_dir.name
        rels_path = task_dir / "logs" / "relationships.json"
        if not rels_path.exists():
            continue
        json_rels = json.loads(rels_path.read_text())
        db_rels = conn.execute("SELECT count(*) as cnt FROM relationships WHERE task_id = ?", (tid,)).fetchone()
        assert len(json_rels) >= db_rels["cnt"], f"relationships.json ({len(json_rels)}) has fewer entries than DB ({db_rels['cnt']}) for {tid}"
    conn.close()


def test_rerun_produces_replace_relationships(demo_inbox):
    if not demo_inbox:
        pytest.skip("DATA_AGENT_DEMO_INBOX is not configured; optional demo integration tests skipped.")
    tmp = tempfile.mkdtemp()
    ws = Path(tmp)
    conn = init_db(ws)
    ingest_inbox(demo_inbox, ws, conn)
    conn.close()

    process_single_task(ws, "task_0007", "local")
    process_single_task(ws, "task_0007", "local")

    conn2 = sqlite3.connect(str(ws / "agent.sqlite"))
    conn2.row_factory = sqlite3.Row
    rows = conn2.execute("SELECT rel_type, count(*) as cnt FROM relationships WHERE task_id = 'task_0007' GROUP BY rel_type").fetchall()
    type_counts = {r["rel_type"]: r["cnt"] for r in rows}
    conn2.close()

    assert type_counts.get("replaces", 0) >= 1, "No replaces relationships after rerun"
    assert type_counts.get("replaced_by", 0) >= 1, "No replaced_by relationships after rerun"

    derived_files = list((ws / "tasks" / "task_0007" / "derived").glob("*thickness*"))
    assert len(derived_files) >= 4, "Old L2 files not preserved: expected >=4 thickness derived files"

    shutil.rmtree(tmp)


def test_open_print_command():
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "data_agent", "open", "--workspace", "work/check-ws", "--task", "task_0001", "--print-command"],
        capture_output=True, text=True, timeout=10,
    )
    output = result.stdout + result.stderr
    assert "--print-command mode" in output, "--print-command flag not recognized"
    assert "Executable:" in output, "Should print executable path"
    assert "DATA_AGENT_WORKSPACE" in output, "Should print workspace env var"
    assert "DATA_AGENT_TASK_ID" in output, "Should print task id env var"
