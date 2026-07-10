# UI Patch Recheck Plan

## Goal

Complete a narrow UI patch recheck without changing the SQLite schema, model routing, or the ingest/process/review workflow. The patch covers connection cleanup, display redaction, raw-response compatibility, focused tests, and a documented verification record.

## Required Changes

### 1. Ingest Connection and Temporary-Directory Cleanup

Files: `data_agent/ui/actions.py`

- Refactor `do_ingest()` and `do_upload_ingest()` so connection acquisition and backend calls run inside a `try` block.
- Initialize `conn` to `None`, then call `conn.close()` exactly once in `finally` only when connection creation succeeded.
- Remove the existing success-path `conn.close()` calls.
- For `do_upload_ingest()`, move temporary inbox cleanup to `finally` so it runs after success, ingest failure, upload-write failure, or database-initialization failure.
- Preserve existing return dictionaries and route all caught error messages through `_safe_msg()`.

Acceptance:

- A successful ingest returns the current success payload and closes its connection.
- An ingest exception returns the current redacted failure payload and still closes its connection.
- Upload temporary files are removed regardless of the outcome.

### 2. Quality Flag Display Redaction

Files: `data_agent/ui/app.py`

- Before formatting each Quality Flag notice, compute `message = safe_display_text(str(flag.get("message", "")))`.
- Use this value in both the `st.warning()` and `st.info()` branches.
- Keep the current severity, confidence, icon, and `requires_review` behavior unchanged.

Acceptance:

- Secrets shaped as `sk-*`, Bearer tokens, and configured environment-variable values do not appear in rendered Quality Flag messages.
- Flag presentation still uses warning styling when `requires_review` is true and info styling otherwise.

### 3. Raw Response Compatibility Fallback

Files: `data_agent/ui/preview.py`, `data_agent/ui/app.py`

- Add `select_raw_response(raw: dict[str, Any]) -> str` in `preview.py`.
- Select the first non-empty value in this exact order: `raw_response_redacted`, `raw_text`, `raw_response`; return an empty string when all are empty.
- Return strings as-is. Serialize dictionaries and lists using `json.dumps(..., ensure_ascii=False, indent=2, default=str)`. Convert scalar values with `str()`.
- In the Raw Response expander, call `safe_display_text(select_raw_response(raw_data))` before applying the existing 2,000-character display limit.
- Keep the expander collapsed by default and retain its existing "redacted" label.

Acceptance:

- Existing model results still prefer their redacted response.
- Historical or compatible results with only `raw_response` remain inspectable.
- Every fallback value passes through the display redactor before reaching Streamlit.

## Tests

Add exactly three focused tests:

1. `do_ingest()` closes a mocked connection exactly once when `ingest_inbox()` raises, and returns a redacted failure message.
2. `select_raw_response()` prefers `raw_response_redacted` and falls back to a dictionary-valued `raw_response`, returning formatted JSON.
3. A Quality Flag-shaped message containing an `sk-*` token or Bearer token is redacted by `safe_display_text()`.

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q data_agent
```

Record the actual test count and command results; do not pre-fill expected results.

## Documentation Recheck

Files: `FRONTEND_CHECK.md`

- Add a dated `UI patch recheck` subsection after the current second-round fixes.
- State only verified outcomes: `finally` cleanup, Quality Flag redaction, Raw Response fallback order, the three focused tests, and the actual full-suite and compile results.
- Do not alter the completed 15-item manual UI checklist unless it is manually rerun as part of this patch.

## Boundaries

- Do not change data models, SQLite schema, model-provider code, processing semantics, review persistence, or raw/L2 lifecycle behavior.
- Do not add browser E2E infrastructure, authentication, APIs, or frontend framework migrations in this patch.
