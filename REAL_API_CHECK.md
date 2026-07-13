# Real API Check

**Status: PASS**

All current-provider calls below used synthetic, temporary inputs only. Result paths are
relative to each scenario's temporary evidence workspace. No API keys, request headers,
base64 images, or full provider responses are recorded in this report.

| Scenario | Date | Commit | Provider | Model | Status | Evidence |
|---|---|---|---|---|---|---|
| DeepSeek Text | 2026-07-13 | `4f00ac5` | DeepSeek | `deepseek-v4-pro` | PASS | task `task_0001`; run `8e8a5576-f13e-4329-8857-2088ec05eac1`; `tasks/task_0001/derived/run_c39af2b2__model_result_fast.json`; 2,717 ms; token usage available; validation WARN; export PASS |
| MiMo Vision | 2026-07-13 | `4f00ac5` | Xiaomi MiMo | `mimo-v2.5` | PASS | `/models` preflight available; task `task_0001`; run `42528c84-651d-4afb-adc8-77c07affe065`; `tasks/task_0001/derived/run_20b83d14__model_result_vision.json`; 2,449 ms; token usage available; validation WARN; export PASS |
| SiliconFlow OCR | 2026-07-13 | `4f00ac5` | SiliconFlow | `PaddlePaddle/PaddleOCR-VL-1.5` | PASS | `/models` preflight available; task `task_0001`; run `74f0eb77-4ee7-470e-8774-cfd89ed0f756`; `tasks/task_0001/derived/run_84b4cb4b__model_result_ocr.json`; 8,268 ms; token usage available; validation WARN; export PASS; plain OCR output normalized and marked for review |
| Auto Fallback | 2026-07-13 | `4f00ac5` | deterministic HTTP 429 → local fallback | synthetic | PASS | failed cloud attempt and selected fallback run `5ba8c4bf-24cf-40ee-a033-d12c1de42feb` persisted independently; validation WARN; export PASS |
| Key Safety Audit | 2026-07-13 | `4f00ac5` | all configured providers | - | PASS | exact-value scans passed for repository and all successful evidence workspaces, including SQLite/JSON/Markdown contents and exported ZIP packages |

Validation WARN is expected for synthetic image review flags and fallback audit flags; none
of the passing scenarios had validation errors.

## Historical provider note

The previously configured Volcengine Ark endpoint was tested on synthetic chart inputs and
timed out twice at 90 seconds. It has been removed from the active vision profile and is
not a current release gate; its failed evidence remains in local temporary workspaces.

Never record keys, headers, raw request bodies, base64 images, or full raw responses here.
