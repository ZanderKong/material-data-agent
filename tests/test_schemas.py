"""Tests for schema serialization and deserialization."""
import json
import pytest
from data_agent.schemas import (
    FileRecord,
    DataObject,
    DataType,
    ProcessingRun,
    ProcessingStatus,
    QualityFlag,
    ReviewRecord,
    ReviewAction,
    Relationship,
    RelationshipType,
    TaskManifest,
    LifecycleLevel,
)


def test_file_record_serialization():
    record = FileRecord(
        task_id="task_0001",
        original_name="test.csv",
        stored_path="/tmp/test.csv",
        checksum_sha256="abc123",
        size_bytes=100,
        lifecycle=LifecycleLevel.L0,
    )
    data = record.model_dump()
    json_str = json.dumps(data)
    recovered = FileRecord(**json.loads(json_str))
    assert recovered.original_name == "test.csv"
    assert recovered.lifecycle == LifecycleLevel.L0


def test_data_object_serialization():
    obj = DataObject(
        task_id="task_0001",
        data_type=DataType.RAW_NUMERIC,
        confidence=0.95,
        file_ids=["f1"],
        data_schema={"columns": ["a", "b"]},
    )
    data = obj.model_dump()
    json_str = json.dumps(data)
    recovered = DataObject(**json.loads(json_str))
    assert recovered.data_type == DataType.RAW_NUMERIC
    assert recovered.data_schema == {"columns": ["a", "b"]}


def test_processing_run_serialization():
    run = ProcessingRun(
        task_id="task_0001",
        tool_name="numeric",
        status=ProcessingStatus.SUCCEEDED,
    )
    data = run.model_dump()
    json_str = json.dumps(data)
    recovered = ProcessingRun(**json.loads(json_str))
    assert recovered.status == ProcessingStatus.SUCCEEDED


def test_quality_flag_serialization():
    flag = QualityFlag(
        task_id="task_0001",
        severity="warning",
        message="test flag",
        requires_review=True,
    )
    data = flag.model_dump()
    json_str = json.dumps(data)
    recovered = QualityFlag(**json.loads(json_str))
    assert recovered.requires_review is True


def test_review_record_serialization():
    review = ReviewRecord(
        task_id="task_0001",
        reviewer="ZQ",
        action=ReviewAction.APPROVE,
        comment="ok",
    )
    data = review.model_dump()
    json_str = json.dumps(data)
    recovered = ReviewRecord(**json.loads(json_str))
    assert recovered.action == ReviewAction.APPROVE


def test_relationship_serialization():
    rel = Relationship(
        task_id="task_0001",
        rel_type=RelationshipType.DERIVED_FROM,
        source_id="obj2",
        target_id="obj1",
    )
    data = rel.model_dump()
    json_str = json.dumps(data)
    recovered = Relationship(**json.loads(json_str))
    assert recovered.rel_type == RelationshipType.DERIVED_FROM


def test_task_manifest_serialization():
    manifest = TaskManifest(
        task_id="task_0001",
        input_files=["a.csv"],
    )
    data = manifest.model_dump()
    json_str = json.dumps(data)
    recovered = TaskManifest(**json.loads(json_str))
    assert recovered.input_files == ["a.csv"]


def test_all_schemas_json_roundtrip():
    schemas = [
        FileRecord(task_id="t1", original_name="f.csv", stored_path="/tmp/f.csv", checksum_sha256="x", size_bytes=1),
        DataObject(task_id="t1", data_type=DataType.RAW_NUMERIC),
        ProcessingRun(task_id="t1"),
        QualityFlag(task_id="t1"),
        ReviewRecord(task_id="t1"),
        Relationship(task_id="t1", rel_type=RelationshipType.DERIVED_FROM, source_id="s", target_id="t"),
        TaskManifest(task_id="t1"),
    ]
    for s in schemas:
        j = json.dumps(s.model_dump())
        loaded = json.loads(j)
        assert loaded is not None
