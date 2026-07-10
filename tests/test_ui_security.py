"""Tests for UI-layer error redaction."""
import os
import pytest
from data_agent.ui.security import safe_ui_error, safe_display_text


class TestSafeDisplayText:
    def test_redacts_sk_token(self):
        result = safe_display_text("key is sk-abcdef1234567890 in text")
        assert "sk-abcdef1234567890" not in result
        assert "REDACTED" in result

    def test_redacts_bearer(self):
        result = safe_display_text("Auth: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.12345 token")
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer [REDACTED]" in result

    def test_does_not_redact_env_names(self):
        result = safe_display_text("set BEST_MODEL_API_KEY in your env")
        assert "BEST_MODEL_API_KEY" in result
        assert "ENV_VAR_NAME_REDACTED" not in result

    def test_redacts_env_values(self, monkeypatch):
        monkeypatch.setenv("BEST_MODEL_API_KEY", "my-secret-api-key-123")
        result = safe_display_text("Error: my-secret-api-key-123 rejected")
        assert "my-secret-api-key-123" not in result
        assert "REDACTED" in result


class TestSafeUiError:
    def test_redacts_exact_secret(self, monkeypatch):
        monkeypatch.setenv("BEST_MODEL_API_KEY", "sk-my-real-secret-key")
        msg = "Error: sk-my-real-secret-key was used"
        result = safe_ui_error(msg)
        assert "sk-my-real-secret-key" not in result
        assert "REDACTED" in result

    def test_redacts_bearer(self):
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.12345"
        result = safe_ui_error(msg)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer [REDACTED]" in result

    def test_redacts_key_env_names(self):
        msg = "Missing BEST_MODEL_API_KEY or FAST_MODEL_API_KEY in env"
        result = safe_ui_error(msg)
        assert "BEST_MODEL_API_KEY" not in result
        assert "FAST_MODEL_API_KEY" not in result
        assert "ENV_VAR_NAME_REDACTED" in result

    def test_non_secret_passes_through(self):
        msg = "File not found: /tmp/test.csv"
        result = safe_ui_error(msg)
        assert "File not found" in result
        assert "REDACTED" not in result

    def test_sk_pattern_redacted(self):
        msg = "Failed to call with key sk-abcdef1234567890"
        result = safe_ui_error(msg)
        assert "sk-abcdef1234567890" not in result
        assert "REDACTED" in result

    def test_handles_non_string_input(self):
        result = safe_ui_error(42)
        assert "42" in result

    def test_actions_error_not_expose_secret(self, monkeypatch):
        monkeypatch.setenv("BEST_MODEL_API_KEY", "my-super-secret")
        from data_agent.ui.actions import _safe_msg
        exc = Exception("Connection failed: my-super-secret token rejected")
        msg = _safe_msg(exc)
        assert "my-super-secret" not in msg
        assert "REDACTED" in msg
        assert "Connection failed" in msg
