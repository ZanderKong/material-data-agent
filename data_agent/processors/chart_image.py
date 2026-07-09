"""Chart image processor: extract metadata from chart screenshots."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from ..schemas import (
    DataObject,
    DataType,
    LifecycleLevel,
    ProcessingRun,
    ProcessingStatus,
    QualityFlag,
)


def process_chart_image(data_obj: DataObject, task_dir: Path, run_id: str = "", run_short: str = "", model_mode: str = "local") -> tuple[ProcessingRun, list[DataObject], list[QualityFlag]]:
    file_path = task_dir / "raw" / Path(data_obj.data_schema.get("filename", ""))
    tid = data_obj.task_id
    subtype = data_obj.subtype
    prefix = f"run_{run_short}__" if run_short else ""
    flags: list[QualityFlag] = []

    img = Image.open(file_path)
    metadata = {
        "width_px": img.width,
        "height_px": img.height,
        "format": img.format,
        "mode": img.mode,
        "size_bytes": file_path.stat().st_size,
    }

    if subtype == "FTIR":
        axis_info = {"x_axis": "wavenumber (cm-1)", "y_axis": "absorbance", "confidence": 0.7}
    elif subtype == "UVVis":
        axis_info = {"x_axis": "wavelength (nm)", "y_axis": "absorbance", "confidence": 0.7}
    else:
        axis_info = {"x_axis": "unknown", "y_axis": "unknown", "confidence": 0.5}

    flags.append(QualityFlag(
        task_id=tid,
        severity="warning",
        target_type="chart_image",
        target_id=data_obj.object_id,
        message=f"axis_confirmation_required: Chart image axis metadata inferred from filename rules. Confidence: {axis_info['confidence']}. Manual confirmation recommended.",
        evidence=str(axis_info),
        requires_review=True,
        confidence=axis_info["confidence"],
    ))

    if model_mode in ("cloud", "auto"):
        flags.append(QualityFlag(
            task_id=tid,
            severity="info",
            target_type="chart_image",
            target_id=data_obj.object_id,
            message="image_observation_requires_review: Chart image analysis may use model-based OCR/vision where available.",
            requires_review=False,
            confidence=0.7,
        ))

    chart_meta = {
        **metadata,
        "axis_info": axis_info,
        "subtype": subtype,
        "model_mode": model_mode,
        "note": "image-derived data has lower confidence than raw CSV spectral data",
    }

    output_name = f"{prefix}chart_metadata.json"
    output_path = task_dir / "derived" / output_name
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chart_meta, f, ensure_ascii=False, indent=2)

    flags.append(QualityFlag(
        task_id=tid,
        severity="info",
        target_type="chart_image",
        target_id=data_obj.object_id,
        message="Image-derived data: lower confidence than raw numeric/spectral data.",
        confidence=0.6,
    ))

    derived_obj = DataObject(
        task_id=tid,
        data_type=DataType.GENERATED_FIGURE,
        subtype="chart_metadata",
        confidence=0.65,
        derived_from=[data_obj.object_id],
        lifecycle=LifecycleLevel.L2,
        data_schema={"output_file": output_name, "chart_metadata": chart_meta},
    )

    warnings: list[str] = ["Chart image confidence is limited. Consider using raw CSV spectral data."]

    run = ProcessingRun(
        run_id=run_id,
        task_id=tid,
        tool_name=f"chart_image:{model_mode}",
        input_data_ids=[data_obj.object_id],
        output_data_ids=[derived_obj.object_id],
        parameters={"method": "rule_based", "model_mode": model_mode},
        status=ProcessingStatus.SUCCEEDED,
        warnings=warnings,
    )

    return run, [derived_obj], flags
