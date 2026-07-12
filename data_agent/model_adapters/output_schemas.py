"""Strict role-level schemas for model-assisted extraction outputs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExtractionBase(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    requires_review: bool
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainties: list[str]


class ObservationExtraction(ExtractionBase):
    factual_observations: list[str]
    trend_statements: list[str]
    interpretation_candidates: list[str]
    operator_notes: list[str]
    sample_ids: list[str]
    time_expressions: list[str]
    phenomenon_types: list[str]


class ChartVisionExtraction(ExtractionBase):
    image_kind: str
    chart_type: str
    x_axis_label: str
    y_axis_label: str
    detected_units: list[str]
    legend_text: list[str]
    visible_series_count: int = Field(ge=0)
    visible_peak_candidates: list[Any]


class SurfaceVisionExtraction(ExtractionBase):
    image_kind: str
    detected_objects: list[str]
    visible_features: list[str]
    scale_bar_text: str
    annotation_text: list[str]


class OcrExtraction(ExtractionBase):
    text_blocks: list[str]
    detected_units: list[str]
    axis_candidates: list[str]
    unreadable_regions: list[str]


def validate_role_output(role: str, data_type: str, output: dict[str, Any]) -> dict[str, Any]:
    if role in {"fast", "observation"}:
        schema = ObservationExtraction
    elif role == "ocr":
        schema = OcrExtraction
    elif role == "vision" and data_type == "visual_image":
        schema = SurfaceVisionExtraction
    elif role == "vision":
        schema = ChartVisionExtraction
    else:
        raise ValueError(f"No output schema registered for role '{role}'")
    return schema.model_validate(output).model_dump(mode="json")
