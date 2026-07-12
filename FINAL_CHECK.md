# FINAL_CHECK.md：最终验收报告

## 0. 验收日期与范围

- **日期**：2026-07-09
- **项目**：Material R&D Data Processing Agent MVP
- **路径**：`<repository root>`（公开发布前已脱敏本机历史路径）
- **范围**：本报告基于 `DEEPSEEK_NEXT_PLAN.md` 模型服务层审计闭环 + `CURRENT_PROGRESS_AND_NEXT_PLAN.md` 下一步计划执行验收。

## 1. pytest 结果

```bash
.venv/bin/python -m pytest -q
```

```
112 passed in 3.02s
```

**结果**：全部通过。0 skipped, 0 failed。

## 2. Demo Workflow 结果

### 2.1 Ingest

```bash
.venv/bin/python -m data_agent ingest --inbox "$DEMO_INBOX" --workspace /tmp/material-agent-ws
```

输出：`Created 9 tasks`，全部 9 个 inbox 文件被登记。

### 2.2 Process (local + auto)

```bash
.venv/bin/python -m data_agent process --workspace /tmp/material-agent-ws --all --models local
.venv/bin/python -m data_agent process --workspace /tmp/material-agent-ws --all --models auto
```

全部成功，无崩溃。

### 2.3 Models Check

```bash
.venv/bin/python -m data_agent models check --workspace /tmp/material-agent-ws --verbose
```

所有 4 个 profile 正常显示（无真实 key 配置时显示 `missing`，无密钥泄露）。

## 3. 模型服务层审计验收

```
model_objects | 10
model_runs    | 10
empty_run_ids | 0
self_replacements | 0
```

| 审计项 | 状态 |
|--------|------|
| model_objects == model_runs | PASS |
| empty_run_ids == 0 | PASS |
| self_replacements == 0 | PASS |
| manifest run_ids 无空字符串 | PASS |
| model_result JSON 保存完整 wrapper 字段 | PASS |
| model_result derived_from 指向 model:* run | PASS |
| replacement 两端 subtype 一致 | PASS |
| legacy adapters 可 import | PASS |
| local 模式零网络调用测试 | PASS |
| API key 不出现在 SQLite/JSON/MD/logs | PASS |
| HTTP error / RequestException 消息已 redaction | PASS |
| OCR stub success=False | PASS |
| Vision stub success=False | PASS |
| forbidden keys 不出现在任何深度 | PASS |

## 4. SQLite 数据库计数

```
tasks               | 9
files               | 18
data_objects        | 含 10 model_result
processing_runs     | 含 10 model:*
quality_flags       | 含 model fallback/unavailable 标记
relationships       | 所有 derived_from 方向正确
```

## 5. Rerun 替代关系验证

- `replaces` / `replaced_by` 方向正确。
- 同一个 object 不会替代自己（self_replacements == 0）。
- replacement 两端 subtype 一致。
- 旧 L2 文件保留，不覆盖。

## 6. Marimo 验证

```bash
.venv/bin/python -m data_agent open --workspace work/check-ws --task task_0001 --print-command
```

输出包含 `--print-command mode`、`Executable:`、`DATA_AGENT_WORKSPACE`。dry-run 正常。

## 7. Acceptance Criteria 逐项确认

| # | 标准 | 状态 |
|---|------|------|
| AC-1 | demo 9 个文件全部登记到 SQLite 和 evidence package | PASS |
| AC-2 | raw 文件为 L1，不修改、不覆盖 | PASS |
| AC-3 | 每个处理 run 都生成新 L2，不覆盖旧 L2 | PASS |
| AC-4 | manifest 能直接索引所有派生文件 | PASS |
| AC-5 | relationships 方向正确，rerun 有 replaces/replaced_by | PASS |
| AC-6 | 厚度 summary 正确记录 missing/outlier | PASS |
| AC-7 | metadata task 有 processor、run 和 L2 index | PASS |
| AC-8 | chart image 支持 local/cloud/auto model mode | PASS |
| AC-9 | 观察文本解释句只进入 interpretation_candidates | PASS |
| AC-10 | surface photo 只做 metadata + manual review flag | PASS |
| AC-11 | review 同步写 DB 和 JSON | PASS |
| AC-12 | marimo open 可启动，复核页能读取 evidence package | PASS |
| AC-13 | `pytest -q` 全部通过 (112 passed) | PASS |
| M-1 | model run id 非空 | PASS |
| M-2 | model_objects == model_runs | PASS |
| M-3 | manifest 不含空 run id | PASS |
| M-4 | model result JSON 完整 wrapper | PASS |
| M-5 | local 模式零网络调用 | PASS |
| M-6 | exact API key 不出现在持久化中 | PASS |
| M-7 | replacement 两端 subtype 一致 | PASS |
| M-8 | model result derived_from 指向 model:* run | PASS |

## 8. 测试覆盖变更

本轮测试从 `43 passed` 提升为 `112 passed, 0 skipped, 0 failed`：

- 修复了测试硬编码 demo 路径的问题：通过 `DATA_AGENT_DEMO_INBOX` 环境变量 + 多层回退路径。
- 新增 `tests/conftest.py` 提供共享 `demo_inbox` fixture。
- 所有集成测试（demo_pipeline、model_evidence）现均可实际执行。

## 9. 结论

Material R&D Data Processing Agent MVP **通过最终验收**。所有核心功能（ingest、process、review、L2 versioning、rerun replacement、metadata processor、model service layer 审计闭环）均已完整验证通过。

此报告不包含科研结论，仅记录处理 Agent 的功能验证结果。
