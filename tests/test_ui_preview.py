"""Tests for UI preview helpers."""
import json
import tempfile
from pathlib import Path

import pytest

from data_agent.ui.preview import (
    get_file_kind,
    preview_csv,
    preview_csv_dataframe,
    preview_json,
    preview_text,
    preview_model_result,
)


class TestGetFileKind:
    def test_image_png(self):
        assert get_file_kind(Path("test.png")) == "image"

    def test_image_jpg(self):
        assert get_file_kind(Path("photo.jpg")) == "image"
        assert get_file_kind(Path("photo.jpeg")) == "image"

    def test_csv(self):
        assert get_file_kind(Path("data.csv")) == "csv"

    def test_json(self):
        assert get_file_kind(Path("config.json")) == "json"

    def test_model_result(self):
        assert get_file_kind(Path("run_abc__model_result_ocr.json")) == "model_result"

    def test_text(self):
        assert get_file_kind(Path("notes.txt")) == "text"
        assert get_file_kind(Path("readme.md")) == "text"
        assert get_file_kind(Path("readme.markdown")) == "text"

    def test_other(self):
        assert get_file_kind(Path("data.xlsx")) == "other"
        assert get_file_kind(Path("binary.bin")) == "other"


class TestPreviewCsv:
    def test_reads_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("a,b\n1,2\n3,4\n")
            f.flush()
            result = preview_csv(Path(f.name), max_rows=50)
        assert result is not None
        assert "a,b" in result

    def test_truncates_to_max_rows(self):
        lines = ["col"] + [str(i) for i in range(100)]
        content = "\n".join(lines)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            result = preview_csv(Path(f.name), max_rows=50)
        assert result is not None
        result_lines = result.strip().split("\n")
        assert len(result_lines) <= 51

    def test_csv_fallback_does_not_read_full_large_file(self):
        lines = [f"col1,col2,col3"] + [f"a{i},b{i},c{i}" for i in range(5000)]
        content = "\n".join(lines)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            path = Path(f.name)
            result = preview_csv(path, max_rows=50)
        assert result is not None
        result_lines = result.strip().split("\n")
        assert len(result_lines) <= 51
        assert "a4999" not in result

    def test_csv_fallback_no_pandas_present(self, monkeypatch):
        import data_agent.ui.preview as pmod
        monkeypatch.setitem(pmod.__dict__, "pd", None)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("x,y\n1,2\n3,4\n")
            f.flush()
            result = preview_csv(Path(f.name), max_rows=50)
        assert result is not None
        assert "x,y" in result

    def test_missing_file(self):
        assert preview_csv(Path("/nonexistent/file.csv")) is None


class TestPreviewCsvDataframe:
    def test_returns_dataframe(self):
        lines = [f"col1,col2"] + [f"a{i},b{i}" for i in range(60)]
        content = "\n".join(lines)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            path = Path(f.name)
            df = preview_csv_dataframe(path, max_rows=50)
        assert df is not None
        assert len(df) == 50
        assert list(df.columns) == ["col1", "col2"]

    def test_missing_file_returns_none(self):
        assert preview_csv_dataframe(Path("/nonexistent/file.csv")) is None


class TestPreviewJson:
    def test_pretty_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"a": 1, "b": [2, 3]}, f)
            f.flush()
            result = preview_json(Path(f.name))
        assert result is not None
        assert '"a": 1' in result

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("not json")
            f.flush()
            result = preview_json(Path(f.name))
        assert result is not None

    def test_missing_file(self):
        assert preview_json(Path("/nonexistent/file.json")) is None


class TestPreviewText:
    def test_reads_text(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("hello world")
            f.flush()
            result = preview_text(Path(f.name))
        assert result == "hello world"

    def test_truncates_long_text(self):
        long_text = "x" * 3000
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(long_text)
            f.flush()
            result = preview_text(Path(f.name), max_chars=1000)
        assert result is not None
        assert len(result) < 3000
        assert "truncated" in result.lower()

    def test_missing_file(self):
        assert preview_text(Path("/nonexistent/file.txt")) is None


class TestPreviewModelResult:
    def test_valid_model_result(self):
        data = {
            "success": True,
            "role": "ocr",
            "provider": "test",
            "model": "test-model",
            "mode": "local",
            "confidence": 0.8,
            "fallback_used": False,
            "fallback_from": "",
            "latency_ms": 100,
            "token_usage": {"total_tokens": 10},
            "schema_version": "model_result_v1",
            "prompt_version": "v1",
            "warnings": ["test_warning"],
            "error": "",
            "raw_text": "some raw text",
            "raw_response": "some response",
            "raw_response_redacted": "redacted response",
            "output_json": {
                "text_blocks": ["a", "b"],
                "requires_review": True,
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            result = preview_model_result(Path(f.name))
        assert result is not None
        audit = result["audit"]
        assert audit["role"] == "ocr"
        assert audit["success"] is True
        assert audit["confidence"] == 0.8
        assert result["risk"]["warnings"] == ["test_warning"]
        assert result["risk"]["requires_review"] is True
        assert result["extracted"]["text_blocks"] == ["a", "b"]
        assert result["raw"]["raw_text"] == "some raw text"
        assert result["raw"]["raw_response_redacted"] == "redacted response"

    def test_output_json_fields_extracted(self):
        data = {
            "output_json": {
                "detected_units": ["mm", "cm"],
                "axis_candidates": ["x", "y"],
                "visible_features": ["peak"],
                "factual_observations": ["curve"],
                "interpretation_candidates": ["trend"],
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            result = preview_model_result(Path(f.name))
        assert result is not None
        assert result["extracted"]["detected_units"] == ["mm", "cm"]
        assert result["extracted"]["visible_features"] == ["peak"]
        assert result["extracted"]["factual_observations"] == ["curve"]

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("bad json")
            f.flush()
            result = preview_model_result(Path(f.name))
        assert result is not None
        assert "_error" in result

    def test_missing_file(self):
        assert preview_model_result(Path("/nonexistent/file.json")) is None
