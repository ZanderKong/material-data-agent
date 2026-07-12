"""Tests for sample index – remediation: chunked CSV, dual observation shapes, two-pass linker, write failure."""
import json
from pathlib import Path
from unittest.mock import patch

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
    return ws


class TestSampleIndex:
    def test_metadata_csv_linked(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id,thickness_um\nA01,B01,32.1\n")], "derived_items": [], "derived": []},
            "task_0003": {"raw_items": [("sample_ftir_raw.csv", "wavenumber_cm-1,absorbance,sample_id,batch_id\n4000,0.12,A01,B01\n")], "derived_items": [], "derived": []},
        })
        result = build_sample_index(ws)
        assert len(result.samples) >= 1
        a01 = next(s for s in result.samples if s.sample_id == "A01")
        linked = [rt.task_id for rt in a01.related_tasks]
        assert "task_0001" in linked

    def test_batch_id_retained(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\nA02,B02\n")], "derived_items": [], "derived": []},
        })
        result = build_sample_index(ws)
        bids = [s.batch_id for s in result.samples]
        assert "B01" in bids
        assert "B02" in bids

    def test_missing_id_unlinked(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0005": {"raw_items": [("data.csv", "x,y\n1,2\n")], "derived_items": [], "derived": []},
        })
        result = build_sample_index(ws)
        assert len(result.unlinked_tasks) >= 1

    def test_ambiguous_batch_warning(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\nA01,B02\n")], "derived_items": [], "derived": []},
        })
        result = build_sample_index(ws)
        assert len(result.warnings) >= 1

    def test_filename_not_auto_linked(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [], "derived_items": [], "derived": []},
        })
        (ws / "tasks" / "task_0001" / "raw" / "B03_data.csv").write_text("col\n1")
        result = build_sample_index(ws)
        for s in result.samples:
            for rt in s.related_tasks:
                assert rt.source != "filename_candidate"

    def test_deterministic_rebuild(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\n")], "derived_items": [], "derived": []},
        })
        r1 = build_sample_index(ws)
        r2 = build_sample_index(ws)
        r1c = {s.sample_id: [t.task_id for t in s.related_tasks] for s in r1.samples}
        r2c = {s.sample_id: [t.task_id for t in s.related_tasks] for s in r2.samples}
        assert r1c == r2c

    def test_preserves_data_type(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0002": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\n"), ("sample_ftir_chart.png", "")], "derived_items": [("model_result.json", "{}")], "derived": []},
        })
        result = build_sample_index(ws)
        assert len(result.samples) >= 1
        a01 = next(s for s in result.samples if s.sample_id == "A01")
        task2_entries = [rt for rt in a01.related_tasks if rt.task_id == "task_0002"]
        assert len(task2_entries) >= 1
        assert task2_entries[0].data_type != "model_result"
        assert task2_entries[0].data_type in ("chart_image_input", "raw_spectral")

    def test_observation_links_to_single_match(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\n")], "derived_items": [], "derived": []},
            "task_0002": {"raw_items": [("obs.txt", "text")], "derived_items": [("structured_observation_result.json", '{"extracted_details": {"sample_ids": ["A01"]}}')], "derived": []},
        })
        result = build_sample_index(ws)
        assert len(result.samples) >= 1
        a01 = next(s for s in result.samples if s.sample_id == "A01")
        obs_entries = [rt for rt in a01.related_tasks if rt.task_id == "task_0002"]
        assert len(obs_entries) == 1
        assert obs_entries[0].source == "structured_observation"
        assert obs_entries[0].confidence == 0.8

    def test_observation_ambiguous_unlinked(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\nA01,B02\n")], "derived_items": [], "derived": []},
            "task_0002": {"raw_items": [("obs.txt", "text")], "derived_items": [("structured_observation_result.json", '{"extracted_details": {"sample_ids": ["A01"]}}')], "derived": []},
        })
        result = build_sample_index(ws)
        unlinked = [u for u in result.unlinked_tasks if u["task_id"] == "task_0002"]
        assert len(unlinked) >= 1

    def test_write_failure_raises(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\n")], "derived_items": [], "derived": []},
        })
        with patch.object(Path, "replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                build_sample_index(ws)

    def test_missing_tasks_dir(self, tmp_path):
        ws = tmp_path / "empty"
        ws.mkdir()
        result = build_sample_index(ws)
        assert len(result.samples) == 0
        assert any("No tasks" in w for w in result.warnings)

    def test_non_modifying(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\n")], "derived_items": [], "derived": []},
        })
        td = ws / "tasks" / "task_0001"
        orig_manifest = (td / "manifest.json").read_text()
        build_sample_index(ws)
        assert (td / "manifest.json").read_text() == orig_manifest

    def test_duplicate_csv_rows_yield_single_related_task(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("sample_metadata.csv", "sample_id,batch_id\nA01,B01\nA01,B01\n")], "derived_items": [], "derived": []},
        })
        result = build_sample_index(ws)
        a01 = next(s for s in result.samples if s.sample_id == "A01")
        t1_entries = [rt for rt in a01.related_tasks if rt.task_id == "task_0001"]
        assert len(t1_entries) == 1

    def test_malformed_csv_produces_parse_warning(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("bad.csv", 'sample_id,bad_col\n"unclosed'), ("good.csv", "sample_id\nA01\n")], "derived_items": [], "derived": []},
        })
        result = build_sample_index(ws)
        assert any(w for w in result.warnings if "bad.csv" in w)
        unlinked = [u for u in result.unlinked_tasks if u["task_id"] == "task_0001" and u["reason"] == "csv_parse_error"]
        assert len(unlinked) >= 1

    def test_filename_candidate_in_unlinked_only(self, tmp_path):
        ws = _make_ws(tmp_path, {
            "task_0001": {"raw_items": [("data.csv", "col\n1\n")], "derived_items": [], "derived": []},
        })
        (ws / "tasks" / "task_0001" / "raw" / "B03_data.csv").write_text("col\n1")
        result = build_sample_index(ws)
        unlinked = [u for u in result.unlinked_tasks if u["task_id"] == "task_0001"]
        assert len(unlinked) >= 1
        candidates = unlinked[0].get("candidate_ids", [])
        assert "B03" in candidates
        for s in result.samples:
            for rt in s.related_tasks:
                assert rt.source != "filename_candidate"
        b03_sample = [s for s in result.samples if s.sample_id == "B03"]
        assert len(b03_sample) == 0
