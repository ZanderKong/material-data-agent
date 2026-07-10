"""Tests for data_agent ui CLI command."""
import subprocess
import sys
from pathlib import Path


def test_ui_command_prints_streamlit_command():
    result = subprocess.run(
        [sys.executable, "-m", "data_agent", "ui", "--workspace", "/tmp/test-ui-ws", "--print-command"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    output = result.stdout
    assert "streamlit" in output.lower()
    assert "DATA_AGENT_UI_WORKSPACE" in output
    resolved = str(Path("/tmp/test-ui-ws").resolve())
    assert resolved in output


def test_ui_command_does_not_create_workspace_in_print_mode():
    ws_path = Path("/tmp/test-ui-print-mode-ws")
    if ws_path.exists():
        import shutil
        shutil.rmtree(str(ws_path))

    result = subprocess.run(
        [sys.executable, "-m", "data_agent", "ui", "--workspace", str(ws_path), "--print-command"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert not ws_path.exists()


def test_ui_command_sets_workspace_env_in_output():
    ws_path = Path("/tmp/my-special-ws").resolve()
    result = subprocess.run(
        [sys.executable, "-m", "data_agent", "ui", "--workspace", str(ws_path), "--print-command"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    output = result.stdout
    resolved_ws = str(ws_path)
    assert f"DATA_AGENT_UI_WORKSPACE={resolved_ws}" in output
