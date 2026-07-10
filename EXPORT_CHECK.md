# Export Check

## Current Status

- **Date**: 2026-07-10
- **Commit**: `5adbc2d`
- **pytest**: 234 passed (8 export-specific tests in `tests/test_export.py`)

## Export Engine

`data_agent/export.py` generates a ZIP review package with:

1. **Validation Gate**: Runs `validate_task(write_report=True)` before export.
2. **README_for_review.md**: Generated at ZIP root with task summary, file lists, quality flags, reviews, and disclaimers.
3. **Atomic ZIP**: Written to temp file first, then atomically replaced.
4. **Path Safety**: Rejects absolute paths, `..` traversal, and symlinks.

## CLI

```bash
python -m data_agent export \
  --workspace <path> \
  --task <task_id> \
  --output <optional-path>
```

- Default output: `workspace/exports/<task_id>_export.zip`
- Validation ERROR still exports (with warning), validation report failure blocks export.
- Exit 0 on success, exit 1 on failure.

## ZIP Contents

```
README_for_review.md
package_validation_report.md
manifest.json
raw/
derived/
logs/
reviews/
```

## Disclaimers in README

- `model_result is model-assisted extraction, not a scientific conclusion.`
- `requires_review=True requires human confirmation.`

## Key Test Scenarios

- Normal task creates ZIP with required entries ✓
- README contains both disclaimers ✓
- Missing task returns failure ✓
- Output directory created automatically ✓
- Symlink rejected ✓
- Validation report included ✓
- Source files preserved after export ✓
