"""File type classification based on filename, extension, and content."""
from __future__ import annotations

import csv
import mimetypes
from pathlib import Path
from typing import Optional

from .schemas import DataType


def classify_file(file_path: Path) -> tuple[DataType, str, float, dict]:
    name = file_path.name.lower()
    ext = file_path.suffix.lower()
    mime, _ = mimetypes.guess_type(str(file_path))
    mime = mime or ""

    subtype = ""
    confidence = 0.9
    schema: dict = {"filename": file_path.name, "extension": ext, "mime_type": mime}

    if "metadata" in name and ext == ".csv":
        return DataType.SAMPLE_METADATA, "", 0.95, schema

    if "thickness" in name and ext == ".csv":
        return DataType.RAW_NUMERIC, "thickness", 0.95, schema

    if "resistance" in name and ext == ".csv":
        return DataType.RAW_NUMERIC, "resistance", 0.95, schema

    if "ftir_raw" in name and ext == ".csv":
        return DataType.RAW_SPECTRAL, "FTIR", 0.95, schema

    if "uvvis_raw" in name and ext == ".csv":
        return DataType.RAW_SPECTRAL, "UVVis", 0.95, schema

    if "ftir" in name and "chart" in name and ext == ".png":
        return DataType.CHART_IMAGE_INPUT, "FTIR", 0.85, schema

    if "uvvis" in name and "chart" in name and ext == ".png":
        return DataType.CHART_IMAGE_INPUT, "UVVis", 0.85, schema

    if "observation" in name and ext == ".txt":
        return DataType.DESCRIPTIVE_OBSERVATION_TEXT, "", 0.95, schema

    if "surface" in name and "photo" in name and ext == ".png":
        return DataType.VISUAL_IMAGE, "", 0.95, schema

    if ext == ".csv":
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = [h.lower() for h in next(reader, [])]

        if "wavenumber" in " ".join(header) or "cm-1" in " ".join(header):
            if "absorbance" in header:
                return DataType.RAW_SPECTRAL, "FTIR", 0.90, schema
        if "wavelength" in " ".join(header) and "absorbance" in header:
            return DataType.RAW_SPECTRAL, "UVVis", 0.90, schema
        if "sample_id" in header or "batch_id" in header:
            if "resistance" in name or "sheet_resistance" in " ".join(header):
                return DataType.RAW_NUMERIC, "resistance", 0.85, schema
            if "thickness" in " ".join(header):
                return DataType.RAW_NUMERIC, "thickness", 0.85, schema
            if "additive" in " ".join(header) or "material" in " ".join(header):
                return DataType.SAMPLE_METADATA, "", 0.85, schema

    schema["classification_method"] = "extension_only"
    confidence = 0.6
    return DataType.RAW_NUMERIC, "", confidence, schema
