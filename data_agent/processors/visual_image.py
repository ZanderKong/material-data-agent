"""Visual image processor: extract metadata and flag for manual review."""
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


def process_visual_image(data_obj: DataObject, task_dir: Path, run_id: str = "", run_short: str = "") -> tuple[ProcessingRun, list[DataObject], list[QualityFlag]]:
    file_path = task_dir / "raw" / Path(data_obj.data_schema.get("filename", ""))
    tid = data_obj.task_id
    prefix = f"run_{run_short}__" if run_short else ""

    img = Image.open(file_path)
    metadata = {
        "width_px": img.width,
        "height_px": img.height,
        "format": img.format,
        "mode": img.mode,
        "size_bytes": file_path.stat().st_size,
        "filename": file_path.name,
    }

    output_name = f"{prefix}visual_metadata.json"
    output_path = task_dir / "derived" / output_name
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    derived_obj = DataObject(
        task_id=tid,
        data_type=DataType.VISUAL_IMAGE,
        subtype="visual_metadata",
        confidence=0.8,
        derived_from=[data_obj.object_id],
        lifecycle=LifecycleLevel.L2,
        data_schema={"output_file": output_name, "metadata": metadata},
    )

    run = ProcessingRun(
        run_id=run_id,
        task_id=tid,
        tool_name="visual_image:local",
        input_data_ids=[data_obj.object_id],
        output_data_ids=[derived_obj.object_id],
        parameters={"method": "metadata_extraction"},
        status=ProcessingStatus.SUCCEEDED,
        warnings=["Visual surface analysis requires manual review. No automated scale bar or particle analysis performed."],
    )

    flags = [
        QualityFlag(
            task_id=tid,
            severity="warning",
            target_type="visual_image",
            target_id=data_obj.object_id,
            message="Manual review required: surface photo analysis cannot be fully automated. No particle size analysis performed.",
            requires_review=True,
            confidence=0.5,
        )
    ]

    return run, [derived_obj], flags
