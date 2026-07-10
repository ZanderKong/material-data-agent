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
