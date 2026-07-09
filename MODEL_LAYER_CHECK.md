# Model Layer Check

## 当前验收状态

- **日期**：2026-07-09
- **pytest**：112 passed, 0 skipped, 0 failed
- **demo workspace**：`/tmp/material-agent-ws`

## 审计 SQL 验证

```sql
model_objects      | 10
model_runs         | 10
empty_run_ids      | 0
self_replacements  | 0
```

全部达标。

## 无密钥本地验证

```bash
# 1. 清空工作区
rm -rf /tmp/material-agent-ws
mkdir -p /tmp/material-agent-ws

# 2. 确保没有 API key
unset BEST_MODEL_API_KEY FAST_MODEL_API_KEY VISION_MODEL_API_KEY OCR_MODEL_API_KEY
rm -f model_profiles.yaml .env

# 3. ingest
.venv/bin/python -m data_agent ingest \
  --inbox "$DEMO_INBOX" \
  --workspace /tmp/material-agent-ws

# 4. local 模式（零网络调用）
.venv/bin/python -m data_agent process --workspace /tmp/material-agent-ws --all --models local

# 验证：chart image / visual image 生成 stub 模型结果（success=False，语义准确）
ls /tmp/material-agent-ws/tasks/task_0002/derived/*model_result*
ls /tmp/material-agent-ws/tasks/task_0006/derived/*model_result*
```

## 无密钥自动降级验证

```bash
# auto 模式（无 key 自动降级）
.venv/bin/python -m data_agent process --workspace /tmp/material-agent-ws --all --models auto

# 验证：所有模型结果文件存在，无 forbidden 字段
for f in /tmp/material-agent-ws/tasks/*/derived/*model_result*; do
  python3 -c "
import json; d=json.load(open('$f'))
forbidden=['final_conclusion','mechanism_explanation','experiment_recommendation']
found=[k for k in forbidden if k in str(d)]
print(f'$f: ok' if not found else f'$f: FOUND {found}')
"
done

# 验证：API key 未写入证据包
grep -rL "sk-" /tmp/material-agent-ws/tasks/*/derived/*.json | wc -l
grep -rL "sk-" /tmp/material-agent-ws/tasks/*/logs/*.json | wc -l
```

## 有密钥云端验证（可选，模板）

```bash
# 1. 配置（不写入仓库）
cp .env.example .env
# 编辑 .env 填入真实值
cp model_profiles.yaml.example model_profiles.yaml

# 2. 验证配置（不泄露 key 值）
.venv/bin/python -m data_agent models check --workspace /tmp/material-agent-ws --verbose

# 3. 运行 cloud 模式
.venv/bin/python -m data_agent process --workspace /tmp/material-agent-ws --all --models cloud

# 4. 验证输出：model_result JSON 是完整 wrapper 而非仅 output_json
python3 -m json.tool /tmp/material-agent-ws/tasks/task_0002/derived/*model_result_ocr.json | head -30
python3 -m json.tool /tmp/material-agent-ws/tasks/task_0002/derived/*model_result_vision.json | head -30

# 5. 确认质量标记
python3 -m json.tool /tmp/material-agent-ws/tasks/task_0002/logs/quality_flags.json
```

## 证据包路径

每个任务目录下的派生文件：

```
task_XXXX/
├── raw/                          # L1 归档副本
├── derived/                      # L2 派生文件
│   ├── run_<short>__chart_metadata.json
│   ├── run_<short>__model_result_ocr.json
│   ├── run_<short>__model_result_vision.json
│   └── run_<short>__model_result_fast.json
├── logs/
│   ├── processing_runs.json
│   ├── quality_flags.json
│   ├── relationships.json
│   └── processing_report.md
├── reviews/
│   └── review_records.json
└── manifest.json
```

## Model Result JSON 顶层字段

保存的 model result JSON 是完整 `ModelResult` wrapper，包含：

- `success`, `role`, `provider`, `model`, `mode`
- `output_json`（仍包含模型抽取内容）
- `raw_text`, `raw_response`, `raw_response_redacted`
- `confidence`, `warnings`, `error`
- `fallback_used`, `fallback_from`
- `latency_ms`, `token_usage`
- `created_at`, `schema_version`, `prompt_version`

禁止字段（`final_conclusion`、`mechanism_explanation`、`experiment_recommendation`）已递归移除。

## API Key 不持久化确认

- SQLite 所有表：无 API key。
- derived JSON：无 API key。
- logs JSON：无 API key。
- Markdown processing_report.md：无 API key。
- CLI `models check --verbose`：显示 `configured/missing`，不泄露 key 值。
- HTTP error / RequestException message：已 redaction。
