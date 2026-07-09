"""Local model adapter: uses rule-based logic, no external API."""
from __future__ import annotations

from .base import ChartImageAnalyzer, ModelResult


class LocalAnalyzer(ChartImageAnalyzer):
    def analyze(self, image_path: str, context: dict | None = None) -> ModelResult:
        return ModelResult(
            success=True,
            data={"method": "local_rules", "note": "No cloud model available. Metadata extracted from filename rules."},
            confidence=0.6,
        )
