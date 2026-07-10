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
