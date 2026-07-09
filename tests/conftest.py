"""Shared test fixtures for data_agent tests."""
import os
from pathlib import Path

import pytest

_NEW_DEMO_INBOX = Path(
    "/Users/kong/Library/Mobile Documents/com~apple~CloudDocs/"
    "ZanderKong/material_data_agent_demo/inbox"
)
_OLD_DEMO_INBOX = Path(
    "/Users/zanderkong/Desktop/数据处理agent/material_data_agent_demo 测试数据/inbox"
)


def _resolve_demo_inbox() -> Path | None:
    env_path = os.environ.get("DATA_AGENT_DEMO_INBOX")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    if _NEW_DEMO_INBOX.exists():
        return _NEW_DEMO_INBOX
    if _OLD_DEMO_INBOX.exists():
        return _OLD_DEMO_INBOX
    return None


@pytest.fixture(scope="session")
def demo_inbox() -> Path | None:
    return _resolve_demo_inbox()
