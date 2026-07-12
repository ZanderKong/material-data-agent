"""Prompt templates for each task role. All prompts enforce output boundaries."""
from __future__ import annotations

SYSTEM_BOUNDARY = (
    "You are a data extraction assistant. Output JSON only. "
    "Only report visible observations, metadata, uncertainty, and review needs. "
    "Do not produce scientific conclusions, mechanism explanations, or experiment recommendations. "
    "Do not invent invisible information. If uncertain, set requires_review=true."
)

CHART_IMAGE_OCR_SYSTEM = SYSTEM_BOUNDARY + (
    " Extract text blocks, labels, numbers, and units visible in the chart image."
)

CHART_IMAGE_OCR_PROMPT = """Analyze this chart image and extract:
- image_kind (e.g. "line_chart", "bar_chart", etc.)
- title
- x_axis_label
- y_axis_label
- detected_units
- legend_text
- visible_series_count
- text_blocks (all visible text)
- axis_candidates (list of axis label candidates)
- unreadable_regions (list of ambiguous or unreadable areas)
- uncertainties (list of ambiguity descriptions)
- requires_review (true if any text is ambiguous)
- confidence (0.0-1.0)

Output JSON only."""

CHART_IMAGE_VISION_SYSTEM = SYSTEM_BOUNDARY + (
    " Describe visible chart structure: chart type, axes, curves, peaks, labels, legends."
)

CHART_IMAGE_VISION_PROMPT = """Analyze this chart image and extract:
- image_kind (e.g. "line_chart", "bar_chart")
- chart_type
- title
- x_axis_label
- y_axis_label
- detected_units
- legend_text
- visible_series_count
- visible_peak_candidates (list of approximate x,y positions of visible peaks)
- text_blocks
- uncertainties (list of any ambiguous features)
- requires_review
- confidence (0.0-1.0)

Output JSON only."""

VISUAL_IMAGE_VISION_SYSTEM = SYSTEM_BOUNDARY + (
    " Describe visible content of surface/microscope images: objects, features, annotations."
)

VISUAL_IMAGE_VISION_PROMPT = """Analyze this image and extract:
- image_kind (e.g. "surface_photo", "SEM", "microscope")
- detected_objects (visible particles, cracks, layers, etc.)
- visible_features (texture, color, patterns)
- scale_bar_text (if visible)
- annotation_text (any text overlays)
- possible_measurement_targets
- uncertainties
- requires_review
- confidence (0.0-1.0)

Do not output particle size statistics, SEM final morphology conclusion, or material performance judgment.
Output JSON only."""

OBSERVATION_TEXT_SYSTEM = SYSTEM_BOUNDARY + (
    " Extract structured observations from experimental notes."
)

OBSERVATION_TEXT_PROMPT = """Analyze this observation text and extract:
- factual_observations (list of observed facts)
- trend_statements (trend-like descriptions)
- interpretation_candidates (phrases suggesting speculation, with uncertainty markers like "可能", "或许", "大概")
- operator_notes
- sample_ids
- time_expressions
- phenomenon_types
- uncertainties (list of ambiguity descriptions)
- requires_review
- confidence (0.0-1.0)

Output JSON only."""


def get_prompt_for_role(role: str, prompt_version: str = "") -> tuple[str, str]:
    if role == "ocr":
        return CHART_IMAGE_OCR_SYSTEM, CHART_IMAGE_OCR_PROMPT
    if role == "vision":
        return CHART_IMAGE_VISION_SYSTEM, CHART_IMAGE_VISION_PROMPT
    if role == "observation":
        return OBSERVATION_TEXT_SYSTEM, OBSERVATION_TEXT_PROMPT
    if role == "fast":
        return OBSERVATION_TEXT_SYSTEM, OBSERVATION_TEXT_PROMPT
    return SYSTEM_BOUNDARY, "Output JSON only."
