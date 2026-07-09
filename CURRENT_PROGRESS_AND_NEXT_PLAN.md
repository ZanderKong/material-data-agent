# 当前项目进度与下一步计划

## 1. 当前进度

检查日期：2026-07-09

当前项目已从基础 MVP 进入"模型服务层审计收口"阶段并完成第二轮修复。

### 已完成

- **pytest**：`112 passed, 0 skipped, 0 failed`
- **demo 验证**：`ingest -> process local -> process auto -> models check` 全链路通过。
- **审计 SQL**：
  - `model_objects = 10, model_runs = 10`
  - `empty_run_ids = 0`
  - `self_replacements = 0`
- **model result JSON**：保存完整 wrapper 字段，递归 sanitize + redaction。
- **model result derived_from**：指向对应 `model:*` run。
- **replacement**：按 subtype 匹配，不产生自替代。
- **legacy adapters**：可 import，不依赖缺失的 `ChartImageAnalyzer`。
- **stub 审计语义**：`local_ocr_stub`/`local_vision_stub` 返回 `success=False`。
- **profile 缓存**：已移除，每次加载。
- **`.gitignore`**：忽略 `work/`。
- **HTTP error / RequestException**：已 redaction。
- **测试 fixture**：使用 `DATA_AGENT_DEMO_INBOX` 环境变量 + 多层回退路径，不再硬编码个人路径。

### 测试覆盖提升

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| pytest | 43 passed, many skipped | 112 passed, 0 skipped, 0 failed |
| classify tests | 全部 skip | 全部 pass |
| demo_pipeline tests | 全部 skip | 全部 pass |
| model_evidence tests | 全部 skip | 全部 pass |
| exact secret leak tests | 未覆盖 | 4 个新测试 |

## 2. 验收命令

```bash
# 快速验收
.venv/bin/python -m pytest -q

# 审计 SQL
sqlite3 /tmp/material-agent-ws/agent.sqlite '
select "model_objects", count(*) from data_objects where data_type="model_result";
select "model_runs", count(*) from processing_runs where tool_name like "model:%";
select "empty_run_ids", count(*) from processing_runs where run_id="";
select "self_replacements", count(*) from relationships where rel_type in ("replaces","replaced_by") and source_id = target_id;
'
```

通过标准：
- `model_objects == model_runs`
- `empty_run_ids == 0`
- `self_replacements == 0`
- `pytest -q` 112 passed, 0 failed

## 3. 完成后的事项

- `FINAL_CHECK.md` 已更新为当前验收结果。
- `MODEL_LAYER_CHECK.md` 已更新。
- 所有测试 fixture 现在通过 `tests/conftest.py` 中的 `demo_inbox` fixture 统一解析。
