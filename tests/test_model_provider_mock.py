"""Tests for model providers using mock HTTP calls."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from data_agent.model_adapters.base import ModelProfile, TaskContext
from data_agent.model_adapters.openai_compatible import call_openai_compatible
from data_agent.model_adapters.redaction import redact_string, sanitize_and_redact_model_result


TEST_SECRET = "unit-test-secret-token-xyz"


def _make_profile(role: str = "fast", supports_vision: bool = False) -> ModelProfile:
    return ModelProfile(
        name=role,
        role=role,
        provider="openai_compatible",
        base_url_env="TEST_BASE",
        api_key_env="TEST_KEY",
        model_env="TEST_MODEL",
        timeout_seconds=10,
        supports_vision=supports_vision,
        supports_json=True,
    )


def _make_env() -> dict[str, str]:
    return {
        "base_url": "https://api.example.com/v1",
        "api_key": TEST_SECRET,
        "model": "test-model-v1",
    }


def _make_ctx() -> TaskContext:
    return TaskContext(
        task_id="task_0001",
        data_type="descriptive_observation_text",
        model_mode="cloud",
    )


def _observation_output(**overrides):
    value = {
        "factual_observations": ["test"],
        "trend_statements": [],
        "interpretation_candidates": [],
        "operator_notes": [],
        "sample_ids": [],
        "time_expressions": [],
        "phenomenon_types": [],
        "uncertainties": [],
        "requires_review": False,
        "confidence": 0.9,
    }
    value.update(overrides)
    return value


def _surface_output(**overrides):
    value = {
        "image_kind": "surface_photo",
        "detected_objects": ["particle"],
        "visible_features": ["uniform texture"],
        "scale_bar_text": "",
        "annotation_text": [],
        "uncertainties": [],
        "requires_review": False,
        "confidence": 0.8,
    }
    value.update(overrides)
    return value


class TestProviderMockText:
    def test_success_with_valid_json(self):
        profile = _make_profile("fast")
        env = _make_env()
        ctx = _make_ctx()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(_observation_output())}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=mock_resp):
            result = call_openai_compatible(profile, ctx, env)

        assert result.success
        assert result.output_json["factual_observations"] == ["test"]
        assert result.output_json["confidence"] == 0.9
        assert result.model == "test-model-v1"
        assert result.token_usage["total_tokens"] == 15

    def test_invalid_json(self):
        profile = _make_profile("fast")
        env = _make_env()
        ctx = _make_ctx()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "not valid json"}}],
        }

        with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=mock_resp):
            result = call_openai_compatible(profile, ctx, env)

        assert not result.success
        assert "invalid_json_content" in result.error

    def test_http_error(self):
        profile = _make_profile("fast")
        env = _make_env()
        ctx = _make_ctx()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=mock_resp):
            result = call_openai_compatible(profile, ctx, env)

        assert not result.success
        assert "500" in result.error

    def test_timeout(self):
        import requests as rq
        profile = _make_profile("fast")
        env = _make_env()
        ctx = _make_ctx()

        with patch("data_agent.model_adapters.openai_compatible.requests.post", side_effect=rq.Timeout):
            result = call_openai_compatible(profile, ctx, env)

        assert not result.success
        assert "timed out" in result.error.lower()

    def test_api_key_not_in_result(self):
        profile = _make_profile("fast")
        env = _make_env()
        ctx = _make_ctx()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"ok": true}'}}],
        }

        with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=mock_resp):
            result = call_openai_compatible(profile, ctx, env)

        result_json = json.dumps(result.model_dump())
        assert TEST_SECRET not in result_json

    def test_http_error_redacts_secret(self):
        profile = _make_profile("fast")
        env = _make_env()
        ctx = _make_ctx()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = f"Server error with secret: {TEST_SECRET}"

        with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=mock_resp):
            result = call_openai_compatible(profile, ctx, env)

        result_json = result.model_dump_json()
        assert TEST_SECRET not in result_json

    def test_request_exception_redacts_secret(self):
        import requests as rq
        profile = _make_profile("fast")
        env = _make_env()
        ctx = _make_ctx()

        with patch("data_agent.model_adapters.openai_compatible.requests.post",
                   side_effect=rq.RequestException(f"Connection failed with key: {TEST_SECRET}")):
            result = call_openai_compatible(profile, ctx, env)

        result_json = result.model_dump_json()
        assert TEST_SECRET not in result_json

    def test_missing_env(self):
        profile = _make_profile("fast")
        ctx = _make_ctx()
        env = {"base_url": "", "api_key": "", "model": ""}
        result = call_openai_compatible(profile, ctx, env)
        assert not result.success
        assert "not configured" in result.error.lower()


class TestProviderMockVision:
    def test_vision_success(self):
        import tempfile
        profile = _make_profile("vision", supports_vision=True)
        env = _make_env()
        ctx = TaskContext(
            task_id="task_0001",
            data_type="visual_image",
            model_mode="cloud",
            has_image=True,
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake png content")
            img_path = f.name

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(_surface_output())}}],
        }

        with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=mock_resp):
            result = call_openai_compatible(profile, ctx, env, image_path=img_path)

        os.unlink(img_path)
        assert result.success
        assert "particle" in str(result.output_json)

    def test_vision_forbidden_keys_removed(self):
        import tempfile
        profile = _make_profile("vision", supports_vision=True)
        env = _make_env()
        ctx = TaskContext(
            task_id="task_0001",
            data_type="visual_image",
            model_mode="cloud",
            has_image=True,
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake png content")
            img_path = f.name

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(_surface_output(
                detected_objects=[], final_conclusion="bad"
            ))}}],
        }

        with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=mock_resp):
            result = call_openai_compatible(profile, ctx, env, image_path=img_path)

        os.unlink(img_path)
        assert "final_conclusion" not in result.output_json
        assert "model_output_excluded_from_conclusion" in result.warnings


class TestStubProviders:
    def test_local_stub(self):
        from data_agent.model_adapters.stubs import local_stub
        ctx = TaskContext(task_id="t1", data_type="raw_numeric", model_mode="local")
        result = local_stub(ctx)
        assert result.success
        assert result.provider == "local_stub"
        assert result.mode == "local"
        assert result.output_json.get("requires_review") is True

    def test_local_ocr_stub(self):
        from data_agent.model_adapters.stubs import local_ocr_stub
        ctx = TaskContext(task_id="t1", data_type="chart_image_input", model_mode="local")
        result = local_ocr_stub(ctx)
        assert not result.success
        assert result.output_json.get("ocr_unavailable") is True
        assert result.confidence == 0.0
        assert "ocr_unavailable" in result.warnings

    def test_local_vision_stub(self):
        from data_agent.model_adapters.stubs import local_vision_stub
        ctx = TaskContext(task_id="t1", data_type="visual_image", model_mode="local")
        result = local_vision_stub(ctx)
        assert not result.success
        assert result.output_json.get("vision_unavailable") is True
        assert result.confidence == 0.0
        assert "image_observation_requires_review" in result.warnings


class TestLegacyAdapterImports:
    def test_local_adapter_importable(self):
        import data_agent.model_adapters.local
        assert data_agent.model_adapters.local

    def test_cloud_stub_adapter_importable(self):
        import data_agent.model_adapters.cloud_stub
        assert data_agent.model_adapters.cloud_stub
