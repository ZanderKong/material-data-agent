"""Tests for review target type/id support."""
import json
from pathlib import Path

import pytest

from data_agent.db import init_db
from data_agent.reviews import write_review
from data_agent.ui.actions import do_review


def _setup_task(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    task_dir = ws / "tasks" / "task_0001"
    task_dir.mkdir(parents=True)
    (task_dir / "reviews").mkdir()
    (task_dir / "logs").mkdir()
    manifest = {
        "task_id": "task_0001",
        "status": "ingested",
        "input_files": [],
        "run_ids": [],
        "flag_ids": [],
        "review_ids": [],
    }
    with open(task_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)
    init_db(ws)
    return ws, task_dir


class TestWriteReviewTargetType:
    def test_preserves_target_type_and_id(self, tmp_path):
        ws, task_dir = _setup_task(tmp_path)
        review = write_review(ws, "task_0001", "approve", "tester", "test comment",
                             target_id="flag_001", target_type="quality_flag")
        assert review.target_type == "quality_flag"
        assert review.target_id == "flag_001"

    def test_defaults_to_task_when_target_id_empty(self, tmp_path):
        ws, task_dir = _setup_task(tmp_path)
        review = write_review(ws, "task_0001", "approve", "tester", "test comment")
        assert review.target_type == "task"
        assert review.target_id == "task_0001"

    def test_do_review_passes_target(self, tmp_path):
        ws, task_dir = _setup_task(tmp_path)
        result = do_review(ws, "task_0001", "approve", "tester", "test comment",
                          target_type="derived_file", target_id="run_abc__chart.csv")
        assert result["success"] is True

        records_path = task_dir / "reviews" / "review_records.json"
        assert records_path.exists()
        records = json.loads(records_path.read_text())
        assert len(records) == 1
        assert records[0]["target_type"] == "derived_file"
        assert records[0]["target_id"] == "run_abc__chart.csv"
