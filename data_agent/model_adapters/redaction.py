"""Redaction utilities: strip API keys and sensitive values from outputs."""
from __future__ import annotations

import copy
import os
from typing import Any

_REDACT_PLACEHOLDER = "[REDACTED]"


def _get_known_secret_values() -> set[str]:
    secrets: set[str] = set()
    for env_var in (
        "BEST_MODEL_API_KEY", "FAST_MODEL_API_KEY",
        "VISION_MODEL_API_KEY", "OCR_MODEL_API_KEY",
    ):
        val = os.environ.get(env_var, "")
        if val:
            secrets.add(val)
    return secrets


def redact_string(text: str, extra_secrets: set[str] | None = None) -> str:
    secrets = _get_known_secret_values()
    if extra_secrets:
        secrets.update(extra_secrets)
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, _REDACT_PLACEHOLDER)
    return result


def redact_value(value: Any, extra_secrets: set[str] | None = None) -> Any:
    if isinstance(value, str):
        return redact_string(value, extra_secrets)
    if isinstance(value, dict):
        return redact_dict(value, extra_secrets)
    if isinstance(value, list):
        return [redact_value(v, extra_secrets) for v in value]
    return value


def redact_dict(data: dict[str, Any], extra_secrets: set[str] | None = None) -> dict[str, Any]:
    sensitive_keys = {"Authorization", "authorization", "api_key", "api-key", "x-api-key"}
    result: dict[str, Any] = {}

    for key, value in data.items():
        if key in sensitive_keys:
            result[key] = _REDACT_PLACEHOLDER
        elif isinstance(value, str):
            result[key] = redact_string(value, extra_secrets)
        elif isinstance(value, dict):
            result[key] = redact_dict(value, extra_secrets)
        elif isinstance(value, list):
            result[key] = [redact_value(v, extra_secrets) for v in value]
        else:
            result[key] = value
    return result


FORBIDDEN_OUTPUT_KEYS = {
    "final_conclusion",
    "mechanism_explanation",
    "experiment_recommendation",
}


def sanitize_model_output_json(output_json: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    removed_keys: list[str] = []
    cleaned = copy.deepcopy(output_json)
    for key in FORBIDDEN_OUTPUT_KEYS:
        if key in cleaned:
            del cleaned[key]
            removed_keys.append(key)
    return cleaned, removed_keys


def sanitize_forbidden_keys_deep(data: Any) -> tuple[Any, list[str]]:
    removed: list[str] = []
    if isinstance(data, dict):
        cleaned: dict[str, Any] = {}
        for key, value in data.items():
            if key in FORBIDDEN_OUTPUT_KEYS:
                removed.append(key)
                continue
            sanitized_val, sub_removed = sanitize_forbidden_keys_deep(value)
            cleaned[key] = sanitized_val
            removed.extend(sub_removed)
        return cleaned, removed
    if isinstance(data, list):
        result: list[Any] = []
        for item in data:
            sanitized_item, sub_removed = sanitize_forbidden_keys_deep(item)
            result.append(sanitized_item)
            removed.extend(sub_removed)
        return result, removed
    return data, removed


def _strip_non_serializable(obj: Any) -> Any:
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {k: _strip_non_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_strip_non_serializable(v) for v in obj]
    return str(obj)


def sanitize_and_redact_model_result(result_dict: dict[str, Any], extra_secrets: set[str] | None = None) -> dict[str, Any]:
    cleaned, _ = sanitize_forbidden_keys_deep(result_dict)
    redacted = redact_dict(cleaned, extra_secrets)
    return _strip_non_serializable(redacted)
