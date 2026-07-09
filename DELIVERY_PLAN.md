# DELIVERY_PLAN.md：材料研发数据处理 Agent MVP 最终交付计划

## 0. 当前验收状态

本文件基于当前工作区最新检查结果生成，用于接替已经过时的 `NEXT_PLAN.md`。

当前已验证通过：

- `.venv/bin/python -m pytest -q`：`43 passed`。
- 全新 `work/check-ws` demo 闭环通过：
  - `ingest` 创建 9 个 task。
  - `process --all --models local` 处理 9 个 task。
  - `review approve` 写入 review。
  - `info` 可展示任务状态。
  - `marimo check` 通过。
- SQLite 计数达标：
  - `tasks=9`
  - `files=18`
  - `data_objects=18`
  - `processing_runs=9`
  - `quality_flags=13`
  - `relationships=18`
  - `reviews=1`
- 已验证 rerun 替代关系：
  - 对 `task_0007` 再次 process 后，存在 `derived_from=3`, `replaces=1`, `replaced_by=1`。
  - 旧 L2 文件保留，新 L2 文件生成，文件名带不同 run 前缀。
- 已验证 marimo dry-run：
  - `data_agent open --print-command` 能输出 `python -m marimo run ...` 与 `DATA_AGENT_WORKSPACE`、`DATA_AGENT_TASK_ID`，且不启动长服务。

## 1. 目标

把当前 MVP 从“功能验收通过”整理为“可交付、可复查、可交给后续 Agent 使用”的稳定成果包。

不再扩展新功能；本阶段只做交付收口、文档同步、最终验收记录和非阻塞风险标注。

## 2. 实施步骤

### D-1. 更新计划文件状态

涉及文件：`README.md`, `NEXT_PLAN.md`, `FIX_PLAN.md`

要做：

- 在 `NEXT_PLAN.md` 顶部增加状态说明：该计划中的核心剩余项已经完成，当前交付以 `DELIVERY_PLAN.md` 为准。
- 在 `README.md` 的“当前验收状态”中把“下一步执行以 `NEXT_PLAN.md` 为准”改为“最终交付以 `DELIVERY_PLAN.md` 为准”。
- 保留 `PLAN.md`、`FIX_PLAN.md`、`NEXT_PLAN.md`，不要删除；它们是审计轨迹。

验证：

```bash
sed -n '1,35p' README.md
sed -n '1,25p' NEXT_PLAN.md
sed -n '1,10p' FIX_PLAN.md
```

预期：

- README 和 NEXT_PLAN 都明确指向 `DELIVERY_PLAN.md`。

### D-2. 生成最终验收报告

新增文件：`FINAL_CHECK.md`

要做：

- 记录最新验收命令和结果：
  - `pytest` 结果。
  - demo workflow 结果。
  - SQLite counts。
  - rerun relationship counts。
  - marimo dry-run 输出摘要。
- 明确列出通过的 acceptance criteria：
  - SQLite 注册链路。
  - evidence package。
  - L2 versioning。
  - rerun relationships。
  - metadata processor。
  - chart model modes。
  - observation text interpretation isolation。
  - visual image manual review flag。
  - review record。
  - marimo dry-run/check。
- 单独列出非阻塞注意事项。

验证：

```bash
sed -n '1,220p' FINAL_CHECK.md
```

预期：

- 报告能独立说明当前 MVP 是否通过验收，以及证据来自哪些命令。

### D-3. 做一次最终干净验收

涉及文件：不改代码，只运行命令。

执行：

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

.venv/bin/python -m data_agent open \
  --workspace work/check-ws \
  --task task_0001 \
  --print-command

.venv/bin/python -m marimo check marimo_apps/task_review.py
```

预期：

- `pytest` 全部通过。
- SQLite 基础计数不低于：
  - `tasks=9`
  - `files>=18`
  - `data_objects>=18`
  - `processing_runs>=12`，因为最终验收包含 rerun、cloud、auto 额外 process。
  - `quality_flags>=13`
  - `relationships>=20`
  - `reviews>=1`
- `task_0007` 存在 `replaces` 和 `replaced_by`。
- marimo dry-run 不启动服务且不报错。

### D-4. 清理交付边界

涉及文件：`.gitignore`, `work/`, `workspace/`, `.pytest_cache/`, `.venv/`

要做：

- 确认 `.gitignore` 已排除：
  - `.venv/`
  - `__pycache__/`
  - `.pytest_cache/`
  - `workspace/`
  - `work/check-ws/`
  - `*.sqlite`
- 不删除本地 `.venv`，但不要把它作为源码交付内容。
- 不把 `work/check-ws` 或 `workspace` 作为最终源码的一部分。

验证：

```bash
cat .gitignore
find . -maxdepth 2 -type f | sort
```

预期：

- 源码层主要交付为 `data_agent/`, `marimo_apps/`, `tests/`, `README.md`, `PLAN.md`, `FIX_PLAN.md`, `NEXT_PLAN.md`, `DELIVERY_PLAN.md`, `FINAL_CHECK.md`, `pyproject.toml`。

## 3. 最终 Acceptance Criteria

- AC-D1：README、NEXT_PLAN、FIX_PLAN 的状态说明不互相矛盾。
- AC-D2：存在 `FINAL_CHECK.md`，且记录最终验收命令、结果和通过项。
- AC-D3：最终干净验收命令全部成功。
- AC-D4：运行产物和虚拟环境不被当作源码交付。
- AC-D5：项目交付边界清晰，后续 Agent 能从 `DELIVERY_PLAN.md` 与 `FINAL_CHECK.md` 理解当前状态。

## 4. 非阻塞后续增强

这些不属于当前交付阻塞项：

- 增加真实 OCR / 云端多模态 provider。
- 给 marimo 页面增加真实按钮，而不仅是 CLI action 提示。
- 增加 Streamlit 或 Taipy 任务看板。
- 增加跨 task sample metadata 自动关联。
- 增加导出压缩包或归档命令。
- 增加更严格的 package schema 版本迁移机制。
