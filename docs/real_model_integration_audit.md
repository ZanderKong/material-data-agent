# Real Model Integration Audit

## Routing and evidence chain

| Data type | Role | Provider profile | Input | Request | Persistence | Failure/fallback audit |
|---|---|---|---|---|---|---|
| `descriptive_observation_text` | `fast` | DeepSeek | bounded UTF-8 L1 text | Chat Completions text + JSON mode | `model_result_fast.json`, `model:fast` run, flags and relationships | cloud failure retained as `model_result_fast_cloud_attempt.json`; auto fallback separate |
| `chart_image_input` | `vision` | Volcengine Ark | L1 image | multimodal `image_url` data URL | `model_result_vision.json`, `model:vision` run | cloud does not fallback; auto preserves both attempts |
| `chart_image_input` | `ocr` | SiliconFlow | L1 image | multimodal `image_url` data URL | `model_result_ocr.json`, `model:ocr` run | cloud does not fallback; auto preserves both attempts |
| `visual_image` | `vision` | Volcengine Ark | L1 image | multimodal `image_url` data URL | `model_result_vision.json`, `model:vision` run | manual-review boundary remains mandatory |

All model results are sanitized before persistence. Runs, quality flags, relationships,
validation, UI previews, and exports consume the same evidence. Local mode makes no network call.

## Implementation boundaries

- Provider differences are expressed through `ModelProfile` capabilities.
- Role-level Pydantic schemas reject missing or incorrectly typed core fields.
- `reasoning_content` is never used as final output.
- Failed cloud attempts cannot be presented as successful local fallback.
- `ingest.py`, `reviews.py`, and `db.py` were not changed.

## Verification state

- Offline provider, parser, fallback, persistence, UI, validation, export, and security tests: PASS.
- Deterministic offline auto-fallback smoke: PASS.
- DeepSeek, Volcengine, and SiliconFlow real calls: NOT RUN because rotated credentials are not configured.
