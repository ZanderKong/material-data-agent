# Real API Check Template

## Prerequisites

1. Revoke any credential exposed outside the local machine and create a new credential.
2. Copy `.env.example` to ignored `.env`, or set the documented variables through a local secret manager.
3. Never pass a key as a command argument and never paste it into reports.
4. Load ignored local values into the current shell; the application does not auto-load `.env`.

```bash
set -a
source .env
set +a
```

Required variable groups:

- `DEEPSEEK_TEXT_BASE_URL`, `DEEPSEEK_TEXT_API_KEY`, `DEEPSEEK_TEXT_MODEL`
- `VOLCENGINE_VISION_BASE_URL`, `VOLCENGINE_VISION_API_KEY`, `VOLCENGINE_VISION_MODEL`
- `SILICONFLOW_OCR_BASE_URL`, `SILICONFLOW_OCR_API_KEY`, `SILICONFLOW_OCR_MODEL`

`VOLCENGINE_VISION_MODEL` is the local Ark endpoint ID. Do not commit it in the example.

## Safe configuration check

```bash
cp model_profiles.yaml.example model_profiles.yaml
.venv/bin/python -m data_agent models check --verbose
```

The check must show only `configured`/`missing`, never values.

## Synthetic smoke scenarios

```bash
.venv/bin/python scripts/run_real_api_check.py --scenario deepseek-text
.venv/bin/python scripts/run_real_api_check.py --scenario volcengine-vision
.venv/bin/python scripts/run_real_api_check.py --scenario siliconflow-ocr
.venv/bin/python scripts/run_real_api_check.py --scenario auto-fallback
```

The runner generates synthetic input in a temporary workspace. DeepSeek and SiliconFlow model
IDs are checked with `/models` before paid inference. Missing configuration returns `SKIPPED`;
model mismatch or provider failure returns `FAIL`. The runner never accepts an API-key option.

## Validation, export, and exact-value audit

Use the workspace and task ID printed by each successful scenario:

```bash
.venv/bin/python -m data_agent validate --workspace "$SMOKE_WORKSPACE" --task "$TASK_ID"
.venv/bin/python -m data_agent export --workspace "$SMOKE_WORKSPACE" --task "$TASK_ID"
.venv/bin/python scripts/audit_secret_leaks.py \
  --repo . \
  --workspace "$SMOKE_WORKSPACE" \
  --zip "$EXPORTED_ZIP"
```

Record only date, commit, provider, model, task ID, run ID, result path, latency, token-usage
availability, flags, validation/export status, and known limitations. Never record keys, key
fragments, request headers, full raw responses, signed URLs, or base64 media.
