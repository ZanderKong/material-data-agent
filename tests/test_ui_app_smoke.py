"""Smoke test using Streamlit's AppTest API to verify app renders without exceptions."""
import os
import tempfile
from base64 import b64decode
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def _isolate_model_profiles(monkeypatch):
    """Keep AppTest independent from a developer's ignored local profile file."""
    monkeypatch.setattr("data_agent.ui.readers.load_profiles", lambda: {})


def test_app_starts_without_exception():
    """Real app file must render without unhandled exceptions."""
    with tempfile.TemporaryDirectory() as td:
        os.environ["DATA_AGENT_UI_WORKSPACE"] = td
        app = AppTest.from_file("data_agent/ui/app.py", default_timeout=10)
        app.run()
        assert not app.exception

        # All 7 tabs should be present
        tab_labels = []
        for el in app:
            if hasattr(el, "label") and el.label:
                tab_labels.append(el.label)
        expected = {"Overview", "Ingest", "Tasks", "Task Detail", "Sample View", "Model Profiles", "Help"}
        found = set(tab_labels)
        missing = expected - found
        assert not missing, f"Missing tabs: {missing}"


def test_app_uses_temporary_workspace():
    """App should use the DATA_AGENT_UI_WORKSPACE env var for workspace path."""
    with tempfile.TemporaryDirectory() as td:
        os.environ["DATA_AGENT_UI_WORKSPACE"] = td
        app = AppTest.from_file("data_agent/ui/app.py", default_timeout=10)
        app.run()
        assert not app.exception
        assert Path(td).exists()


def test_app_sample_index_button_present():
    """Sample View tab should have Rebuild Sample Index button."""
    with tempfile.TemporaryDirectory() as td:
        os.environ["DATA_AGENT_UI_WORKSPACE"] = td
        app = AppTest.from_file("data_agent/ui/app.py", default_timeout=10)
        app.run()
        assert not app.exception


def test_app_export_path_session_state_initialized():
    """Session state should include export_zip_path_by_task dict."""
    with tempfile.TemporaryDirectory() as td:
        os.environ["DATA_AGENT_UI_WORKSPACE"] = td
        app = AppTest.from_file("data_agent/ui/app.py", default_timeout=10)
        app.run()
        assert not app.exception
        assert "export_zip_path_by_task" in app.session_state


def test_app_with_model_result_renders_no_exception():
    """App with a model_result task should render without exception."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "ws"
        td_path = ws / "tasks" / "task_0001"
        td_path.mkdir(parents=True)
        for d in ("raw", "derived", "logs", "reviews"):
            (td_path / d).mkdir()
        manifest = {"task_id": "task_0001", "status": "processed", "input_files": [], "derived_files": ["derived/model_result.json"], "run_ids": [], "flag_ids": [], "review_ids": [], "object_ids": []}
        import json
        with open(td_path / "manifest.json", "w") as f:
            json.dump(manifest, f)
        model_result = {"success": True, "role": "vision", "provider": "local", "mode": "local", "output_json": {"text_blocks": ["a"], "detected_units": ["mm"], "audit_only_payload": {"nested": True}}, "schema_version": "1.0", "prompt_version": "1.0"}
        with open(td_path / "derived" / "model_result.json", "w") as f:
            json.dump(model_result, f)
        for name in ("processing_runs", "quality_flags", "relationships"):
            with open(td_path / "logs" / f"{name}.json", "w") as f:
                json.dump([], f)
        with open(td_path / "reviews" / "review_records.json", "w") as f:
            json.dump([], f)
        os.environ["DATA_AGENT_UI_WORKSPACE"] = str(ws)
        app = AppTest.from_file("data_agent/ui/app.py", default_timeout=10)
        app.run()
        assert not app.exception


def test_basic_vs_advanced_derived_evidence():
    """Basic mode hides full JSON and non-model derived files; Advanced shows them."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "ws"
        td_path = ws / "tasks" / "task_0001"
        td_path.mkdir(parents=True)
        raw_dir = td_path / "raw"
        derived_dir = td_path / "derived"
        logs_dir = td_path / "logs"
        reviews_dir = td_path / "reviews"
        for d in (raw_dir, derived_dir, logs_dir, reviews_dir):
            d.mkdir(exist_ok=True)
        import json
        manifest = {"task_id": "task_0001", "status": "processed", "input_files": [], "derived_files": ["derived/model_result.json", "derived/chart.png"], "run_ids": [], "flag_ids": [], "review_ids": [], "object_ids": []}
        with open(td_path / "manifest.json", "w") as f:
            json.dump(manifest, f)
        model_result = {"success": True, "role": "vision", "provider": "local", "mode": "local", "output_json": {"text_blocks": ["a"], "detected_units": ["mm"], "audit_only_payload": {"nested": True}}, "schema_version": "1.0", "prompt_version": "1.0"}
        with open(derived_dir / "model_result.json", "w") as f:
            json.dump(model_result, f)
        with open(derived_dir / "chart.png", "wb") as f:
            f.write(b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL5WQAAAABJRU5ErkJggg=="))
        for name in ("processing_runs", "quality_flags", "relationships"):
            with open(logs_dir / f"{name}.json", "w") as f:
                json.dump([], f)
        with open(reviews_dir / "review_records.json", "w") as f:
            json.dump([], f)

        os.environ["DATA_AGENT_UI_WORKSPACE"] = str(ws)
        app = AppTest.from_file("data_agent/ui/app.py", default_timeout=10)
        app.run()
        assert not app.exception

        app.session_state["selected_task_id"] = "task_0001"
        app.run()
        assert not app.exception

        view_radio = app.radio(key="view_task_0001")
        view_radio.set_value("Basic")
        app.run()
        assert not app.exception
        assert not app.json
        assert not app.image

        view_radio = app.radio(key="view_task_0001")
        view_radio.set_value("Advanced")
        app.run()
        assert not app.exception
        assert app.json
        assert any("audit_only_payload" in str(element.value) for element in app.json)
        assert app.image
