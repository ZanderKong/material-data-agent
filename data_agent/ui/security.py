"""UI-layer error redaction for safe display in Streamlit."""
from __future__ import annotations

import os
import re

from data_agent.model_adapters.redaction import redact_string as _redact_string


_SK_PATTERN = re.compile(r'sk-[A-Za-z0-9_\-]{10,}')
_BEARER_PATTERN = re.compile(r'Bearer\s+[A-Za-z0-9_\-\.=\+\/]{10,}')

_KEY_ENV_NAMES = {
    "BEST_MODEL_API_KEY", "FAST_MODEL_API_KEY",
    "VISION_MODEL_API_KEY", "OCR_MODEL_API_KEY",
    "DEEPSEEK_TEXT_API_KEY", "MIMO_VISION_API_KEY",
    "SILICONFLOW_OCR_API_KEY",
}


def safe_display_text(text: str) -> str:
    """Redact secrets for display (raw response, etc).

    Redacts sk-* tokens, Bearer headers, and env var values.
    Does NOT redact env var names (unlike safe_ui_error) since
    display text may legitimately reference them in documentation.
    """
    text = _SK_PATTERN.sub("[REDACTED]", text)
    text = _BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    for env_name in _KEY_ENV_NAMES:
        val = os.environ.get(env_name, "")
        if val and val in text:
            text = text.replace(val, "[REDACTED]")
    text = _redact_string(text)
    return text


def safe_ui_error(message: object) -> str:
    """Redact secrets from error messages for Streamlit display.

    Also redacts env var NAMES in addition to values and patterns,
    since error messages should not leak which env vars are configured.
    """
    text = str(message)
    text = _SK_PATTERN.sub("[REDACTED]", text)
    text = _BEARER_PATTERN.sub("Bearer [REDACTED]", text)

    for env_name in _KEY_ENV_NAMES:
        val = os.environ.get(env_name, "")
        if val and val in text:
            text = text.replace(val, "[REDACTED]")
        if env_name in text:
            text = text.replace(env_name, "[ENV_VAR_NAME_REDACTED]")

    text = _redact_string(text)
    return text
