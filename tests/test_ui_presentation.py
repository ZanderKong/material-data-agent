"""Tests for UI presentation helpers."""
import pytest

from data_agent.ui.presentation import (
    suggested_quality_action,
    format_quality_flag,
    format_model_output,
    cloud_mode_notice,
)


class TestSuggestedQualityAction:
    def test_axis_confirmation(self):
        assert "axis" in suggested_quality_action({"message": "axis_confirmation_required", "requires_review": True}).lower()

    def test_model_unavailable(self):
        action = suggested_quality_action({"message": "model_unavailable for ocr", "requires_review": True})
        assert "local" in action.lower()

    def test_fallback_used(self):
        action = suggested_quality_action({"message": "fallback_used: local_stub", "requires_review": True})
        assert "local" in action.lower()

    def test_low_confidence(self):
        action = suggested_quality_action({"message": "low_confidence detection", "requires_review": True})
        assert "low confidence" in action.lower()

    def test_requires_review_generic(self):
        action = suggested_quality_action({"message": "unknown issue", "requires_review": True})
        assert "review" in action.lower()

    def test_no_action_required(self):
        action = suggested_quality_action({"message": "info only", "requires_review": False})
        assert "no action" in action.lower()


class TestFormatQualityFlag:
    def test_redacts_message(self, monkeypatch):
        monkeypatch.setenv("BEST_MODEL_API_KEY", "secret-abc")
        result = format_quality_flag({"message": "error with secret-abc", "requires_review": True})
        assert "secret-abc" not in result["message"]
        assert "REDACTED" in result["message"]

    def test_includes_suggested_action(self):
        result = format_quality_flag({"message": "low_confidence result", "requires_review": True})
        assert result["suggested_action"]


class TestFormatModelOutput:
    def test_extracts_text_blocks(self):
        result = format_model_output({"text_blocks": ["a", "b"], "detected_units": ["mm"]})
        assert result["text_blocks"] == ["a", "b"]
        assert result["detected_units"] == ["mm"]

    def test_empty_output(self):
        result = format_model_output({})
        assert result == {"text_blocks": None, "detected_units": None, "axis_candidates": None, "visible_features": None, "factual_observations": None, "interpretation_candidates": None, "method": None, "note": None}

    def test_non_dict_input(self):
        result = format_model_output(None)
        assert result == {}


class TestCloudModeNotice:
    def test_local_empty(self):
        assert cloud_mode_notice("local") == ""

    def test_cloud_non_empty(self):
        assert "cloud" in cloud_mode_notice("cloud").lower()

    def test_auto_non_empty(self):
        assert "auto" in cloud_mode_notice("auto").lower()
