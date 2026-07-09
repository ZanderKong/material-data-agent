"""Spectral data processor: FTIR and UV-Vis analysis."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..schemas import (
    DataObject,
    DataType,
    LifecycleLevel,
    ProcessingRun,
    ProcessingStatus,
    QualityFlag,
)

FTIR_PEAK_REGIONS = [
    (3340, 3460, "~3400 cm-1"),
    (1580, 1660, "~1620 cm-1"),
    (1080, 1160, "~1120 cm-1"),
]

UVVIS_PEAK_REGIONS = [
    (410, 450, "~430 nm"),
    (600, 640, "~620 nm"),
]


def process_spectral(data_obj: DataObject, task_dir: Path, run_id: str = "", run_short: str = "") -> tuple[ProcessingRun, list[DataObject], list[QualityFlag]]:
    file_path = task_dir / "raw" / Path(data_obj.data_schema.get("filename", ""))
    prefix = f"run_{run_short}__" if run_short else ""
    subtype = data_obj.subtype

    if subtype == "FTIR":
        return _process_ftir(data_obj, file_path, task_dir, prefix, run_id)
    elif subtype == "UVVis":
        return _process_uvvis(data_obj, file_path, task_dir, prefix, run_id)
    else:
        run = ProcessingRun(
            run_id=run_id,
            task_id=data_obj.task_id,
            tool_name="spectral",
            parameters={"subtype": subtype},
            status=ProcessingStatus.FAILED,
            errors=[f"Unknown spectral subtype: {subtype}"],
        )
        return run, [], []


def _detect_peaks(x: np.ndarray, y: np.ndarray, regions: list[tuple], window: int = 5, smooth: str = "mean") -> list[dict]:
    results = []
    for lo, hi, label in regions:
        mask = (x >= lo) & (x <= hi)
        x_region = x[mask]
        y_region = y[mask]
        if len(x_region) == 0:
            results.append({"region": label, "peak_x": None, "peak_y": None, "status": "no_data"})
            continue
        idx = np.argmax(y_region)
        peak_x = float(x_region[idx])
        peak_y = float(y_region[idx])
        results.append({
            "region": label,
            "peak_wavenumber_cm_1": peak_x if "cm" in label else None,
            "peak_wavelength_nm": peak_x if "nm" in label else None,
            "absorbance_at_peak": peak_y,
            "status": "detected",
        })
    return results


def _process_ftir(
    data_obj: DataObject, file_path: Path, task_dir: Path, prefix: str, run_id: str
) -> tuple[ProcessingRun, list[DataObject], list[QualityFlag]]:
    df = pd.read_csv(file_path)
    tid = data_obj.task_id
    x_col = "wavenumber_cm-1"
    y_col = "absorbance"
    x = df[x_col].values
    y = df[y_col].values

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x, y, linewidth=1)
    ax.set_xlabel("Wavenumber (cm-1)")
    ax.set_ylabel("Absorbance")
    ax.set_title("Reconstructed FTIR Spectrum")
    ax.invert_xaxis()
    plot_png_name = f"{prefix}ftir_reconstructed.png"
    plot_path = task_dir / "derived" / plot_png_name
    fig.savefig(plot_path, dpi=100)
    plt.close(fig)

    peaks = _detect_peaks(x, y, FTIR_PEAK_REGIONS)
    params = {"window": 5, "smooth_method": "none", "threshold_method": "local_max_in_region", "regions": FTIR_PEAK_REGIONS}

    peak_table_name = f"{prefix}ftir_peak_table.csv"
    peak_table_path = task_dir / "derived" / peak_table_name
    pd.DataFrame(peaks).to_csv(peak_table_path, index=False)

    derived_obj = DataObject(
        task_id=tid,
        data_type=DataType.DERIVED_TABLE,
        subtype="ftir_peaks",
        confidence=0.90,
        derived_from=[data_obj.object_id],
        lifecycle=LifecycleLevel.L2,
        data_schema={
            "output_file": peak_table_name,
            "reconstructed_plot": plot_png_name,
            "peaks": peaks,
            "x_col": x_col,
            "y_col": y_col,
        },
    )

    run = ProcessingRun(
        run_id=run_id,
        task_id=tid,
        tool_name="spectral:ftir",
        input_data_ids=[data_obj.object_id],
        output_data_ids=[derived_obj.object_id],
        parameters=params,
        status=ProcessingStatus.SUCCEEDED,
        warnings=[],
    )

    flags = [
        QualityFlag(
            task_id=tid,
            severity="info",
            target_type="processing",
            target_id=run.run_id,
            message=f"FTIR peak detection completed. Peaks found near {', '.join([p['region'] for p in peaks if p['status'] == 'detected'])}",
            evidence=f"Peak extraction parameters: window={params['window']}, method={params['threshold_method']}",
            confidence=0.90,
        )
    ]

    return run, [derived_obj], flags


def _process_uvvis(
    data_obj: DataObject, file_path: Path, task_dir: Path, prefix: str, run_id: str
) -> tuple[ProcessingRun, list[DataObject], list[QualityFlag]]:
    df = pd.read_csv(file_path)
    tid = data_obj.task_id
    x_col = "wavelength_nm"
    y_col = "absorbance"
    x = df[x_col].values
    y = df[y_col].values

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x, y, linewidth=1)
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Absorbance")
    ax.set_title("Reconstructed UV-Vis Spectrum")
    plot_png_name = f"{prefix}uvvis_reconstructed.png"
    plot_path = task_dir / "derived" / plot_png_name
    fig.savefig(plot_path, dpi=100)
    plt.close(fig)

    peaks = _detect_peaks(x, y, UVVIS_PEAK_REGIONS)
    params = {"window": 5, "smooth_method": "none", "threshold_method": "local_max_in_region", "regions": UVVIS_PEAK_REGIONS}

    peak_table_name = f"{prefix}uvvis_peak_table.csv"
    peak_table_path = task_dir / "derived" / peak_table_name
    pd.DataFrame(peaks).to_csv(peak_table_path, index=False)

    derived_obj = DataObject(
        task_id=tid,
        data_type=DataType.DERIVED_TABLE,
        subtype="uvvis_peaks",
        confidence=0.90,
        derived_from=[data_obj.object_id],
        lifecycle=LifecycleLevel.L2,
        data_schema={
            "output_file": peak_table_name,
            "reconstructed_plot": plot_png_name,
            "peaks": peaks,
            "x_col": x_col,
            "y_col": y_col,
        },
    )

    run = ProcessingRun(
        run_id=run_id,
        task_id=tid,
        tool_name="spectral:uvvis",
        input_data_ids=[data_obj.object_id],
        output_data_ids=[derived_obj.object_id],
        parameters=params,
        status=ProcessingStatus.SUCCEEDED,
        warnings=[],
    )

    flags = [
        QualityFlag(
            task_id=tid,
            severity="info",
            target_type="processing",
            target_id=run.run_id,
            message=f"UV-Vis peak detection completed. Absorption regions near {', '.join([p['region'] for p in peaks if p['status'] == 'detected'])}",
            evidence=f"Peak extraction parameters: window={params['window']}, method={params['threshold_method']}",
            confidence=0.90,
        )
    ]

    return run, [derived_obj], flags
