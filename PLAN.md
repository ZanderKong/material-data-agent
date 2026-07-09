# PLAN.md：材料研发数据处理 Agent MVP

## 0. 给执行 Agent 的工作方式要求

先进入 OpenCode Plan Mode，阅读本计划、demo 数据和现有项目结构，再输出你自己的执行理解。获得确认后再进入 build 模式。严格按本计划实现，不要擅自扩展为 ELN、报告系统、多用户平台或完整科研 Agent。

项目根目录：`/Users/zanderkong/Documents/Codex/2026-07-09/1-agent-marimo-l0-l1-l2`

demo 数据目录：`/Users/zanderkong/Desktop/数据处理agent/material_data_agent_demo 测试数据`

## 1. 目标 (Goal)

实现一个本地可运行的材料研发数据处理 Agent MVP：接收 demo `inbox/` 中的 CSV、谱图原始数据、图表图片、观察文本和表面图片，生成可追溯 evidence package、SQLite 注册表、L0/L1/L2/L3 状态、processing run、quality flags、relationships、review records，并提供 marimo 单任务复核工作台。

## 2. 假设与约束 (Assumptions & Constraints)

- 核心逻辑必须独立于 marimo；marimo 只负责读取、展示、显式重跑和写复核记录。
- 原始文件不可修改；ingest 后复制到 task 的 `raw/`，登记为 L1。
- 每次处理或重跑都生成新的 L2 派生结果，不覆盖旧 L2。
- L3 是废弃/失败/替代状态，不等于删除文件。
- 第一版使用 SQLite + 本地文件夹，不做 Postgres、权限系统、云部署。
- 云端 OCR/多模态模型是可选增强；无 API key 时必须能用本地规则完成 MVP，并标记低置信/需人工确认。
- 数据处理 Agent 只输出事实观察、统计趋势、质量风险；不能输出机理解释、因果判断、最终科研结论或实验建议。
- 优先通过 demo 中的 `expected_notes/expected_behavior.md` 验收。

## 3. 目标目录结构

实现后项目应大致包含：

```text
data_agent/
  __init__.py
  __main__.py
  cli.py
  config.py
  db.py
  schemas.py
  ingest.py
  classify.py
  process.py
  reviews.py
  package.py
  reports.py
  processors/
    numeric.py
    spectral.py
    chart_image.py
    observation_text.py
    visual_image.py
  model_adapters/
    base.py
    local.py
    cloud_stub.py
marimo_apps/
  task_review.py
tests/
  test_ingest.py
  test_demo_pipeline.py
  test_processors.py
pyproject.toml
README.md
```

运行产生的数据放在项目内：

```text
workspace/
  agent.sqlite
  tasks/
    task_0001/
      manifest.json
      raw/
      derived/
      logs/
      reviews/
```

## 4. 实施步骤 (Implementation Steps)

### F-1. 项目初始化与依赖

涉及文件：`pyproject.toml`, `README.md`

- 创建 Python 项目配置，最低支持 Python 3.10；如果本机只有 3.9，则在 README 中说明使用可用虚拟环境。
- 依赖建议：`pydantic`, `pandas`, `openpyxl`, `numpy`, `matplotlib`, `pillow`, `typer`, `rich`, `pytest`, `marimo`。
- CLI 入口使用 `python -m data_agent ...`，不要依赖全局脚本安装。
- README 写清 demo 路径、初始化、ingest、process、open、test 命令。

验证：

- `python -m data_agent --help` 能显示 CLI。
- `pytest` 至少能启动测试收集。

### F-2. 定义 schema 与生命周期模型

涉及文件：`data_agent/schemas.py`

- 定义 Pydantic 模型：
  - `FileRecord`
  - `DataObject`
  - `ProcessingRun`
  - `Relationship`
  - `QualityFlag`
  - `ReviewRecord`
  - `TaskManifest`
- 生命周期枚举：`L0`, `L1`, `L2`, `L3`。
- 数据类型枚举至少包括：
  - `sample_metadata`
  - `raw_numeric`
  - `raw_spectral`
  - `chart_image_input`
  - `descriptive_observation_text`
  - `visual_image`
  - `derived_table`
  - `generated_figure`
  - `structured_observation`
- processing run 状态至少包括：`pending`, `running`, `succeeded`, `failed`, `deprecated`。
- quality flag 至少包含：`flag_id`, `severity`, `target_type`, `target_id`, `message`, `evidence`, `requires_review`, `confidence`。

验证：

- 新增单元测试检查 schema 可序列化为 JSON，再读回不丢字段。

### F-3. SQLite 注册系统

涉及文件：`data_agent/db.py`

- 初始化 `workspace/agent.sqlite`。
- 建表：`files`, `data_objects`, `processing_runs`, `relationships`, `quality_flags`, `reviews`, `tasks`。
- 提供函数：
  - `init_db(workspace)`
  - `insert_file(record)`
  - `insert_data_object(obj)`
  - `insert_processing_run(run)`
  - `insert_quality_flag(flag)`
  - `insert_relationship(rel)`
  - `insert_review(review)`
  - `get_task(task_id)`
- JSON 字段可先用 TEXT 存储，但写入前必须 `json.dumps`。

验证：

- 测试创建临时 workspace，初始化 DB，插入并读回一条 file/run/flag/review。

### F-4. Evidence package 写入与读取

涉及文件：`data_agent/package.py`

- 创建 task 目录：
  - `manifest.json`
  - `raw/`
  - `derived/`
  - `logs/processing_runs.json`
  - `logs/quality_flags.json`
  - `logs/relationships.json`
  - `logs/processing_report.md`
  - `reviews/review_records.json`
- `manifest.json` 汇总 task 状态、输入文件、派生文件、run ids、flag ids、review ids。
- 所有 JSON 使用 pretty print，便于人工审查和 Git diff。
- 提供 `load_package(task_dir)` 和 `write_package(...)`。

验证：

- ingest 一个临时文件后，断言以上文件和目录都存在。
- `manifest.json` 可被 `load_package()` 读回。

### F-5. Ingest：从 inbox 创建 task

涉及文件：`data_agent/ingest.py`, `data_agent/cli.py`

- CLI：
  - `python -m data_agent ingest --inbox "<demo>/inbox" --workspace ./workspace`
- 对 inbox 每个文件：
  - 先登记 L0 事件。
  - 计算 checksum。
  - 创建独立 task，例如 `task_0001`。
  - 复制原始文件到 `raw/`。
  - 将 raw 副本登记为 L1。
  - 写入 manifest、DB、初始 relationship。
- 不修改 demo 源文件，不移动源文件。

验证：

- 对 demo inbox 运行后应生成 9 个 task。
- 每个 task 都有 raw 文件、manifest、DB file record。
- checksum 记录存在。

### F-6. 文件类型识别

涉及文件：`data_agent/classify.py`

- 根据扩展名、MIME、文件名、列名和内容识别类型。
- demo 识别要求：
  - `sample_metadata.csv` -> `sample_metadata`
  - `sample_thickness.csv` -> `raw_numeric`
  - `sample_resistance.csv` -> `raw_numeric`
  - `sample_ftir_raw.csv` -> `raw_spectral`, subtype `FTIR`
  - `sample_uvvis_raw.csv` -> `raw_spectral`, subtype `UVVis`
  - `sample_ftir_chart.png` -> `chart_image_input`, subtype `FTIR`
  - `sample_uvvis_chart.png` -> `chart_image_input`, subtype `UVVis`
  - `observation_sample_A.txt` -> `descriptive_observation_text`
  - `sample_surface_photo.png` -> `visual_image`
- 识别结果写入 data object，带 `confidence` 和 `schema_json`。

验证：

- 单元测试逐个 demo 文件断言分类正确。

### F-7. 数值数据处理

涉及文件：`data_agent/processors/numeric.py`

- `sample_thickness.csv`：
  - 按 `sample_id`, `batch_id` 分组。
  - 生成 count、missing count、mean、std。
  - 空 thickness 生成 quality flag。
  - `9999` 生成 suspicious outlier flag。
  - 不删除 `9999`，但派生摘要需说明包含/排除策略；默认保留原值并额外给出 flagged count。
- `sample_resistance.csv`：
  - 检测 `ohm/sq` 和 `kOhm/sq`。
  - 生成标准列 `sheet_resistance_ohm_sq`。
  - `kOhm/sq` 转换乘以 1000，并记录 relationship/processing parameter。
  - 缺失值生成 flag。
  - 生成 summary CSV 和 PNG plot。
- 输出写入 `derived/`，run 记录写入 `logs/processing_runs.json`。

验证：

- 断言派生 summary CSV 存在。
- 断言 thickness 有 missing flag 和 outlier flag。
- 断言 resistance 有 unit conversion 记录和 plot。

### F-8. 原始谱图数据处理

涉及文件：`data_agent/processors/spectral.py`

- FTIR：
  - x 轴识别 `wavenumber_cm-1`，y 轴 `absorbance`。
  - 生成重绘图 PNG。
  - 用基础峰检测提取近似 3400、1620、1120 cm-1 附近峰位。
  - 生成 peak table CSV。
- UV-Vis：
  - x 轴识别 `wavelength_nm`，y 轴 `absorbance`。
  - 生成重绘图 PNG。
  - 提取约 430 nm 和 620 nm 区域主吸收峰。
- 记录峰检测参数：窗口、平滑方式、阈值、prominence 或等价参数。
- 不做科研解释，只写“检测到峰/吸收区域”。

验证：

- FTIR 和 UV-Vis 均生成 reconstructed plot 和 peak table。
- processing run 中包含 peak extraction parameters。

### F-9. 图表截图处理：本地 + 模型适配器

涉及文件：`data_agent/processors/chart_image.py`, `data_agent/model_adapters/base.py`, `data_agent/model_adapters/local.py`, `data_agent/model_adapters/cloud_stub.py`

- 本地处理：
  - 读取图片尺寸、基础 metadata。
  - 尝试基于文件名和图中文字可见信息识别 chart subtype。
  - 记录 axis metadata：FTIR 为 wavenumber/absorbance，UV-Vis 为 wavelength/absorbance；如果来自规则推断，confidence 不得高于 0.7。
  - 可选做简单曲线 digitization；若实现，必须标记 low confidence。
- 模型增强：
  - 定义统一接口 `analyze_chart_image(image_path, context) -> ModelResult`。
  - `cloud_stub.py` 只做接口占位，不硬编码真实 API key。
  - 如果没有云端配置，输出 `model_unavailable` quality flag，但流程继续。
- 图表截图派生数据的置信度必须低于原始谱图 CSV。
- 生成 quality flags：axis confirmation required、digitization low confidence、image-derived data lower confidence。

验证：

- 两张 chart png 都生成 chart metadata JSON。
- 无云配置时不失败，必须产生需人工确认的 quality flag。

### F-10. 观察文本处理

涉及文件：`data_agent/processors/observation_text.py`

- 读取 UTF-8 文本。
- 规则抽取：
  - 含“可能是”的句子标记为 `interpretation_candidate`。
  - 其他描述按句子拆为 factual observations。
  - 尽量提取 sample id、时间表达、颜色变化、龟裂、脱落。
- 输出 `structured_observations.json`：
  - `factual_observations`
  - `trend_or_statements`
  - `interpretation_candidates`
  - `excluded_from_conclusion: true`
- 最后一类不得进入 final conclusion 字段；第一版不应有 final conclusion 字段。

验证：

- 断言“可能是...”进入 `interpretation_candidates`。
- 断言颜色变化、龟裂、脱落在 factual observations 中。

### F-11. 表面图片处理

涉及文件：`data_agent/processors/visual_image.py`

- 对 `sample_surface_photo.png`：
  - 保存图片 metadata：尺寸、格式、mode。
  - 生成 preview 或直接引用 raw。
  - 尝试检测 scale bar 区域可选；若实现，标记 low confidence。
  - 生成 `manual_review_required` quality flag。
- 不做完整 SEM 粒径分析，不输出确定性粒径结论。

验证：

- 生成 visual metadata JSON。
- 生成人工复核 flag。

### F-12. 统一 process 编排

涉及文件：`data_agent/process.py`, `data_agent/cli.py`

- CLI：
  - `python -m data_agent process --workspace ./workspace --all`
  - `python -m data_agent process --workspace ./workspace --task task_0001`
  - `--models local|cloud|auto`，默认 `local`
- process 根据 data type 分发到对应 processor。
- 每次处理创建 processing run：
  - 输入 data ids
  - 输出 data ids
  - tool name/version
  - parameters
  - status
  - warnings
  - created_at
- 失败时不改变 L1；失败 run 标记 failed，可作为 L3 对象记录。

验证：

- 对 demo 全量 process 不崩溃。
- 每个 task 至少有一个 succeeded 或明确 failed 的 processing run。
- 原始文件仍为 L1。

### F-13. Review 记录与重跑

涉及文件：`data_agent/reviews.py`, `data_agent/cli.py`

- CLI：
  - `python -m data_agent review --workspace ./workspace --task task_0001 --action approve --reviewer ZQ --comment "..."`
  - `python -m data_agent review --workspace ./workspace --task task_0001 --action deprecate --target <id>`
- 支持 action：
  - `approve`
  - `return_for_rerun`
  - `mark_low_confidence`
  - `deprecate`
  - `link_related_data`
- review record 必须包含 reviewer、created_at、target_type、target_id、before_value、after_value、comment。
- rerun 不覆盖旧 L2，新 L2 通过 `replaces` / `replaced_by` relationship 关联旧结果。

验证：

- 写入 approve review 后，`reviews/review_records.json` 和 DB 都能查到。
- rerun 生成新 run 和新 L2。

### F-14. Processing report

涉及文件：`data_agent/reports.py`

- 每个 task 生成 `logs/processing_report.md`。
- 内容包括：
  - 输入文件
  - 识别类型
  - 输出派生文件
  - processing run 摘要
  - quality flags 摘要
  - review 状态
  - 明确声明：本报告不包含科研结论，只包含事实观察、统计趋势和处理风险。
- report 用于人工 review，不作为最终研究报告。

验证：

- 每个 task 有 processing report。
- 文本中不出现“结论：添加剂提高...”这类因果判断。

### F-15. Marimo 单任务复核页

涉及文件：`marimo_apps/task_review.py`

- 只打开一个 task，不加载全项目数据。
- 从环境变量或 CLI 参数读取：
  - `DATA_AGENT_WORKSPACE`
  - `DATA_AGENT_TASK_ID`
- 页面展示：
  - manifest
  - raw 文件预览/路径
  - derived 文件列表
  - processing runs
  - quality flags
  - relationships
  - review records
- 提供显式按钮或说明用于：
  - approve
  - return_for_rerun
  - mark_low_confidence
  - deprecate
- 重型处理必须通过显式 rerun 触发，不要由 reactive cell 自动执行。

验证：

- `python -m data_agent open --workspace ./workspace --task <id>` 能启动或打印 marimo 启动命令。
- 页面可读取 task evidence package。

### F-16. Demo 集成测试

涉及文件：`tests/test_demo_pipeline.py`

- 测试使用真实 demo 路径；如果路径不存在，测试应 skip 并给出清晰原因。
- 测试流程：
  - 临时 workspace
  - ingest demo inbox
  - process all
  - 检查 expected behavior
- 断言重点：
  - 9 个输入文件被登记
  - 原始副本为 L1
  - 每个 task 有 manifest
  - CSV/spectral/text/image/chart 均有对应派生或质量 flag
  - 厚度空值、9999、电阻单位转换、文本 interpretation_candidate 都被识别

验证：

- `pytest -q` 通过。

## 5. 总体验证命令 (Verification)

建议最终执行：

```bash
python -m data_agent --help
python -m data_agent ingest --inbox "/Users/zanderkong/Desktop/数据处理agent/material_data_agent_demo 测试数据/inbox" --workspace ./workspace
python -m data_agent process --workspace ./workspace --all --models local
python -m data_agent review --workspace ./workspace --task task_0001 --action approve --reviewer ZQ --comment "demo approval"
pytest -q
```

人工检查：

```bash
find ./workspace/tasks -maxdepth 3 -type f | sort
```

至少确认存在：

- `manifest.json`
- `raw/` 原始副本
- `derived/` 派生 CSV/PNG/JSON
- `logs/processing_runs.json`
- `logs/quality_flags.json`
- `logs/relationships.json`
- `logs/processing_report.md`
- `reviews/review_records.json`

## 6. Acceptance Criteria

- AC-1：demo inbox 中所有文件都能登记为 L0，并归档为不可变 L1。
- AC-2：每个 task 都生成标准 evidence package。
- AC-3：SQLite 中能查询文件、数据对象、处理 run、质量风险、关系、复核记录。
- AC-4：数值 CSV 生成摘要表、质量 flags 和图表。
- AC-5：FTIR/UV-Vis 原始谱图生成重绘图和 peak table。
- AC-6：图表截图被识别为 chart image，并生成低置信/人工确认 flags。
- AC-7：观察文本区分 factual observations 和 interpretation_candidate。
- AC-8：表面图片不做过度分析，生成 metadata 和 manual review flag。
- AC-9：review 命令能写入 review record。
- AC-10：marimo 工作台能打开单个 task 并展示 evidence package。
- AC-11：所有处理日志记录工具、参数、时间、输入输出关系。
- AC-12：系统不输出科研最终结论或实验建议。

## 7. 潜在风险与注意事项

- 不要把业务逻辑写进 marimo；处理函数必须在 `data_agent/` 内。
- 不要覆盖旧派生文件；重跑生成新文件和 relationship。
- 不要删除、移动或修改 demo 源文件。
- 不要把云端模型作为必需路径；本地流程必须可跑完。
- 不要把图表图片 digitization 结果伪装成高置信原始数据。
- 不要把“可能是...”这类解释句存为事实结论。
- 如果实现中发现计划与 demo 文件不一致，先记录差异并询问，不要自行扩大功能范围。
