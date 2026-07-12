"""Tests for package validation – remediation: path safety, ID checks, relationship integrity, report failure."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data_agent.validation import (
    validate_task,
    validate_all,
    _safe_resolve,
    _strict_read_json_list,
    _sha256_file,
)


class TestSafeResolve:
    def test_normal_relative_accepted(self, tmp_path):
        td = tmp_path / "task"
        td.mkdir()
        (td / "file.txt").write_text("x")
        result = _safe_resolve(td, "file.txt")
        assert result is not None
        assert result.name == "file.txt"

    def test_absolute_rejected(self, tmp_path):
        td = tmp_path / "task"
        td.mkdir()
        assert _safe_resolve(td, "/etc/passwd") is None

    def test_absolute_inside_task_rejected(self, tmp_path):
        td = tmp_path / "task"
        td.mkdir()
        abs_inside = str((td / "secret.txt").resolve())
        assert _safe_resolve(td, abs_inside) is None

    def test_dot_dot_rejected(self, tmp_path):
        td = tmp_path / "task"
        td.mkdir()
        (tmp_path / "outside.txt").write_text("x")
        assert _safe_resolve(td, "../outside.txt") is None

    def test_sibling_prefix_rejected(self, tmp_path):
        td = tmp_path / "tasks" / "task_0001"
        td.mkdir(parents=True)
        evil = tmp_path / "tasks" / "task_evil"
        evil.mkdir()
        (evil / "secret.txt").write_text("x")
        assert _safe_resolve(td, "../task_evil/secret.txt") is None

    def test_empty_rejected(self, tmp_path):
        assert _safe_resolve(tmp_path, "") is None
        assert _safe_resolve(tmp_path, "   ") is None

    def test_raw_manifest_traversal_rejected(self, tmp_path):
        td = tmp_path / "task_0001"
        td.mkdir()
        raw_dir = td / "raw"
        raw_dir.mkdir()
        evil = tmp_path / "evil.txt"
        evil.write_text("x")
        from data_agent.validation import _resolve_manifest_raw
        assert _resolve_manifest_raw(td, "../../evil.txt") is None


class TestStrictReaders:
    def test_list_with_scalar_item_raises(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text('[{"a":1}, "string"]')
        with pytest.raises(ValueError, match="not a dict"):
            _strict_read_json_list(f)

    def test_list_with_null_item_raises(self, tmp_path):
        f = tmp_path / "null.json"
        f.write_text('[{"a":1}, null]')
        with pytest.raises(ValueError):
            _strict_read_json_list(f)

    def test_list_all_dicts_ok(self, tmp_path):
        f = tmp_path / "ok.json"
        f.write_text('[{"a":1}, {"b":2}]')
        result = _strict_read_json_list(f)
        assert len(result) == 2


class TestValidateTask:
    def _build_ws(self, tmp_path: Path, **kwargs) -> Path:
        ws = tmp_path / "ws"
        ws.mkdir()
        td = ws / "tasks" / "task_0001"
        td.mkdir(parents=True)
        for d in ("raw", "derived", "logs", "reviews"):
            (td / d).mkdir()
        manifest = {
            "task_id": "task_0001",
            "status": kwargs.get("status", "ingested"),
            "input_files": kwargs.get("input_files", []),
            "derived_files": kwargs.get("derived_files", []),
            "run_ids": kwargs.get("run_ids", []),
            "flag_ids": kwargs.get("flag_ids", []),
            "review_ids": kwargs.get("review_ids", []),
            "object_ids": kwargs.get("object_ids", []),
        }
        with open(td / "manifest.json", "w") as f:
            json.dump(manifest, f)
        return ws

    def _init_db(self, ws: Path):
        from data_agent.db import init_db
        init_db(ws).close()

    def test_normal_task_pass_clean(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "pass"

    def test_missing_manifest_error(self, tmp_path):
        ws = tmp_path / "ws"
        (ws / "tasks" / "task_0001").mkdir(parents=True)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_empty_run_id_error(self, tmp_path):
        ws = self._build_ws(tmp_path, run_ids=[""])
        with open(ws / "tasks" / "task_0001" / "logs" / "processing_runs.json", "w") as f:
            json.dump([{"run_id": "", "tool_name": "x", "status": "succeeded", "created_at": "2024-01-01"}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_requires_review_warn(self, tmp_path):
        ws = self._build_ws(tmp_path)
        with open(ws / "tasks" / "task_0001" / "logs" / "quality_flags.json", "w") as f:
            json.dump([{"flag_id": "f1", "requires_review": True, "message": "check"}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "warn"

    def test_invalid_json_errors(self, tmp_path):
        ws = self._build_ws(tmp_path)
        (ws / "tasks" / "task_0001" / "logs" / "processing_runs.json").write_text("{bad")
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_self_replacement_error(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        with open(ws / "tasks" / "task_0001" / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "replaces", "source_id": "x", "target_id": "x"}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_valid_reciprocal_ok(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        with open(ws / "tasks" / "task_0001" / "logs" / "relationships.json", "w") as f:
            json.dump([
                {"rel_id": "r1", "rel_type": "replaces", "source_id": "new_obj", "target_id": "old_obj"},
                {"rel_id": "r2", "rel_type": "replaced_by", "source_id": "old_obj", "target_id": "new_obj"},
            ], f)
        result = validate_task(ws, "task_0001", write_report=False)
        for ch in result.checks:
            if "reciprocal" in ch.message.lower():
                assert ch.status != "error", f"False reciprocal error: {ch.message}"

    def test_missing_reciprocal_error(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        with open(ws / "tasks" / "task_0001" / "logs" / "relationships.json", "w") as f:
            json.dump([
                {"rel_id": "r1", "rel_type": "replaces", "source_id": "new_obj", "target_id": "old_obj"},
            ], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_manifest_input_symlink_error(self, tmp_path):
        ws = self._build_ws(tmp_path, input_files=["link.csv"])
        td = ws / "tasks" / "task_0001"
        target = td / "raw" / "real.csv"
        target.write_text("a,b\n1,2")
        (td / "raw" / "link.csv").symlink_to(target)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_report_write_failure_error(self, tmp_path):
        ws = self._build_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        self._init_db(ws)
        real_replace = Path.replace
        def fail_replace(self, target):
            self.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            raise OSError("simulated replace failure")
        with patch.object(Path, "replace", fail_replace):
            result = validate_task(ws, "task_0001", write_report=True)
        assert result.status == "error"
        assert any("report_write_failed" in ch.name for ch in result.checks)

    def test_validate_all_exit_code(self, tmp_path):
        ws = tmp_path / "ws2"
        ws.mkdir()
        for i in (1, 2):
            td = ws / "tasks" / f"task_{i:04d}"
            td.mkdir(parents=True)
            for d in ("raw", "derived", "logs", "reviews"):
                (td / d).mkdir()
            with open(td / "manifest.json", "w") as f:
                json.dump({"task_id": f"task_{i:04d}", "status": "ingested", "input_files": [], "derived_files": [], "run_ids": [], "flag_ids": [], "review_ids": [], "object_ids": []}, f)
        results = validate_all(ws, write_report=False)
        assert len(results) == 2

    def test_stale_report_not_trusted(self, tmp_path):
        ws = self._build_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        stale = td / "logs" / "package_validation_result.json"
        stale.write_text('{"task_id":"task_0001","status":"pass"}')
        real_replace = Path.replace
        def fail_replace(self, target):
            raise OSError("simulated failure")
        with patch.object(Path, "replace", fail_replace):
            result = validate_task(ws, "task_0001", write_report=True)
        assert result.status == "error"

    def test_absolute_manifest_derived_rejected(self, tmp_path):
        ws = self._build_ws(tmp_path, derived_files=["/etc/hosts"])
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_raw_traversal_rejected(self, tmp_path):
        ws = self._build_ws(tmp_path, input_files=["../../secret.txt"])
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_checksum_l1_only(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        conn.execute("INSERT INTO files (file_id, task_id, original_name, stored_path, checksum_sha256, size_bytes, lifecycle, registered_at) VALUES (?,?,?,?,?,?,?,?)", ("f1", "task_0001", "data.csv", str(ws / "tasks" / "task_0001" / "raw" / "data.csv"), "badhash", 4, "L1", "2024-01-01"))
        conn.commit()
        conn.close()
        (ws / "tasks" / "task_0001" / "raw" / "data.csv").write_text("test")
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_relationship_file_endpoint_accepted(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        conn.execute("INSERT INTO files (file_id, task_id, original_name, stored_path, checksum_sha256, size_bytes, lifecycle, registered_at) VALUES (?,?,?,?,?,?,?,?)", ("f_src", "task_0001", "src.csv", "/tmp/fake", "hash", 4, "L0", "2024-01-01"))
        conn.execute("INSERT INTO files (file_id, task_id, original_name, stored_path, checksum_sha256, size_bytes, lifecycle, registered_at) VALUES (?,?,?,?,?,?,?,?)", ("f_tgt", "task_0001", "tgt.csv", "/tmp/fake", "hash", 4, "L1", "2024-01-01"))
        conn.commit()
        conn.close()
        with open(ws / "tasks" / "task_0001" / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "derived_from", "source_id": "f_src", "target_id": "f_tgt", "metadata": {"run_id": ""}}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        unknown_errors = [ch for ch in result.checks if "unknown" in ch.name and ch.status == "error"]
        assert not unknown_errors, f"File endpoint rejected as unknown: {unknown_errors}"

    def test_relationship_data_object_endpoint_accepted(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        conn.execute("INSERT INTO data_objects (object_id, task_id, data_type, subtype, lifecycle, created_at) VALUES (?,?,?,?,?,?)", ("obj_src", "task_0001", "raw_numeric", "raw", "L1", "2024-01-01"))
        conn.execute("INSERT INTO data_objects (object_id, task_id, data_type, subtype, lifecycle, created_at) VALUES (?,?,?,?,?,?)", ("obj_tgt", "task_0001", "raw_spectral", "raw", "L2", "2024-01-01"))
        conn.commit()
        conn.close()
        with open(ws / "tasks" / "task_0001" / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "derived_from", "source_id": "obj_src", "target_id": "obj_tgt", "metadata": {"run_id": ""}}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        unknown_errors = [ch for ch in result.checks if "unknown" in ch.name and ch.status == "error"]
        assert not unknown_errors

    def test_relationship_ghost_source_errors(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        conn.execute("INSERT INTO data_objects (object_id, task_id, data_type, subtype, lifecycle, created_at) VALUES (?,?,?,?,?,?)", ("obj_tgt", "task_0001", "raw_spectral", "raw", "L2", "2024-01-01"))
        conn.commit()
        conn.close()
        with open(ws / "tasks" / "task_0001" / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "derived_from", "source_id": "ghost_src", "target_id": "obj_tgt", "metadata": {"run_id": ""}}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"
        assert any("unknown_source" in ch.name for ch in result.checks)

    def test_relationship_ghost_target_errors(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        conn.execute("INSERT INTO data_objects (object_id, task_id, data_type, subtype, lifecycle, created_at) VALUES (?,?,?,?,?,?)", ("obj_src", "task_0001", "raw_numeric", "raw", "L1", "2024-01-01"))
        conn.commit()
        conn.close()
        with open(ws / "tasks" / "task_0001" / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "derived_from", "source_id": "obj_src", "target_id": "ghost_tgt", "metadata": {"run_id": ""}}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"
        assert any("unknown_target" in ch.name for ch in result.checks)

    def test_relationship_cross_task_endpoint_errors(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        td2 = ws / "tasks" / "task_0002"
        td2.mkdir(parents=True)
        for d in ("raw", "derived", "logs", "reviews"):
            (td2 / d).mkdir()
        with open(td2 / "manifest.json", "w") as f:
            json.dump({"task_id": "task_0002", "status": "ingested", "input_files": [], "derived_files": [], "run_ids": [], "flag_ids": [], "review_ids": [], "object_ids": []}, f)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        conn.execute("INSERT INTO data_objects (object_id, task_id, data_type, subtype, lifecycle, created_at) VALUES (?,?,?,?,?,?)", ("obj_src", "task_0001", "raw_numeric", "raw", "L1", "2024-01-01"))
        conn.execute("INSERT INTO data_objects (object_id, task_id, data_type, subtype, lifecycle, created_at) VALUES (?,?,?,?,?,?)", ("obj_other", "task_0002", "raw_spectral", "raw", "L2", "2024-01-01"))
        conn.commit()
        conn.close()
        with open(ws / "tasks" / "task_0001" / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "derived_from", "source_id": "obj_src", "target_id": "obj_other", "metadata": {"run_id": ""}}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"
        assert any("unknown_target" in ch.name for ch in result.checks)

    def test_replaces_ghost_source_errors(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        conn.execute("INSERT INTO data_objects (object_id, task_id, data_type, subtype, lifecycle, created_at) VALUES (?,?,?,?,?,?)", ("obj_tgt", "task_0001", "raw_spectral", "raw", "L2", "2024-01-01"))
        conn.commit()
        conn.close()
        with open(ws / "tasks" / "task_0001" / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "replaces", "source_id": "ghost", "target_id": "obj_tgt"}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"
        assert any("replaces" in ch.name and "unknown_source" in ch.name for ch in result.checks)

    def test_replaced_by_ghost_target_errors(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        conn.execute("INSERT INTO data_objects (object_id, task_id, data_type, subtype, lifecycle, created_at) VALUES (?,?,?,?,?,?)", ("obj_src", "task_0001", "raw_numeric", "raw", "L2", "2024-01-01"))
        conn.commit()
        conn.close()
        with open(ws / "tasks" / "task_0001" / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "replaced_by", "source_id": "obj_src", "target_id": "ghost"}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"
        assert any("replaced_by" in ch.name and "unknown_target" in ch.name for ch in result.checks)

    def test_write_report_sets_nonempty_absolute_paths(self, tmp_path):
        ws = self._build_ws(tmp_path)
        result = validate_task(ws, "task_0001", write_report=True)
        assert result.result_path
        assert result.report_path
        assert Path(result.result_path).is_absolute()
        assert Path(result.report_path).is_absolute()
        assert Path(result.result_path).is_file()
        assert Path(result.report_path).is_file()

    def test_persisted_json_matches_returned_result(self, tmp_path):
        ws = self._build_ws(tmp_path)
        result = validate_task(ws, "task_0001", write_report=True)
        with open(result.result_path, "r") as f:
            persisted = json.load(f)
        assert persisted["task_id"] == result.task_id
        assert persisted["validated_at"] == result.validated_at
        assert persisted["status"] == result.status
        assert persisted["result_path"] == result.result_path
        assert persisted["report_path"] == result.report_path

    def test_report_write_failure_clears_paths(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        td = ws / "tasks" / "task_0001"
        def fail_json_replace(self, target):
            raise OSError("simulated json write failure")
        with patch.object(Path, "replace", fail_json_replace):
            result = validate_task(ws, "task_0001", write_report=True)
        assert result.status == "error"
        assert any("report_write_failed" in ch.name for ch in result.checks)
        assert result.result_path == ""

    def test_report_write_failure_md_clears_path(self, tmp_path):
        ws = self._build_ws(tmp_path)
        self._init_db(ws)
        td = ws / "tasks" / "task_0001"
        tmp_md = td / "logs" / "package_validation_report.md.tmp"
        call_count = [0]
        real_replace = Path.replace
        def fail_second_replace(self, target):
            call_count[0] += 1
            if call_count[0] == 2:
                tmp_md.write_text("partial md")
                raise OSError("simulated md write failure")
            return real_replace(self, target)
        with patch.object(Path, "replace", fail_second_replace):
            result = validate_task(ws, "task_0001", write_report=True)
        assert result.status == "error"
        assert any("report_write_failed" in ch.name for ch in result.checks)
        assert result.report_path == ""
        assert not tmp_md.exists()


class TestRelationshipModelResultSemantics:
    def _build_ws_with_db(self, tmp_path, task_id="task_0001"):
        ws = tmp_path / "ws"
        ws.mkdir()
        td = ws / "tasks" / task_id
        td.mkdir(parents=True)
        for d in ("raw", "derived", "logs", "reviews"):
            (td / d).mkdir()
        manifest = {"task_id": task_id, "status": "processed", "input_files": [], "derived_files": [], "run_ids": ["run_1"], "flag_ids": [], "review_ids": [], "object_ids": ["obj_src", "obj_tgt"]}
        with open(td / "manifest.json", "w") as f:
            json.dump(manifest, f)
        from data_agent.db import init_db
        init_db(ws).close()
        return ws

    def _insert_objects_and_file(self, ws, conn, task_id, tgt_data_type, tgt_subtype):
        conn.execute("INSERT INTO data_objects (object_id, task_id, data_type, subtype, lifecycle, created_at) VALUES (?,?,?,?,?,?)", ("obj_src", task_id, "raw_numeric", "raw", "L1", "2024-01-01"))
        conn.execute("INSERT INTO data_objects (object_id, task_id, data_type, subtype, lifecycle, created_at) VALUES (?,?,?,?,?,?)", ("obj_tgt", task_id, tgt_data_type, tgt_subtype, "L2", "2024-01-01"))
        conn.execute("INSERT INTO files (file_id, task_id, original_name, stored_path, checksum_sha256, size_bytes, lifecycle, registered_at) VALUES (?,?,?,?,?,?,?,?)", ("f1", task_id, "data.csv", "/tmp/f.csv", "hash", 4, "L1", "2024-01-01"))
        conn.commit()

    def test_normal_l2_with_nonmodel_run_no_false_positive(self, tmp_path):
        ws = self._build_ws_with_db(tmp_path)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        self._insert_objects_and_file(ws, conn, "task_0001", tgt_data_type="numeric_table", tgt_subtype="raw")
        conn.execute("INSERT INTO processing_runs (run_id, task_id, tool_name, status, created_at) VALUES (?,?,?,?,?)", ("run_1", "task_0001", "csv_processor", "succeeded", "2024-01-01"))
        conn.commit()
        conn.close()
        td = ws / "tasks" / "task_0001"
        with open(td / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "derived_from", "source_id": "obj_src", "target_id": "obj_tgt", "metadata": {"run_id": "run_1"}}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        false_positive = [ch for ch in result.checks if ch.name == "rels_model_result_non_model_run" and ch.status == "error"]
        assert not false_positive, f"Falsely flagged as model_result: {false_positive}"

    def test_model_result_with_nonmodel_run_errors(self, tmp_path):
        ws = self._build_ws_with_db(tmp_path)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        self._insert_objects_and_file(ws, conn, "task_0001", tgt_data_type="model_result", tgt_subtype="model")
        conn.execute("INSERT INTO processing_runs (run_id, task_id, tool_name, status, created_at) VALUES (?,?,?,?,?)", ("run_1", "task_0001", "csv_processor", "succeeded", "2024-01-01"))
        conn.commit()
        conn.close()
        td = ws / "tasks" / "task_0001"
        with open(td / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "derived_from", "source_id": "obj_src", "target_id": "obj_tgt", "metadata": {"run_id": "run_1"}}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert any(ch.name == "rels_model_result_non_model_run" and ch.status == "error" for ch in result.checks)

    def test_model_result_with_model_run_passes(self, tmp_path):
        ws = self._build_ws_with_db(tmp_path)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        self._insert_objects_and_file(ws, conn, "task_0001", tgt_data_type="model_result", tgt_subtype="model")
        conn.execute("INSERT INTO processing_runs (run_id, task_id, tool_name, status, created_at) VALUES (?,?,?,?,?)", ("run_1", "task_0001", "model:vision", "succeeded", "2024-01-01"))
        conn.commit()
        conn.close()
        td = ws / "tasks" / "task_0001"
        with open(td / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "derived_from", "source_id": "obj_src", "target_id": "obj_tgt", "metadata": {"run_id": "run_1"}}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        false_positive = [ch for ch in result.checks if ch.name == "rels_model_result_non_model_run" and ch.status == "error"]
        assert not false_positive, f"model run falsely flagged: {false_positive}"

    def test_registry_read_failure_produces_warn_not_false_unknown(self, tmp_path):
        ws = self._build_ws_with_db(tmp_path)
        from data_agent.db import get_conn
        conn = get_conn(ws)
        self._insert_objects_and_file(ws, conn, "task_0001", tgt_data_type="numeric_table", tgt_subtype="raw")
        conn.execute("INSERT INTO processing_runs (run_id, task_id, tool_name, status, created_at) VALUES (?,?,?,?,?)", ("run_1", "task_0001", "csv_processor", "succeeded", "2024-01-01"))
        conn.commit()
        conn.close()
        td = ws / "tasks" / "task_0001"
        with open(td / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "derived_from", "source_id": "obj_src", "target_id": "obj_tgt", "metadata": {"run_id": "run_1"}}], f)
        from unittest.mock import patch
        with patch("data_agent.validation.get_conn", side_effect=OSError("simulated db failure")):
            result = validate_task(ws, "task_0001", write_report=False)
        warn = [ch for ch in result.checks if ch.name == "rels_registry_unavailable" and ch.status == "warn"]
        assert len(warn) >= 1, f"No registry unavailable WARN: {[ch.name for ch in result.checks]}"
        unknown_errors = [ch for ch in result.checks if "unknown" in ch.name and ch.status == "error"]
        assert not unknown_errors, f"Registry failure produced false unknown endpoint errors: {unknown_errors}"


class TestIncompleteMarkerProtocol:
    def _build_ws(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        td = ws / "tasks" / "task_0001"
        td.mkdir(parents=True)
        for d in ("raw", "derived", "logs", "reviews"):
            (td / d).mkdir()
        manifest = {"task_id": "task_0001", "status": "ingested", "input_files": [], "derived_files": [], "run_ids": [], "flag_ids": [], "review_ids": [], "object_ids": []}
        with open(td / "manifest.json", "w") as f:
            json.dump(manifest, f)
        return ws

    def test_md_replace_failure_leaves_marker(self, tmp_path):
        ws = self._build_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        marker_path = td / "logs" / "package_validation_incomplete.json"
        real_replace = Path.replace
        def fail_md_replace(self, target):
            if target.name == "package_validation_report.md":
                raise OSError("simulated md replace failure")
            return real_replace(self, target)
        with patch.object(Path, "replace", fail_md_replace):
            result = validate_task(ws, "task_0001", write_report=True)
        assert result.status == "error"
        assert any(ch.name == "report_write_failed" for ch in result.checks)
        assert marker_path.exists()

    def test_json_replace_failure_leaves_marker(self, tmp_path):
        ws = self._build_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        marker_path = td / "logs" / "package_validation_incomplete.json"
        real_replace = Path.replace
        def fail_json_replace(self, target):
            if target.name == "package_validation_result.json":
                raise OSError("simulated json replace failure")
            return real_replace(self, target)
        with patch.object(Path, "replace", fail_json_replace):
            result = validate_task(ws, "task_0001", write_report=True)
        assert result.status == "error"
        assert marker_path.exists()

    def test_marker_masks_stale_pass(self, tmp_path):
        ws = self._build_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        json_path = td / "logs" / "package_validation_result.json"
        json_path.write_text('{"task_id":"task_0001","status":"pass","validated_at":"2026-01-01","errors":[],"warnings":[],"result_path":"/f.json","report_path":"/f.md"}')
        md_path = td / "logs" / "package_validation_report.md"
        md_path.write_text("# old pass")
        marker_path = td / "logs" / "package_validation_incomplete.json"
        marker_path.write_text('{"task_id":"task_0001","validated_at":"2026-01-01","message":"incomplete"}')
        from data_agent.ui.readers import read_validation_result
        result = read_validation_result(td)
        assert result is not None
        assert result["status"] == "error"
        assert result["errors"] == ["上一次验证报告未完整写入，请重新验证"]
        assert result["result_path"] == ""

    def test_successful_retry_clears_marker(self, tmp_path):
        ws = self._build_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        marker_path = td / "logs" / "package_validation_incomplete.json"
        marker_path.write_text('{"task_id":"task_0001","validated_at":"2026-01-01","message":"incomplete"}')
        result = validate_task(ws, "task_0001", write_report=True)
        assert not marker_path.exists()
        assert result.result_path
        assert result.report_path
        from data_agent.ui.readers import read_validation_result
        persisted = read_validation_result(td)
        assert persisted is not None
        assert persisted["status"] != "error"


class TestRegistryUnavailableRunIdGuard:
    def _build_ws(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        td = ws / "tasks" / "task_0001"
        td.mkdir(parents=True)
        for d in ("raw", "derived", "logs", "reviews"):
            (td / d).mkdir()
        manifest = {"task_id": "task_0001", "status": "processed", "input_files": [], "derived_files": [], "run_ids": [], "flag_ids": [], "review_ids": [], "object_ids": []}
        with open(td / "manifest.json", "w") as f:
            json.dump(manifest, f)
        from data_agent.db import init_db
        init_db(ws).close()
        return ws

    def test_registry_failure_skips_run_id_check(self, tmp_path):
        from data_agent.validation import _check_relationships, _Collector
        ws = self._build_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        with open(td / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "derived_from", "source_id": "obj_src", "target_id": "obj_tgt", "metadata": {"run_id": "run_1"}}], f)
        collector = _Collector()
        with patch("data_agent.validation.get_conn", side_effect=OSError("simulated db failure")):
            _check_relationships(td, ws, collector)
        warn = [ch for ch in collector.checks if ch.name == "rels_registry_unavailable" and ch.status == "warn"]
        assert len(warn) == 1, f"Expected one rels_registry_unavailable WARN, got: {[ch.name for ch in collector.checks]}"
        run_missing = [ch for ch in collector.checks if ch.name == "rels_derived_from_run_missing"]
        assert not run_missing, f"Registry unavailable should not check run_id, got run_missing"
        model_run_errors = [ch for ch in collector.checks if ch.name == "rels_model_result_non_model_run"]
        assert not model_run_errors, f"Registry unavailable should not check model run"
        unknown_errors = [ch for ch in collector.checks if "unknown" in ch.name and ch.status == "error"]
        assert not unknown_errors, f"Registry unavailable should not produce unknown endpoint errors: {unknown_errors}"
