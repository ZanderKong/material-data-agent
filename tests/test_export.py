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

    def test_export_blocked_by_blank_report_path(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        from data_agent.validation import validate_task
        with patch("data_agent.export.validate_task") as mock_val:
            mock_val.return_value.result_path = ""
            mock_val.return_value.report_path = ""
            mock_val.return_value.checks = []
            mock_val.return_value.status = "pass"
            result = export_task(ws, "task_0001")
        assert not result.success

    def test_export_blocked_by_wrong_report_path(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        with patch("data_agent.export.validate_task") as mock_val:
            mock_val.return_value.result_path = "/wrong/path.json"
            mock_val.return_value.report_path = "/wrong/report.md"
            mock_val.return_value.checks = []
            mock_val.return_value.status = "pass"
            result = export_task(ws, "task_0001")
        assert not result.success

    def test_export_blocked_by_stale_persisted_validated_at(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        from data_agent.validation import ValidationResult
        with patch("data_agent.export.validate_task") as mock_val:
            mock_val.return_value = ValidationResult(
                task_id="task_0001",
                status="pass",
                errors=[],
                warnings=[],
                checks=[],
                validated_at="2026-01-01T00:00:00+00:00",
                result_path=str((td / "logs" / "package_validation_result.json").resolve()),
                report_path=str((td / "logs" / "package_validation_report.md").resolve()),
            )
            (td / "logs" / "package_validation_result.json").write_text(json.dumps({
                "task_id": "task_0001",
                "validated_at": "2000-01-01T00:00:00+00:00",
                "status": "pass",
                "result_path": str((td / "logs" / "package_validation_result.json").resolve()),
                "report_path": str((td / "logs" / "package_validation_report.md").resolve()),
            }))
            (td / "logs" / "package_validation_report.md").write_text("# test")
            result = export_task(ws, "task_0001")
        assert not result.success

    def test_export_blocked_by_different_task_id_in_json(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        from data_agent.validation import ValidationResult
        with patch("data_agent.export.validate_task") as mock_val:
            mock_val.return_value = ValidationResult(
                task_id="task_0001",
                status="pass",
                errors=[],
                warnings=[],
                checks=[],
                validated_at="2026-01-01T00:00:00+00:00",
                result_path=str((td / "logs" / "package_validation_result.json").resolve()),
                report_path=str((td / "logs" / "package_validation_report.md").resolve()),
            )
            (td / "logs" / "package_validation_result.json").write_text(json.dumps({
                "task_id": "task_other",
                "validated_at": "2026-01-01T00:00:00+00:00",
                "status": "pass",
                "result_path": str((td / "logs" / "package_validation_result.json").resolve()),
                "report_path": str((td / "logs" / "package_validation_report.md").resolve()),
            }))
            (td / "logs" / "package_validation_report.md").write_text("# test")
            result = export_task(ws, "task_0001")
        assert not result.success

    def test_export_with_validation_error_still_succeeds_with_warning(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        with patch("data_agent.export.validate_task") as mock_val:
            from data_agent.validation import ValidationResult
            td = ws / "tasks" / "task_0001"
            mock_val.return_value = ValidationResult(
                task_id="task_0001",
                status="error",
                errors=["test error"],
                warnings=[],
                checks=[],
                validated_at="2026-01-01T00:00:00+00:00",
                result_path=str((td / "logs" / "package_validation_result.json").resolve()),
                report_path=str((td / "logs" / "package_validation_report.md").resolve()),
            )
            (td / "logs" / "package_validation_result.json").write_text(json.dumps({
                "task_id": "task_0001",
                "validated_at": "2026-01-01T00:00:00+00:00",
                "status": "error",
                "result_path": str((td / "logs" / "package_validation_result.json").resolve()),
                "report_path": str((td / "logs" / "package_validation_report.md").resolve()),
            }))
            (td / "logs" / "package_validation_report.md").write_text("# test")
            result = export_task(ws, "task_0001")
        assert result.success
        assert result.validation_status == "error"
        assert any("EXPORTED WITH VALIDATION ERRORS" in w for w in result.warnings)

    def test_export_blocked_by_incomplete_marker(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        out = tmp_path / "should_not_exist.zip"
        marker_path = td / "logs" / "package_validation_incomplete.json"
        marker_path.write_text('{"task_id":"task_0001","validated_at":"2026-01-01","message":"incomplete"}')
        from data_agent.validation import ValidationResult
        with patch("data_agent.export.validate_task") as mock_val:
            mock_val.return_value = ValidationResult(
                task_id="task_0001",
                status="pass",
                errors=[],
                warnings=[],
                checks=[],
                validated_at="2026-01-01T00:00:00+00:00",
                result_path="",
                report_path="",
            )
            result = export_task(ws, "task_0001", output_path=out)
        assert not result.success
        assert not out.exists()

    def test_symlinked_directory_under_raw_blocks_export(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        out = tmp_path / "should_not_exist.zip"
        real_dir = td / "derived"
        link_dir = td / "raw" / "linked_subdir"
        link_dir.symlink_to(real_dir, target_is_directory=True)
        result = export_task(ws, "task_0001", output_path=out)
        assert not result.success
        assert not out.exists()

    def test_zip_contains_directory_entries_for_empty_dirs(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        for d in ("raw", "derived", "logs", "reviews"):
            for f in list((td / d).iterdir()):
                if f.is_file():
                    f.unlink()
        result = export_task(ws, "task_0001")
        assert result.success
        with zipfile.ZipFile(result.zip_path, "r") as zf:
            names = zf.namelist()
        assert "raw/" in names
        assert "derived/" in names
        assert "logs/" in names
        assert "reviews/" in names

    def test_zip_contains_directory_entries_with_content(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        result = export_task(ws, "task_0001")
        with zipfile.ZipFile(result.zip_path, "r") as zf:
            names = zf.namelist()
        assert "raw/" in names
        assert "derived/" in names
        assert "logs/" in names
        assert "reviews/" in names

    def test_no_zip_created_on_preflight_failure(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        out = tmp_path / "should_not_exist.zip"
        link = td / "raw" / "bad_link.lnk"
        link.symlink_to(td / "raw" / "data.csv")
        result = export_task(ws, "task_0001", output_path=out)
        assert not result.success
        assert not out.exists()

    def test_broken_top_level_dir_symlink_blocks_export(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        out = tmp_path / "should_not_exist.zip"
        import shutil
        shutil.rmtree(td / "raw")
        (td / "raw").symlink_to(tmp_path / "nonexistent_dir")
        result = export_task(ws, "task_0001", output_path=out)
        assert not result.success
        assert not out.exists()

    def test_broken_top_level_file_symlink_blocks_export(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        out = tmp_path / "should_not_exist.zip"
        (td / "manifest.json").unlink()
        (td / "manifest.json").symlink_to(tmp_path / "nonexistent_file")
        result = export_task(ws, "task_0001", output_path=out)
        assert not result.success
        assert not out.exists()

    def test_existing_zip_not_overwritten_on_failure(self, tmp_path):
        ws = _build_demo_ws(tmp_path)
        td = ws / "tasks" / "task_0001"
        out = tmp_path / "existing.zip"
        out.write_bytes(b"ORIGINAL ZIP CONTENT")
        link = td / "raw" / "bad_link.lnk"
        link.symlink_to(td / "raw" / "data.csv")
        result = export_task(ws, "task_0001", output_path=out)
        assert not result.success
        assert out.read_bytes() == b"ORIGINAL ZIP CONTENT"
