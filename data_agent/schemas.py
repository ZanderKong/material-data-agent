"""Pydantic schema definitions for the data agent lifecycle model."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class LifecycleLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class DataType(str, Enum):
    SAMPLE_METADATA = "sample_metadata"
    RAW_NUMERIC = "raw_numeric"
    RAW_SPECTRAL = "raw_spectral"
    CHART_IMAGE_INPUT = "chart_image_input"
    DESCRIPTIVE_OBSERVATION_TEXT = "descriptive_observation_text"
    VISUAL_IMAGE = "visual_image"
    DERIVED_TABLE = "derived_table"
    GENERATED_FIGURE = "generated_figure"
    STRUCTURED_OBSERVATION = "structured_observation"
    MODEL_RESULT = "model_result"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class ReviewAction(str, Enum):
    APPROVE = "approve"
    RETURN_FOR_RERUN = "return_for_rerun"
    MARK_LOW_CONFIDENCE = "mark_low_confidence"
    DEPRECATE = "deprecate"
    LINK_RELATED_DATA = "link_related_data"


class RelationshipType(str, Enum):
    INPUT_OF = "input_of"
    OUTPUT_OF = "output_of"
    DERIVED_FROM = "derived_from"
    REPLACES = "replaces"
    REPLACED_BY = "replaced_by"
    RELATED_TO = "related_to"


class FileRecord(BaseModel):
    file_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    original_name: str
    stored_path: str
    checksum_sha256: str
    size_bytes: int
    mime_type: str = ""
    lifecycle: LifecycleLevel = LifecycleLevel.L0
    registered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DataObject(BaseModel):
    object_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    data_type: DataType
    subtype: str = ""
    confidence: float = 1.0
    file_ids: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    data_schema: dict[str, Any] = Field(default_factory=dict)
    lifecycle: LifecycleLevel = LifecycleLevel.L1
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProcessingRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    tool_name: str = "data_agent"
    tool_version: str = "0.1.0"
    input_data_ids: list[str] = Field(default_factory=list)
    output_data_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: ProcessingStatus = ProcessingStatus.PENDING
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class QualityFlag(BaseModel):
    flag_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    severity: str = "info"
    target_type: str = ""
    target_id: str = ""
    message: str = ""
    evidence: str = ""
    requires_review: bool = False
    confidence: float = 1.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReviewRecord(BaseModel):
    review_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    reviewer: str = ""
    action: ReviewAction = ReviewAction.APPROVE
    target_type: str = ""
    target_id: str = ""
    before_value: str = ""
    after_value: str = ""
    comment: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Relationship(BaseModel):
    rel_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    rel_type: RelationshipType
    source_id: str
    target_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TaskManifest(BaseModel):
    task_id: str
    status: str = "created"
    input_files: list[str] = Field(default_factory=list)
    derived_files: list[str] = Field(default_factory=list)
    object_ids: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    flag_ids: list[str] = Field(default_factory=list)
    review_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
