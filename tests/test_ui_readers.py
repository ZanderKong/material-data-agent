"""Tests for UI readers helpers."""
import json
import tempfile
from pathlib import Path

import pytest

from data_agent.ui.readers import (
    read_workspace_summary,
    read_task_list,
    read_raw_files,
    read_derived_files,
    read_processing_runs,
    read_quality_flags,
    read_review_records,
    read_model_profiles,
)
from data_agent.ingest import ingest_inbox
from data_agent.db import init_db
from tests.conftest import _resolve_demo_inbox


@pytest.fixture
def empty_ws():
    tmp = tempfile.mkdtemp()
    ws = Path(tmp)
    yield ws


class TestReadWorkspaceSummary:
    def test_empty_workspace(self, empty_ws):
        summary = read_workspace_summary(empty_ws)
        assert summary["task_count"] == 0
        assert not summary["has_db"]

    def test_with_tasks(self):
        demo = _resolve_demo_inbox()
        if not demo:
            pytest.skip("Demo inbox not available")
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        ws = Path(tmp)
        conn = init_db(ws)
        ingest_inbox(demo, ws, conn)
        conn.close()
        try:
            summary = read_workspace_summary(ws)
            assert summary["task_count"] == 9
            assert summary["has_db"]
            assert summary["has_tasks_dir"]
            assert "ingested" in summary.get("status_counts", {})
        finally:
            shutil.rmtree(tmp)


class TestReadTaskList:
    def test_empty(self, empty_ws):
        tasks = read_task_list(empty_ws)
        assert tasks == []

    def test_with_tasks(self):
        demo = _resolve_demo_inbox()
        if not demo:
            pytest.skip("Demo inbox not available")
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        ws = Path(tmp)
        conn = init_db(ws)
        ingest_inbox(demo, ws, conn)
        conn.close()
        try:
            tasks = read_task_list(ws)
            assert len(tasks) == 9
            for t in tasks:
                assert "task_id" in t
                assert t["task_id"].startswith("task_")
                assert "input_files" in t
                assert "status" in t
        finally:
            shutil.rmtree(tmp)


class TestReadRawFiles:
    def test_no_raw(self, empty_ws):
        task_dir = empty_ws / "tasks" / "task_0001"
        assert read_raw_files(task_dir) == []

    def test_with_files(self):
        demo = _resolve_demo_inbox()
        if not demo:
            pytest.skip("Demo inbox not available")
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        ws = Path(tmp)
        conn = init_db(ws)
        ingest_inbox(demo, ws, conn)
        conn.close()
        try:
            task_dir = ws / "tasks" / "task_0001"
            files = read_raw_files(task_dir)
            assert len(files) >= 1
            assert all("name" in f and "size_bytes" in f for f in files)
        finally:
            shutil.rmtree(tmp)


class TestReadDerivedFiles:
    def test_no_derived(self, empty_ws):
        task_dir = empty_ws / "tasks" / "task_0001"
        assert read_derived_files(task_dir) == []


class TestReadProcessingRuns:
    def test_empty(self, empty_ws):
        task_dir = empty_ws / "tasks" / "task_0001"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "logs").mkdir(exist_ok=True)
        runs = read_processing_runs(task_dir)
        assert runs == []


class TestReadQualityFlags:
    def test_empty(self, empty_ws):
        task_dir = empty_ws / "tasks" / "task_0001"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "logs").mkdir(exist_ok=True)
        flags = read_quality_flags(task_dir)
        assert flags == []


class TestReadReviewRecords:
    def test_empty(self, empty_ws):
        task_dir = empty_ws / "tasks" / "task_0001"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "reviews").mkdir(exist_ok=True)
        reviews = read_review_records(task_dir)
        assert reviews == []


class TestReadModelProfiles:
    def test_returns_list(self):
        profiles = read_model_profiles()
        assert isinstance(profiles, list)
        for p in profiles:
            assert "name" in p
            assert "api_key" in p
            assert p["api_key"] in ("configured", "missing", "")


class TestDictError:
    def test_manifest_none(self, empty_ws):
        from data_agent.ui.readers import read_task_manifest
        task_dir = empty_ws / "tasks" / "task_0001"
        task_dir.mkdir(parents=True, exist_ok=True)
        result = read_task_manifest(task_dir)
        assert result is None
