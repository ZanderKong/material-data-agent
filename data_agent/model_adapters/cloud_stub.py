"""Cloud model adapter stub: placeholder for future cloud API integration."""
from __future__ import annotations

from .base import ModelResult


class CloudStubAnalyzer:
    def analyze(self, image_path: str, context: dict | None = None) -> ModelResult:
        return ModelResult(
            success=False,
            role="cloud_stub",
            provider="cloud_stub",
            mode="cloud",
            output_json={"method": "cloud_stub"},
            error="Cloud model not configured. Set appropriate API keys to enable.",
            confidence=0.0,
        )
