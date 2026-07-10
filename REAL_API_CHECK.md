# Real API Check

**Status: NOT RUN**

This document records the status of real API verification. Core functionality (local mode, validation, export, sample index) is complete and tested. Real API verification requires user-provided API keys and is a separate manual gate.

## Required Steps

1. Configure `model_profiles.yaml` with valid provider entries.
2. Set environment variables for API keys (see `docs/real_api_check_template.md` for safe shell commands).
3. Run the three scenarios documented in `docs/real_api_check_template.md`.
4. Perform the key-safety audit after each scenario.
5. Record results below.

## Text Call Results

| Date | Provider | Model | Role | Status | Task ID | Model Result Path | Run ID | Flags |
|------|----------|-------|------|--------|---------|-------------------|--------|-------|
| *NOT RUN* | - | - | fast/text | - | - | - | - | - |

## Vision/OCR Call Results

| Date | Provider | Model | Role | Status | Task ID | Model Result Path | Run ID | Flags |
|------|----------|-------|------|--------|---------|-------------------|--------|-------|
| *NOT RUN* | - | - | vision/ocr | - | - | - | - | - |

## Auto Fallback Results

| Date | Provider | Model | Role | Status | Task ID | Model Result Path | Run ID | Flags |
|------|----------|-------|------|--------|---------|-------------------|--------|-------|
| *NOT RUN* | - | - | vision/ocr (auto) | - | - | - | - | - |

## Key Safety Audit

**Result: NOT RUN**

## Completion Criteria

- [ ] At least one text real call succeeded
- [ ] At least one vision/OCR call succeeded, or provider failure + verified auto fallback documented as PARTIAL
- [ ] No key matches found in workspace files, SQLite, or exported ZIP
- [ ] No key stored in git or documentation

## Notes

- If no API keys are available, this document remains NOT RUN. Core completion is not blocked.
- Any secret leak blocks all completion claims.
- The `docs/real_api_check_template.md` contains detailed setup and scenario instructions.
