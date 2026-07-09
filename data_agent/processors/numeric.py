"""Numeric data processor: thickness and resistance analysis."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from ..schemas import (
    DataObject,
    DataType,
    LifecycleLevel,
    ProcessingRun,
    ProcessingStatus,
    QualityFlag,
)


def process_numeric(data_obj: DataObject, task_dir: Path, run_id: str = "", run_short: str = "") -> tuple[ProcessingRun, list[DataObject], list[QualityFlag]]:
    file_path = task_dir / "raw" / Path(data_obj.data_schema.get("filename", ""))
    prefix = f"run_{run_short}__" if run_short else ""
    subtype = data_obj.subtype

    if subtype == "thickness":
        return _process_thickness(data_obj, file_path, task_dir, prefix, run_id)
    elif subtype == "resistance":
        return _process_resistance(data_obj, file_path, task_dir, prefix, run_id)
    else:
        run = ProcessingRun(
            task_id=data_obj.task_id,
            run_id=run_id,
            tool_name="numeric",
            parameters={"subtype": subtype, "file": str(file_path)},
            status=ProcessingStatus.FAILED,
            errors=[f"Unknown numeric subtype: {subtype}"],
        )
        return run, [], []


def _process_thickness(
    data_obj: DataObject, file_path: Path, task_dir: Path, prefix: str, run_id: str
) -> tuple[ProcessingRun, list[DataObject], list[QualityFlag]]:
    df = pd.read_csv(file_path)
    flags: list[QualityFlag] = []
    tid = data_obj.task_id

    missing_mask = df["thickness_um"].isna()
    outlier_mask = df["thickness_um"] == 9999

    if missing_mask.any():
        flags.append(QualityFlag(
            task_id=tid,
            severity="warning",
            target_type="data_point",
            target_id=f"{data_obj.object_id}:missing",
            message=f"Missing thickness values found at positions: {df[missing_mask]['position'].tolist()}",
            evidence=f"{int(missing_mask.sum())} missing values",
            requires_review=True,
        ))

    if outlier_mask.any():
        flags.append(QualityFlag(
            task_id=tid,
            severity="warning",
            target_type="data_point",
            target_id=f"{data_obj.object_id}:outlier",
            message=f"Suspicious outlier value 9999 found at positions: {df[outlier_mask]['position'].tolist()}",
            evidence=f"{int(outlier_mask.sum())} suspicious values (9999). Retained in data, flagged separately.",
            requires_review=True,
        ))

    clean_mask = (~missing_mask) & (~outlier_mask)
    df["_clean"] = clean_mask
    df["_missing"] = missing_mask
    df["_outlier"] = outlier_mask

    summary = df.groupby(["sample_id", "batch_id"]).agg(
        raw_count=("thickness_um", "size"),
        valid_count=("_clean", "sum"),
        missing_count=("_missing", "sum"),
        outlier_count=("_outlier", "sum"),
        mean_excluding_flagged=("thickness_um", lambda x: x[clean_mask.loc[x.index]].mean() if clean_mask.loc[x.index].any() else None),
        std_excluding_flagged=("thickness_um", lambda x: x[clean_mask.loc[x.index]].std() if clean_mask.loc[x.index].any() else None),
    ).reset_index()

    summary_csv_name = f"{prefix}thickness_summary.csv"
    summary_path = task_dir / "derived" / summary_csv_name
    summary.to_csv(summary_path, index=False)

    fig, ax = plt.subplots(figsize=(8, 4))
    for sid in df["sample_id"].unique():
        sdf = df[df["sample_id"] == sid]
        valid = sdf[sdf["thickness_um"] != 9999]
        ax.scatter(valid["position"], valid["thickness_um"], label=str(sid))
    ax.set_xlabel("Position")
    ax.set_ylabel("Thickness (um)")
    ax.set_title("Thickness by Position")
    ax.legend()
    plot_png_name = f"{prefix}thickness_plot.png"
    plot_path = task_dir / "derived" / plot_png_name
    fig.savefig(plot_path, dpi=100)
    plt.close(fig)

    derived_obj = DataObject(
        task_id=tid,
        data_type=DataType.DERIVED_TABLE,
        subtype="thickness_summary",
        confidence=0.95,
        derived_from=[data_obj.object_id],
        lifecycle=LifecycleLevel.L2,
        data_schema={
            "output_file": summary_csv_name,
            "plot_png": plot_png_name,
            "total_points": len(df),
            "missing_count": int(missing_mask.sum()),
            "outlier_count": int(outlier_mask.sum()),
        },
    )

    run = ProcessingRun(
        run_id=run_id,
        task_id=tid,
        tool_name="numeric:thickness",
        input_data_ids=[data_obj.object_id],
        output_data_ids=[derived_obj.object_id],
        parameters={"group_cols": ["sample_id", "batch_id"], "value_col": "thickness_um", "outlier_values": [9999]},
        status=ProcessingStatus.SUCCEEDED,
        warnings=(
            [f"Missing values: {int(missing_mask.sum())}"] if missing_mask.any() else []
        ) + (
            [f"Flagged outliers (9999): {int(outlier_mask.sum())}"] if outlier_mask.any() else []
        ),
    )

    return run, [derived_obj], flags


def _process_resistance(
    data_obj: DataObject, file_path: Path, task_dir: Path, prefix: str, run_id: str
) -> tuple[ProcessingRun, list[DataObject], list[QualityFlag]]:
    df = pd.read_csv(file_path)
    flags: list[QualityFlag] = []
    tid = data_obj.task_id

    df["sheet_resistance_ohm_sq"] = np.where(
        df["unit"] == "kOhm/sq",
        df["sheet_resistance"] * 1000,
        df["sheet_resistance"],
    )

    kohm_mask = df["unit"] == "kOhm/sq"
    converted_count = int(kohm_mask.sum())

    if converted_count > 0:
        flags.append(QualityFlag(
            task_id=tid,
            severity="info",
            target_type="processing",
            target_id=f"{data_obj.object_id}:unit_conversion",
            message=f"Converted {converted_count} kOhm/sq values to ohm/sq (multiplied by 1000)",
            evidence=str(df[kohm_mask][["sheet_resistance", "unit", "sheet_resistance_ohm_sq"]].to_dict()),
        ))

    missing_mask = df["sheet_resistance"].isna()
    if missing_mask.any():
        flags.append(QualityFlag(
            task_id=tid,
            severity="warning",
            target_type="data_point",
            target_id=f"{data_obj.object_id}:missing",
            message=f"Missing resistance value at replicate: {df[missing_mask]['replicate'].tolist()}",
            evidence=f"{int(missing_mask.sum())} missing values",
            requires_review=True,
        ))

    summary = df.groupby(["sample_id", "batch_id"])["sheet_resistance_ohm_sq"].agg(
        count="count",
        mean="mean",
        std="std",
        min="min",
        max="max",
    ).reset_index()

    summary_csv_name = f"{prefix}resistance_summary.csv"
    summary_path = task_dir / "derived" / summary_csv_name
    summary.to_csv(summary_path, index=False)

    fig, ax = plt.subplots(figsize=(8, 4))
    for sid in df["sample_id"].unique():
        sdf = df[df["sample_id"] == sid]
        ax.scatter(sdf["replicate"], sdf["sheet_resistance_ohm_sq"], label=str(sid))
    ax.set_xlabel("Replicate")
    ax.set_ylabel("Sheet Resistance (ohm/sq)")
    ax.set_title("Sheet Resistance by Sample")
    ax.legend()
    plot_png_name = f"{prefix}resistance_plot.png"
    plot_path = task_dir / "derived" / plot_png_name
    fig.savefig(plot_path, dpi=100)
    plt.close(fig)

    derived_obj = DataObject(
        task_id=tid,
        data_type=DataType.DERIVED_TABLE,
        subtype="resistance_summary",
        confidence=0.95,
        derived_from=[data_obj.object_id],
        lifecycle=LifecycleLevel.L2,
        data_schema={
            "output_file": summary_csv_name,
            "plot_png": plot_png_name,
            "kohm_conversions": converted_count,
            "total_points": len(df),
            "missing_count": int(missing_mask.sum()),
        },
    )

    run = ProcessingRun(
        run_id=run_id,
        task_id=tid,
        tool_name="numeric:resistance",
        input_data_ids=[data_obj.object_id],
        output_data_ids=[derived_obj.object_id],
        parameters={"conversion": "kOhm/sq * 1000 -> ohm/sq", "group_cols": ["sample_id", "batch_id"]},
        status=ProcessingStatus.SUCCEEDED,
        warnings=(
            [f"Unit conversion: {converted_count} kOhm/sq -> ohm/sq"] if converted_count > 0 else []
        ),
    )

    return run, [derived_obj], flags
