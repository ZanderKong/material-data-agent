"""Shared test fixtures for data_agent tests."""
import os
from pathlib import Path

import pytest


def _resolve_demo_inbox() -> Path | None:
    env_path = os.environ.get("DATA_AGENT_DEMO_INBOX")
    if not env_path:
        return None
    p = Path(env_path)
    if p.is_dir():
        return p
    return None


@pytest.fixture(scope="session")
def demo_inbox() -> Path | None:
    return _resolve_demo_inbox()


class TestDemoInboxFixturePortability:
    def test_returns_none_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("DATA_AGENT_DEMO_INBOX", raising=False)
        result = _resolve_demo_inbox()
        assert result is None

    def test_returns_path_when_env_points_to_dir(self, tmp_path, monkeypatch):
        inbox = tmp_path / "demo_inbox"
        inbox.mkdir()
        monkeypatch.setenv("DATA_AGENT_DEMO_INBOX", str(inbox))
        result = _resolve_demo_inbox()
        assert result == inbox

    def test_returns_none_when_env_points_to_file(self, tmp_path, monkeypatch):
        f = tmp_path / "not_a_dir"
        f.write_text("x")
        monkeypatch.setenv("DATA_AGENT_DEMO_INBOX", str(f))
        result = _resolve_demo_inbox()
        assert result is None

    def test_returns_none_when_env_points_to_missing_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_AGENT_DEMO_INBOX", str(tmp_path / "nonexistent"))
        result = _resolve_demo_inbox()
        assert result is None
