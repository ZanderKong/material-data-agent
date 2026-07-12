# Real API Check

**Status: PARTIAL**

Engineering support for the three providers is implemented and verified offline. Real paid
calls were not run because rotated credentials are not configured. No credential from
conversation history was used.

| Scenario | Date | Commit | Provider | Model | Status | Command | Evidence |
|---|---|---|---|---|---|---|---|
| DeepSeek Text | 2026-07-13 | working tree based on `135c98c` | DeepSeek | `deepseek-v4-pro` | NOT RUN | `python scripts/run_real_api_check.py --scenario deepseek-text` | Rotated environment variables missing |
| Volcengine Vision | 2026-07-13 | working tree based on `135c98c` | Volcengine Ark | local endpoint ID | NOT RUN | `python scripts/run_real_api_check.py --scenario volcengine-vision` | Rotated environment variables missing |
| SiliconFlow OCR | 2026-07-13 | working tree based on `135c98c` | SiliconFlow | `PaddlePaddle/PaddleOCR-VL-1.5` | NOT RUN | `python scripts/run_real_api_check.py --scenario siliconflow-ocr` | Rotated environment variables missing |
| Auto Fallback | 2026-07-13 | working tree based on `135c98c` | deterministic failure → local fallback | synthetic | PASS | `python scripts/run_real_api_check.py --scenario auto-fallback` | task `task_0001`; selected run `fc7abe5c-535c-4197-b22b-2bae8fc45b0e`; result `tasks/task_0001/derived/run_73ad7d87__model_result_fast.json`; latency 0 ms; token usage unavailable; fallback/review flags present; validation WARN; export PASS |
| Key Safety Audit | 2026-07-13 | working tree based on `135c98c` | all providers | - | PARTIAL | `python scripts/audit_secret_leaks.py --repo .` | scanner PASS; real-value scan remains NOT RUN |

This file may be changed to `PASS` only after all real-provider scenarios succeed, their
packages validate and export, and the exact-value audit passes. Never record keys, headers,
raw request bodies, base64 images, or full raw responses here.
