"""Provider payload, response parsing, and audited fallback contracts."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from data_agent.db import init_db
from data_agent.ingest import ingest_inbox
from data_agent.model_adapters.base import ModelExecution, ModelProfile, ModelResult, TaskContext
from data_agent.model_adapters.openai_compatible import build_chat_request, call_openai_compatible
from data_agent.process import _execute_model_role, process_single_task


def observation_output(**overrides):
    value = {
        "factual_observations": ["sample visible"], "trend_statements": [],
        "interpretation_candidates": [], "operator_notes": [], "sample_ids": ["S-01"],
        "time_expressions": [], "phenomenon_types": [], "uncertainties": [],
        "requires_review": False, "confidence": 0.9,
    }
    value.update(overrides)
    return value


def ocr_output(**overrides):
    value = {
        "text_blocks": ["Absorbance"], "detected_units": ["a.u."],
        "axis_candidates": ["Wavelength"], "unreadable_regions": [],
        "uncertainties": [], "requires_review": False, "confidence": 0.92,
    }
    value.update(overrides)
    return value


def profile(role="fast", provider="deepseek", image=False, json_mode="required"):
    return ModelProfile(
        name=role, role=role, provider=provider, base_url_env="URL", api_key_env="KEY",
        model_env="MODEL", supports_vision=image, supports_json=json_mode != "disabled",
        input_modalities=["text", "image"] if image else ["text"], json_mode=json_mode,
        thinking_mode="disabled" if provider == "deepseek" else "provider_default",
    )


def env(model="deepseek-v4-pro"):
    return {"base_url": "https://provider.example/v1", "api_key": "test-secret", "model": model}


def response(content, *, usage=True, finish_reason="stop"):
    resp = MagicMock()
    resp.status_code = 200
    body = {"choices": [{"finish_reason": finish_reason, "message": {"content": content}}]}
    if usage:
        body["usage"] = {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}
    resp.json.return_value = body
    return resp


def test_deepseek_payload_contains_real_text_and_json_mode():
    p = profile()
    ctx = TaskContext(task_id="t", data_type="descriptive_observation_text", has_text=True, model_mode="cloud")
    endpoint, payload = build_chat_request(p, ctx, "deepseek-v4-pro", base_url="https://api.deepseek.com/", text_input="S-01 became cloudy")
    assert endpoint == "https://api.deepseek.com/chat/completions"
    assert payload["model"] == "deepseek-v4-pro"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["thinking"] == {"type": "disabled"}
    assert "<observation_text>" in payload["messages"][1]["content"]
    assert "S-01 became cloudy" in payload["messages"][1]["content"]


@pytest.mark.parametrize("provider_name,model,expect_detail", [
    ("xiaomi_mimo", "mimo-v2.5", False),
    ("siliconflow", "PaddlePaddle/PaddleOCR-VL-1.5", True),
])
def test_multimodal_provider_payload(provider_name, model, expect_detail, tmp_path):
    image = tmp_path / "chart.png"
    image.write_bytes(b"valid-test-bytes")
    p = profile("ocr", provider_name, image=True, json_mode="disabled")
    ctx = TaskContext(task_id="t", data_type="chart_image_input", has_image=True, model_mode="cloud")
    endpoint, payload = build_chat_request(p, ctx, model, base_url="https://provider.example/v1", image_path=str(image))
    assert endpoint == "https://provider.example/v1/chat/completions"
    assert payload["model"] == model
    assert "response_format" not in payload
    parts = payload["messages"][1]["content"]
    image_part = next(part for part in parts if part["type"] == "image_url")
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")
    if expect_detail:
        assert image_part["image_url"]["detail"] == "high"
    else:
        assert "detail" not in image_part["image_url"]
    if provider_name == "xiaomi_mimo":
        assert payload["max_completion_tokens"] == 2048
        assert "max_tokens" not in payload


@pytest.mark.parametrize("wrapped", [
    lambda value: json.dumps(value),
    lambda value: "```json\n" + json.dumps(value) + "\n```",
    lambda value: "Result follows: " + json.dumps(value) + " End.",
    lambda value: json.dumps(json.dumps(value)),
])
def test_robust_json_extraction(wrapped):
    p = profile()
    ctx = TaskContext(task_id="t", data_type="descriptive_observation_text", model_mode="cloud")
    with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=response(wrapped(observation_output()))):
        result = call_openai_compatible(p, ctx, env())
    assert result.success
    assert result.output_json["sample_ids"] == ["S-01"]


def test_content_array_and_missing_usage():
    content = [{"type": "text", "text": json.dumps(observation_output())}]
    with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=response(content, usage=False)):
        result = call_openai_compatible(profile(), TaskContext(task_id="t", data_type="descriptive_observation_text", model_mode="cloud"), env())
    assert result.success
    assert "token_usage_unavailable" in result.warnings


def test_reasoning_content_is_not_used_as_final_content():
    resp = response("")
    resp.json.return_value["choices"][0]["message"]["reasoning_content"] = json.dumps(observation_output())
    with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=resp):
        result = call_openai_compatible(profile(), TaskContext(task_id="t", data_type="descriptive_observation_text", model_mode="cloud"), env())
    assert not result.success
    assert "empty_content" in result.error


@pytest.mark.parametrize("status", [400, 401, 429, 500])
def test_http_failures_are_explicit_and_redacted(status):
    resp = MagicMock(status_code=status, text="Bearer test-secret")
    with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=resp):
        result = call_openai_compatible(profile(), TaskContext(task_id="t", data_type="descriptive_observation_text", model_mode="cloud"), env())
    assert not result.success
    assert f"HTTP {status}" in result.error
    assert "test-secret" not in result.error


def test_schema_missing_field_and_finish_length():
    with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=response('{"confidence": 0.5}')):
        result = call_openai_compatible(profile(), TaskContext(task_id="t", data_type="descriptive_observation_text", model_mode="cloud"), env())
    assert not result.success
    assert "schema validation" in result.error
    with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=response(json.dumps(observation_output()), finish_reason="length")):
        truncated = call_openai_compatible(profile(), TaskContext(task_id="t", data_type="descriptive_observation_text", model_mode="cloud"), env())
    assert truncated.success and truncated.requires_review
    assert "model_output_truncated" in truncated.warnings


def test_response_body_not_json_and_timeout():
    bad = MagicMock(status_code=200)
    bad.json.side_effect = ValueError("bad")
    with patch("data_agent.model_adapters.openai_compatible.requests.post", return_value=bad):
        result = call_openai_compatible(profile(), TaskContext(task_id="t", data_type="descriptive_observation_text", model_mode="cloud"), env())
    assert not result.success and "not JSON" in result.error
    with patch("data_agent.model_adapters.openai_compatible.requests.post", side_effect=requests.Timeout):
        timed = call_openai_compatible(profile(), TaskContext(task_id="t", data_type="descriptive_observation_text", model_mode="cloud"), env())
    assert not timed.success and "timed out" in timed.error


def test_auto_execution_preserves_failed_cloud_attempt(monkeypatch):
    p = profile()
    monkeypatch.setenv("URL", "https://provider.example/v1")
    monkeypatch.setenv("KEY", "test-secret")
    monkeypatch.setenv("MODEL", "deepseek-v4-pro")
    failed = ModelResult(success=False, role="fast", provider="deepseek", mode="auto", error="HTTP 429", requires_review=True)
    with patch("data_agent.process.call_openai_compatible", return_value=failed):
        execution = _execute_model_role("fast", {"fast": p}, TaskContext(task_id="t", data_type="descriptive_observation_text", model_mode="auto"), text_input="test")
    assert execution is not None
    assert len(execution.attempts) == 2
    assert not execution.attempts[0].success
    assert execution.selected_result.fallback_used
    assert execution.selected_result.provider.startswith("local")


def test_auto_persists_cloud_attempt_and_fallback(tmp_path):
    inbox = tmp_path / "inbox"
    workspace = tmp_path / "workspace"
    inbox.mkdir()
    workspace.mkdir()
    (inbox / "observation_smoke.txt").write_text("S-01 became cloudy; 可能与温度有关", encoding="utf-8")
    conn = init_db(workspace)
    [task_id] = ingest_inbox(inbox, workspace, conn)
    conn.close()
    failed = ModelResult(success=False, role="fast", provider="deepseek", mode="auto", error="HTTP 429", requires_review=True)
    fallback = ModelResult(success=True, role="fast", provider="local_stub", mode="local", output_json={"requires_review": True}, fallback_used=True, fallback_from="fast", requires_review=True)
    execution = ModelExecution(attempts=[failed, fallback], selected_result=fallback)
    with patch("data_agent.process._execute_model_role", return_value=execution):
        assert process_single_task(workspace, task_id, "auto")
    derived = workspace / "tasks" / task_id / "derived"
    assert list(derived.glob("*model_result_fast_cloud_attempt.json"))
    assert list(derived.glob("*model_result_fast.json"))
    db = sqlite3.connect(workspace / "agent.sqlite")
    statuses = [row[0] for row in db.execute("SELECT status FROM processing_runs WHERE tool_name='model:fast'")]
    messages = [row[0] for row in db.execute("SELECT message FROM quality_flags")]
    db.close()
    assert "failed" in statuses and "succeeded" in statuses
    assert any("model_unavailable" in message for message in messages)
    assert any("fallback_used" in message for message in messages)
