"""Tests for workspace-level sample index."""
import csv
import json
from pathlib import Path

import pytest

from data_agent.sample_index import build_sample_index, load_sample_index


def _make_ws(tmp_path, tasks_spec):
    ws = tmp_path / "ws"
    ws.mkdir()
    for tid, files in tasks_spec.items():
        td = ws / "tasks" / tid
        td.mkdir(parents=True)
        for d in ("raw", "derived", "logs", "reviews"):
            (td / d).mkdir()
        manifest = {"task_id": tid, "status": "ingested", "input_files": [f.split("/")[-1] for f in files.get("raw", [])], "derived_files": files.get("derived", []), "run_ids": [], "flag_ids": [], "review_ids": [], "object_ids": []}
        with open(td / "manifest.json", "w") as f:
            json.dump(manifest, f)
        for rp, content in files.get("raw_items", []):
            with open(td / "raw" / rp, "w") as f:
                f.write(content)
        for dp, content in files.get("derived_items", []):
            with open(td / "derived" / dp, "w") as f:
                f.write(content)
        for _ in range(2):
            pass
    return ws


class TestSampleIndex:
    def test_metadata_csv_linked(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id,thickness_um\nA01,B01,32.1\n")], "derived_items": [], "derived": []},
            "task_0003": {"raw_items": [("sample_ftir_raw.csv", "wavenumber_cm-1,absorbance,sample_id,batch_id\n4000,0.12,A01,B01\n")], "derived_items": [], "derived": []},
        })
        result = build_sample_index(ws)
        assert len(result.samples) >= 1
        sample_ids = [s.sample_id for s in result.samples]
        assert "A01" in sample_ids
        a01 = next(s for s in result.samples if s.sample_id == "A01")
        linked_tasks = [rt.task_id for rt in a01.related_tasks]
        assert "task_0001" in linked_tasks

    def test_batch_id_retained(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\nA02,B02\n")], "derived_items": [], "derived": []},
        })
        result = build_sample_index(ws)
        bids = [s.batch_id for s in result.samples]
        assert "B01" in bids
        assert "B02" in bids

    def test_missing_id_goes_to_unlinked(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0005": {"raw_items": [("sample_resistance.csv", "sheet_resistance_ohm_sq,temperature\n100,25\n200,30\n")], "derived_items": [], "derived": []},
        })
        result = build_sample_index(ws)
        assert len(result.unlinked_tasks) >= 1 or len(result.samples) == 0

    def test_ambiguous_batch_separated(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\nA01,B02\n")], "derived_items": [], "derived": []},
        })
        result = build_sample_index(ws)
        assert len(result.warnings) >= 1

    def test_filename_candidate_not_auto_linked(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [], "derived_items": [], "derived": []},
        })
        td = ws / "tasks" / "task_0001" / "raw"
        (td / "B03_measurement.csv").write_text("col1\n1\n")
        result = build_sample_index(ws)
        unlinked_ids = [u["task_id"] for u in result.unlinked_tasks]
        assert "task_0001" in unlinked_ids or len(result.samples) == 0

    def test_deterministic_rebuild(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\n")], "derived_items": [], "derived": []},
        })
        r1 = build_sample_index(ws)
        r2 = build_sample_index(ws)
        assert len(r1.samples) == len(r2.samples)

    def test_cli_writes_index(self, tmp_path):
        import subprocess, sys
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\n")], "derived_items": [], "derived": []},
        })
        subprocess.run([sys.executable, "-m", "data_agent", "index-samples", "--workspace", str(ws)], capture_output=True, timeout=30)
        assert (ws / "sample_index.json").exists()

    def test_index_does_not_modify_tasks(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\n")], "derived_items": [], "derived": []},
        })
        td = ws / "tasks" / "task_0001"
        orig_manifest = (td / "manifest.json").read_text()
        build_sample_index(ws)
        assert (td / "manifest.json").read_text() == orig_manifest

    def test_load_sample_index(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\n")], "derived_items": [], "derived": []},
        })
        build_sample_index(ws)
        loaded = load_sample_index(ws)
        assert loaded is not None
        assert len(loaded.samples) >= 1
