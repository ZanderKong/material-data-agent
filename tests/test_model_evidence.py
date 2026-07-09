"""Tests for model evidence writing and end-to-end behavior."""
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from data_agent.ingest import ingest_inbox
from data_agent.process import process_single_task, process_all_tasks
from data_agent.db import init_db


TEST_SECRET = "unit-test-secret-token-xyz"


class TestModelEvidenceLocal:
    @pytest.fixture(scope="module")
    def ws_local(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        tmp = tempfile.mkdtemp()
        ws = Path(tmp)
        conn = init_db(ws)
        ingest_inbox(demo_inbox, ws, conn)
        conn.close()
        count = process_all_tasks(ws, "local")
        assert count > 0, "No tasks processed"
        yield ws
        shutil.rmtree(tmp)

    def test_local_makes_no_network_calls(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        tmp = tempfile.mkdtemp()
        ws = Path(tmp)
        conn = init_db(ws)
        ingest_inbox(demo_inbox, ws, conn)
        conn.close()
        with patch("data_agent.model_adapters.openai_compatible.requests.post") as mock_post:
            count = process_all_tasks(ws, "local")
        mock_post.assert_not_called()
        assert count > 0
        shutil.rmtree(tmp)

    def test_model_objects_count_equals_model_runs_count(self, ws_local):
        db_path = ws_local / "agent.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        model_objects = conn.execute(
            "SELECT count(*) as cnt FROM data_objects WHERE data_type = 'model_result'"
        ).fetchone()
        model_runs = conn.execute(
            "SELECT count(*) as cnt FROM processing_runs WHERE tool_name LIKE 'model:%'"
        ).fetchone()
        conn.close()
        assert model_objects["cnt"] == model_runs["cnt"], \
            f"model_objects={model_objects['cnt']} != model_runs={model_runs['cnt']}"

    def test_no_empty_run_ids(self, ws_local):
        db_path = ws_local / "agent.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        empty_runs = conn.execute(
            "SELECT count(*) as cnt FROM processing_runs WHERE run_id = ''"
        ).fetchone()
        conn.close()
        assert empty_runs["cnt"] == 0, "Found processing runs with empty run_id"

    def test_manifest_no_empty_run_ids(self, ws_local):
        for task_dir in (ws_local / "tasks").iterdir():
            if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                continue
            manifest = json.loads((task_dir / "manifest.json").read_text())
            empties = [r for r in manifest.get("run_ids", []) if not r]
            assert not empties, f"{task_dir.name} manifest contains empty run_ids"

    def test_model_result_json_has_full_wrapper_fields(self, ws_local):
        required = {
            "success", "role", "provider", "mode", "output_json",
            "schema_version", "prompt_version",
        }
        for task_dir in (ws_local / "tasks").iterdir():
            if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                continue
            for derived in (task_dir / "derived").glob("*model_result*.json"):
                data = json.loads(derived.read_text())
                missing = required - set(data)
                assert not missing, f"{derived} missing fields: {missing}"
                assert "output_json" in data

    def test_model_result_json_not_persist_forbidden_fields(self, ws_local):
        forbidden = {"final_conclusion", "mechanism_explanation", "experiment_recommendation"}
        for task_dir in (ws_local / "tasks").iterdir():
            if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                continue
            for derived in (task_dir / "derived").glob("*model_result*"):
                content = derived.read_text()
                for fk in forbidden:
                    assert fk not in content, f"{fk} found in {derived}"

    def test_model_l2_has_derived_from(self, ws_local):
        db_path = ws_local / "agent.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        model_objects = conn.execute(
            "SELECT object_id, task_id FROM data_objects WHERE data_type = 'model_result'"
        ).fetchall()
        for obj in model_objects:
            rel = conn.execute(
                "SELECT rel_id FROM relationships WHERE target_id = ? AND rel_type = 'derived_from'",
                (obj["object_id"],),
            ).fetchone()
            assert rel is not None, f"Model result {obj['object_id']} has no derived_from"
        conn.close()

    def test_model_derived_from_points_to_model_run(self, ws_local):
        db_path = ws_local / "agent.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT d.subtype, pr.tool_name, r.metadata
            FROM relationships r
            JOIN data_objects d ON r.target_id = d.object_id
            JOIN processing_runs pr ON json_extract(r.metadata, '$.run_id') = pr.run_id
            WHERE d.data_type = 'model_result' AND r.rel_type = 'derived_from'
        """).fetchall()
        for row in rows:
            assert row["tool_name"].startswith("model:"), \
                f"Model result target {row['subtype']} derived_from run tool_name={row['tool_name']} not model:*"
        assert len(rows) > 0, "No model_result derived_from relationships found"
        conn.close()

    def test_no_api_keys_in_sqlite(self, ws_local):
        db_path = ws_local / "agent.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        tables = ["files", "data_objects", "processing_runs", "quality_flags", "relationships", "reviews", "tasks"]
        for table in tables:
            try:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                for row in rows:
                    row_str = str(dict(row))
                    assert "sk-" not in row_str, f"API key pattern found in {table}"
            except sqlite3.OperationalError:
                pass
        conn.close()

    def test_no_api_keys_in_markdown_report(self, ws_local):
        for task_dir in (ws_local / "tasks").iterdir():
            if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                continue
            report = task_dir / "logs" / "processing_report.md"
            if report.exists():
                text = report.read_text()
                assert "sk-" not in text, f"API key pattern found in report {task_dir.name}"

    def test_no_api_keys_in_derived_json(self, ws_local):
        for task_dir in (ws_local / "tasks").iterdir():
            if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                continue
            for derived in (task_dir / "derived").glob("*.json"):
                text = derived.read_text()
                assert "sk-" not in text, f"API key pattern found in {derived}"

    def test_auto_without_key_does_not_crash(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        tmp = tempfile.mkdtemp()
        ws = Path(tmp)
        conn = init_db(ws)
        ingest_inbox(demo_inbox, ws, conn)
        conn.close()
        try:
            count = process_all_tasks(ws, "auto")
            assert count > 0
        except Exception as e:
            assert False, f"auto mode should not crash: {e}"
        finally:
            shutil.rmtree(tmp)


class TestModelEvidenceSecretLeak:
    def test_exact_secret_not_in_sqlite(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        os.environ["TEST_MODEL_KEY"] = TEST_SECRET
        os.environ["FAST_MODEL_API_KEY"] = TEST_SECRET
        try:
            tmp = tempfile.mkdtemp()
            ws = Path(tmp)
            conn = init_db(ws)
            ingest_inbox(demo_inbox, ws, conn)
            conn.close()
            process_all_tasks(ws, "local")

            db_path = ws / "agent.sqlite"
            conn2 = sqlite3.connect(str(db_path))
            conn2.row_factory = sqlite3.Row
            tables = ["files", "data_objects", "processing_runs", "quality_flags", "relationships", "reviews", "tasks"]
            for table in tables:
                try:
                    rows = conn2.execute(f"SELECT * FROM {table}").fetchall()
                    for row in rows:
                        row_str = str(dict(row))
                        assert TEST_SECRET not in row_str, f"Exact secret found in {table}"
                except sqlite3.OperationalError:
                    pass
            conn2.close()
            shutil.rmtree(tmp)
        finally:
            del os.environ["TEST_MODEL_KEY"]
            del os.environ["FAST_MODEL_API_KEY"]

    def test_exact_secret_not_in_derived_json(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        os.environ["TEST_MODEL_KEY"] = TEST_SECRET
        try:
            tmp = tempfile.mkdtemp()
            ws = Path(tmp)
            conn = init_db(ws)
            ingest_inbox(demo_inbox, ws, conn)
            conn.close()
            process_all_tasks(ws, "local")

            for task_dir in (ws / "tasks").iterdir():
                if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                    continue
                for derived in (task_dir / "derived").glob("*.json"):
                    text = derived.read_text()
                    assert TEST_SECRET not in text, f"Exact secret found in {derived}"
            shutil.rmtree(tmp)
        finally:
            del os.environ["TEST_MODEL_KEY"]

    def test_exact_secret_not_in_markdown_report(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        os.environ["FAST_MODEL_API_KEY"] = TEST_SECRET
        try:
            tmp = tempfile.mkdtemp()
            ws = Path(tmp)
            conn = init_db(ws)
            ingest_inbox(demo_inbox, ws, conn)
            conn.close()
            process_all_tasks(ws, "local")

            for task_dir in (ws / "tasks").iterdir():
                if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                    continue
                report = task_dir / "logs" / "processing_report.md"
                if report.exists():
                    text = report.read_text()
                    assert TEST_SECRET not in text, f"Exact secret found in report {task_dir.name}"
            shutil.rmtree(tmp)
        finally:
            del os.environ["FAST_MODEL_API_KEY"]

    def test_exact_secret_not_in_logs_json(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        os.environ["BEST_MODEL_API_KEY"] = TEST_SECRET
        try:
            tmp = tempfile.mkdtemp()
            ws = Path(tmp)
            conn = init_db(ws)
            ingest_inbox(demo_inbox, ws, conn)
            conn.close()
            process_all_tasks(ws, "local")

            for task_dir in (ws / "tasks").iterdir():
                if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                    continue
                for log_file in (task_dir / "logs").glob("*.json"):
                    text = log_file.read_text()
                    assert TEST_SECRET not in text, f"Exact secret found in {log_file}"
            shutil.rmtree(tmp)
        finally:
            del os.environ["BEST_MODEL_API_KEY"]


class TestModelEvidenceRerun:
    def test_rerun_preserves_old_l2_with_model_results(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        tmp = tempfile.mkdtemp()
        ws = Path(tmp)
        conn = init_db(ws)
        ingest_inbox(demo_inbox, ws, conn)
        conn.close()

        task_id = "task_0007"
        process_single_task(ws, task_id, "local")
        process_single_task(ws, task_id, "local")

        db_path = ws / "agent.sqlite"
        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        rows = conn2.execute(
            "SELECT rel_type, count(*) as cnt FROM relationships WHERE task_id = ? GROUP BY rel_type",
            (task_id,),
        ).fetchall()
        type_counts = {r["rel_type"]: r["cnt"] for r in rows}
        conn2.close()

        assert type_counts.get("replaces", 0) >= 1, "No replaces after rerun with models"
        assert type_counts.get("replaced_by", 0) >= 1, "No replaced_by after rerun with models"

        shutil.rmtree(tmp)

    def test_rerun_replacement_same_subtype(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        tmp = tempfile.mkdtemp()
        ws = Path(tmp)
        conn = init_db(ws)
        ingest_inbox(demo_inbox, ws, conn)
        conn.close()

        process_single_task(ws, "task_0001", "local")
        process_single_task(ws, "task_0001", "local")

        db_path = ws / "agent.sqlite"
        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        rows = conn2.execute("""
            SELECT d1.subtype as src_subtype, d2.subtype as tgt_subtype
            FROM relationships r
            JOIN data_objects d1 ON r.source_id = d1.object_id
            JOIN data_objects d2 ON r.target_id = d2.object_id
            WHERE r.rel_type = 'replaces'
        """).fetchall()
        for row in rows:
            assert row["src_subtype"] == row["tgt_subtype"], \
                f"replaces across subtypes: {row['src_subtype']} -> {row['tgt_subtype']}"
        assert len(rows) > 0, "No replaces relationships found"
        conn2.close()

        shutil.rmtree(tmp)

    def test_rerun_no_self_replacement(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        tmp = tempfile.mkdtemp()
        ws = Path(tmp)
        conn = init_db(ws)
        ingest_inbox(demo_inbox, ws, conn)
        conn.close()

        process_single_task(ws, "task_0001", "local")
        process_single_task(ws, "task_0001", "local")

        db_path = ws / "agent.sqlite"
        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        self_repl = conn2.execute(
            "SELECT count(*) as cnt FROM relationships WHERE rel_type in ('replaces','replaced_by') AND source_id = target_id"
        ).fetchone()
        conn2.close()
        assert self_repl["cnt"] == 0, f"Found {self_repl['cnt']} self-replacement relationships"

        shutil.rmtree(tmp)

    def test_model_l2_in_manifest_derived_files(self, demo_inbox):
        if not demo_inbox:
            pytest.skip("Demo inbox not available")
        tmp = tempfile.mkdtemp()
        ws = Path(tmp)
        conn = init_db(ws)
        ingest_inbox(demo_inbox, ws, conn)
        conn.close()
        process_all_tasks(ws, "local")

        for task_dir in (ws / "tasks").iterdir():
            if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                continue
            manifest = json.loads((task_dir / "manifest.json").read_text())
            for df in manifest.get("derived_files", []):
                full_path = task_dir / df
                assert full_path.exists(), f"manifest derived_file not found: {full_path}"

        shutil.rmtree(tmp)
