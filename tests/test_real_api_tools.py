"""Offline safety tests for the opt-in real API and secret-audit tools."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PYTHON = REPO / ".venv" / "bin" / "python"


def _clean_provider_env() -> dict[str, str]:
    env = os.environ.copy()
    for prefix in ("DEEPSEEK_TEXT", "VOLCENGINE_VISION", "SILICONFLOW_OCR"):
        for suffix in ("BASE_URL", "API_KEY", "MODEL"):
            env.pop(f"{prefix}_{suffix}", None)
    return env


def test_real_api_runner_skips_without_credentials():
    result = subprocess.run(
        [str(PYTHON), "scripts/run_real_api_check.py", "--scenario", "deepseek-text"],
        cwd=REPO, env=_clean_provider_env(), capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "status=SKIPPED" in result.stdout
    assert "Authorization" not in result.stdout + result.stderr


def test_auto_fallback_runner_is_offline_and_audited():
    result = subprocess.run(
        [str(PYTHON), "scripts/run_real_api_check.py", "--scenario", "auto-fallback"],
        cwd=REPO, env=_clean_provider_env(), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "status=PASS" in result.stdout
    assert "fallback=True" in result.stdout
    assert "validation=warn" in result.stdout
    assert "export=True" in result.stdout


def test_secret_audit_detects_exact_value_without_printing_it(tmp_path):
    secret = "unit-test-exact-secret-never-print"
    (tmp_path / "result.json").write_text(f'{{"value":"{secret}"}}', encoding="utf-8")
    env = _clean_provider_env()
    env["DEEPSEEK_TEXT_API_KEY"] = secret
    result = subprocess.run(
        [str(PYTHON), "scripts/audit_secret_leaks.py", "--repo", str(REPO), "--workspace", str(tmp_path)],
        cwd=REPO, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "exact match found" in result.stdout
    assert secret not in result.stdout + result.stderr
