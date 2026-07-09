"""Tests for DB and evidence package."""
import tempfile
from pathlib import Path
from data_agent.db import init_db, get_conn, insert_file, insert_processing_run, insert_quality_flag, insert_review
from data_agent.schemas import (
    FileRecord,
    ProcessingRun,
    QualityFlag,
    ReviewRecord,
    ReviewAction,
)
from data_agent.package import create_task_dir, write_manifest, load_manifest
from data_agent.schemas import TaskManifest, LifecycleLevel


def test_init_db_insert_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        conn = init_db(ws)
        record = FileRecord(
            task_id="task_test",
            original_name="test.csv",
            stored_path="/tmp/test.csv",
            checksum_sha256="abc",
            size_bytes=100,
            lifecycle=LifecycleLevel.L1,
        )
        insert_file(conn, record)
        conn.close()

        conn2 = get_conn(ws)
        row = conn2.execute("SELECT * FROM files WHERE file_id = ?", (record.file_id,)).fetchone()
        assert row is not None
        assert row["original_name"] == "test.csv"
        conn2.close()


def test_init_db_insert_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        conn = init_db(ws)
        run = ProcessingRun(task_id="task_test", tool_name="test")
        insert_processing_run(conn, run)
        conn.close()

        conn2 = get_conn(ws)
        row = conn2.execute("SELECT * FROM processing_runs WHERE run_id = ?", (run.run_id,)).fetchone()
        assert row is not None
        conn2.close()


def test_init_db_insert_flag():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        conn = init_db(ws)
        flag = QualityFlag(task_id="task_test", message="test", requires_review=True)
        insert_quality_flag(conn, flag)
        conn.close()

        conn2 = get_conn(ws)
        row = conn2.execute("SELECT * FROM quality_flags WHERE flag_id = ?", (flag.flag_id,)).fetchone()
        assert row is not None
        conn2.close()


def test_init_db_insert_review():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        conn = init_db(ws)
        review = ReviewRecord(task_id="task_test", reviewer="ZQ", action=ReviewAction.APPROVE, comment="ok")
        insert_review(conn, review)
        conn.close()

        conn2 = get_conn(ws)
        row = conn2.execute("SELECT * FROM reviews WHERE review_id = ?", (review.review_id,)).fetchone()
        assert row is not None
        conn2.close()


def test_manifest_write_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        task_dir = Path(tmpdir)
        create_task_dir(task_dir)
        manifest = TaskManifest(task_id="t1", input_files=["a.csv"])
        write_manifest(task_dir, manifest)
        loaded = load_manifest(task_dir)
        assert loaded is not None
        assert loaded.task_id == "t1"
        assert loaded.input_files == ["a.csv"]
