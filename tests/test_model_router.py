"""Tests for model routing logic."""
import pytest

from data_agent.model_adapters.base import TaskContext
from data_agent.model_adapters.router import route_model_calls, get_fallback_chain
from data_agent.model_adapters.base import ModelProfile


def _make_ctx(data_type: str, model_mode: str = "local") -> TaskContext:
    return TaskContext(
        task_id="task_0001",
        data_type=data_type,
        model_mode=model_mode,
    )


class TestRouteModelCalls:
    def test_raw_numeric_no_models_local(self):
        assert route_model_calls(_make_ctx("raw_numeric", "local")) == []

    def test_raw_numeric_no_models_cloud(self):
        assert route_model_calls(_make_ctx("raw_numeric", "cloud")) == []

    def test_raw_numeric_no_models_auto(self):
        assert route_model_calls(_make_ctx("raw_numeric", "auto")) == []

    def test_raw_spectral_no_models(self):
        for mode in ("local", "cloud", "auto"):
            assert route_model_calls(_make_ctx("raw_spectral", mode)) == []

    def test_sample_metadata_no_models(self):
        for mode in ("local", "cloud", "auto"):
            assert route_model_calls(_make_ctx("sample_metadata", mode)) == []

    def test_chart_image_ocr_vision_cloud(self):
        roles = route_model_calls(_make_ctx("chart_image_input", "cloud"))
        assert "ocr" in roles
        assert "vision" in roles

    def test_chart_image_ocr_vision_auto(self):
        roles = route_model_calls(_make_ctx("chart_image_input", "auto"))
        assert "ocr" in roles
        assert "vision" in roles

    def test_chart_image_local_stub_only(self):
        roles = route_model_calls(_make_ctx("chart_image_input", "local"))
        assert roles == ["local_stub"]

    def test_visual_image_vision_ocr_cloud(self):
        roles = route_model_calls(_make_ctx("visual_image", "cloud"))
        assert "vision" in roles
        assert "ocr" in roles

    def test_visual_image_local_vision_stub(self):
        roles = route_model_calls(_make_ctx("visual_image", "local"))
        assert "local_vision_stub" in roles

    def test_observation_text_fast_non_local(self):
        roles = route_model_calls(_make_ctx("descriptive_observation_text", "cloud"))
        assert "fast" in roles

    def test_observation_text_no_models_local(self):
        roles = route_model_calls(_make_ctx("descriptive_observation_text", "local"))
        assert roles == []

    def test_structured_observation_no_models(self):
        for mode in ("local", "cloud", "auto"):
            assert route_model_calls(_make_ctx("structured_observation", mode)) == []


class TestFallbackChain:
    def test_default_fallbacks(self):
        assert "local_ocr_stub" in get_fallback_chain("ocr", {})
        assert "local_stub" in get_fallback_chain("vision", {})
        assert "local_stub" in get_fallback_chain("fast", {})

    def test_profile_fallbacks(self):
        profiles = {
            "ocr": ModelProfile(
                name="ocr",
                role="ocr",
                provider="openai_compatible",
                fallback=["custom_stub"],
            ),
        }
        chain = get_fallback_chain("ocr", profiles)
        assert "custom_stub" in chain
