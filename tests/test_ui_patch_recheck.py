"""Focused tests for UI patch recheck: connection cleanup, raw response, quality flag redaction."""
import json
from unittest.mock import MagicMock

from data_agent.ui.actions import do_ingest
from data_agent.ui.preview import select_raw_response
from data_agent.ui.security import safe_display_text


class TestIngestConnectionCleanup:
    def test_conn_closed_when_ingest_raises(self, tmp_path, monkeypatch):
        ws = tmp_path / "ws"
        ws.mkdir()

        inbox = tmp_path / "inbox"
        inbox.mkdir()

        mock_conn = MagicMock()
        mock_init_db = MagicMock(return_value=mock_conn)
        mock_ingest_inbox = MagicMock(side_effect=RuntimeError("ingest explosion sk-abc1234567890"))

        monkeypatch.setattr("data_agent.ui.actions.init_db", mock_init_db)
        monkeypatch.setattr("data_agent.ui.actions.ingest_inbox", mock_ingest_inbox)

        result = do_ingest(str(inbox), ws)
        assert result["success"] is False
        mock_conn.close.assert_called_once()
        assert "sk-abc1234567890" not in result["message"]
        assert "REDACTED" in result["message"]


class TestSelectRawResponse:
    def test_prefers_redacted_and_serializes_raw_response_fallback(self):
        assert select_raw_response({"raw_response_redacted": "clean text", "raw_text": "raw text", "raw_response": "full"}) == "clean text"

        result = select_raw_response({"raw_response_redacted": "", "raw_text": "", "raw_response": {"key": "value"}})
        assert json.loads(result) == {"key": "value"}


class TestQualityFlagRedaction:
    def test_safe_display_text_redacts_quality_flag_secrets(self, monkeypatch):
        env_secret = "real-secret-789xyz"
        monkeypatch.setenv("BEST_MODEL_API_KEY", env_secret)
        msg = (
            "Chart model returned sk-proj-abc123def456; "
            "Auth failed: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123; "
            f"configured value {env_secret}"
        )
        result = safe_display_text(msg)

        assert "sk-proj-abc123def456" not in result
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer [REDACTED]" in result
        assert env_secret not in result
        assert "REDACTED" in result


class TestSampleIndexFailureUI:
    def test_do_index_samples_empty_workspace_succeeds(self, tmp_path):
        from data_agent.ui.actions import do_index_samples
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "tasks").mkdir()
        result = do_index_samples(ws)
        assert result.get("success") is True

    def test_do_index_samples_oserror_returns_failure(self, tmp_path, monkeypatch):
        from data_agent.ui.actions import do_index_samples
        from data_agent.sample_index import build_sample_index
        def mock_build(ws):
            raise OSError("simulated disk full")
        monkeypatch.setattr("data_agent.ui.actions.build_sample_index", mock_build)
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "tasks").mkdir()
        result = do_index_samples(ws)
        assert result.get("success") is False
        assert len(result.get("warnings", [])) >= 1


class TestExportPathTaskSpecific:
    def test_export_path_keyed_by_task(self):
        session_state = {}
        tid = "task_0001"
        zip_path = "/tmp/export_task_0001.zip"
        export_paths = session_state.get("export_zip_path_by_task", {})
        assert export_paths.get(tid) is None
        export_paths[tid] = zip_path
        session_state["export_zip_path_by_task"] = export_paths
        stored = session_state.get("export_zip_path_by_task", {}).get(tid)
        assert stored == zip_path


class TestPersistedValidationReader:
    def test_reads_persisted_validation_json(self, tmp_path):
        from data_agent.ui.readers import read_validation_result
        td = tmp_path / "task_0001"
        td.mkdir(parents=True)
        (td / "logs").mkdir()
        val_json = td / "logs" / "package_validation_result.json"
        val_json.write_text('{"task_id":"task_0001","status":"warn","validated_at":"2026-01-01","errors":[],"warnings":[],"report_path":"/tmp/rpt.md","result_path":"/tmp/rpt.json"}')
        result = read_validation_result(td)
        assert result is not None
        assert result["task_id"] == "task_0001"
        assert result["status"] == "warn"

    def test_returns_none_when_no_file(self, tmp_path):
        from data_agent.ui.readers import read_validation_result
        td = tmp_path / "task_none"
        td.mkdir(parents=True)
        result = read_validation_result(td)
        assert result is None

    def test_returns_none_for_invalid_json(self, tmp_path):
        from data_agent.ui.readers import read_validation_result
        td = tmp_path / "task_0001"
        td.mkdir(parents=True)
        (td / "logs").mkdir()
        val_json = td / "logs" / "package_validation_result.json"
        val_json.write_text("{bad")
        result = read_validation_result(td)
        assert result is None
