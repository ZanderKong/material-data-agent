# Real API Check Template

## Prerequisites

1. A configured `model_profiles.yaml` with valid provider entries.
2. Environment variables set for each profile's API key (e.g., `BEST_MODEL_API_KEY`, `FAST_MODEL_API_KEY`, `VISION_MODEL_API_KEY`, `OCR_MODEL_API_KEY`).
3. A workspace with ingested and processed demo tasks (see `docs/ui_walkthrough.md`).

## Safe Environment Setup

The application reads environment variables but does **not** auto-load `.env`. You must load them into the current shell.

### macOS / Linux
```bash
set -a; source .env; set +a
```

### Windows (PowerShell)
```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^([^=]+)=(.*)') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }
```

## Key Safety Rules

- Never put a real API key in command arguments.
- `.env` and `model_profiles.yaml` are gitignored — never commit real keys.
- Use `models check` to verify configuration without exposing key values.
- `models check --verbose` shows only `configured/missing`, never the key itself.

## Provider Guidance

- **DeepSeek**: Can serve fast/best text roles. Endpoint typically `https://api.deepseek.com/v1`. Check current official documentation for the latest model names.
- **OpenAI-compatible multimodal**: Can serve vision/ocr roles. Examples: OpenAI GPT-4V, Qwen-VL, Gemini via OpenAI-compatible proxy.
- Always use the most current endpoint and model name from the provider's official documentation.

## Manual Test Scenarios

Run each scenario against a **separate temporary workspace**. Do not use the demo workspace.

### Scenario 1: Observation Text with Fast/Cloud

```bash
# Create a fresh workspace
rm -rf /tmp/real-api-text-ws && mkdir -p /tmp/real-api-text-ws

# Ingest an observation text task
.venv/bin/python -m data_agent ingest \
  --inbox "$DEMO_INBOX" \
  --workspace /tmp/real-api-text-ws

# Process with cloud mode (text only)
.venv/bin/python -m data_agent process \
  --workspace /tmp/real-api-text-ws \
  --task task_0001 \
  --models cloud
```

### Scenario 2: Chart Image with OCR/Vision Cloud

```bash
.venv/bin/python -m data_agent process \
  --workspace /tmp/real-api-text-ws \
  --task task_0002 \
  --models cloud
```

### Scenario 3: Visual Image with Vision/OCR Auto Fallback

```bash
.venv/bin/python -m data_agent process \
  --workspace /tmp/real-api-text-ws \
  --task task_0006 \
  --models auto
```

## Recording Results

For each scenario, record **only** the following:
- Date
- Provider and model names (from `model_profiles.yaml`)
- Role (fast/text/vision/ocr)
- Result status (processing run status)
- Task ID
- Model-result file path
- Processing-run ID
- Quality flags generated
- Validation status

**Do NOT record**: request headers, API key fragments, raw request JSON, signed URLs, or full model responses.

## Key Safety Audit

After running real API tests, run the following inline audit:

```bash
# Inside the project directory, NOT inside a workspace
.venv/bin/python -c "
import os, json, sqlite3, sys
secrets = {v for k in ('BEST_MODEL_API_KEY','FAST_MODEL_API_KEY','VISION_MODEL_API_KEY','OCR_MODEL_API_KEY') if (v:=os.environ.get(k,''))}
matches = []
# Scan workspace files
import pathlib
ws = pathlib.Path('/tmp/real-api-text-ws')
for f in ws.rglob('*'):
    if f.is_file() and f.suffix in ('.json','.md','.txt','.csv'):
        try:
            content = f.read_text()
            for s in secrets:
                if s in content:
                    matches.append(str(f))
                    break
        except: pass
# Scan SQLite
try:
    db = ws / 'agent.sqlite'
    if db.exists():
        conn = sqlite3.connect(str(db))
        for row in conn.execute('SELECT sql FROM sqlite_master').fetchall():
            for s in secrets:
                if row[0] and s in row[0]:
                    matches.append('sqlite_schema')
        conn.close()
except: pass
if matches:
    print('SECURITY FAILURE - key found in:')
    for m in matches: print(f'  {m}')
    sys.exit(1)
else:
    print('PASS - no key found')
"
```
