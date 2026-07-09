# FIX_PLAN.md：材料研发数据处理 Agent MVP 验收修复计划

> **注意**：此文件是上一轮完整修复计划，大部分项已完成。当前交付以 `DELIVERY_PLAN.md` 为准。此文件保留用于审计上下文，请勿删除。

## 0. 执行要求

先在 OpenCode Plan Mode 阅读本计划、`PLAN.md`、现有代码和 demo 数据。确认理解后再进入 build 模式。严格修复验收问题，不新增 ELN、多用户、报告 Agent、科研结论生成等功能。

项目目录：`/Users/zanderkong/Documents/Codex/2026-07-09/1-agent-marimo-l0-l1-l2`

demo 目录：`/Users/zanderkong/Desktop/数据处理agent/material_data_agent_demo 测试数据`

验收必须使用全新 workspace，例如 `work/check-ws`，不要复用已有 `workspace/`。

## 1. 目标

把当前“demo 可跑原型”修成满足 MVP 计划的可审计数据处理 Agent：

- SQLite 真实记录 task、file、data object、processing run、quality flag、relationship、review。
- evidence package 的 `manifest.json` 能直接索引 raw、derived、run、flag、review。
- 重跑不覆盖旧 L2，能记录替代关系。
- demo 数据的厚度、电阻、谱图、图表、文本、图片处理结果正确。
- marimo 单任务复核页能由 CLI 启动并读取 evidence package。

## 2. 修复优先级

P0 必须完成，否则不算通过：

- SQLite ingest 注册链路
- L2 版本化输出与不覆盖
- manifest `derived_files`
- marimo open 可启动

P1 必须完成后才能交付给用户试用：

- 厚度 summary 统计修正
- metadata processor
- relationships 方向和 rerun 替代关系
- chart model adapter wiring

P2 可作为质量补强：

- README 环境说明
- timezone-aware datetime
- `.gitignore`
- 更完整测试断言

## 3. 实施步骤

### F-0. 建立干净验收基线

涉及文件：不改业务文件，只运行验证。

操作：

- 创建虚拟环境并安装依赖：

```bash
python3.10 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

- 如果本机没有 `python3.10`，使用任意 Python 3.10+。
- 跑现有测试：

```bash
.venv/bin/python -m pytest -q
```

- 创建全新验收 workspace：

```bash
rm -rf work/check-ws
```

验证：

- 记录当前测试结果。
- 不要修改已有 `workspace/` 作为验收依据。

Review 重点：

- 执行者是否用了干净 `work/check-ws`。
- 是否错误依赖已有产物。

---

### F-1. 修复 ingest 到 SQLite 的注册链路

涉及文件：`data_agent/ingest.py`, `data_agent/cli.py`, `data_agent/db.py`

要做：

- `ingest_inbox()` 改为接收 `workspace` 或 `conn`，不能只接收 `tasks_dir`。
- 每个文件 ingest 时写入：
  - `tasks` 表：`task_id`, `manifest_json`
  - `files` 表：L1 raw 副本记录，包含 checksum、size、stored_path、lifecycle=L1
  - `data_objects` 表：L1 data object，包含 type、subtype、confidence、file_ids、schema
- 如果保留 L0 概念，至少在 task/manifest/relationship 中记录 L0 -> L1 transition；不要创建未落库的孤儿 `FileRecord`。
- `DataObject.file_ids` 必须引用已写入 DB 的 L1 file id。
- `sample_metadata.csv` 也必须写入 DB data_objects。

不要做：

- 不要移动或修改 demo 源文件。
- 不要只写 JSON，不写 DB。

验证：

```bash
.venv/bin/python -m data_agent ingest \
  --inbox "/Users/zanderkong/Desktop/数据处理agent/material_data_agent_demo 测试数据/inbox" \
  --workspace work/check-ws

sqlite3 work/check-ws/agent.sqlite '
select "tasks", count(*) from tasks
union all select "files", count(*) from files
union all select "data_objects", count(*) from data_objects;
'
```

预期：

- `tasks = 9`
- `files >= 9`
- `data_objects >= 9`

新增测试：

- demo ingest 后断言 DB 中 tasks/files/data_objects 数量达标。
- 断言 `sample_metadata.csv` 存在 L1 data object。

---

### F-2. 建立统一 RunContext 和 L2 版本化输出

涉及文件：`data_agent/process.py`, `data_agent/processors/*.py`, `data_agent/schemas.py`

要做：

- process 每次运行先生成唯一 `run_id`。
- 将 `run_id` 或 `RunContext` 传入 processor。
- 所有派生文件名必须带 run 前缀：
  - `run_<short>__thickness_summary.csv`
  - `run_<short>__resistance_plot.png`
  - `run_<short>__ftir_peak_table.csv`
  - `run_<short>__chart_metadata.json`
- processor 不得写固定文件名覆盖旧结果。
- `ProcessingRun.output_data_ids` 必须对应新 L2 object ids。

不要做：

- 不要删除旧 `derived/` 文件。
- 不要为了简单直接清空 task 目录。

验证：

```bash
.venv/bin/python -m data_agent process --workspace work/check-ws --task task_0007 --models local
.venv/bin/python -m data_agent process --workspace work/check-ws --task task_0007 --models local
find work/check-ws/tasks/task_0007/derived -type f | sort
```

预期：

- 同类输出出现两个不同 run 前缀版本。
- 旧文件仍存在。

新增测试：

- 对同一 task process 两次，断言 derived 文件数量增加且文件名不同。

---

### F-3. 修复 manifest 派生索引

涉及文件：`data_agent/process.py`, `data_agent/package.py`

要做：

- 每个 L2 输出文件都写入 `manifest.derived_files`。
- 保存相对 task 的路径，例如：
  - `derived/run_ab12cd34__thickness_summary.csv`
- manifest 同步维护：
  - `object_ids`
  - `run_ids`
  - `flag_ids`
  - `review_ids`
  - `derived_files`
- metadata task 如果生成 metadata index，也应有 derived file。

验证：

```bash
python - <<'PY'
import json, glob
for p in sorted(glob.glob("work/check-ws/tasks/task_*/manifest.json")):
    d=json.load(open(p))
    print(p, d.get("derived_files"))
PY
```

预期：

- 除纯失败 task 外，已处理 task 的 `derived_files` 非空。
- 文件路径真实存在。

新增测试：

- process demo 后，逐个 manifest 检查 `derived_files` 指向存在的文件。

---

### F-4. 修复 relationships 方向与 rerun 替代关系

涉及文件：`data_agent/process.py`, `data_agent/reviews.py`, `data_agent/db.py`

要做：

- `derived_from` 方向固定为：
  - `source_id = L1/raw data object`
  - `target_id = L2/derived data object`
- 当前反向写法必须修正。
- 同一 task 同一 subtype 再次 process 时：
  - 新 L2 写 `replaces -> old L2`
  - 旧 L2 写 `replaced_by -> new L2`
- `review --action return_for_rerun` 先写 review record 和 manifest 状态。
- 下一次 process 检测到已有旧 L2 后生成替代关系。
- 默认不把旧 L2 改成 L3，只通过 relationship 表明被替代。

验证：

```bash
sqlite3 work/check-ws/agent.sqlite '
select rel_type, source_id, target_id from relationships order by created_at;
'
```

新增测试：

- `derived_from` 方向是 L1 -> L2。
- rerun 后存在 `replaces` 和 `replaced_by`。

Review 重点：

- 不要只在 JSON 写 relationship，DB 也必须写。
- 不要覆盖旧 L2 来模拟替代。

---

### F-5. 修复厚度 summary 统计

涉及文件：`data_agent/processors/numeric.py`

要做：

- 在原始 df 上按 `sample_id,batch_id` 计算：
  - `raw_count`
  - `valid_count`
  - `missing_count`
  - `outlier_count`
  - `mean_excluding_flagged`
  - `std_excluding_flagged`
- 均值和标准差使用排除 missing 与 `9999` 后的数据。
- summary 仍保留质量风险信息，不删除原始 raw。
- A01 应 `missing_count=1`。
- A02 应 `outlier_count=1`。

验证：

```bash
cat work/check-ws/tasks/task_0007/derived/*thickness_summary.csv
```

新增测试：

- 读取 thickness summary，断言 A01 missing_count=1，A02 outlier_count=1。

---

### F-6. 补齐 sample_metadata processor

涉及文件：`data_agent/process.py`, 新增 `data_agent/processors/metadata.py`

要做：

- 给 `DataType.SAMPLE_METADATA` 增加 processor。
- 生成：
  - `run_<short>__sample_metadata_index.json`
  - 可选 `run_<short>__sample_metadata_clean.csv`
- JSON 至少包含：
  - `sample_id`
  - `batch_id`
  - `project_id`
  - `additive_ratio_pct`
- 写 processing run、L2 data object、relationship、manifest derived file。
- 第一版不强制跨 task 自动关联，但 report 应说明 metadata 可供后续 linking。

验证：

```bash
.venv/bin/python -m data_agent info --workspace work/check-ws
find work/check-ws/tasks/task_0004 -maxdepth 3 -type f | sort
```

预期：

- `sample_metadata.csv` task 的 Runs 不再是 0。
- 有 metadata index 派生文件。

新增测试：

- metadata task 有 run、L2 object、derived file。

---

### F-7. 接入 chart model adapter

涉及文件：`data_agent/process.py`, `data_agent/processors/chart_image.py`, `data_agent/model_adapters/*.py`

要做：

- `--models local|cloud|auto` 必须传给 chart processor。
- local：
  - 调用 `LocalAnalyzer`
  - `chart_metadata.json` 包含 `method=local_rules`
- cloud：
  - 调用 `CloudStubAnalyzer`
  - 无配置不失败
  - 生成 `model_unavailable` quality flag
- auto：
  - 先尝试 cloud
  - cloud unavailable 后 fallback local
  - processing run warnings 记录 fallback
- 不调用真实云 API，不读取真实 key。

验证：

```bash
.venv/bin/python -m data_agent process --workspace work/check-ws --task task_0002 --models local
.venv/bin/python -m data_agent process --workspace work/check-ws --task task_0002 --models cloud
.venv/bin/python -m data_agent process --workspace work/check-ws --task task_0002 --models auto
```

新增测试：

- 三种 mode 都不崩。
- cloud mode 生成 `model_unavailable` flag。
- auto mode 有 fallback warning。

---

### F-8. 修复 marimo open 与复核页

涉及文件：`data_agent/cli.py`, `marimo_apps/task_review.py`

要做：

- `cli.open` 不要调用裸 `marimo`。
- 改成：

```python
[sys.executable, "-m", "marimo", "run", str(marimo_path)]
```

- `task_review.py` 用：

```python
import os
task_id = os.environ.get("DATA_AGENT_TASK_ID", "")
workspace_path = os.environ.get("DATA_AGENT_WORKSPACE", "./workspace")
```

- 不要用 `mo.status.get_env`，当前 marimo 版本没有这个 API。
- 页面补充展示 `logs/relationships.json`。
- Actions 区域可以继续给 CLI 命令，不强制按钮化。

验证：

```bash
.venv/bin/python -m marimo check marimo_apps/task_review.py
.venv/bin/python -m data_agent open --workspace work/check-ws --task task_0001
```

预期：

- 不再报 `FileNotFoundError: 'marimo'`。
- 不再报 `mo.status.get_env`。
- 可启动 marimo 服务。

---

### F-9. 修复 README 与项目卫生

涉及文件：`README.md`, `.gitignore`, `pyproject.toml`

要做：

- README 命令统一说明需要 Python 3.10+ venv。
- 命令示例使用：

```bash
.venv/bin/python -m data_agent ...
```

- 增加完整验收命令。
- 新增 `.gitignore`：
  - `.venv/`
  - `__pycache__/`
  - `.pytest_cache/`
  - `workspace/`
  - `work/check-ws/`
  - `*.sqlite`
- 可选修复 `datetime.utcnow()` warning，改为 timezone-aware UTC。

验证：

```bash
.venv/bin/python -m pytest -q
```

Review 重点：

- 不要把运行产物、缓存、sqlite 当成交付源码。

---

## 4. 最终验收命令

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

.venv/bin/python -m marimo check marimo_apps/task_review.py
```

最低预期：

- `tasks = 9`
- `files >= 9`
- `data_objects >= 18`
- `processing_runs >= 9`
- `quality_flags >= 12`
- `relationships >= 9`
- `reviews >= 1`

## 5. 最终 Acceptance Criteria

- AC-1：demo 9 个文件全部登记到 SQLite 和 evidence package。
- AC-2：raw 文件为 L1，不修改、不覆盖。
- AC-3：每个处理 run 都生成新的 L2，不覆盖旧 L2。
- AC-4：manifest 能直接索引所有派生文件。
- AC-5：relationships 方向正确，rerun 有替代关系。
- AC-6：厚度 summary 正确记录 missing/outlier。
- AC-7：metadata task 有 processor、run 和 L2 index。
- AC-8：chart image 支持 local/cloud/auto model mode。
- AC-9：文本解释句只进入 `interpretation_candidates`。
- AC-10：surface photo 只做 metadata + manual review flag。
- AC-11：review 同步写 DB 和 JSON。
- AC-12：marimo open 可启动，复核页能读 manifest/runs/flags/relationships/reviews。
- AC-13：`pytest -q` 通过，新增测试覆盖上述审计行为。
