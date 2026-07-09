# Opencode / DeepSeek Fix Plan: Model Service Audit Closure

## 1. Current State

The configurable model service layer has been partially implemented. The current branch already contains:

- model profile files and examples
- model router
- OpenAI-compatible provider
- local stubs
- redaction helpers
- prompt templates
- `DataType.MODEL_RESULT`
- `models check` CLI
- model-related tests and docs
- generated validation artifacts under `work/model-check`

However, the implementation is not ready to ship. The next iteration must focus on correctness, auditability, and verification. Do not add new features until the issues in this file are fixed.

## 2. Hard Rules For This Fix Pass

- Do not add new model roles.
- Do not add new provider types.
- Do not change SQLite table structure.
- Do not write migrations.
- Do not rewrite ingest/review/report architecture.
- Do not change raw numeric, raw spectral, or metadata processing behavior.
- Do not make network calls in `local` mode.
- Do not store API keys in SQLite, JSON, Markdown, CLI output, or errors.
- Do not continue broad feature work until the P0 audit issues pass tests.

## 3. P0 Fixes

### P0.1 Model ProcessingRun IDs Are Empty

Current problem:

- `data_agent/process.py` creates model `ProcessingRun` records with `run_id=""`.
- SQLite `processing_runs.run_id` is the primary key.
- Multiple model runs overwrite each other.
- `work/model-check` showed 10 `model_result` data objects but only 1 `model:*` processing run.
- Manifests contain empty `run_ids`.

Fix:

- In `data_agent/process.py`, never construct `ProcessingRun(run_id="")`.
- Let `ProcessingRun` generate its own UUID or explicitly create one.
- Every model result object must have a matching model processing run.
- Manifest must never include empty `run_ids`.

Specific target:

- Fix around `data_agent/process.py` where `model_run = ProcessingRun(run_id="", ...)` is built.

Acceptance checks:

```bash
sqlite3 work/model-check/agent.sqlite '
select count(*) from data_objects where data_type="model_result";
select count(*) from processing_runs where tool_name like "model:%";
select count(*) from processing_runs where run_id="";
'
```

Expected:

- first count equals second count
- third count is `0`

Also add an automated test:

- `count(model_result data_objects) == count(model:* processing_runs)`
- no manifest contains empty run id

### P0.2 ModelResult JSON Only Stores `output_json`

Current problem:

- `derived/run_*__model_result_<role>.json` currently stores only `result.output_json`.
- This loses important audit details:
  - role
  - provider
  - model
  - mode
  - success
  - fallback status
  - fallback source
  - error
  - warnings
  - latency
  - token usage
  - schema version
  - prompt version

Fix:

- Persist the complete redacted `ModelResult.model_dump()` to the model result JSON file.
- The model's extracted structured content must remain under `output_json`.
- Do not persist request headers or Authorization values.
- Do not persist raw request bodies containing secrets.

Specific target:

- Replace `json.dump(result.output_json, ...)` in `data_agent/process.py` with a safe full result dump.

Required JSON shape:

```json
{
  "success": false,
  "role": "ocr",
  "provider": "local_ocr_stub",
  "model": "",
  "mode": "local",
  "input_type": "image",
  "output_json": {
    "ocr_unavailable": true,
    "requires_review": true
  },
  "raw_text": "",
  "raw_response": {},
  "confidence": 0.0,
  "warnings": ["ocr_unavailable"],
  "error": "",
  "fallback_used": true,
  "fallback_from": "ocr",
  "latency_ms": 0,
  "token_usage": {},
  "created_at": "...",
  "schema_version": "model_result_v1",
  "prompt_version": "stub_v1"
}
```

Acceptance checks:

- Every `*model_result*.json` contains top-level `role`, `provider`, `success`, and `output_json`.
- Forbidden fields are absent at every depth:
  - `final_conclusion`
  - `mechanism_explanation`
  - `experiment_recommendation`

### P0.3 Model Relationships Must Reference The Correct Run

Current problem:

- Relationships for model result L2 objects use the parent processor run id in metadata.
- This makes it harder to trace the actual model invocation.

Fix:

- For model result objects, the `derived_from` relationship metadata must use the model run id.
- For normal processor outputs, keep using the processor run id.

Implementation guidance:

- Insert main processor derived objects and model result derived objects in separate loops, or attach a mapping from output object id to the correct run id.
- Do not weaken existing L1 -> L2 relationship tests.

Acceptance checks:

```bash
sqlite3 work/model-check/agent.sqlite '
select r.rel_id, r.metadata
from relationships r
join data_objects d on r.target_id = d.object_id
where d.data_type="model_result"
limit 5;
'
```

Expected:

- metadata contains the matching `model:*` run id, not the parent chart/visual/observation run id.

## 4. P1 Fixes

### P1.1 Restore Legacy Adapter Compatibility

Current problem:

- `data_agent/model_adapters/local.py` and `cloud_stub.py` still import `ChartImageAnalyzer`.
- `ChartImageAnalyzer` no longer exists in `base.py`.
- They also construct `ModelResult(data=...)`, but the new Pydantic model has no `data` field.

Fix options:

Preferred:

- Remove legacy `ChartImageAnalyzer` usage from `local.py` and `cloud_stub.py`.
- Make these modules delegate to `stubs.py`, or keep thin compatibility classes that return the new `ModelResult` shape.

Alternative:

- Reintroduce a small `ChartImageAnalyzer` shim in `base.py`.
- Still update old `ModelResult(data=...)` usage to `output_json=...`.

Acceptance checks:

```bash
python - <<'PY'
import data_agent.model_adapters.local
import data_agent.model_adapters.cloud_stub
print("legacy adapter imports ok")
PY
```

### P1.2 Implement Real Local-No-Network Test

Current problem:

- `tests/test_model_evidence.py::test_local_makes_no_network_calls` is currently `pass`.

Fix:

- Patch `data_agent.model_adapters.openai_compatible.requests.post`.
- Run a local mode processing pass.
- Assert `requests.post` was not called.

Acceptance:

- The test fails if any local-mode path calls the provider.

### P1.3 Redact Error Paths

Current problem:

- HTTP error text and `RequestException` messages are inserted into `ModelResult.error` without guaranteed redaction.

Fix:

- Run all error strings through `redact_string`.
- Redact `resp.text` before adding it to errors.
- Avoid persisting request payloads or headers.

Specific targets:

- `data_agent/model_adapters/openai_compatible.py`

Acceptance tests:

- Mock HTTP response text containing the actual API key.
- Assert key is not in `ModelResult.model_dump_json()`.
- Mock `RequestException` containing the key.
- Assert key is not persisted.

### P1.4 Strengthen Key-Leak Tests

Current problem:

- Tests mostly search for `sk-`.
- Real configured keys may not start with `sk-`.

Fix:

- Set a unique test key value, for example `unit-test-secret-token-xyz`.
- Search for the exact value in:
  - SQLite rows
  - derived JSON
  - logs JSON
  - Markdown report
  - CLI `models check --verbose` output

Acceptance:

- The exact test key is absent from all persisted artifacts and command output.

### P1.5 Stub Semantics Should Not Pretend OCR/Vision Succeeded

Current problem:

- `local_ocr_stub` and `local_vision_stub` currently return `success=True`.
- This can make unavailable OCR/vision look successful in audit records.

Fix:

- For unavailable OCR/vision stubs, set:
  - `success=false`
  - `confidence=0.0`
  - `requires_review=true` in `output_json`
  - warnings include `ocr_unavailable` or `image_observation_requires_review`
- The workflow should still complete successfully because model failure is non-fatal.

Acceptance:

- Main task processing succeeds.
- Model run status for unavailable OCR/vision can be `failed`.
- Quality flags explain fallback/unavailable state.

## 5. P2 Cleanup

### P2.1 Ignore Or Remove Generated Work Artifacts

Current problem:

- `work/` is currently untracked.

Fix:

- Add `work/` to `.gitignore`, or delete generated `work/model-check` before final status.
- Keep `work/check-ws/` ignore if still useful.

Acceptance:

```bash
git status --short
```

Expected:

- no untracked `work/` validation artifacts

### P2.2 Profile Cache Behavior

Current problem:

- `process.py` has a module-level `_PROFILES_CACHE`.
- Tests that change env/config may observe stale profile state.

Fix:

- Either remove the cache or expose a small reset function used by tests.
- Simpler preferred fix: load profiles per processing call for now; config files are small.

Acceptance:

- Tests can modify `model_profiles.yaml` and env vars without cross-test contamination.

### P2.3 Improve Model Result Replacement Semantics

Current behavior:

- Replacement relationships are based on final output subtype, then applied to all derived outputs.

Fix:

- Ensure model result reruns replace old model results of the same model result subtype.
- Do not create confusing replacement relationships between unrelated output types.

Acceptance:

- Rerun of a chart task creates replacements for:
  - old chart metadata -> new chart metadata
  - old OCR model result -> new OCR model result
  - old vision model result -> new vision model result
- It should not replace a chart metadata object with a model result object.

## 6. Required Tests To Add Or Update

Update or add tests in:

- `tests/test_model_evidence.py`
- `tests/test_model_provider_mock.py`
- `tests/test_model_router.py`
- `tests/test_model_profiles.py`

Required coverage:

1. Model run ids are non-empty.
2. Model run count equals model result data object count.
3. Manifest contains no empty run id.
4. Model result JSON has full `ModelResult` wrapper.
5. Model result JSON contains `output_json`.
6. Local mode makes no network call.
7. Exact API key value never appears in SQLite/JSON/Markdown/CLI output.
8. HTTP error and RequestException messages are redacted.
9. Legacy adapter imports still work.
10. Raw numeric, raw spectral, and metadata still do not route to models.

## 7. Validation Commands

Use the project virtual environment if available. If not, create it first.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

No-key demo validation:

```bash
rm -rf work/model-check

.venv/bin/python -m data_agent ingest \
  --inbox "<demo>/inbox" \
  --workspace work/model-check

.venv/bin/python -m data_agent process \
  --workspace work/model-check \
  --all \
  --models local

.venv/bin/python -m data_agent process \
  --workspace work/model-check \
  --all \
  --models auto

.venv/bin/python -m data_agent models check \
  --workspace work/model-check \
  --verbose
```

Audit SQL checks:

```bash
sqlite3 work/model-check/agent.sqlite '
select count(*) as model_objects from data_objects where data_type="model_result";
select count(*) as model_runs from processing_runs where tool_name like "model:%";
select count(*) as empty_run_ids from processing_runs where run_id="";
'
```

Manifest check:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

for p in sorted(Path("work/model-check/tasks").glob("task_*/manifest.json")):
    m = json.loads(p.read_text())
    empties = [r for r in m.get("run_ids", []) if not r]
    assert not empties, f"{p} contains empty run_ids"
print("manifest run_ids ok")
PY
```

Model result JSON shape check:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

required = {"success", "role", "provider", "mode", "output_json", "schema_version", "prompt_version"}
for p in Path("work/model-check/tasks").glob("task_*/derived/*model_result*.json"):
    data = json.loads(p.read_text())
    missing = required - set(data)
    assert not missing, f"{p} missing {missing}"
print("model_result JSON shape ok")
PY
```

## 8. Definition Of Done

This fix pass is complete when:

- `pytest -q` passes.
- Demo workflow passes in no-key `local` mode.
- Demo workflow passes in no-key `auto` mode.
- There are no empty model run ids.
- Model result object count equals model processing run count.
- Model result JSON files contain full redacted `ModelResult`.
- Local mode has a real no-network test.
- Legacy adapter imports do not fail.
- API keys are not persisted anywhere.
- Generated `work/` artifacts are not left as untracked files.

## 9. Execution Notes For DeepSeek

Work in this order:

1. Fix `ProcessingRun` IDs for model runs.
2. Fix full `ModelResult` JSON persistence.
3. Fix relationship metadata to point to correct model run ids.
4. Repair legacy adapter imports.
5. Add or strengthen tests.
6. Fix redaction error paths.
7. Clean generated work artifacts.
8. Run full tests and demo validation.

Do not broaden scope. This pass is about making the existing model service layer reliable and auditable.
