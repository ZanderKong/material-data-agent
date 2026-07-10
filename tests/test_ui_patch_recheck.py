"""Focused tests for UI patch recheck: connection cleanup, raw response, quality flag redaction."""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
    def test_prefers_redacted_and_falls_back(self):
        assert select_raw_response({"raw_response_redacted": "clean text", "raw_text": "raw text", "raw_response": "full"}) == "clean text"

    def test_falls_back_to_raw_text_when_no_redacted(self):
        assert select_raw_response({"raw_response_redacted": "", "raw_text": "raw text"}) == "raw text"

    def test_falls_back_to_raw_response_last(self):
        assert select_raw_response({"raw_response_redacted": "", "raw_text": "", "raw_response": "full response"}) == "full response"

    def test_serializes_dict_raw_response(self):
        result = select_raw_response({"raw_response_redacted": "", "raw_text": "", "raw_response": {"key": "value"}})
        assert isinstance(result, str)
        assert '"key"' in result
        assert '"value"' in result

    def test_serializes_list_raw_response(self):
        result = select_raw_response({"raw_response_redacted": "", "raw_text": "", "raw_response": [1, 2, 3]})
        assert isinstance(result, str)
        assert "1" in result

    def test_returns_empty_when_all_empty(self):
        assert select_raw_response({}) == ""


class TestQualityFlagRedaction:
    def test_safe_display_text_redacts_sk_in_flag_message(self):
        msg = "Chart model returned sk-proj-abc123def456 for processing"
        result = safe_display_text(msg)
        assert "sk-proj-abc123def456" not in result
        assert "REDACTED" in result

    def test_safe_display_text_redacts_bearer_in_flag_message(self):
        msg = "Auth failed: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123 invalid"
        result = safe_display_text(msg)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer [REDACTED]" in result

    def test_safe_display_text_redacts_env_value_in_flag_message(self, monkeypatch):
        monkeypatch.setenv("BEST_MODEL_API_KEY", "real-secret-789xyz")
        result = safe_display_text("Error: real-secret-789xyz was rejected")
        assert "real-secret-789xyz" not in result
        assert "REDACTED" in result
