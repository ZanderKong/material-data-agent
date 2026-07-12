# Validation Check

## Current Status

- **Date**: 2026-07-11
- **Commit**: `f1724c6` (baseline), Release Candidate
- **pytest**: 242 passed, 52 skipped（45 validation-specific tests）

## Validation Engine

`data_agent/validation.py` performs 6 phases of evidence package validation:

1. **Structure**: Checks for manifest.json, raw/, derived/, logs/, reviews/ directories.
2. **Manifest References**: Verifies input_files and derived_files exist on disk.
3. **ID Lists**: Validates run_ids, flag_ids, review_ids against their respective JSON files.
4. **Processing Runs**: Checks run_id uniqueness, required fields, model run parameters.
5. **Data Objects**: Verifies L2 derived_from, model-result JSON structure, data-schema file references.
6. **Relationships & Checksum**: Validates self-replacement prohibition, SHA-256 checksum integrity.

### Remediation Round 2 Improvements

- **Relationship endpoint registry** now includes both `data_objects.object_id` and `files.file_id`. File-backed endpoints are no longer falsely flagged as unknown.
- **Independent source/target validation**: Each endpoint is checked separately. A single unknown endpoint (ghost source or ghost target) now produces an ERROR.
- **Cross-task endpoint isolation**: Endpoints from other tasks are correctly rejected.
- **Atomic report writing fix**: `result_path` and `report_path` are set to absolute resolved paths BEFORE serialization, so the persisted JSON contains non-blank paths. On write failure, the corresponding path is cleared.

## CLI

```bash
python -m data_agent validate --workspace <path> --task <task_id>
python -m data_agent validate --workspace <path> --all
```

- `--task` validates a single task; `--all` validates all tasks; both missing is an error.
- ERROR exit code 1; PASS/WARN exit code 0.
- Generates `logs/package_validation_result.json` and `logs/package_validation_report.md`.

## Key Test Scenarios

- Normal task PASS ✓
- Missing manifest ERROR ✓
- Empty run_id ERROR ✓
- requires_review WARN ✓
- Invalid JSON ERROR ✓
- Self-replacement ERROR ✓
- Missing SQLite WARN + continues ✓
- validate_all returns every task ✓
- File endpoint accepted in relationship ✓
- Ghost source / ghost target independently ERROR ✓
- Cross-task endpoint rejected ✓
- Write report sets nonempty absolute paths ✓
- Persisted JSON matches returned result ✓
- Report write failure clears paths ✓

### Round 3 Improvements (2026-07-11)

- **Model-result semantics**: Only `data_type == "model_result"` objects require a `model:*` processing run. Normal L2 objects with non-model runs no longer produce false `rels_model_result_non_model_run` errors.
- **Registry-unavailable WARN**: SQLite registry read failures now produce `rels_registry_unavailable` WARN and skip all DB-dependent checks (endpoint, subtype, run-model verification, run_id presence). No false unknown-endpoint errors or run_missing errors on DB failure.

### Release Candidate Guard (2026-07-11)

- **Registry-unavailable run_id guard**: All derived_from DB-dependent checks (endpoint, run_id, model-run) are now inside `if registry_available` block. When registry fails, only JSON structure checks run (format, duplicates, self-replacement, reciprocal). No `rels_derived_from_run_missing` false positive when `run_ids` is empty due to DB failure.
- **Direct unit test**: `test_registry_failure_skips_run_id_check` calls `_check_relationships()` directly with mocked `get_conn`, asserting WARN is present and all three DB-dependent error types are absent.
- **Portable fixtures**: `tests/conftest.py` no longer contains hardcoded user paths. Demo inbox resolved only via `DATA_AGENT_DEMO_INBOX` env var; returns `None` when unset/missing/not-a-dir.
- **Incomplete marker protocol**: A `logs/package_validation_incomplete.json` marker is written before report generation and deleted only after both JSON and Markdown succeed. `read_validation_result()` checks the marker first; if present, returns `status: error` regardless of any stale PASS JSON.
- **Test coverage**: Normal L2 false positive, model-result non-model run, model-run pass, registry failure WARN, incomplete marker lifecycle (md/json replace failure, stale PASS masked, successful retry clears marker).

REAL_API_CHECK: NOT RUN
