# OpenCode / DeepSeek V4 Pro Execution Plan: Material Data Agent Next Iteration

> Repository: `ZanderKong/material-data-agent`
>
> Baseline commit when this plan was written: `9157146`
>
> Baseline automated test count: `183 collected`
>
> This document is an execution contract. Follow the order, file boundaries, interfaces, checks, and refusal gates exactly. Do not replace required behavior with a smaller approximation and do not claim completion from tests that do not cover the required workflow.

## 0. Mission

Move the project from a runnable local demo to a credible materials R&D data product prototype by implementing:

1. Data Input Contract.
2. Evidence Package Validation.
3. Single-task Review Package Export.
4. Real API check documentation and manual evidence workflow.
5. HR-facing Streamlit polish, including a minimal Basic/Advanced task view.
6. A minimal workspace-level sample index and Sample View.

The required implementation scope is P0, P1, and P2 in this plan. P3 is explicitly deferred and must not be implemented unless all required gates already pass and the user separately requests it.

## 1. Absolute Rules

DeepSeek must obey all rules below.

### 1.1 Never do these things

- Do not rewrite `ingest.py`, `process.py`, or `reviews.py`.
- Do not redesign or rewrite the Model Service Layer.
- Do not change the SQLite schema or run a migration.
- Do not add LangChain, CrewAI, pi-go, Craft Agents, or another general agent framework.
- Do not migrate to FastAPI, React, or another frontend stack.
- Do not add authentication, permissions, or API-key encryption.
- Do not add chart digitization or a complex OCR engine.
- Do not generate scientific conclusions, mechanism explanations, or experiment recommendations.
- Do not store a real API key in source, tests, fixtures, snapshots, SQLite, JSON, Markdown, logs, command output, screenshots, or UI text.
- Do not make Streamlit `session_state` the business source of truth.
- Do not let UI code directly write SQLite, manifest, review files, or quality flags.
- Do not modify or delete raw files.
- Do not overwrite or delete old L2 files.
- Do not bypass `write_review()`.
- Do not silently repair validation failures.
- Do not treat a generated ZIP as proof that validation passed.

### 1.2 Editing discipline

- Read a file before editing it.
- Preserve existing patterns and public behavior unless this plan explicitly changes them.
- Keep new backend logic outside `ui/app.py`; the app may render and call wrappers only.
- Use standard-library modules where sufficient (`json`, `hashlib`, `zipfile`, `pathlib`, `tempfile`).
- Do not add a dependency without recording why the standard library is insufficient. This plan requires no new dependency.
- Do not update documented test counts until the final commands have actually run.
- Do not include unrelated formatting or refactors.

### 1.3 Completion language

- Use `PASS` only for behavior directly verified in the current run.
- Use `WARN` for incomplete evidence, low confidence, or missing optional registry context.
- Use `ERROR` for corruption, broken references, missing required files, and invalid package structure.
- Use `NOT RUN` for a real API check when no user-provided environment key is available.
- Never convert `NOT RUN` or a mock HTTP test into a real API `PASS`.

## 2. Mandatory Repository Reading

Before editing, read these files completely:

- `README.md`
- `FRONTEND_CHECK.md`
- `MODEL_LAYER_CHECK.md`
- `FINAL_CHECK.md`
- `docs/model_service_layer.md`
- `docs/frontend_operation_loop.md`
- `docs/ui_walkthrough.md`
- `data_agent/cli.py`
- `data_agent/schemas.py`
- `data_agent/db.py`
- `data_agent/package.py`
- `data_agent/ingest.py`
- `data_agent/process.py`
- `data_agent/reviews.py`
- `data_agent/ui/app.py`
- `data_agent/ui/actions.py`
- `data_agent/ui/readers.py`
- `data_agent/ui/preview.py`
- `data_agent/ui/security.py`
- `data_agent/model_adapters/base.py`
- `data_agent/model_adapters/router.py`
- `data_agent/model_adapters/profiles.py`
- `data_agent/model_adapters/openai_compatible.py`
- `tests/test_model_evidence.py`
- `tests/test_ui_patch_recheck.py`
- `tests/test_ui_preview.py`
- `tests/test_ui_security.py`
- `tests/test_review_target.py`

After reading, write a short execution note in the coding session containing:

- Current capabilities.
- Reusable functions.
- Core modules that will remain unchanged.
- Current baseline test count.
- Any dirty worktree files that belong to the user.

Do not create a new plan file or replace this plan during execution.

## 3. Phase 0: Baseline and Safety Gate

### Step 0.1: Confirm repository state

Run:

```bash
git status --short
git log -1 --oneline
git diff --check
```

Required result:

- Record the current commit.
- Preserve unrelated user changes.
- Stop and ask only if an existing change directly overlaps a required edit and cannot be safely incorporated.

### Step 0.2: Confirm baseline tests

Run:

```bash
.venv/bin/python -m pytest --collect-only -q
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q data_agent
```

Required result:

- Baseline should be 183 collected tests at commit `9157146`.
- If the repository has advanced, use the actual current count and record why it differs.
- Any baseline failure must be understood before feature work. Do not hide a baseline failure by weakening a test.

### Step 0.3: Create an isolated verification workspace

Use a temporary workspace such as:

```bash
export NEXT_ITERATION_WS=/tmp/material-agent-next-iteration-ws
rm -rf "$NEXT_ITERATION_WS"
mkdir -p "$NEXT_ITERATION_WS"
```

Use `DATA_AGENT_DEMO_INBOX` or the existing test fixture resolution. Do not delete a user workspace.

Self-check:

- The path is outside the repository.
- No real API key is printed.
- No tracked file was generated by the baseline commands.

## 4. Phase P0-A: Data Input Contract

### Step A1: Add the contract document

Create `docs/data_input_contract.md` with these exact sections:

1. Purpose and scope.
2. General recommendations.
3. Numeric data format.
4. Spectral data format.
5. Image data format.
6. Observation text format.
7. Supported tolerance.
8. Out-of-contract behavior.

Required content:

- One file contains one data type.
- First row is a header.
- CSV is recommended; Excel is optional.
- UTF-8 is recommended.
- `sample_id` is required or strongly recommended; `batch_id` is recommended.
- Units belong in column names such as `thickness_um`, `resistance_ohm_sq`, `wavenumber_cm-1`, and `wavelength_nm`.
- Numeric columns contain numeric values; missing values use blank or `NA`.
- Raw values are not manually rewritten before ingest.
- Facts and interpretations are separated in observation text.
- Chart screenshots retain axes, legends, units, and title.
- Microscope images retain a scale bar where available.
- Multi-panel images require manual review.

Include these examples:

```csv
sample_id,batch_id,position,thickness_um
A01,B01,center,32.1
A01,B01,edge,34.2
```

```csv
wavenumber_cm-1,absorbance,sample_id,batch_id
4000,0.12,A01,B01
3999,0.13,A01,B01
```

Include a Chinese observation example that explicitly labels factual observation and operator hypothesis.

The tolerance section must distinguish:

- The system may attempt Chinese headers, common unit forms, blank/NA/`--`, mixed units, low-confidence image extraction, and interpretation candidates.
- The system will not invent missing sample IDs, unknown units, invisible axes, unreadable scale bars, or labels for mixed unmarked samples.
- Out-of-contract uncertainty should produce a quality flag or manual-review requirement, not a fabricated success.

### Step A2: Add discoverability

Modify:

- `README.md`: add a relative link to `docs/data_input_contract.md` near Quick Start and Local UI documentation.
- `data_agent/ui/app.py`: add an Ingest hint with the short recommendation supplied in the task.
- `data_agent/ui/app.py`: add a Help section summarizing the contract and showing the local documentation path.
- `docs/ui_walkthrough.md`: explain where users read the contract before ingest.

The UI must still work if the Markdown file is missing. Render an embedded short summary; do not read and inject arbitrary Markdown into the app.

### Step A3: Self-check

Run:

```bash
test -f docs/data_input_contract.md
rg -n "Data Input Contract|推荐输入格式|sample_id|wavenumber_cm-1" \
  README.md docs/data_input_contract.md docs/ui_walkthrough.md data_agent/ui/app.py
```

Manual review:

- Confirm a nontechnical reader can identify recommended input and system limits.
- Confirm the contract does not promise automatic repair of every dirty file.
- Confirm ingest behavior was not changed.

Refuse completion if the document is present but not linked, examples are missing, or ingest now rejects files without an approved requirement.

## 5. Phase P0-B: Package Validation Backend

### Step B1: Add validation types and stable result contract

Create `data_agent/validation.py`.

Define module-local Pydantic types; do not modify `schemas.py`:

```python
ValidationStatus = Literal["pass", "warn", "error"]

class ValidationCheck(BaseModel):
    name: str
    status: ValidationStatus
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

class ValidationResult(BaseModel):
    task_id: str
    status: ValidationStatus
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: list[ValidationCheck] = Field(default_factory=list)
    report_path: str = ""
    result_path: str = ""
    validated_at: str
```

Public functions:

```python
def validate_task(
    workspace: Path,
    task_id: str,
    write_report: bool = True,
) -> ValidationResult

def validate_all(
    workspace: Path,
    write_report: bool = True,
) -> list[ValidationResult]
```

Roll-up rule:

- Any error check means result `error`.
- Otherwise any warning check means result `warn`.
- Otherwise result `pass`.

### Step B2: Implement strict package reading

Do not reuse `_read_json_list()` for validation because it hides invalid JSON.

Add private helpers in `validation.py`:

- Strict JSON object reader.
- Strict JSON list reader.
- Safe path resolver that rejects absolute paths and `..` traversal.
- SHA-256 reader equivalent to the existing ingest checksum behavior.
- Check collector that keeps errors/warnings/checks synchronized.

Rules:

- A missing optional list file is allowed only when the corresponding manifest ID list is empty.
- A present but invalid JSON file is always ERROR.
- A present JSON file with the wrong top-level type is ERROR.
- Validation must continue after individual failures to produce a complete report.

### Step B3: Implement structure and manifest checks

Required directories/files:

- task directory.
- `manifest.json`.
- `raw/`, `derived/`, `logs/`, `reviews/`.

Manifest checks:

- Each `input_files` item maps to a file under `raw/`.
- Each `derived_files` path safely resolves under the task directory and exists.
- Each `run_ids` item exists in `processing_runs.json`.
- Each `flag_ids` item exists in `quality_flags.json`.
- Each `review_ids` item exists in `review_records.json`.
- Each `object_ids` item exists in SQLite when registry context is available.
- Empty IDs and duplicate IDs are ERROR.

Do not require every auxiliary derived plot to appear in `manifest.derived_files`; existing processors may only index their primary output there.

### Step B4: Implement run and data-object checks

Processing run checks:

- `run_id` is non-empty and unique.
- `tool_name`, `status`, and `created_at` or `started_at` exist.
- Status is one of the current `ProcessingStatus` values.
- `model:*` runs have `provider`, `model`, and `mode` keys in parameters.
- Missing model keys are ERROR; an empty model name for a local/none provider may be WARN.

Data-object checks use existing read-only DB queries:

- L2 objects have non-empty `derived_from`.
- Known data-schema file keys (`output_file`, `plot_png`, `reconstructed_plot`, `clean_csv`) resolve under `derived/` and exist.
- Model-result objects point to a readable model-result JSON.
- Model-result JSON contains `success`, `role`, `provider`, `mode`, `output_json`, `schema_version`, and `prompt_version`.
- Invalid model-result JSON is ERROR.

If `agent.sqlite` is missing or unreadable:

- File-package checks continue.
- Add one WARN explaining that registry-level checks were skipped.
- Do not mark registry checks PASS.

### Step B5: Implement relationship checks

Build a known-ID set from existing files, data objects, processing runs, flags, and reviews.

Check:

- Relationship IDs are non-empty and unique.
- `source_id` and `target_id` are traceable when registry context exists.
- `derived_from` has a valid source and target.
- `derived_from.metadata.run_id`, when present, references a run.
- `replaces` and `replaced_by` never have the same source and target.
- `new replaces old` has the reciprocal `old replaced_by new` record.
- Both replacement endpoints have the same subtype.
- Multiple L2 objects of one subtype produced by reruns have replacement evidence.
- A model-result derived relationship resolves to the expected `model:*` run through metadata.

Do not infer or create missing relationships.

### Step B6: Implement raw checksum and quality-risk checks

Checksum:

- Query L1 file records that point into the task `raw/` directory.
- Recompute SHA-256 and compare with `checksum_sha256`.
- Mismatch is ERROR.
- Missing registry/checksum evidence is WARN.
- Never compare or modify the original L0 source file.

Quality flags:

- `requires_review=True` produces WARN.
- Message identifiers containing `model_unavailable`, `fallback_used`, or `low_confidence` produce WARN.
- Ordinary informational flags do not automatically make validation WARN.
- Flag messages included in reports pass through the existing model-layer redaction helpers.

### Step B7: Write structured and human reports

When `write_report=True`, atomically write:

- `logs/package_validation_result.json`
- `logs/package_validation_report.md`

Use a temporary sibling file followed by `Path.replace()`.

The Markdown report contains:

- task ID and timestamp.
- overall status.
- errors and warnings.
- a table of every named check.
- a disclaimer that validation checks evidence integrity, not scientific correctness.

If report writing fails:

- Return an ERROR result with check name `report_write_failed`.
- Leave report paths empty if not written.
- Export must treat missing validation artifacts as failure.

Validation must not modify manifest, SQLite, raw, derived, quality flags, relationships, or reviews.

### Step B8: Add CLI

Modify `data_agent/cli.py`:

```bash
python -m data_agent validate --workspace <path> --task <task_id>
python -m data_agent validate --workspace <path> --all
```

Requirements:

- `--task` and `--all` are mutually exclusive.
- Neither selected means usage error.
- Render a concise Rich table.
- Single or aggregate ERROR exits 1.
- PASS and WARN exit 0.
- Do not print traceback or unredacted provider errors.

### Step B9: Add UI backend wrappers and readers

Modify:

- `ui/actions.py`: add `do_validate_package(ws, task_id)` calling only `validate_task()`.
- `ui/readers.py`: add strict/safe `read_validation_result(task_dir)` for existing report JSON.
- `ui/app.py`: add `Validate Package` in Task Detail.

UI displays:

- PASS/WARN/ERROR.
- error and warning lists.
- report path.
- last validation timestamp.

All dynamic text passes through `safe_display_text()` or `safe_ui_error()`.

The persisted validation JSON is truth. Session state may cache only a path or selected view.

### Step B10: Tests

Create `tests/test_validation.py` with focused fixtures and these cases:

1. Normal demo task returns PASS or WARN.
2. Missing manifest returns ERROR.
3. Missing manifest-referenced derived file returns ERROR.
4. Empty run ID returns ERROR.
5. `requires_review=True` returns WARN.
6. Model-result wrapper missing a required field returns ERROR.
7. Self-replacement returns ERROR.
8. Invalid JSON returns ERROR instead of empty-list PASS.
9. Raw checksum mismatch returns ERROR.
10. Missing SQLite returns WARN and still validates package files.
11. `validate_all()` returns every task.
12. CLI all exits 1 when any task is ERROR.
13. Validation leaves manifest, raw bytes, and SQLite checksum unchanged.

### Step B11: Self-check

Run targeted tests first:

```bash
.venv/bin/python -m pytest -q tests/test_validation.py
.venv/bin/python -m data_agent validate --workspace "$NEXT_ITERATION_WS" --all
```

Create damaged copies under `/tmp` and verify each ERROR scenario. Do not damage the canonical workspace.

Refuse completion if invalid JSON is hidden, ERROR exits 0, reports are missing, or validation changes business state.

## 6. Phase P0-E1: HR-facing Overview and Safety Notice

### Step E1.1: Add pure presentation helpers

Create `data_agent/ui/presentation.py`:

```python
def suggested_quality_action(flag: dict[str, Any]) -> str
def format_quality_flag(flag: dict[str, Any]) -> dict[str, Any]
def format_model_output(output_json: dict[str, Any]) -> dict[str, Any]
def cloud_mode_notice(mode: str) -> str
```

Suggested-action precedence:

1. `axis_confirmation_required` → `Confirm axis metadata`.
2. `model_unavailable` or `fallback_used` → `Use local result or retry with configured model`.
3. `low_confidence` → `Mark low confidence or rerun`.
4. Other `requires_review=True` → `Review before approval`.
5. Otherwise → `No action required`.

These are workflow actions, not scientific recommendations.

`format_quality_flag()` must redact the message before returning display data.

### Step E1.2: Extend workspace summary

Extend `read_workspace_summary()` to aggregate from task package files:

- task count.
- processing run count.
- quality flag count.
- review count.
- model-result file count.
- existing status counts.

Do not query or write SQLite from the UI reader. Invalid task JSON should not crash Overview; count it in an `invalid_record_count` warning field.

### Step E1.3: Redesign Overview without marketing-page excess

Keep the application operational and compact.

Overview first screen contains:

- `Material Data Agent`.
- `材料研发数据处理与证据链复核工具`.
- One-sentence purpose.
- Metrics for Tasks, Runs, Flags, Reviews, Model Results.
- Workflow text: `Upload → Ingest → Process → Review → Validate → Export`.
- Six concise capabilities.
- Five-step walkthrough with exact tab names.

Do not add a large landing hero, decorative gradients, nested cards, or irrelevant illustration.

### Step E1.4: Add cloud/auto risk notice

Whenever sidebar mode or Task Detail process mode is `auto` or `cloud`, show:

> cloud/auto 模式可能会把选中的图片或文本发送到你配置的外部模型服务。敏感数据请使用 local 模式，或确认有权限后再使用。

The notice appears before the Process buttons. Local mode does not show the warning.

### Step E1.5: Improve risk and model-result display

- Render quality flags as compact warning/info panels with severity, requires_review, confidence, redacted message, and suggested action.
- Preserve flag IDs for review targeting.
- Render common model-output fields as readable tables/lists: text_blocks, detected_units, axis_candidates, visible_features, factual_observations, interpretation_candidates.
- Preserve Audit, Risk, Extracted Output, Raw Response, full JSON, and non-scientific disclaimers.

### Step E1.6: Minimal Basic/Advanced task view

Use `st.radio(horizontal=True)` for compatibility with the declared Streamlit floor.

Basic is the default and shows:

- Task summary.
- Key derived files.
- Quality-risk panels.
- Review controls.
- Validate and Export controls after Export is implemented.

Advanced shows:

- Raw files.
- Every derived file.
- Processing runs.
- Relationships.
- Raw response.
- Full JSON.

This is display-only. Both modes read the same package data.

### Step E1.7: Tests and self-check

Add `tests/test_ui_presentation.py` covering:

- Every suggested-action mapping.
- Message redaction.
- Model-output field formatting.
- cloud notice empty for local and non-empty for auto/cloud.
- workspace summary aggregation and invalid-record tolerance.

Static check:

```bash
rg -n "Cloud/auto|cloud/auto|Validate Package|Basic|Advanced" data_agent/ui
```

Manual UI gate:

- Start Streamlit against the isolated workspace.
- Confirm first screen explains purpose without code knowledge.
- Confirm auto/cloud warning appears before process.
- Confirm Basic hides raw JSON and Advanced still exposes full evidence.
- Confirm no text overlaps and long IDs/messages wrap safely.

Refuse completion if Advanced loses evidence, Basic still opens with raw JSON noise, or a suggested action becomes scientific advice.

## 7. Phase P1-C: Package Export

### Step C1: Add export result contract

Create `data_agent/export.py` with module-local Pydantic model:

```python
class ExportResult(BaseModel):
    success: bool
    task_id: str
    zip_path: str = ""
    validation_status: Literal["pass", "warn", "error"]
    file_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    message: str

def export_task(
    workspace: Path,
    task_id: str,
    output_path: Path | None = None,
) -> ExportResult
```

Default output:

```text
workspace/exports/<task_id>_export.zip
```

### Step C2: Validate before export

Export flow is fixed:

1. Confirm task directory exists.
2. Call `validate_task(workspace, task_id, write_report=True)`.
3. Require both validation JSON and Markdown artifacts to exist.
4. If validation status is ERROR, continue export but add a prominent warning.
5. Generate a redacted `README_for_review.md` in memory or a temporary directory.
6. Write ZIP to a temporary sibling path.
7. Atomically replace the target ZIP.

Validation ERROR does not mean export failure. It means `success=True`, `validation_status="error"`, and a warning message such as `EXPORTED WITH VALIDATION ERRORS`.

Validation report generation failure means export failure.

### Step C3: ZIP layout and safety

Required archive root:

```text
manifest.json
raw/
derived/
logs/
reviews/
README_for_review.md
package_validation_report.md
```

Rules:

- Include all regular non-hidden files below raw, derived, logs, reviews.
- Validation Markdown appears both under logs and as the root convenience copy.
- Archive names are relative POSIX paths.
- Reject absolute paths, `..`, symlinks, sockets, and output paths inside the task directory.
- Do not include the ZIP itself.
- Replacing a prior export is allowed only through atomic replacement.

### Step C4: README_for_review.md

Include:

- task ID.
- input/raw/derived file lists.
- processing-run summary.
- quality-flag summary.
- review summary.
- validation status and report location.
- `model_result is model-assisted extraction, not a scientific conclusion`.
- `requires_review=True requires human confirmation`.

Do not include raw file content, full model raw responses, secrets, or Authorization values.

### Step C5: Add CLI

```bash
python -m data_agent export \
  --workspace <path> \
  --task <task_id> \
  --output <optional-path>
```

CLI behavior:

- Backend/task/ZIP failure exits 1.
- Successful export exits 0 even when validation is ERROR, but prints an unmistakable warning and validation status.
- Print only the resolved ZIP path, file count, validation status, and redacted message.

### Step C6: Add UI export flow

Modify:

- `ui/actions.py`: `do_export_package(ws, task_id, output_path=None)`.
- `ui/readers.py`: safe helper for an existing export path if needed.
- `ui/app.py`: `Export Review Package` and `st.download_button`.

The UI may cache the export path in session state, but it must verify file existence on every render. The ZIP on disk is truth.

### Step C7: Tests

Create `tests/test_export.py`:

1. Normal task creates readable ZIP.
2. ZIP contains every required root entry.
3. README contains both disclaimers.
4. Missing task returns failure.
5. Missing output directory is created.
6. Validation report is included.
7. Validation ERROR still exports and is marked.
8. Validation-report write failure blocks export.
9. Symlink/path traversal is rejected.
10. Export does not modify manifest, raw bytes, SQLite, or existing L2.
11. CLI exit behavior matches the result contract.

### Step C8: Self-check

Run:

```bash
.venv/bin/python -m pytest -q tests/test_export.py
.venv/bin/python -m data_agent export \
  --workspace "$NEXT_ITERATION_WS" \
  --task task_0001
unzip -l "$NEXT_ITERATION_WS/exports/task_0001_export.zip"
```

Open README and validation report from the ZIP. Scan the ZIP extraction for fake and configured secrets without printing the secret.

Refuse completion if the ZIP omits reports, contains unsafe paths, modifies evidence, or labels validation ERROR as PASS.

## 8. Phase P1-D: Real API Check

### Step D1: Add documentation artifacts

Create:

- `docs/real_api_check_template.md`
- `REAL_API_CHECK.md`

Update:

- `README.md`
- `docs/model_service_layer.md`
- `.env.example` and `model_profiles.yaml.example` only if comments/role guidance are needed; never add a live endpoint or key.

`REAL_API_CHECK.md` begins with `Status: NOT RUN`.

### Step D2: Document safe environment setup

State clearly:

- The application reads environment variables but does not auto-load `.env`.
- `.env` and `model_profiles.yaml` are gitignored.
- Keys must not be command arguments.
- A user may load a local `.env` into the current shell with `set -a; source .env; set +a`.
- `models check` must show only `configured/missing`.

Provider guidance:

- DeepSeek may serve fast/best text roles.
- An OpenAI-compatible multimodal provider may serve vision/ocr.
- Endpoint/model values come from current official provider documentation at execution time; do not hardcode assumptions into tests.

### Step D3: Manual real-call matrix

Use a separate temporary workspace.

Required scenarios:

1. Observation text task with fast/cloud.
2. Chart image with OCR/vision cloud.
3. Visual image with vision/ocr auto fallback.

Record only:

- date.
- provider and model names.
- role.
- result status.
- task ID.
- model-result path.
- processing-run ID.
- quality flags.
- validation status.

Do not record request headers, API key fragments, raw request JSON, or signed URLs.

### Step D4: Key-safety audit

Use an inline Python audit or a temporary script outside the repository that:

- Reads configured key values from environment variables.
- Scans agent.sqlite, derived JSON, logs, Markdown, exported ZIP content, and UI-visible error artifacts.
- Prints only `PASS` or file paths containing a match.
- Never prints the secret value or matching line.

Also preserve automated fake-secret tests and local no-network tests.

### Step D5: Completion behavior

- If no keys are available, complete docs and mock tests, leave `REAL_API_CHECK.md` as NOT RUN, and report the manual gate as pending.
- At least one text real call must succeed for text PASS.
- At least one vision/OCR call must succeed, or a provider failure plus verified auto fallback may be recorded as PARTIAL.
- Any key match is a security failure and blocks completion.

Do not add a new real-api CLI in this iteration. The manual flow is sufficient and keeps the Model Service Layer unchanged.

## 9. Phase P2-F: Minimal Sample Index and Sample View

### Step F1: Add sample-index data contract

Create `data_agent/sample_index.py` with module-local Pydantic models:

```python
class RelatedTask(BaseModel):
    task_id: str
    data_type: str
    source: str
    confidence: float

class SampleEntry(BaseModel):
    sample_id: str
    batch_id: str = ""
    related_tasks: list[RelatedTask] = Field(default_factory=list)
    available_data: list[str] = Field(default_factory=list)

class SampleIndexResult(BaseModel):
    schema_version: str = "sample_index_v1"
    generated_at: str
    samples: list[SampleEntry] = Field(default_factory=list)
    unlinked_tasks: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

def build_sample_index(workspace: Path) -> SampleIndexResult
def load_sample_index(workspace: Path) -> SampleIndexResult | None
```

Output is `workspace/sample_index.json`, written atomically. Do not add a SQLite table.

### Step F2: Implement extraction precedence

Use this exact order:

1. Explicit `sample_id`/`batch_id` from metadata CSV: confidence 1.0.
2. Explicit columns from numeric/spectral CSV: confidence 0.95.
3. `extracted_details.sample_ids` from structured observation JSON: confidence 0.8.
4. Obvious filename IDs: confidence 0.5 candidate only; never auto-link.

CSV behavior:

- Read only target columns.
- Use chunks (`chunksize=5000`) to avoid whole-file loading.
- Treat blank, NA, None, and `nan` as missing.
- Trim surrounding whitespace.
- Preserve case; do not uppercase IDs.

### Step F3: Implement conservative linking

- Stable key is `(sample_id, batch_id)`.
- Explicit identical keys merge related tasks.
- Same sample ID with multiple explicit batch IDs creates separate entries and a warning.
- Observation ID without batch links only when exactly one existing sample entry has that ID.
- Ambiguous/no-ID tasks go to `unlinked_tasks` with reason and candidate IDs.
- Do not create quality flags or relationships for sample-index uncertainty in v1.
- Sort samples and related tasks deterministically before writing.

### Step F4: CLI

```bash
python -m data_agent index-samples --workspace <path>
```

- Missing tasks directory produces an empty index with WARN and exit 0.
- Parse errors are recorded per task in warnings/unlinked_tasks; one bad task does not stop all indexing.
- Output write failure exits 1.
- Print sample and unlinked counts.

### Step F5: UI

Add a `Sample View` tab.

Add wrappers/readers:

- `do_index_samples(ws)` calls `build_sample_index()`.
- `read_sample_index(ws)` calls `load_sample_index()` or returns an empty display state.

Display:

- sample count and unlinked count.
- batch filter.
- sample ID, batch ID, available data.
- related task IDs, data type, source, confidence.
- warnings and unlinked reasons.
- Rebuild button.

The tab never writes SQLite and never creates task relationships.

### Step F6: Tests

Create `tests/test_sample_index.py`:

1. Metadata and spectral tasks with the same ID link.
2. Numeric and observation tasks link conservatively.
3. batch_id is retained.
4. Missing ID goes to unlinked_tasks.
5. Ambiguous batch remains unlinked or separately indexed, never guessed.
6. Filename candidate does not auto-link.
7. Invalid source JSON/CSV is recorded without crashing all indexing.
8. Rebuild output is deterministic.
9. Build does not modify task packages or SQLite.
10. CLI writes `sample_index.json` and reports counts.

### Step F7: Self-check

Run:

```bash
.venv/bin/python -m pytest -q tests/test_sample_index.py
.venv/bin/python -m data_agent index-samples --workspace "$NEXT_ITERATION_WS"
.venv/bin/python -m json.tool "$NEXT_ITERATION_WS/sample_index.json"
```

Manually inspect at least one linked and one unlinked task in Sample View.

Refuse completion if a filename candidate becomes a confirmed association, ambiguous batches merge, or SQLite is changed.

## 10. Documentation and Checkpoint Files

Create or update only after the corresponding behavior passes:

- `README.md`
- `FRONTEND_CHECK.md`
- `docs/ui_walkthrough.md`
- `docs/data_input_contract.md`
- `VALIDATION_CHECK.md`
- `EXPORT_CHECK.md`
- `REAL_API_CHECK.md`
- `docs/real_api_check_template.md`
- `docs/model_service_layer.md`

Checkpoint rules:

- Record date, commit, commands, actual outputs, demo workspace, and known limitations.
- Do not copy historical 112/180/183 counts as current results.
- Preserve historical checkpoints but label them historical.
- Validation and Export reports must not contain scientific claims.
- REAL_API_CHECK remains NOT RUN or PARTIAL unless its manual gate is proven.

## 11. Full Review Plan

### 11.1 Code review checklist

- [ ] SQLite schema unchanged.
- [ ] No migration files.
- [ ] `ingest.py`, `process.py`, `reviews.py` not rewritten.
- [ ] Model router/provider/profile behavior not rewritten.
- [ ] UI calls backend wrappers only.
- [ ] Review still calls `write_review()`.
- [ ] Validation does not mutate business state.
- [ ] Export does not mutate evidence state.
- [ ] Sample index writes only workspace JSON.
- [ ] Raw files unchanged.
- [ ] Old L2 files remain.
- [ ] No generic agent framework or unnecessary dependency.
- [ ] No unrelated refactor.

### 11.2 Automated test checklist

Run targeted tests during each phase, then run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q data_agent
git diff --check
```

Required regressions to remain green:

- local mode makes no network calls.
- exact/fake secrets do not persist.
- model-result wrapper remains complete.
- replacement endpoints have matching subtype.
- self-replacement remains impossible.
- review target behavior remains correct.
- UI display redaction remains correct.

Do not weaken old tests to make new behavior pass.

### 11.3 Manual CLI checklist

Using an isolated workspace:

```text
ingest → process local → review → validate → export → index-samples
```

Verify:

- Every command returns the documented exit code.
- Validation report paths exist.
- Export ZIP opens.
- Sample index parses.
- Rerun still preserves old L2.
- Validation after rerun recognizes replacement relationships.

### 11.4 Manual UI checklist

- [ ] Overview explains product and workflow on first screen.
- [ ] Input Contract is visible before ingest.
- [ ] Task list and selection still work.
- [ ] Basic View is readable without raw JSON.
- [ ] Advanced View preserves complete evidence.
- [ ] Quality-risk panels show redacted messages and workflow actions.
- [ ] auto/cloud notice appears before processing.
- [ ] Validate Package shows the same status as CLI.
- [ ] Export Review Package downloads a valid ZIP.
- [ ] Sample View shows linked and unlinked tasks.
- [ ] Existing review actions still persist through backend logic.
- [ ] No long text overlaps or breaks controls.

### 11.5 Security checklist

- [ ] `.env` and `model_profiles.yaml` remain ignored.
- [ ] No real key appears in git diff or tracked files.
- [ ] No key appears in SQLite, JSON, Markdown, logs, ZIP, or UI.
- [ ] Raw response and quality flags are redacted before display.
- [ ] Export README is redacted.
- [ ] Validation errors are redacted.
- [ ] cloud/auto notice explains external transmission.
- [ ] ZIP paths cannot escape extraction root.
- [ ] Sample index contains IDs only, not raw sensitive contents.

## 12. Implementation Order and Commit Boundaries

Use this order:

### Commit 1: Input contract

- Contract document, README link, Help/Ingest hints, documentation check.

### Commit 2: Validation backend

- Validation module, CLI, reports, tests, VALIDATION_CHECK.

### Commit 3: Validation UI and Overview polish

- UI wrappers/readers, Overview metrics, walkthrough, cloud notice, presentation helpers/tests.

### Commit 4: Export

- Export module, CLI, UI download, tests, EXPORT_CHECK.

### Commit 5: Real API documentation

- Template, NOT RUN report, safe manual commands, docs updates.

### Commit 6: Sample index

- Backend, CLI, Sample View, tests and docs.

Before each commit:

- Run the phase's targeted tests.
- Inspect `git diff --check`.
- Stage only files for that phase.

Do not squash unrelated phases while debugging. A final squash is optional only after all gates pass and the user requests it.

## 13. Final Acceptance Gate

DeepSeek may state `core next iteration complete` only when all required items below are true:

- Data Input Contract exists and is discoverable from README, Help, and Ingest.
- `validate --task` and `validate --all` work with correct exit codes.
- Validation JSON and Markdown reports are generated and accurate.
- Task Detail can validate without direct database writes.
- Export CLI and UI generate a safe ZIP with reports and review README.
- Overview, Basic/Advanced, risk panels, walkthrough, and cloud notice pass manual UI review.
- Sample index and Sample View pass conservative-linking tests.
- Full pytest, compileall, and diff checks pass.
- Existing no-network, key-safety, review, lifecycle, and replacement tests pass.
- Raw hashes and old L2 artifacts remain unchanged.
- README and checkpoint files contain actual current results.
- No secret appears anywhere in tracked or generated evidence.

Real API is a separate manual gate:

- Without user keys, report `Real API check: NOT RUN`; core completion may proceed, but do not claim real cloud verification.
- With user keys, at least one text call must succeed and vision/OCR must succeed or produce a documented PARTIAL with verified auto fallback.
- Any secret leak blocks all completion claims.

P3 remains deferred:

- One-click Demo.
- Deep visual redesign beyond the minimal Basic/Advanced split.
- Rerun diff.
- Batch review.
- Production deployment.

## 14. Mandatory Final Report Format

At the end, report:

1. Implemented modules and exact files.
2. Deferred modules and reason.
3. Public CLI commands added.
4. Validation/export/sample-index artifacts created.
5. Targeted and full test commands with actual results.
6. Manual CLI and UI results.
7. Real API status: PASS, PARTIAL, FAIL, or NOT RUN.
8. Security scan result.
9. Git status and commit list.
10. Known limitations.

Do not end with a vague summary. Every completion claim must point to a command, file, report, test, or manual observation.
