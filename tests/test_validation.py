"""Tests for package validation engine."""
import json
import os
import shutil
from pathlib import Path

import pytest

from data_agent.validation import (
    validate_task,
    validate_all,
    _strict_read_json,
    _strict_read_json_list,
    _resolve_data_file,
    _sha256_file,
    _safe_resolve,
)


class TestStrictReaders:
    def test_strict_json_object(self, tmp_path):
        f = tmp_path / "o.json"
        f.write_text('{"key": "val"}')
        assert _strict_read_json(f) == {"key": "val"}

    def test_strict_json_list(self, tmp_path):
        f = tmp_path / "l.json"
        f.write_text('[{"a": 1}]')
        result = _strict_read_json_list(f)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_strict_json_list_rejects_object(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text('{"a": 1}')
        with pytest.raises(ValueError):
            _strict_read_json_list(f)

    def test_strict_json_missing_returns_none(self, tmp_path):
        assert _strict_read_json(tmp_path / "nonexistent.json") is None

    def test_strict_json_list_invalid_raises(self, tmp_path):
        f = tmp_path / "corrupt.json"
        f.write_text("{bad json")
        with pytest.raises(json.JSONDecodeError):
            _strict_read_json_list(f)


class TestResolveDataFile:
    def test_resolves_in_derived(self, tmp_path):
        td = tmp_path / "task_0001"
        (td / "derived").mkdir(parents=True)
        (td / "derived" / "output.json").write_text("{}")
        result = _resolve_data_file(td, "output.json")
        assert result is not None
        assert result.name == "output.json"

    def test_returns_none_for_missing(self, tmp_path):
        td = tmp_path / "task_0002"
        td.mkdir()
        assert _resolve_data_file(td, "no_such_file.csv") is None


class TestSafeResolve:
    def test_absolute_path_rejected(self, tmp_path):
        assert _safe_resolve(tmp_path, "/etc/passwd") is None

    def test_dot_dot_rejected(self, tmp_path):
        td = tmp_path / "task"
        td.mkdir()
        assert _safe_resolve(td, "../../secret.txt") is None


class TestChecksum:
    def test_sha256_computes(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("hello")
        digest = _sha256_file(f)
        assert len(digest) == 64


class TestValidateTask:
    def _build_demo_ws(self, tmp_path: Path) -> tuple[Path, Path]:
        ws = tmp_path / "ws"
        ws.mkdir()
        td = ws / "tasks" / "task_0001"
        td.mkdir(parents=True)
        for d in ("raw", "derived", "logs", "reviews"):
            (td / d).mkdir()
        manifest = {
            "task_id": "task_0001",
            "status": "processed",
            "input_files": [],
            "derived_files": [],
            "run_ids": [],
            "flag_ids": [],
            "review_ids": [],
            "object_ids": [],
        }
        with open(td / "manifest.json", "w") as f:
            json.dump(manifest, f)
        return ws, td

    def _init_registry(self, ws: Path):
        from data_agent.db import init_db
        init_db(ws).close()

    def test_normal_task_passes(self, tmp_path):
        ws, td = self._build_demo_ws(tmp_path)
        self._init_registry(ws)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "pass"

    def test_missing_manifest_errors(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        td = ws / "tasks" / "task_0001"
        td.mkdir(parents=True)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_requires_review_warns(self, tmp_path):
        ws, td = self._build_demo_ws(tmp_path)
        with open(td / "logs" / "quality_flags.json", "w") as f:
            json.dump([{"flag_id": "f1", "requires_review": True, "message": "check"}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "warn"

    def test_empty_run_id_errors(self, tmp_path):
        ws, td = self._build_demo_ws(tmp_path)
        with open(td / "logs" / "processing_runs.json", "w") as f:
            json.dump([{"run_id": "", "tool_name": "test", "status": "succeeded", "created_at": "2024-01-01"}], f)
        manifest = json.loads((td / "manifest.json").read_text())
        manifest["run_ids"] = [""]
        with open(td / "manifest.json", "w") as f:
            json.dump(manifest, f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_invalid_json_errors(self, tmp_path):
        ws, td = self._build_demo_ws(tmp_path)
        (td / "logs" / "processing_runs.json").write_text("{corrupt")
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_self_replacement_errors(self, tmp_path):
        ws, td = self._build_demo_ws(tmp_path)
        with open(td / "logs" / "relationships.json", "w") as f:
            json.dump([{"rel_id": "r1", "rel_type": "replaces", "source_id": "x", "target_id": "x"}], f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"

    def test_missing_sqlite_warns_and_continues(self, tmp_path):
        ws, td = self._build_demo_ws(tmp_path)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status in ("pass", "warn")
        any_warn = any("agent.sqlite" in w.lower() for w in result.warnings)
        assert any_warn

    def test_validate_all_returns_every_task(self, tmp_path):
        ws = tmp_path / "ws"
        for i in range(1, 4):
            td = ws / "tasks" / f"task_{i:04d}"
            td.mkdir(parents=True)
            for d in ("raw", "derived", "logs", "reviews"):
                (td / d).mkdir()
            with open(td / "manifest.json", "w") as f:
                json.dump({"task_id": f"task_{i:04d}", "status": "ingested", "input_files": [], "derived_files": [], "run_ids": [], "flag_ids": [], "review_ids": []}, f)
        results = validate_all(ws, write_report=False)
        assert len(results) == 3

    def test_writes_reports(self, tmp_path):
        ws, td = self._build_demo_ws(tmp_path)
        result = validate_task(ws, "task_0001", write_report=True)
        assert (td / "logs" / "package_validation_result.json").exists()
        assert (td / "logs" / "package_validation_report.md").exists()

    def test_manifest_referenced_derived_missing_errors(self, tmp_path):
        ws, td = self._build_demo_ws(tmp_path)
        manifest = json.loads((td / "manifest.json").read_text())
        manifest["derived_files"] = ["derived/nonexistent.csv"]
        with open(td / "manifest.json", "w") as f:
            json.dump(manifest, f)
        result = validate_task(ws, "task_0001", write_report=False)
        assert result.status == "error"
