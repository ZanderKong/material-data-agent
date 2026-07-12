# Export Check

> Historical checkpoint. This report records the state at its original commit/date and is not the current release status. See `CURRENT_RELEASE_STATUS.md` for the latest verified state.

## Current Status

- **Date**: 2026-07-11
- **Commit**: `f1724c6` (baseline), Release Candidate
- **pytest**: 242 passed, 52 skipped（25 export-specific tests）

## Export Engine

`data_agent/export.py` generates a ZIP review package with:

1. **Validation Gate**: Runs `validate_task(write_report=True)` before export.
2. **Report Identity Check**: Verifies the persisted JSON matches the current validation result (task_id, validated_at, status, result_path, report_path). Stale or mismatched reports block export.
3. **README_for_review.md**: Generated at ZIP root with task summary, file lists, quality flags, reviews, and disclaimers.
4. **Atomic ZIP**: Written to temp file first, then atomically replaced.
5. **Path Safety**: Rejects absolute paths, `..` traversal, and symlinks (including directory symlinks).

### Remediation Round 2 Improvements

- **Directory symlink detection**: Top-level directories (`raw/`, `derived/`, `logs/`, `reviews/`) and child directories during traversal are checked for symlinks. Directory symlinks block export.
- **Explicit ZIP directory entries**: `raw/`, `derived/`, `logs/`, `reviews/` are always written as explicit directory entries in the archive.
- **Persistent report identity verification**: Export now validates persisted JSON fields (task_id, validated_at, status, result_path, report_path) against the in-memory validation result. Mismatched or stale reports block export.
- **Validation ERROR still exports**: Tasks with validation errors can still be exported, with a conspicuous "EXPORTED WITH VALIDATION ERRORS" warning.

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

## Key Test Scenarios

- Normal task creates ZIP with required entries ✓
- README contains both disclaimers ✓
- Missing task returns failure ✓
- Output directory created automatically ✓
- Symlink rejected ✓
- Validation report included ✓
- Source files preserved after export ✓
- Symlinked directory under raw/ blocks export ✓
- ZIP contains explicit directory entries (even with content) ✓
- ZIP contains explicit directory entries (empty dirs) ✓
- No ZIP created on preflight failure ✓
- Export blocked by blank report path ✓
- Export blocked by wrong report path ✓
- Export blocked by stale validated_at in persisted JSON ✓
- Export blocked by different task_id in persisted JSON ✓
- Validation error still exports with warning ✓

### Round 3 Improvements (2026-07-11)

- **Broken top-level symlink detection**: `manifest.json`, `raw/`, `derived/`, `logs/`, `reviews/` are checked for `is_symlink()` BEFORE `exists()`. Broken symlinks (where target is missing) are rejected. Test coverage: broken directory symlink, broken file symlink, existing ZIP not overwritten on failure.
- **Incomplete marker blocks export**: If `logs/package_validation_incomplete.json` exists, export returns `success=False` immediately. Marker presence prevents export of potentially incomplete/partial validation artifacts.
- **Preflight order fix**: `is_symlink()` checked before `exists()` ensures broken symlinks don't pass silently.

REAL_API_CHECK: NOT RUN
