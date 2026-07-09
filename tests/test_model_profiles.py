"""Tests for model profile loading, env resolution, and redaction."""
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from data_agent.model_adapters.base import ModelProfile
from data_agent.model_adapters.profiles import (
    load_profiles,
    resolve_profile_env,
    is_profile_available,
    list_profile_status,
)
from data_agent.model_adapters.redaction import (
    redact_string,
    redact_dict,
    redact_value,
    sanitize_model_output_json,
    sanitize_forbidden_keys_deep,
    sanitize_and_redact_model_result,
)


class TestProfileLoading:
    def test_missing_config_returns_empty(self):
        profiles = load_profiles(Path("nonexistent_file.yaml"))
        assert profiles == {}

    def test_empty_config_returns_empty_dict(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("profiles: {}\n")
            f.flush()
            profiles = load_profiles(Path(f.name))
        os.unlink(f.name)
        assert profiles == {}

    def test_loads_profiles_correctly(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""profiles:
  fast:
    role: fast
    provider: openai_compatible
    base_url_env: FAST_MODEL_BASE_URL
    api_key_env: FAST_MODEL_API_KEY
    model_env: FAST_MODEL_NAME
    enabled: true
    priority: 10
    fallback: ["local_stub"]
    timeout_seconds: 45
    cost_tier: low
    supports_vision: false
    supports_json: true
""")
            f.flush()
            profiles = load_profiles(Path(f.name))
        os.unlink(f.name)
        assert "fast" in profiles
        assert profiles["fast"].role == "fast"
        assert profiles["fast"].provider == "openai_compatible"
        assert profiles["fast"].timeout_seconds == 45


class TestProfileEnv:
    def test_missing_env_vars(self):
        profile = ModelProfile(
            name="fast",
            role="fast",
            provider="openai_compatible",
            base_url_env="FAST_MODEL_BASE_URL",
            api_key_env="FAST_MODEL_API_KEY",
            model_env="FAST_MODEL_NAME",
        )
        env = resolve_profile_env(profile)
        assert env["base_url"] == ""
        assert env["api_key"] == ""
        assert env["model"] == ""

    def test_env_configured_is_detected(self):
        os.environ["TEST_MODEL_URL"] = "http://test"
        os.environ["TEST_MODEL_KEY"] = "test-key"
        os.environ["TEST_MODEL_NAME"] = "test-model"
        profile = ModelProfile(
            name="test",
            role="test",
            provider="openai_compatible",
            base_url_env="TEST_MODEL_URL",
            api_key_env="TEST_MODEL_KEY",
            model_env="TEST_MODEL_NAME",
        )
        assert is_profile_available(profile)
        env = resolve_profile_env(profile)
        assert env["base_url"] == "http://test"
        del os.environ["TEST_MODEL_URL"]
        del os.environ["TEST_MODEL_KEY"]
        del os.environ["TEST_MODEL_NAME"]

    def test_disabled_profile_not_available(self):
        profile = ModelProfile(
            name="disabled",
            role="test",
            provider="openai_compatible",
            enabled=False,
        )
        assert not is_profile_available(profile)


class TestProfileStatus:
    def test_verbose_does_not_print_key_value(self):
        os.environ["SECRET_KEY_ENV"] = "secret-12345"
        profile = ModelProfile(
            name="test",
            role="test",
            provider="openai_compatible",
            api_key_env="SECRET_KEY_ENV",
        )
        status = list_profile_status(profile, show_values=False)
        assert status["api_key"] == "configured"
        assert "secret-12345" not in str(status.values())
        del os.environ["SECRET_KEY_ENV"]

    def test_missing_env_shows_missing(self):
        profile = ModelProfile(
            name="missing",
            role="test",
            provider="openai_compatible",
            base_url_env="NONEXISTENT_URL",
        )
        status = list_profile_status(profile, show_values=False)
        assert status["base_url"] == "missing"


class TestRedaction:
    def test_redact_string(self):
        os.environ["BEST_MODEL_API_KEY"] = "sk-secret-abc"
        result = redact_string("Bearer sk-secret-abc header")
        assert "[REDACTED]" in result
        assert "sk-secret-abc" not in result
        del os.environ["BEST_MODEL_API_KEY"]

    def test_redact_string_with_extra_secrets(self):
        result = redact_string("my token custom-key-xyz is here", {"custom-key-xyz"})
        assert "[REDACTED]" in result
        assert "custom-key-xyz" not in result

    def test_redact_value_string(self):
        from data_agent.model_adapters.redaction import redact_value
        result = redact_value("text with custom-key-xyz inside", {"custom-key-xyz"})
        assert "[REDACTED]" in result
        assert "custom-key-xyz" not in result

    def test_redact_value_list(self):
        from data_agent.model_adapters.redaction import redact_value
        result = redact_value(["a", "b custom-key-xyz c"], {"custom-key-xyz"})
        assert "[REDACTED]" in result[1]
        assert "custom-key-xyz" not in result[1]

    def test_redact_value_nested(self):
        from data_agent.model_adapters.redaction import redact_value
        result = redact_value(
            {"top": "hello", "nested": {"deep": "secret-token-123"}},
            {"secret-token-123"},
        )
        assert "[REDACTED]" in result["nested"]["deep"]
        assert "secret-token-123" not in result["nested"]["deep"]

    def test_redact_dict_strips_authorization(self):
        data = {"Authorization": "Bearer token123", "data": "hello"}
        result = redact_dict(data)
        assert result["Authorization"] == "[REDACTED]"
        assert result["data"] == "hello"

    def test_redact_dict_strips_api_key(self):
        data = {"api_key": "key123", "info": "test"}
        result = redact_dict(data)
        assert result["api_key"] == "[REDACTED]"

    def test_redact_dict_recursive(self):
        data = {"nested": {"Authorization": "Bearer xyz"}, "items": [{"api_key": "abc"}]}
        result = redact_dict(data)
        assert result["nested"]["Authorization"] == "[REDACTED]"
        assert result["items"][0]["api_key"] == "[REDACTED]"

    def test_sanitize_removes_forbidden_keys(self):
        output = {
            "factual_observations": ["test"],
            "final_conclusion": "should be removed",
            "mechanism_explanation": "should be removed",
            "experiment_recommendation": "should be removed",
        }
        cleaned, removed = sanitize_model_output_json(output)
        assert "final_conclusion" not in cleaned
        assert "mechanism_explanation" not in cleaned
        assert "experiment_recommendation" not in cleaned
        assert cleaned == {"factual_observations": ["test"]}
        assert set(removed) == {"final_conclusion", "mechanism_explanation", "experiment_recommendation"}

    def test_sanitize_forbidden_keys_deep(self):
        data = {
            "ok": "value",
            "nested": {
                "final_conclusion": "bad",
                "deep_nested": {
                    "mechanism_explanation": "also bad",
                },
            },
            "list": [
                {"experiment_recommendation": "remove me", "keep": "yes"},
            ],
        }
        cleaned, removed = sanitize_forbidden_keys_deep(data)
        assert "final_conclusion" not in str(cleaned)
        assert "mechanism_explanation" not in str(cleaned)
        assert "experiment_recommendation" not in str(cleaned)
        assert cleaned["ok"] == "value"
        assert cleaned["list"][0]["keep"] == "yes"
        assert len(removed) == 3

    def test_sanitize_and_redact_model_result(self):
        data = {
            "success": True,
            "role": "ocr",
            "provider": "openai",
            "mode": "cloud",
            "output_json": {"text": "hello"},
            "final_conclusion": "should be gone",
            "raw_text": "some text with secret-abc in it",
            "raw_response": {},
            "confidence": 0.8,
            "warnings": [],
            "created_at": "2025-01-01T00:00:00Z",
            "schema_version": "model_result_v1",
            "prompt_version": "v1",
        }
        result = sanitize_and_redact_model_result(data, {"secret-abc"})
        assert "final_conclusion" not in result
        assert "secret-abc" not in str(result)
        assert "[REDACTED]" in result["raw_text"]
        assert result["success"] is True
        assert result["output_json"]["text"] == "hello"
