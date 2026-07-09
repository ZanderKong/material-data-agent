"""Tests for file classification."""
import pytest
from pathlib import Path
from data_agent.classify import classify_file
from data_agent.schemas import DataType

DEMO_DIR = Path("/Users/zanderkong/Desktop/数据处理agent/material_data_agent_demo 测试数据/inbox")


def _classify(name: str):
    path = DEMO_DIR / name
    if not path.exists():
        pytest.skip(f"Demo file not found: {path}")
    return classify_file(path)


def test_sample_metadata():
    dtype, subtype, conf, _ = _classify("sample_metadata.csv")
    assert dtype == DataType.SAMPLE_METADATA


def test_thickness():
    dtype, subtype, conf, _ = _classify("sample_thickness.csv")
    assert dtype == DataType.RAW_NUMERIC
    assert subtype == "thickness"


def test_resistance():
    dtype, subtype, conf, _ = _classify("sample_resistance.csv")
    assert dtype == DataType.RAW_NUMERIC
    assert subtype == "resistance"


def test_ftir_raw():
    dtype, subtype, conf, _ = _classify("sample_ftir_raw.csv")
    assert dtype == DataType.RAW_SPECTRAL
    assert subtype == "FTIR"


def test_uvvis_raw():
    dtype, subtype, conf, _ = _classify("sample_uvvis_raw.csv")
    assert dtype == DataType.RAW_SPECTRAL
    assert subtype == "UVVis"


def test_ftir_chart():
    dtype, subtype, conf, _ = _classify("sample_ftir_chart.png")
    assert dtype == DataType.CHART_IMAGE_INPUT
    assert subtype == "FTIR"


def test_uvvis_chart():
    dtype, subtype, conf, _ = _classify("sample_uvvis_chart.png")
    assert dtype == DataType.CHART_IMAGE_INPUT
    assert subtype == "UVVis"


def test_observation_text():
    dtype, subtype, conf, _ = _classify("observation_sample_A.txt")
    assert dtype == DataType.DESCRIPTIVE_OBSERVATION_TEXT


def test_surface_photo():
    dtype, subtype, conf, _ = _classify("sample_surface_photo.png")
    assert dtype == DataType.VISUAL_IMAGE
