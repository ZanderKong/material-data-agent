# Current Release Status

**Release judgment: READY FOR PORTFOLIO README REWRITE**

## Verified baseline

- Date: 2026-07-13
- Branch: `codex/real-model-release-gate`
- Provider implementation commit: `4f00ac5`
- Python: 3.11.15
- Default offline tests: `263 passed, 52 skipped`
- Demo tests: not run because `DATA_AGENT_DEMO_INBOX` is not configured
- Compile check: PASS
- `git diff --check`: PASS
- Exact-value key safety audit: PASS for the repository and all successful synthetic evidence packages

## Provider status

| Provider | Role | Model | Real API status | Evidence status |
|---|---|---|---|---|
| DeepSeek | observation text | `deepseek-v4-pro` | PASS | real run, validation WARN, export PASS |
| Xiaomi MiMo | chart/surface vision | `mimo-v2.5` | PASS | `/models` preflight, real run, validation WARN, export PASS |
| SiliconFlow | OCR | `PaddlePaddle/PaddleOCR-VL-1.5` | PASS | `/models` preflight, real run, validation WARN, export PASS |
| Deterministic fallback | cloud failure → local result | synthetic | PASS | failed cloud attempt and independent fallback run persisted |

## Mode and security status

- `local`: offline tests confirm zero network calls.
- `cloud`: all three active providers are verified with synthetic real calls.
- `auto`: deterministic HTTP 429 failure is retained separately from the selected local fallback.
- SiliconFlow plain OCR responses are normalized conservatively into the OCR schema and always marked for review; no missing layout or units are invented.
- `.env` and real `model_profiles.yaml` remain ignored and untracked.
- Secret scans did not find exact configured key values in tracked files, evidence workspaces, SQLite, reports, or exported ZIP packages.

The historical Volcengine Ark timeout is not part of the active provider configuration. See
[REAL_API_CHECK.md](REAL_API_CHECK.md) for the detailed, non-sensitive evidence record.
