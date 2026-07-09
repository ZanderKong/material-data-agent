"""Local stub model providers: return structured ModelResult without network calls."""
from __future__ import annotations

import time
from typing import Any

from .base import ModelResult, TaskContext


def _make_stub_result(
    success: bool,
    role: str,
    provider: str,
    output_json: dict[str, Any] | None = None,
    error: str = "",
    confidence: float = 0.0,
    warnings: list[str] | None = None,
) -> ModelResult:
    return ModelResult(
        success=success,
        role=role,
        provider=provider,
        mode="local",
        output_json=output_json or {},
        error=error,
        confidence=confidence,
        warnings=warnings or [],
        fallback_used=False,
        prompt_version="stub_v1",
    )


def local_stub(ctx: TaskContext) -> ModelResult:
    msg = "Local stub: no model available. Metadata extracted from filename and local rules only."
    return _make_stub_result(
        success=True,
        role=ctx.data_type,
        provider="local_stub",
        output_json={
            "method": "local_rules",
            "note": msg,
            "requires_review": True,
        },
        confidence=0.6,
        warnings=[msg],
    )


def local_ocr_stub(ctx: TaskContext) -> ModelResult:
    msg = "OCR unavailable: local mode does not support text extraction from images."
    return _make_stub_result(
        success=False,
        role="ocr",
        provider="local_ocr_stub",
        output_json={
            "method": "local_ocr_stub",
            "note": msg,
            "ocr_unavailable": True,
            "requires_review": True,
        },
        confidence=0.0,
        warnings=[msg, "ocr_unavailable"],
    )


def local_vision_stub(ctx: TaskContext) -> ModelResult:
    msg = "Vision unavailable: local mode does not support image content analysis."
    return _make_stub_result(
        success=False,
        role="vision",
        provider="local_vision_stub",
        output_json={
            "method": "local_vision_stub",
            "note": msg,
            "vision_unavailable": True,
            "requires_review": True,
        },
        confidence=0.0,
        warnings=[msg, "image_observation_requires_review"],
    )


STUB_REGISTRY: dict[str, Any] = {
    "local_stub": local_stub,
    "local_ocr_stub": local_ocr_stub,
    "local_vision_stub": local_vision_stub,
}
