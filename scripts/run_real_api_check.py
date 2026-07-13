#!/usr/bin/env python3
"""Run safe, synthetic, opt-in real-provider smoke checks."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib.pyplot as plt
import requests
import yaml
from PIL import Image, ImageDraw

from data_agent.db import init_db
from data_agent.export import export_task
from data_agent.ingest import ingest_inbox
from data_agent.model_adapters.redaction import redact_string
import data_agent.process as process_module
from data_agent.validation import validate_task


SCENARIOS = ("deepseek-text", "mimo-vision", "siliconflow-ocr", "auto-fallback")
CONFIG = {
    "deepseek-text": {
        "role": "fast", "provider": "deepseek", "prefix": "DEEPSEEK_TEXT",
        "modalities": ["text"], "json_mode": "required", "thinking_mode": "disabled",
        "max_output_tokens": 2048,
    },
    "mimo-vision": {
        "role": "vision", "provider": "xiaomi_mimo", "prefix": "MIMO_VISION",
        "modalities": ["text", "image"], "json_mode": "required", "thinking_mode": "disabled",
        "max_output_tokens": 512,
    },
    "siliconflow-ocr": {
        "role": "ocr", "provider": "siliconflow", "prefix": "SILICONFLOW_OCR",
        "modalities": ["text", "image"], "json_mode": "disabled", "thinking_mode": "provider_default",
        "max_output_tokens": 256,
    },
}


def _required(prefix: str) -> tuple[dict[str, str], list[str]]:
    names = [f"{prefix}_BASE_URL", f"{prefix}_API_KEY", f"{prefix}_MODEL"]
    values = {name: os.environ.get(name, "") for name in names}
    return values, [name for name, value in values.items() if not value]


def _preflight_models(values: dict[str, str], requested_model: str) -> bool:
    base = values[next(name for name in values if name.endswith("_BASE_URL"))].rstrip("/")
    key = values[next(name for name in values if name.endswith("_API_KEY"))]
    try:
        response = requests.get(
            f"{base}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30
        )
        if response.status_code != 200:
            return False
        body = response.json()
        models = body.get("data", []) if isinstance(body, dict) else []
        return any(isinstance(item, dict) and item.get("id") == requested_model for item in models)
    except (requests.RequestException, ValueError):
        return False


def _write_profile(path: Path, spec: dict[str, object], prefix: str) -> None:
    role = str(spec["role"])
    config = {"profiles": {role: {
        "role": role, "provider": spec["provider"],
        "base_url_env": f"{prefix}_BASE_URL", "api_key_env": f"{prefix}_API_KEY",
        "model_env": f"{prefix}_MODEL", "endpoint_path": "/chat/completions",
        "input_modalities": spec["modalities"], "json_mode": spec["json_mode"],
        "image_detail": "high", "thinking_mode": spec["thinking_mode"],
        "max_output_tokens": int(spec["max_output_tokens"]), "enabled": True,
        "fallback": ["local_ocr_stub", "local_stub"] if role == "ocr" else ["local_stub"],
        "timeout_seconds": 90, "supports_vision": "image" in spec["modalities"],
        "supports_json": spec["json_mode"] != "disabled",
    }}}
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def _make_input(inbox: Path, scenario: str) -> None:
    if scenario in {"deepseek-text", "auto-fallback"}:
        (inbox / "observation_smoke.txt").write_text(
            "2026-01-01 10:00，样品 SYN-01 表面可见轻微浑浊。可能与温度变化有关。操作员备注：仅为合成测试。",
            encoding="utf-8",
        )
    elif scenario == "mimo-vision":
        x = [1, 2, 3, 4, 5]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(x, [1, 3, 2, 4, 3], label="Synthetic A")
        ax.plot(x, [2, 2, 3, 3, 4], label="Synthetic B")
        ax.set(title="Synthetic Material Chart", xlabel="Time (s)", ylabel="Signal (a.u.)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(inbox / "ftir_chart_smoke.png")
        plt.close(fig)
    else:
        image = Image.new("RGB", (900, 300), "white")
        draw = ImageDraw.Draw(image)
        draw.text((40, 50), "Synthetic OCR: Sample SYN-01", fill="black")
        draw.text((40, 120), "Wavelength 550 nm", fill="black")
        draw.text((40, 190), "Signal 0.82 a.u.", fill="black")
        image.save(inbox / "uvvis_chart_ocr.png")


def _find_result(workspace: Path, task_id: str, role: str, provider: str) -> tuple[Path | None, dict]:
    for path in sorted((workspace / "tasks" / task_id / "derived").glob(f"*model_result_{role}.json"), reverse=True):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("provider") == provider:
            return path, data
    return None, {}


def _run_one(scenario: str) -> int:
    workspace = Path(tempfile.mkdtemp(prefix=f"material-agent-{scenario}-"))
    inbox = workspace / "synthetic_inbox"
    inbox.mkdir()
    _make_input(inbox, scenario)

    if scenario == "auto-fallback":
        spec = CONFIG["deepseek-text"]
        prefix = "DATA_AGENT_FALLBACK_TEST"
        os.environ.update({
            f"{prefix}_BASE_URL": "https://deterministic.invalid",
            f"{prefix}_API_KEY": "synthetic-test-key",
            f"{prefix}_MODEL": "synthetic-model",
        })
    else:
        spec = CONFIG[scenario]
        prefix = str(spec["prefix"])
        values, missing = _required(prefix)
        if missing:
            print(f"scenario={scenario} status=SKIPPED reason=missing_environment workspace={workspace}")
            return 2
        requested = values[f"{prefix}_MODEL"]
        if scenario in {"deepseek-text", "mimo-vision", "siliconflow-ocr"}:
            available = _preflight_models(values, requested)
            print(f"scenario={scenario} provider={spec['provider']} requested_model={'available' if available else 'unavailable'}")
            if not available:
                print(f"scenario={scenario} status=FAIL reason=model_preflight_failed workspace={workspace}")
                return 1

    profile_path = workspace / "model_profiles.yaml"
    _write_profile(profile_path, spec, prefix)
    os.environ["DATA_AGENT_MODEL_PROFILES"] = str(profile_path)
    conn = init_db(workspace)
    [task_id] = ingest_inbox(inbox, workspace, conn)
    conn.close()

    if scenario == "auto-fallback":
        import data_agent.model_adapters.openai_compatible as adapter
        original_post = adapter.requests.post
        adapter.requests.post = lambda *args, **kwargs: SimpleNamespace(status_code=429, text="synthetic rate limit")
        try:
            process_module.process_single_task(workspace, task_id, "auto")
        finally:
            adapter.requests.post = original_post
        provider = "local_stub"
        role = "fast"
    else:
        # A provider smoke validates one role only.  Chart inputs normally route
        # to both OCR and vision, which would otherwise turn an intentionally
        # single-provider profile into a false validation failure.
        original_router = process_module.route_model_calls
        process_module.route_model_calls = lambda _ctx: [str(spec["role"])]
        try:
            process_module.process_single_task(workspace, task_id, "cloud")
        finally:
            process_module.route_model_calls = original_router
        provider = str(spec["provider"])
        role = str(spec["role"])

    result_path, result = _find_result(workspace, task_id, role, provider)
    validation = validate_task(workspace, task_id)
    export = export_task(workspace, task_id)
    conn = sqlite3.connect(workspace / "agent.sqlite")
    row = conn.execute(
        "SELECT run_id, status FROM processing_runs WHERE task_id=? AND tool_name=? ORDER BY created_at DESC LIMIT 1",
        (task_id, f"model:{role}"),
    ).fetchone()
    conn.close()
    status = "PASS" if result_path and result.get("success") and validation.status != "error" and export.success else "FAIL"
    if scenario == "auto-fallback":
        attempts = list((workspace / "tasks" / task_id / "derived").glob("*cloud_attempt.json"))
        status = "PASS" if attempts and result.get("fallback_used") and validation.status != "error" and export.success else "FAIL"
    print(" ".join([
        f"scenario={scenario}", f"provider={provider}", f"model={result.get('model', '')}",
        f"status={status}", f"task_id={task_id}", f"run_id={row[0] if row else ''}",
        f"run_status={row[1] if row else ''}", f"result_path={result_path or ''}",
        f"latency_ms={result.get('latency_ms', 0)}", f"token_usage_available={bool(result.get('token_usage'))}",
        f"fallback={bool(result.get('fallback_used'))}", f"validation={validation.status}",
        f"export={export.success}", f"workspace={workspace}",
    ]))
    return 0 if status == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, choices=(*SCENARIOS, "all"))
    args = parser.parse_args()
    scenarios = SCENARIOS if args.scenario == "all" else (args.scenario,)
    results = [_run_one(scenario) for scenario in scenarios]
    if 1 in results:
        return 1
    if 2 in results:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"status=FAIL error={redact_string(str(exc))}")
        raise SystemExit(1)
