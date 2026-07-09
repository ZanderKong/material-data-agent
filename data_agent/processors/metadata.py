"""Sample metadata processor: generate metadata index."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..schemas import (
    DataObject,
    DataType,
    LifecycleLevel,
    ProcessingRun,
    ProcessingStatus,
    QualityFlag,
)


def process_metadata(data_obj: DataObject, task_dir: Path, run_id: str = "", run_short: str = "") -> tuple[ProcessingRun, list[DataObject], list[QualityFlag]]:
    file_path = task_dir / "raw" / Path(data_obj.data_schema.get("filename", ""))
    tid = data_obj.task_id
    prefix = f"run_{run_short}__" if run_short else ""

    df = pd.read_csv(file_path)

    index_data = []
    for _, row in df.iterrows():
        index_data.append({
            "sample_id": str(row.get("sample_id", "")),
            "batch_id": str(row.get("batch_id", "")),
            "project_id": str(row.get("project_id", "")),
            "material": str(row.get("material", "")),
            "additive_ratio_pct": float(row.get("additive_ratio_pct", 0)) if pd.notna(row.get("additive_ratio_pct")) else None,
            "preparation_date": str(row.get("preparation_date", "")),
            "notes": str(row.get("notes", "")),
        })

    output_name = f"{prefix}sample_metadata_index.json"
    output_path = task_dir / "derived" / output_name
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"samples": index_data, "count": len(index_data)}, f, ensure_ascii=False, indent=2)

    clean_csv_name = f"{prefix}sample_metadata_clean.csv"
    clean_csv_path = task_dir / "derived" / clean_csv_name
    df.to_csv(clean_csv_path, index=False)

    derived_obj = DataObject(
        task_id=tid,
        data_type=DataType.DERIVED_TABLE,
        subtype="metadata_index",
        confidence=0.95,
        derived_from=[data_obj.object_id],
        lifecycle=LifecycleLevel.L2,
        data_schema={
            "output_file": output_name,
            "clean_csv": clean_csv_name,
            "sample_count": len(index_data),
        },
    )

    run = ProcessingRun(
        run_id=run_id,
        task_id=tid,
        tool_name="metadata:index",
        input_data_ids=[data_obj.object_id],
        output_data_ids=[derived_obj.object_id],
        parameters={"method": "csv_parse"},
        status=ProcessingStatus.SUCCEEDED,
    )

    flags = [
        QualityFlag(
            task_id=tid,
            severity="info",
            target_type="metadata",
            target_id=data_obj.object_id,
            message=f"Sample metadata index generated: {len(index_data)} samples. Note: cross-task linking not performed; metadata available for subsequent linking.",
            confidence=0.95,
        )
    ]

    return run, [derived_obj], flags
