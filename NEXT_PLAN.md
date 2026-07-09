# NEXT_PLAN.md：当前验收后的下一步收口计划

> **状态说明**：此文件中的核心剩余项（rerun 替代关系、一致性测试、marimo smoke check、文档更新）均已完成。当前最终交付以 `DELIVERY_PLAN.md` 为准。此文件保留用于审计上下文。

## 0. 当前状态摘要

本文件基于当前工作区的实际验收结果生成，用于接替 `FIX_PLAN.md` 作为下一轮执行计划。

已验证通过：

- `.venv/bin/python -m pytest -q` 通过，当前结果为 `37 passed`。
- 使用全新 `work/check-ws` 跑通 demo：
  - `ingest` 创建 9 个 task。
  - `process --all --models local` 处理 9 个 task。
  - `review approve` 能写入 review。
  - SQLite 当前最低计数达标：`tasks=9`, `files=18`, `data_objects=18`, `processing_runs=9`, `quality_flags=13`, `relationships=18`, `reviews=1`。
- 当前代码已经具备：
  - SQLite ingest 注册链路。
  - run 前缀 L2 输出文件。
  - `manifest.derived_files`。
  - metadata processor。
  - chart `local/cloud/auto` adapter wiring。
  - timezone-aware UTC timestamps。
  - `.gitignore` 与 README venv 命令。
  - `cli.open` 使用 `sys.executable -m marimo`。

仍需收口：

- rerun 替代关系未完成。对 `task_0007` 连续 process 后，SQLite relationships 只有 `derived_from`，没有 `replaces/replaced_by`。
- marimo open 已能进入服务启动流程，但缺少自动化 smoke test，当前只能证明不再立即报 `marimo` 找不到或 `mo.status.get_env` 错误。
- `FIX_PLAN.md` 仍包含大量已完成项；后续执行应以本文件为主。

## 1. 目标

完成 MVP 验收剩余收口：确保重跑生成明确替代关系，补充对应测试，并让 marimo 启动具备可重复验证的 smoke check。

## 2. 实施步骤

### N-1. 修复 rerun 替代关系

涉及文件：`data_agent/process.py`, `data_agent/db.py`, `tests/test_demo_pipeline.py`

要做：

- 在每次 process 前查询当前 task 已有 L2 data objects。
- 新 L2 生成后，按同一 task + 同一 subtype 或同一 `data_schema.output_file` 语义匹配旧 L2。
- 对每个被替代的旧 L2 写两条关系：
  - `replaces`: `source_id = new_l2_object_id`, `target_id = old_l2_object_id`
  - `replaced_by`: `source_id = old_l2_object_id`, `target_id = new_l2_object_id`
- 同步写 SQLite `relationships` 和 evidence package `logs/relationships.json`。
- 不把旧 L2 文件删除，不覆盖旧 L2 文件。
- 默认不把旧 L2 lifecycle 改为 L3；仅通过 relationship 表示替代。

验证：

```bash
rm -rf work/check-ws
.venv/bin/python -m data_agent ingest --inbox "/Users/zanderkong/Desktop/数据处理agent/material_data_agent_demo 测试数据/inbox" --workspace work/check-ws
.venv/bin/python -m data_agent process --workspace work/check-ws --task task_0007 --models local
.venv/bin/python -m data_agent process --workspace work/check-ws --task task_0007 --models local
sqlite3 work/check-ws/agent.sqlite 'select rel_type, count(*) from relationships where task_id="task_0007" group by rel_type;'
find work/check-ws/tasks/task_0007/derived -type f | sort
```

预期：

- `derived/` 下有两组不同 run 前缀的 thickness 输出。
- relationships 中存在 `derived_from`、`replaces`、`replaced_by`。

新增测试：

- 对 `task_0007` process 两次后断言 `replaces` 和 `replaced_by` 都存在。
- 断言旧 L2 文件仍存在。

### N-2. 补强 manifest 与 relationship 一致性测试

涉及文件：`tests/test_demo_pipeline.py`, `tests/test_db_package.py`

要做：

- 新增测试：manifest 中每个 `derived_files` 路径都真实存在。
- 新增测试：DB 中每个 `processing_runs.output_data_ids` 至少能在 `data_objects` 表查到。
- 新增测试：每个 L2 object 至少有一条 `derived_from` relationship。
- 新增测试：evidence package `logs/relationships.json` 与 SQLite relationship 数量一致或至少不缺少 DB 中同 task 的关系。

验证：

```bash
.venv/bin/python -m pytest -q
```

预期：

- 所有新增测试通过。

### N-3. 增加 marimo open smoke check

涉及文件：`data_agent/cli.py`, `tests/test_demo_pipeline.py` 或新增 `tests/test_marimo_open.py`

要做：

- 给 `data_agent open` 增加一个非启动服务的 dry-run/print 模式，例如：

```bash
.venv/bin/python -m data_agent open --workspace work/check-ws --task task_0001 --print-command
```

- `--print-command` 只打印将要执行的命令和环境变量，不启动 marimo 服务。
- 保持默认 `open` 行为仍启动 marimo。
- 测试 `--print-command` 输出必须包含：
  - 当前 Python 可执行文件。
  - `-m marimo run`。
  - `DATA_AGENT_WORKSPACE`。
  - `DATA_AGENT_TASK_ID`。
- 保留 `.venv/bin/python -m marimo check marimo_apps/task_review.py` 作为静态校验。

验证：

```bash
.venv/bin/python -m data_agent open --workspace work/check-ws --task task_0001 --print-command
.venv/bin/python -m marimo check marimo_apps/task_review.py
.venv/bin/python -m pytest -q
```

预期：

- dry-run 不启动长时间服务。
- 静态 marimo check 通过。
- 测试可自动覆盖 open 命令。

### N-4. 更新文档，标明当前验收入口

涉及文件：`README.md`, `FIX_PLAN.md`

要做：

- README 增加“当前验收状态”小节，说明：
  - 基础 demo 闭环已通过。
  - 下一步执行以 `NEXT_PLAN.md` 为准。
- 在 `FIX_PLAN.md` 顶部增加一句说明：该文件是上一轮完整修复计划，当前剩余项以 `NEXT_PLAN.md` 为准。
- 不删除 `FIX_PLAN.md`，保留审计上下文。

验证：

```bash
sed -n '1,40p' README.md
sed -n '1,20p' FIX_PLAN.md
```

预期：

- 两处都能看到 `NEXT_PLAN.md` 引用。

## 3. 最终验收命令

```bash
rm -rf work/check-ws

.venv/bin/python -m pytest -q

.venv/bin/python -m data_agent ingest \
  --inbox "/Users/zanderkong/Desktop/数据处理agent/material_data_agent_demo 测试数据/inbox" \
  --workspace work/check-ws

.venv/bin/python -m data_agent process \
  --workspace work/check-ws \
  --all \
  --models local

.venv/bin/python -m data_agent process \
  --workspace work/check-ws \
  --task task_0007 \
  --models local

.venv/bin/python -m data_agent process \
  --workspace work/check-ws \
  --task task_0002 \
  --models cloud

.venv/bin/python -m data_agent process \
  --workspace work/check-ws \
  --task task_0002 \
  --models auto

.venv/bin/python -m data_agent review \
  --workspace work/check-ws \
  --task task_0001 \
  --action approve \
  --reviewer ZQ \
  --comment "demo approval"

.venv/bin/python -m data_agent info --workspace work/check-ws

sqlite3 work/check-ws/agent.sqlite '
select "tasks", count(*) from tasks
union all select "files", count(*) from files
union all select "data_objects", count(*) from data_objects
union all select "processing_runs", count(*) from processing_runs
union all select "quality_flags", count(*) from quality_flags
union all select "relationships", count(*) from relationships
union all select "reviews", count(*) from reviews;
'

sqlite3 work/check-ws/agent.sqlite '
select rel_type, count(*) from relationships where task_id="task_0007" group by rel_type;
'

.venv/bin/python -m data_agent open --workspace work/check-ws --task task_0001 --print-command
.venv/bin/python -m marimo check marimo_apps/task_review.py
```

## 4. Acceptance Criteria

- AC-N1：同一 task 重跑后，旧 L2 保留，新 L2 生成，且存在 `replaces/replaced_by` relationships。
- AC-N2：manifest、SQLite、evidence package 三处对 L2 与 relationships 的记录一致。
- AC-N3：marimo open 有可自动测试的 dry-run/print-command 模式。
- AC-N4：README 与 `FIX_PLAN.md` 明确指向 `NEXT_PLAN.md` 作为当前下一步计划。
- AC-N5：`pytest -q` 通过，最终验收命令全部成功。
