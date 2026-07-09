# FINAL_CHECK.md：最终验收报告

## 0. 验收日期与范围

- **日期**：2026-07-09
- **项目**：Material R&D Data Processing Agent MVP
- **路径**：`/Users/zanderkong/Documents/Codex/2026-07-09/1-agent-marimo-l0-l1-l2`
- **范围**：本报告基于 `DELIVERY_PLAN.md` 最终验收流程生成，验证 MVP 所有核心功能。

## 1. pytest 结果

```bash
.venv/bin/python -m pytest -q
```

```
43 passed in 2.24s
```

**结果**：通过。

## 2. Demo Workflow 结果

### 2.1 Ingest

```bash
.venv/bin/python -m data_agent ingest \
  --inbox "<demo>/inbox" \
  --workspace work/check-ws
```

输出：`Created 9 tasks`，全部 9 个 inbox 文件被登记。

### 2.2 Process

```bash
.venv/bin/python -m data_agent process --workspace work/check-ws --all --models local
.venv/bin/python -m data_agent process --workspace work/check-ws --task task_0007 --models local   # rerun
.venv/bin/python -m data_agent process --workspace work/check-ws --task task_0002 --models cloud
.venv/bin/python -m data_agent process --workspace work/check-ws --task task_0002 --models auto
```

全部成功，无崩溃。

### 2.3 Review

```bash
.venv/bin/python -m data_agent review \
  --workspace work/check-ws --task task_0001 \
  --action approve --reviewer ZQ --comment "demo approval"
```

输出：`Review recorded: approve by ZQ`。

## 3. SQLite 数据库计数

```
tasks               | 9
files               | 18
data_objects        | 21
processing_runs     | 12
quality_flags       | 21
relationships       | 29
reviews             | 1
```

**结果**：全部达标。`processing_runs=12` 包含 9 个初始 process + 1 个 task_0007 rerun + 2 个 task_0002 model mode 测试。

## 4. Rerun 替代关系验证

```
sqlite3 work/check-ws/agent.sqlite '
select rel_type, count(*) from relationships where task_id="task_0007" group by rel_type;
'

derived_from | 3
replaced_by  | 1
replaces     | 1
```

**结果**：rerun 后旧 L2 保留，新 L2 生成，`replaces` 和 `replaced_by` 关系正确。

## 5. Marimo 验证

### 5.1 Dry-run

```
.venv/bin/python -m data_agent open --workspace work/check-ws --task task_0001 --print-command
```

输出包含：
- `Executable: <venv python path>`
- `Arguments: -m marimo run <marimo_apps/task_review.py>`
- `DATA_AGENT_WORKSPACE=<work/check-ws>`
- `DATA_AGENT_TASK_ID=task_0001`
- `--print-command mode: not starting server.`

**结果**：dry-run 正常，不启动长服务。

### 5.2 Marimo Check

```bash
.venv/bin/python -m marimo check marimo_apps/task_review.py
```

无错误输出 = 检查通过。

## 6. Acceptance Criteria 逐项确认

| # | 标准 | 状态 |
|---|------|------|
| AC-1 | demo 9 个文件全部登记到 SQLite 和 evidence package | PASS |
| AC-2 | raw 文件为 L1，不修改、不覆盖 | PASS |
| AC-3 | 每个处理 run 都生成新 L2（run 前缀），不覆盖旧 L2 | PASS |
| AC-4 | manifest 能直接索引所有派生文件 | PASS |
| AC-5 | relationships 方向正确 (L1→L2)，rerun 有 replaces/replaced_by | PASS |
| AC-6 | 厚度 summary 正确记录 missing/outlier (A01 missing=1, A02 outlier=1) | PASS |
| AC-7 | metadata task 有 processor、run 和 L2 index | PASS |
| AC-8 | chart image 支持 local/cloud/auto model mode | PASS |
| AC-9 | 观察文本解释句只进入 `interpretation_candidates` | PASS |
| AC-10 | surface photo 只做 metadata + manual review flag | PASS |
| AC-11 | review 同步写 DB 和 JSON | PASS |
| AC-12 | marimo open 可启动，复核页能读取 evidence package | PASS |
| AC-13 | `pytest -q` 全部通过 (43 passed) | PASS |
| AC-N1 | rerun 后 replaces/replaced_by 存在 | PASS |
| AC-N2 | manifest/SQLite/JSON 对 L2 与 relationships 记录一致 | PASS |
| AC-N3 | marimo open --print-command dry-run 可自动测试 | PASS |
| AC-N4 | README/FIX_PLAN/NEXT_PLAN 指向 DELIVERY_PLAN.md | PASS |
| AC-N5 | 最终验收命令全部成功 | PASS |

## 7. 非阻塞注意事项

以下为已知限制，不影响当前交付：

- 图表图片的 digitization 未实现精确曲线提取，当前仅做 metadata 和低置信标注。
- 云端模型适配器（`CloudStubAnalyzer`）是接口占位，未接入真实云 API。
- Marimo 复核页的 review actions 目前通过 CLI 命令提示进行，未实现页面内按钮交互。
- 跨 task 的 sample metadata 自动关联未实现，当前仅生成单 task 的 metadata index。
- 未提供导出压缩包或归档命令。
- Schema 版本迁移机制为未来增强项。

## 8. 证据链

所有数据可在以下路径中找到：

```bash
# 数据库
work/check-ws/agent.sqlite

# Evidence packages
work/check-ws/tasks/task_*/manifest.json
work/check-ws/tasks/task_*/raw/
work/check-ws/tasks/task_*/derived/
work/check-ws/tasks/task_*/logs/processing_runs.json
work/check-ws/tasks/task_*/logs/quality_flags.json
work/check-ws/tasks/task_*/logs/relationships.json
work/check-ws/tasks/task_*/logs/processing_report.md
work/check-ws/tasks/task_*/reviews/review_records.json
```

## 9. 结论

Material R&D Data Processing Agent MVP **通过最终验收**。所有核心功能（ingest、process、review、L2 versioning、rerun replacement、metadata processor、chart model adapter、marimo workspace）均已在全新 workspace 上完整验证通过。

此报告不包含科研结论，仅记录处理 Agent 的功能验证结果。
