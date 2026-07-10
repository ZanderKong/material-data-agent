# Validation Check

## Current Status

- **Date**: 2026-07-10
- **Commit**: `5adbc2d`
- **pytest**: 234 passed (20 validation-specific tests in `tests/test_validation.py`)

## Validation Engine

`data_agent/validation.py` performs 6 phases of evidence package validation:

1. **Structure**: Checks for manifest.json, raw/, derived/, logs/, reviews/ directories.
2. **Manifest References**: Verifies input_files and derived_files exist on disk.
3. **ID Lists**: Validates run_ids, flag_ids, review_ids against their respective JSON files.
4. **Processing Runs**: Checks run_id uniqueness, required fields, model run parameters.
5. **Data Objects**: Verifies L2 derived_from, model-result JSON structure, data-schema file references.
6. **Relationships & Checksum**: Validates self-replacement prohibition, SHA-256 checksum integrity.

## CLI

```bash
python -m data_agent validate --workspace <path> --task <task_id>
python -m data_agent validate --workspace <path> --all
```

- `--task` validates a single task; `--all` validates all tasks; both missing is an error.
- ERROR exit code 1; PASS/WARN exit code 0.
- Generates `logs/package_validation_result.json` and `logs/package_validation_report.md`.

## Demo Results

Workspace: `/tmp/material-agent-next-iteration-ws` (9 tasks, local mode processed)

| Task | Status | Errors | Warnings |
|------|--------|--------|----------|
| task_0001 | WARN | 0 | 1 |
| task_0002 | WARN | 0 | 2 |
| task_0003 | PASS | 0 | 0 |
| task_0004 | PASS | 0 | 0 |
| task_0005 | WARN | 0 | 1 |
| task_0006 | WARN | 0 | 5 |
| task_0007 | WARN | 0 | 2 |
| task_0008 | WARN | 0 | 2 |
| task_0009 | PASS | 0 | 0 |

WARNs are expected: local stubs produce requires_review flags and empty model names.

## Key Test Scenarios

- Normal task PASS ✓
- Missing manifest ERROR ✓
- Empty run_id ERROR ✓
- requires_review WARN ✓
- Invalid JSON ERROR ✓
- Self-replacement ERROR ✓
- Missing SQLite WARN + continues ✓
- validate_all returns every task ✓
