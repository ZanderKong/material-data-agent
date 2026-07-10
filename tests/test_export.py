"""Tests for evidence package export – remediation: safety, preflight, validation gate, README generation."""
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from data_agent.export import export_task


def _build_demo_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    td = ws / "tasks" / "task_0001"
    td.mkdir(parents=True)
    for d in ("raw", "derived", "logs", "reviews"):
        (td / d).mkdir()
    manifest = {
        "task_id": "task_0001",
        "status": "processed",
        "input_files": ["data.csv"],
        "derived_files": [],
        "run_ids": [],
        "flag_ids": [],
        "review_ids": [],
        "object_ids": [],
    }
    with open(td / "manifest.json", "w") as f:
        json.dump(manifest, f)
    (td / "raw" / "data.csv").write_text("a,b\n1,2")
    (td / "derived" / "result.json").write_text('{"ok": true}')
    for name in ("processing_runs", "quality_flags", "relationships", "review_records"):
        p = td / "logs" / f"{name}.json" if name != "review_records" else td / "reviews" / f"{name}.json"
        p.write_text("[]")
    return ws


class TestExportTask:
    def test_normal_creates_zip(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        result = export_task(ws, "task_0001")
        assert result.success
        assert Path(result.zip_path).is_file()
        assert result.file_count > 0

    def test_zip_contains_required_entries(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        result = export_task(ws, "task_0001")
        with zipfile.ZipFile(result.zip_path, "r") as zf:
            names = zf.namelist()
            assert "README_for_review.md" in names
            assert "manifest.json" in names
            assert "package_validation_report.md" in names

    def test_raw_derived_log_review_files_included(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        result = export_task(ws, "task_0001")
        with zipfile.ZipFile(result.zip_path, "r") as zf:
            names = zf.namelist()
        assert any(n.startswith("raw/") for n in names)
        assert any(n.startswith("derived/") for n in names)
        assert any(n.startswith("logs/") for n in names)
        assert any(n.startswith("reviews/") for n in names)

    def test_readme_contains_disclaimers(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        result = export_task(ws, "task_0001")
        with zipfile.ZipFile(result.zip_path, "r") as zf:
            readme = zf.read("README_for_review.md").decode("utf-8")
        assert "model-assisted extraction" in readme
        assert "requires_review" in readme.lower()

    def test_missing_task_fails(self, tmp_path):
        ws = tmp_path / "empty"
        ws.mkdir()
        result = export_task(ws, "task_nonexistent")
        assert not result.success

    def test_output_directory_created(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        out = tmp_path / "custom_exports" / "out.zip"
        result = export_task(ws, "task_0001", output_path=out)
        assert result.success
        assert out.is_file()

    def test_output_inside_task_fails(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        inside = td / "derived" / "inside.zip"
        result = export_task(ws, "task_0001", output_path=inside)
        assert not result.success
        assert not inside.exists()

    def test_symlink_causes_failure(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        link = td / "derived" / "link.lnk"
        link.symlink_to(td / "raw" / "data.csv")
        result = export_task(ws, "task_0001")
        assert not result.success

    def test_validation_report_included(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        result = export_task(ws, "task_0001")
        with zipfile.ZipFile(result.zip_path, "r") as zf:
            assert "package_validation_report.md" in zf.namelist()

    def test_preserves_source_files(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        orig = (td / "raw" / "data.csv").read_text()
        result = export_task(ws, "task_0001")
        assert result.success
        assert (td / "raw" / "data.csv").read_text() == orig

    def test_readme_failure_blocks_export(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        with patch("data_agent.export._generate_readme", side_effect=RuntimeError("boom")):
            result = export_task(ws, "task_0001")
        assert not result.success

    def test_archive_names_relative(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        result = export_task(ws, "task_0001")
        with zipfile.ZipFile(result.zip_path, "r") as zf:
            for name in zf.namelist():
                assert ".." not in name
                assert not name.startswith("/")
