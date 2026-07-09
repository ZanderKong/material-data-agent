"""Tests for file classification."""
import pytest
from pathlib import Path
from data_agent.classify import classify_file
from data_agent.schemas import DataType


def _classify(name: str, inbox: Path):
    path = inbox / name
    if not path.exists():
        pytest.skip(f"Demo file not found: {path}")
    return classify_file(path)


def test_sample_metadata(demo_inbox):
    if not demo_inbox:
        pytest.skip("Demo inbox not available")
    dtype, subtype, conf, _ = _classify("sample_metadata.csv", demo_inbox)
    assert dtype == DataType.SAMPLE_METADATA


def test_thickness(demo_inbox):
    if not demo_inbox:
        pytest.skip("Demo inbox not available")
    dtype, subtype, conf, _ = _classify("sample_thickness.csv", demo_inbox)
    assert dtype == DataType.RAW_NUMERIC
    assert subtype == "thickness"


def test_resistance(demo_inbox):
    if not demo_inbox:
        pytest.skip("Demo inbox not available")
    dtype, subtype, conf, _ = _classify("sample_resistance.csv", demo_inbox)
    assert dtype == DataType.RAW_NUMERIC
    assert subtype == "resistance"


def test_ftir_raw(demo_inbox):
    if not demo_inbox:
        pytest.skip("Demo inbox not available")
    dtype, subtype, conf, _ = _classify("sample_ftir_raw.csv", demo_inbox)
    assert dtype == DataType.RAW_SPECTRAL
    assert subtype == "FTIR"


def test_uvvis_raw(demo_inbox):
    if not demo_inbox:
        pytest.skip("Demo inbox not available")
    dtype, subtype, conf, _ = _classify("sample_uvvis_raw.csv", demo_inbox)
    assert dtype == DataType.RAW_SPECTRAL
    assert subtype == "UVVis"


def test_ftir_chart(demo_inbox):
    if not demo_inbox:
        pytest.skip("Demo inbox not available")
    dtype, subtype, conf, _ = _classify("sample_ftir_chart.png", demo_inbox)
    assert dtype == DataType.CHART_IMAGE_INPUT
    assert subtype == "FTIR"


def test_uvvis_chart(demo_inbox):
    if not demo_inbox:
        pytest.skip("Demo inbox not available")
    dtype, subtype, conf, _ = _classify("sample_uvvis_chart.png", demo_inbox)
    assert dtype == DataType.CHART_IMAGE_INPUT
    assert subtype == "UVVis"


def test_observation_text(demo_inbox):
    if not demo_inbox:
        pytest.skip("Demo inbox not available")
    dtype, subtype, conf, _ = _classify("observation_sample_A.txt", demo_inbox)
    assert dtype == DataType.DESCRIPTIVE_OBSERVATION_TEXT


def test_surface_photo(demo_inbox):
    if not demo_inbox:
        pytest.skip("Demo inbox not available")
    dtype, subtype, conf, _ = _classify("sample_surface_photo.png", demo_inbox)
    assert dtype == DataType.VISUAL_IMAGE
