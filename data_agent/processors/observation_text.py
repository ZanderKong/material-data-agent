"""Observation text processor: extract factual observations and interpretation candidates."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..schemas import (
    DataObject,
    DataType,
    LifecycleLevel,
    ProcessingRun,
    ProcessingStatus,
    QualityFlag,
)


def process_observation_text(data_obj: DataObject, task_dir: Path, run_id: str = "", run_short: str = "") -> tuple[ProcessingRun, list[DataObject], list[QualityFlag]]:
    file_path = task_dir / "raw" / Path(data_obj.data_schema.get("filename", ""))
    tid = data_obj.task_id
    prefix = f"run_{run_short}__" if run_short else ""

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    lines = [l.strip() for l in lines if l.strip()]

    factual_observations: list[str] = []
    interpretation_candidates: list[str] = []
    trend_statements: list[str] = []

    for line in lines:
        if not line:
            continue
        if line.startswith("可能是") or re.match(r"^可能是", line):
            interpretation_candidates.append(line)
        elif re.search(r"可能是|可能|或许|大概", line) and not line.startswith("备注"):
            interpretation_candidates.append(line)
        elif line.startswith("备注"):
            factual_observations.append(line)
        else:
            factual_observations.append(line)

    extractions: dict[str, list[str]] = {
        "sample_ids": [],
        "color_changes": [],
        "cracking": [],
        "delamination": [],
        "time_expressions": [],
    }
    for line in factual_observations:
        ids = re.findall(r"[A-Z]\d+", line)
        extractions["sample_ids"].extend(ids)
        if re.search(r"变\w*|颜色|紫色|绿色|黄色", line):
            extractions["color_changes"].append(line)
        if re.search(r"龟裂|裂纹", line):
            extractions["cracking"].append(line)
        if re.search(r"脱落|剥离", line):
            extractions["delamination"].append(line)
        if re.search(r"\d+\s*秒|\d+\s*分钟|\d+\s*小时", line):
            extractions["time_expressions"].append(line)

    result = {
        "factual_observations": factual_observations,
        "trend_or_statements": trend_statements,
        "interpretation_candidates": interpretation_candidates,
        "extracted_details": extractions,
        "excluded_from_conclusion": True,
    }

    output_name = f"{prefix}structured_observations.json"
    output_path = task_dir / "derived" / output_name
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    derived_obj = DataObject(
        task_id=tid,
        data_type=DataType.STRUCTURED_OBSERVATION,
        subtype="observation_analysis",
        confidence=0.85,
        derived_from=[data_obj.object_id],
        lifecycle=LifecycleLevel.L2,
        data_schema={
            "output_file": output_name,
            "factual_count": len(factual_observations),
            "interpretation_count": len(interpretation_candidates),
        },
    )

    run = ProcessingRun(
        run_id=run_id,
        task_id=tid,
        tool_name="observation_text",
        input_data_ids=[data_obj.object_id],
        output_data_ids=[derived_obj.object_id],
        parameters={"method": "rule_based_sentence_split", "keywords": ["可能是", "龟裂", "脱落", "颜色"]},
        status=ProcessingStatus.SUCCEEDED,
    )

    flags: list[QualityFlag] = []
    if interpretation_candidates:
        flags.append(QualityFlag(
            task_id=tid,
            severity="info",
            target_type="observation",
            target_id=data_obj.object_id,
            message=f"Found {len(interpretation_candidates)} interpretation candidate(s) - excluded from factual conclusions",
            evidence=str(interpretation_candidates),
            requires_review=True,
            confidence=0.85,
        ))

    return run, [derived_obj], flags
