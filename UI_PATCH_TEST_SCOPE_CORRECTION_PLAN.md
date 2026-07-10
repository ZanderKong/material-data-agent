# UI Patch Test Scope Correction Plan

## Purpose

Align the completed UI patch with its approved scope: add two to three focused tests, and make `FRONTEND_CHECK.md` report the exact resulting test count.

## Required Changes

### 1. Reduce the New Patch Tests to Three Test Functions

Files: `tests/test_ui_patch_recheck.py`

- Keep exactly three tests, matching the three patch responsibilities.
- Test one: mock `init_db()` and `ingest_inbox()` so ingest fails; assert the connection closes exactly once and the returned message redacts an `sk-*` token.
- Test two: verify `select_raw_response()` prefers `raw_response_redacted`, falls back to a dictionary-valued `raw_response` when higher-priority values are empty, and returns formatted JSON.
- Test three: verify a Quality Flag-shaped message is redacted by `safe_display_text()` for an `sk-*` token, a Bearer token, and a configured environment-variable value.
- Remove the seven narrower tests that duplicate these three behavioral contracts.

Acceptance:

- The file contains exactly three `test_` functions.
- The three required behaviors remain covered without changing production code.

### 2. Correct the Verification Record

Files: `FRONTEND_CHECK.md`

- In the `UI Patch Recheck` subsection, replace the current mixed wording about "3" versus "10" tests with an exact statement that three focused tests were added.
- Re-run the full test suite and update the recorded passed count and elapsed result using the actual output.
- Keep the existing compile result only if `compileall` is re-run successfully; otherwise replace it with the observed result.

## Verification

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q data_agent
```

The final documentation must report the same number of tests as the collected suite and must not claim tests that no longer exist.

## Boundaries

- Do not alter `data_agent/ui/actions.py`, `data_agent/ui/app.py`, `data_agent/ui/preview.py`, or `data_agent/ui/security.py`.
- Do not change database, model, ingest, processing, review, or UI behavior.
- This correction is documentation-and-test-scope only; do not add further UI features.
