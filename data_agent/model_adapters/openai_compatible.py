"""Audited OpenAI-compatible Chat Completions provider implementation."""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Any

import requests
from pydantic import ValidationError

from .base import ModelProfile, ModelResult, TaskContext
from .output_schemas import validate_role_output
from .prompts import get_prompt_for_role
from .redaction import redact_dict, redact_string, sanitize_forbidden_keys_deep


_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
_MAX_IMAGE_BYTES = 20 * 1024 * 1024


def _encode_image(image_path: str) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise ValueError("Image input is missing or is not a regular file")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("Image input is empty")
    if size > _MAX_IMAGE_BYTES:
        raise ValueError(f"Image input exceeds {_MAX_IMAGE_BYTES} byte limit")
    mime = _MIME_TYPES.get(path.suffix.lower())
    if mime is None:
        raise ValueError(f"Unsupported image type: {path.suffix.lower() or '<none>'}")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _join_endpoint(base_url: str, endpoint_path: str) -> str:
    base = base_url.rstrip("/")
    path = "/" + endpoint_path.strip("/")
    if base.endswith(path):
        return base
    return base + path


def build_chat_request(
    profile: ModelProfile,
    ctx: TaskContext,
    model_name: str,
    *,
    base_url: str = "",
    text_input: str = "",
    image_path: str = "",
) -> tuple[str, dict[str, Any]]:
    """Build a provider request without headers or secrets."""
    system_msg, user_prompt = get_prompt_for_role(profile.role)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_msg}]
    modalities = profile.effective_input_modalities()

    if image_path:
        if "image" not in modalities or not ctx.has_image:
            raise ValueError(f"Profile '{profile.name}' does not accept image input")
        image_url: dict[str, str] = {"url": _encode_image(image_path)}
        # Ark accepts OpenAI-style image_url payloads but its endpoint can stall
        # on the optional detail extension for otherwise valid chart images.
        if profile.provider not in {"volcengine_ark", "xiaomi_mimo"}:
            image_url["detail"] = profile.image_detail
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": image_url,
                },
            ],
        })
    else:
        if ctx.has_text:
            if not text_input.strip():
                raise ValueError("Observation text input is empty")
            user_prompt = f"{user_prompt}\n\n<observation_text>\n{text_input}\n</observation_text>"
        messages.append({"role": "user", "content": user_prompt})

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.0,
    }
    if profile.provider == "xiaomi_mimo":
        payload["max_completion_tokens"] = profile.max_output_tokens
    else:
        payload["max_tokens"] = profile.max_output_tokens
    if profile.effective_json_mode() in {"required", "preferred"}:
        payload["response_format"] = {"type": "json_object"}
    if profile.thinking_mode != "provider_default":
        payload["thinking"] = {"type": profile.thinking_mode}
    endpoint = _join_endpoint(base_url, profile.endpoint_path) if base_url else profile.endpoint_path
    return endpoint, payload


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                value = item.get("text", "")
                if isinstance(value, str):
                    parts.append(value)
        return "\n".join(parts)
    return ""


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty_content")
    candidates = [stripped]
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict):
                return value
        except (json.JSONDecodeError, TypeError):
            pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(stripped[index:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    raise ValueError("invalid_json_content")


def _parse_response(raw: Any) -> tuple[dict[str, Any], str, list[str], bool]:
    if not isinstance(raw, dict):
        raise ValueError("response_body_not_object")
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("empty_choices")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ValueError("invalid_choice")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("missing_message")
    # reasoning_content is deliberately not a final-content fallback.
    content = _content_to_text(message.get("content"))
    if not content:
        content = _content_to_text(message.get("final_content"))
    parsed = _extract_json_object(content)
    parsed, forbidden = sanitize_forbidden_keys_deep(parsed)
    warnings: list[str] = []
    requires_review = False
    if forbidden:
        warnings.append("model_output_excluded_from_conclusion")
        requires_review = True
    if choice.get("finish_reason") == "length":
        warnings.append("model_output_truncated")
        requires_review = True
    return parsed, content, warnings, requires_review


def _parse_siliconflow_ocr_plaintext(raw: Any) -> tuple[dict[str, Any], str, list[str], bool]:
    """Conservatively normalize SiliconFlow OCR's documented plain-text output.

    PaddleOCR-VL may return recognized text instead of the JSON requested by the
    generic extraction contract.  This preserves only visible text and marks the
    result for review; it does not infer missing layout, values, or units.
    """
    if not isinstance(raw, dict):
        raise ValueError("response_body_not_object")
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("empty_choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("missing_message")
    content = _content_to_text(message.get("content"))
    if not content.strip():
        raise ValueError("empty_content")

    blocks: list[str] = []
    seen: set[str] = set()
    for line in content.splitlines():
        normalized = re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            blocks.append(normalized)
    if not blocks:
        raise ValueError("empty_content")

    joined = "\n".join(blocks)
    units = re.findall(r"(?<![\w.])(?:nm|μm|um|mm|cm|mV|V|mA|A|Pa|kPa|MPa|GPa|K|°C|a\.u\.)(?!\w)", joined, re.IGNORECASE)
    axis_candidates = [block for block in blocks if re.search(r"\b(?:axis|wavelength|time|signal|intensity|voltage|temperature)\b", block, re.IGNORECASE)]
    warnings = ["siliconflow_ocr_plaintext_normalized"]
    if choices[0].get("finish_reason") == "length":
        warnings.append("model_output_truncated")
    return ({
        "text_blocks": blocks,
        "detected_units": list(dict.fromkeys(units)),
        "axis_candidates": axis_candidates,
        "unreadable_regions": ["Layout and omitted text require manual confirmation."],
        "uncertainties": ["Provider returned plain OCR text without structured layout."],
        "requires_review": True,
        "confidence": 0.5,
    }, content, warnings, True)


def call_openai_compatible(
    profile: ModelProfile,
    ctx: TaskContext,
    env: dict[str, str],
    image_path: str = "",
    text_input: str = "",
) -> ModelResult:
    start = time.monotonic()
    base_url = env.get("base_url", "").rstrip("/")
    api_key = env.get("api_key", "")
    model_name = env.get("model", "")
    secrets = {api_key} if api_key else None

    def failure(error: str, *, latency_ms: int = 0, warnings: list[str] | None = None) -> ModelResult:
        return ModelResult(
            success=False,
            role=profile.role,
            provider=profile.provider,
            model=model_name,
            mode=ctx.model_mode,
            input_type="image" if image_path else "text",
            error=redact_string(error, secrets),
            warnings=warnings or [],
            latency_ms=latency_ms,
            prompt_version="v2",
            requires_review=True,
        )

    if not base_url or not api_key or not model_name:
        return failure("Model not configured: missing base_url, api_key, or model env var.")

    try:
        endpoint, payload = build_chat_request(
            profile, ctx, model_name, base_url=base_url, text_input=text_input, image_path=image_path
        )
    except (OSError, ValueError) as exc:
        return failure(f"Invalid model input: {exc}")

    headers = {"Content-Type": "application/json"}
    if profile.provider == "xiaomi_mimo":
        headers["api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=profile.timeout_seconds)
        latency_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code != 200:
            body = redact_string(getattr(resp, "text", "")[:500], secrets)
            return failure(f"HTTP {resp.status_code}: {body}", latency_ms=latency_ms)
        try:
            raw = resp.json()
        except (ValueError, json.JSONDecodeError):
            return failure("Response body is not JSON", latency_ms=latency_ms)
        redacted_raw = redact_dict(raw, secrets) if isinstance(raw, dict) else {}
        try:
            parsed, content, warnings, requires_review = _parse_response(raw)
        except ValueError as exc:
            if profile.provider == "siliconflow" and profile.role == "ocr" and profile.effective_json_mode() == "disabled":
                try:
                    parsed, content, warnings, requires_review = _parse_siliconflow_ocr_plaintext(raw)
                except ValueError:
                    parsed = None
            else:
                parsed = None
            if parsed is None:
                failed = failure(f"Model response validation failed: {exc}", latency_ms=latency_ms)
                failed.raw_response = redacted_raw
                return failed
        try:
            output_json = validate_role_output(profile.role, ctx.data_type, parsed)
        except ValidationError as exc:
            failed = failure(f"Model response schema validation failed: {exc}", latency_ms=latency_ms, warnings=warnings)
            failed.raw_response = redacted_raw
            failed.raw_text = redact_string(content, secrets)
            return failed
        requires_review = requires_review or bool(output_json.get("requires_review"))
        usage = raw.get("usage") if isinstance(raw, dict) else None
        token_usage: dict[str, Any] = {}
        if isinstance(usage, dict):
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
        else:
            warnings.append("token_usage_unavailable")
        return ModelResult(
            success=True,
            role=profile.role,
            provider=profile.provider,
            model=model_name,
            mode=ctx.model_mode,
            input_type="image" if image_path else "text",
            output_json=output_json,
            raw_text=redact_string(content, secrets),
            raw_response=redacted_raw,
            confidence=float(output_json.get("confidence", 0.0)),
            warnings=warnings,
            latency_ms=latency_ms,
            token_usage=token_usage,
            prompt_version="v2",
            requires_review=requires_review,
        )
    except requests.Timeout:
        return failure(
            f"Request timed out after {profile.timeout_seconds}s",
            latency_ms=int((time.monotonic() - start) * 1000),
        )
    except requests.RequestException as exc:
        return failure(
            f"Request error: {exc}",
            latency_ms=int((time.monotonic() - start) * 1000),
        )
