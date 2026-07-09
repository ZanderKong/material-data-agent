"""Model adapter base interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelResult:
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""
    confidence: float = 0.0


class ChartImageAnalyzer:
    def analyze(self, image_path: str, context: dict | None = None) -> ModelResult:
        raise NotImplementedError
