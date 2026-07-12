# Current Release Status

**Release judgment: PARTIALLY READY**

## Verified baseline

- Date: 2026-07-13
- Base commit: `135c98c`
- Branch: `codex/real-model-release-gate`
- Python: 3.11.15
- Default offline tests: `262 passed, 52 skipped`
- Demo tests: skipped because `DATA_AGENT_DEMO_INBOX` is not configured
- Compile check: PASS
- Deterministic auto fallback: PASS
- Fallback package validation/export: WARN/PASS

## Provider status

| Provider | Role | Model | Offline contract | Real API |
|---|---|---|---|---|
| DeepSeek | observation text | `deepseek-v4-pro` | PASS | NOT RUN — rotated credentials missing |
| Volcengine Ark | chart/surface vision | local endpoint ID | PASS | NOT RUN — rotated credentials missing |
| SiliconFlow | OCR | `PaddlePaddle/PaddleOCR-VL-1.5` | PASS | NOT RUN — rotated credentials missing |

## Mode and security status

- `local`: PASS; zero network requests.
- `cloud`: offline request, response, schema, error, redaction, and persistence tests PASS.
- `auto`: cloud failure and fallback are separate auditable results; synthetic smoke PASS.
- `.env` and real `model_profiles.yaml` remain ignored and untracked.
- Exact-value scanner is implemented and tested without printing secret values.
- Real-key scan is NOT RUN because rotated keys are not configured.

## Remaining release gates

1. Configure newly rotated provider credentials locally.
2. Run all three real-provider smoke scenarios.
3. Validate and export each real-provider package.
4. Run exact-value audit against each workspace and ZIP.
5. Re-run the full suite and bind documentation to the final commit.

The project is not yet `READY FOR PORTFOLIO README REWRITE`.
