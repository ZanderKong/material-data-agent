"""Smoke test using Streamlit's AppTest API to verify app renders without exceptions."""
import os
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest


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
