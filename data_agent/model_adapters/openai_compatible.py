"""OpenAI-compatible provider: HTTP calls to chat/completions endpoint."""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import requests

from .base import ModelProfile, ModelResult, TaskContext
from .prompts import get_prompt_for_role
from .redaction import redact_dict, redact_string, sanitize_model_output_json


def _encode_image(image_path: str) -> str:
    path = Path(image_path)
    ext = path.suffix.lower().lstrip(".")
    mime_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
    mime = mime_map.get(ext, "image/png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def call_openai_compatible(
    profile: ModelProfile,
    ctx: TaskContext,
    env: dict[str, str],
    image_path: str = "",
) -> ModelResult:
    start = time.time()
    base_url = env.get("base_url", "").rstrip("/")
    api_key = env.get("api_key", "")
    model_name = env.get("model", "")

    if not base_url or not api_key or not model_name:
        return ModelResult(
            success=False,
            role=profile.role,
            provider=profile.provider,
            mode=ctx.model_mode,
            error="Model not configured: missing base_url, api_key, or model env var.",
            fallback_used=True,
            fallback_from=profile.name,
            prompt_version="",
        )

    system_msg, user_prompt = get_prompt_for_role(profile.role)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_msg},
    ]

    if profile.supports_vision and ctx.has_image and image_path:
        img_url = _encode_image(image_path)
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": img_url}},
            ],
        })
    else:
        messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.0,
    }
    if profile.supports_json:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=profile.timeout_seconds,
        )
        latency_ms = int((time.time() - start) * 1000)

        if resp.status_code != 200:
            redacted_text = redact_string(resp.text[:500], {api_key}) if api_key else redact_string(resp.text[:500])
            return ModelResult(
                success=False,
                role=profile.role,
                provider=profile.provider,
                model=model_name,
                mode=ctx.model_mode,
                error=f"HTTP {resp.status_code}: {redacted_text}",
                latency_ms=latency_ms,
                prompt_version="",
            )

        raw = resp.json()
        redacted_raw = redact_dict(raw, {api_key} if api_key else None)

        content = ""
        choices = raw.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        output_json: dict[str, Any] = {}
        parse_error = ""
        try:
            if content.strip():
                output_json = json.loads(content)
        except json.JSONDecodeError as e:
            parse_error = f"Invalid JSON from model: {e}"

        output_json, forbidden_keys = sanitize_model_output_json(output_json)
        warnings: list[str] = []
        if forbidden_keys:
            warnings.append("model_output_excluded_from_conclusion")

        token_usage: dict[str, Any] = {}
        usage = raw.get("usage", {})
        if usage:
            token_usage = {"prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"), "total_tokens": usage.get("total_tokens")}

        success = bool(output_json) and not parse_error

        return ModelResult(
            success=success,
            role=profile.role,
            provider=profile.provider,
            model=model_name,
            mode=ctx.model_mode,
            input_type="image" if image_path else "text",
            output_json=output_json,
            raw_text=redact_string(content, {api_key} if api_key else None),
            raw_response=redacted_raw,
            confidence=0.8 if success else 0.0,
            warnings=warnings,
            error=parse_error,
            latency_ms=latency_ms,
            token_usage=token_usage,
            prompt_version="v1",
        )

    except requests.Timeout:
        latency_ms = int((time.time() - start) * 1000)
        return ModelResult(
            success=False,
            role=profile.role,
            provider=profile.provider,
            model=model_name,
            mode=ctx.model_mode,
            error=f"Request timed out after {profile.timeout_seconds}s",
            fallback_used=True,
            fallback_from=profile.name,
            latency_ms=latency_ms,
            prompt_version="",
        )
    except requests.RequestException as e:
        latency_ms = int((time.time() - start) * 1000)
        redacted_err = redact_string(str(e), {api_key}) if api_key else redact_string(str(e))
        return ModelResult(
            success=False,
            role=profile.role,
            provider=profile.provider,
            model=model_name,
            mode=ctx.model_mode,
            error=f"Request error: {redacted_err}",
            fallback_used=True,
            fallback_from=profile.name,
            latency_ms=latency_ms,
            prompt_version="",
        )
