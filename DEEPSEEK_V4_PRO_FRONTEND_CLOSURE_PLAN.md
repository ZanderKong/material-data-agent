# DeepSeek V4 Pro Coding Plan: Streamlit UI 验收收口

## 0. 执行目标

本计划交给 DeepSeek V4 Pro 直接执行。目标是把当前已经实现的 Streamlit 本地 UI 收口成可验收、可演示、可复核的前端迭代。

完成后必须达到：

- 用户可以通过 UI 完成 `ingest -> process -> review`。
- UI 能清楚展示 raw、derived、model_result、quality_flags、processing runs、relationships、reviews。
- raw CSV 只预览前 50 行，不整文件文本展示。
- UI 所有错误展示都经过脱敏，不泄露真实 API key、Bearer token 或相关环境变量值。
- 进入已有 workspace 后 Task List 能自动加载，不强制用户先点 Refresh。
- model_result 不再只是一坨 JSON，而是分区展示审计信息、风险信息、提取结果、原始响应。
- Review 可以选择 target type 和 target id，并通过底层 review 写入逻辑记录。
- 新增 `python -m data_agent ui --print-command` 快捷命令。
- README、FRONTEND_CHECK、MODEL_LAYER_CHECK、UI walkthrough 文档状态一致。
- 全量 pytest 通过，并把真实测试结果写入文档。
- FRONTEND_CHECK 的手工 UI 验收必须是真实打开 UI 后记录，不能只改 checkbox。

## 1. 严格边界

必须做：

- 修正 raw CSV preview。
- 统一 UI error redaction。
- Task List 初始自动加载。
- Model Result 分区展示。
- Review target 可选支持。
- `data_agent ui --print-command` 或等价快捷启动入口。
- 新增 `docs/ui_walkthrough.md`。
- 更新 README、FRONTEND_CHECK、MODEL_LAYER_CHECK 中和本轮相关的状态。
- 新增或更新对应 tests。
- 进行真实手工 UI 验收并记录证据。

禁止做：

- 不改 model router 行为。
- 不改 provider 调用策略。
- 不改 SQLite schema。
- 不改 processing pipeline 的核心处理逻辑。
- 不做真实 OCR。
- 不做图表 digitization。
- 不做 FastAPI/React 迁移。
- 不做登录、权限、账号体系。
- 不删除 raw 文件，不覆盖旧 L2，不改变 rerun 的版本化语义。
- 不把真实 API key、endpoint secret、Bearer token 写入仓库。
- 不仅靠改文档宣称通过，必须有测试和手工验收记录。

## 2. 当前已知事实

当前仓库中已有：

- `data_agent/ui/app.py`：Streamlit 主入口。
- `data_agent/ui/readers.py`：workspace/task 只读 helper。
- `data_agent/ui/preview.py`：`preview_csv()`、`preview_json()`、`preview_text()`、`preview_model_result()`。
- `data_agent/ui/actions.py`：ingest/process/review UI action wrapper。
- `data_agent/reviews.py`：底层 `write_review()`。
- `data_agent/cli.py`：Typer CLI，已有 `review --target`。
- `FRONTEND_CHECK.md`：前端验收记录，但手工验收 checkbox 仍未完成。
- `README.md`：当前测试数量仍旧，和前端验收记录不一致。
- `MODEL_LAYER_CHECK.md`：模型层历史 checkpoint，仍记录 112 passed。

已确认的问题：

- `app.py` 的 Raw Files 区中 raw CSV 当前走 `preview_text()`，应改为 `preview_csv()`。
- `preview_csv()` 的 pandas 路径用了 `nrows=50`，但 fallback 会整文件 `read_text()`，大文件风险仍在。
- `app.py` 中多处 `st.error(result["message"])` 没有统一脱敏。
- `actions.py` 捕获异常后直接返回 `str(e)`。
- Task List 主要依赖 `st.session_state.task_list`，首次打开已有 workspace 时可能误显示 No tasks found。
- `reviews.py` 当前非空 target 会被写成 `target_type="data_object"`，无法准确记录 `quality_flag` 等 target type。
- `resolve_workspace()` 会创建目录；新增 UI CLI 打印命令时不得调用它，避免违反“不默认创建 workspace”。

## 3. 实施顺序

### Step 1: 建立执行基线

要做什么：

- 运行 `git status --short`，确认已有用户改动。
- 确认可用 Python 环境。优先使用项目 `.venv/bin/python`；如果不存在，按 README 创建 venv 并安装 dev 依赖。
- 运行一次全量测试，记录真实输出。

目的：

- 避免覆盖用户未提交改动。
- 锁定实施前测试基线。
- 后续文档中的 pytest 数量必须来自真实输出。

必须达到：

- 知道当前测试是通过、失败，还是环境缺失。
- 若环境缺失，先修复本地测试环境，不得直接跳过测试。

限制：

- 不修改业务代码。
- 不把临时 venv、cache、workspace 写入仓库。
- 不因为旧文档写了 `158 passed` 就直接沿用，最终以本次实际运行结果为准。

建议命令：

```bash
git status --short
.venv/bin/python -m pytest -q
```

如果 `.venv/bin/python` 不存在：

```bash
python3.10 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

### Step 2: 修正 raw CSV 预览

要做什么：

- 在 `data_agent/ui/app.py` 的 Raw Files 区拆分 kind 分支：
  - `image` -> `st.image(...)`
  - `csv` -> `preview_csv(...)`
  - `json` -> `preview_json(...)`
  - `text` -> `preview_text(...)`
- 在 `data_agent/ui/preview.py` 中修正 `preview_csv()` fallback，不能对大 CSV 整文件 `read_text()`。
- fallback 应只读取 header + `max_rows` 行，最多返回 51 行文本。

目的：

- raw CSV 的 UI 预览和 derived CSV 一致。
- 避免大 CSV 被当作完整文本读入，造成 UI 卡顿或内存风险。

必须达到：

- raw CSV 预览只展示前 50 行数据加表头。
- raw txt/md 仍走文本预览。
- raw json 仍格式化展示。
- raw image 仍图片展示。

限制：

- 不改变 `get_file_kind()` 的现有分类语义，除非测试明确要求。
- 不引入新的大型依赖。
- 不修改 raw 文件内容。

测试要求：

- 新增或更新 `tests/test_ui_preview.py`：
  - `test_csv_preview_does_not_read_full_large_file`
  - 确认 fallback 只读前 50 行，不包含第 51 行之后的数据。
- 如果无法直接测试 Streamlit 分支，至少补一个可测试 helper，例如 `render_raw_file_preview` 或轻量分类函数，覆盖 raw csv 会选择 csv preview。

### Step 3: 统一 UI 错误脱敏

要做什么：

- 新增 UI 层错误脱敏函数，建议放在 `data_agent/ui/actions.py` 或新增 `data_agent/ui/security.py`。
- 函数名建议：`safe_ui_error(message: object) -> str`。
- 复用 `data_agent.model_adapters.redaction.redact_string()`。
- 额外兜底脱敏：
  - `sk-...` 形式 token。
  - `Bearer ...` 形式 authorization header。
  - 字面量 `BEST_MODEL_API_KEY`、`FAST_MODEL_API_KEY`、`VISION_MODEL_API_KEY`、`OCR_MODEL_API_KEY`。
  - 当前环境变量中这些 key 对应的真实值。
- 所有 UI 失败展示都必须经过 `safe_ui_error()`：
  - ingest error
  - upload error
  - process task error
  - process all error
  - review error
  - model profile error
  - preview/model_result error
- `actions.py` 捕获异常后返回的 `message` 也应是脱敏后的。

目的：

- cloud/auto 模式下即使底层 provider 抛出敏感错误，也不会被 Streamlit 展示出来。
- 前端展示安全性和模型层 redaction 一致。

必须达到：

- UI 上看到的是 `Error: Request failed: [REDACTED]` 这类内容。
- UI 不显示完整 API key、Bearer token、环境变量真实值。
- `app.py` 中不得直接 `st.error(raw_exception)` 或 `st.error(result["message"])` 展示未经脱敏的错误。

限制：

- 不改变底层 model adapter 的错误语义。
- 不吞掉错误类型到无法排查；脱敏后仍应保留足够上下文，例如 HTTP status、操作名。
- 不打印 secret 到 stdout/stderr。

测试要求：

- 新增测试：
  - `test_safe_ui_error_redacts_exact_secret`
  - `test_safe_ui_error_redacts_bearer`
  - `test_safe_ui_error_redacts_key_env_names`
  - `test_actions_error_message_not_expose_secret`
- 测试中使用临时环境变量，结束后必须清理。

### Step 4: Task List 初始自动加载

要做什么：

- `data_agent/ui/app.py` 初始化时支持 `DATA_AGENT_UI_WORKSPACE` 作为默认 workspace。
- 记录当前 task list 对应的 workspace，例如 `task_list_workspace`。
- 当 workspace 有 `tasks/` 且当前 session 没有该 workspace 的 task list 时，自动调用 `read_task_list(ws)`。
- Refresh 按钮仍强制重新读取。
- ingest/process/review 成功后重新读取 task list。

目的：

- 用户进入已有 workspace 后可以直接看到任务列表。
- 避免误把“没点刷新”显示成 “No tasks found”。

必须达到：

- 首次输入 `/tmp/material-agent-ui-ws` 后，Tasks tab 自动显示 task list。
- 切换 workspace 后不能继续显示旧 workspace 的 task list。
- Refresh、ingest、process、review 后状态会更新。

限制：

- 不长期缓存 manifest。
- 不把 `session_state` 当业务真相源。
- 不引入后台轮询。

测试要求：

- 如果可测试，新增 helper 并覆盖：
  - workspace 变化时 task list 失效。
  - `DATA_AGENT_UI_WORKSPACE` 会作为默认值。
- 手工验收必须记录“启动 UI -> 输入已有 workspace -> 未点击 Refresh 即显示 task list”。

### Step 5: 增加 `data_agent ui` 快捷命令

要做什么：

- 在 `data_agent/cli.py` 增加 Typer command：
  - `python -m data_agent ui`
  - `python -m data_agent ui --workspace ./workspace`
  - `python -m data_agent ui --workspace ./workspace --print-command`
- 命令行为：
  - 打印 Streamlit 启动命令。
  - 通过 `DATA_AGENT_UI_WORKSPACE` 把 workspace 传给 UI。
  - `--print-command` 只打印，不启动。
  - 非 `--print-command` 时使用 `subprocess.run(...)` 启动 Streamlit。

目的：

- 用户无需记住 `python -m streamlit run data_agent/ui/app.py` 的完整路径。
- 便于手工验收和 README 统一入口。

必须达到：

- `python -m data_agent ui --print-command` 能打印可复制执行的命令。
- `python -m data_agent ui --workspace /tmp/material-agent-ui-ws --print-command` 能显示环境变量和 workspace。
- 命令不默认创建或删除 workspace。

限制：

- 不调用 `resolve_workspace()`，因为它会创建目录。
- 不重写 Streamlit UI 逻辑。
- 不在测试中真实启动长期阻塞的 Streamlit 服务。

测试要求：

- 新增 CLI runner 或等价测试：
  - `test_ui_command_prints_streamlit_command`
  - `test_ui_command_does_not_create_workspace_in_print_mode`
  - `test_ui_command_sets_workspace_env_in_output`

### Step 6: Model Result 分区展示

要做什么：

- 扩展 `preview_model_result()`，确保返回以下字段：
  - 审计信息：role、provider、model、mode、success、confidence、fallback_used、fallback_from、latency_ms、token_usage、schema_version、prompt_version。
  - 风险信息：warnings、error、requires_review、ocr_unavailable、vision_unavailable。
  - 提取结果：output_json、text_blocks、detected_units、axis_candidates、visible_features、factual_observations、interpretation_candidates。
  - 原始响应：raw_text、raw_response、raw_response_redacted。
- 在 `app.py` 中把 model_result 展示拆成四区：
  - Audit
  - Risk
  - Extracted Output
  - Raw Response
- Raw Response 必须默认折叠，并标注“已脱敏”。
- 展示固定文案：
  - `model_result 是模型辅助提取结果，不是科研结论。`
  - `requires_review=True 时必须人工确认。`
  - `success=False 表示模型不可用、fallback 或 stub，不代表分析成功。`

目的：

- 让用户能快速判断模型输出的来源、成功状态、fallback、风险和可读结果。
- 避免用户误把 model_result 当作科研结论。

必须达到：

- 打开 chart image 或 visual image task 时，model_result 不是单纯 JSON dump。
- 能直接看到 role/provider/model/mode/success/fallback/error/output_json。
- 原始响应默认折叠且脱敏。

限制：

- 不增加科研结论、机理解释、实验建议。
- 不恢复被 sanitize 移除的 forbidden fields。
- 不对模型输出做新的科学解释。

测试要求：

- 更新 `tests/test_ui_preview.py`：
  - model_result helper 返回 raw redacted 字段。
  - output_json 常见字段能被提取。
  - invalid JSON 仍返回 `_error`，错误展示经过脱敏。

### Step 7: Review target 支持

要做什么：

- 更新 `data_agent/reviews.py` 的 `write_review()`：
  - 参数增加 `target_type: str = "task"`。
  - 当 `target_id` 为空时，写入 `target_type="task"`、`target_id=task_id`。
  - 当 `target_id` 非空时，写入调用方传入的 `target_type` 和 `target_id`。
- 更新 CLI `review`：
  - 保留现有 `--target`。
  - 新增 `--target-type`，默认 `task`。
- 更新 `data_agent/ui/actions.py` 的 `do_review()`：
  - 接收 `target_type`、`target_id`。
  - 调用底层 `write_review()`，不得绕过底层直接写 JSON。
- 更新 `app.py` Review 区：
  - 增加 target type selectbox：`task`、`quality_flag`、`data_object`、`derived_file`。
  - 增加 target id 输入框。
  - 默认 target type 为 `task`，target id 为空时按当前 task 记录。
  - 如果当前 flags 有 `flag_id`，可在 caption 或 select helper 中提示可复制的 flag id。

目的：

- UI review 能针对任务、质量标记或派生对象做审阅记录。
- review 记录可在 DB 和 `review_records.json` 中复核 target。

必须达到：

- 默认提交 review 仍兼容旧行为。
- 选择 `quality_flag` 并输入某个 `flag_id` 后，`review_records.json` 中能看到对应 `target_type` 和 `target_id`。
- SQLite reviews 表也写入同样 target 信息。

限制：

- 不改 SQLite schema。
- 不绕过 `write_review()`。
- 不做复杂 target 浏览器，第一版只做可选文本输入即可。

测试要求：

- 新增或更新：
  - `test_write_review_preserves_target_type_and_id`
  - `test_do_review_passes_target`
  - CLI print/help 或 runner 覆盖 `--target-type`。

### Step 8: Process/Rerun 文案与关系可见性

要做什么：

- 在 `app.py` 的 Process / Rerun 区增加明确说明：
  - Rerun will create new L2 derived files.
  - Old L2 files will be kept.
  - Replacement relationships will be recorded as replaces/replaced_by.
  - Raw files will not be modified.
- Relationships 区展示时不要截断到无法辨认。
- Relationships 表至少显示：
  - `rel_type`
  - `source_id`
  - `target_id`
  - metadata 中的 `run_id` 或关键字段。

目的：

- 让用户在 UI 中知道 rerun 的版本化语义。
- 手工复检可以直接看到 replacement 关系。

必须达到：

- 对同一 task 连续 process 两次后，UI Relationships 区能看到 `derived_from`、`replaces`、`replaced_by`。
- raw 文件不变。

限制：

- 不改变 rerun 的实际业务逻辑。
- 不删除旧 L2。
- 不新增对比视图，这属于后续 P2。

测试要求：

- 优先依赖已有 rerun tests。
- 手工验收必须记录连续 process 两次后的 derived 文件数量和 relationships 结果。

### Step 9: 新增 UI walkthrough 文档

要做什么：

- 新增 `docs/ui_walkthrough.md`。
- 按真实操作顺序写：
  1. 启动 UI。
  2. 输入 workspace。
  3. ingest demo inbox。
  4. 查看 task list。
  5. 打开 task detail。
  6. process selected task。
  7. 查看 model_result。
  8. 查看 quality_flags。
  9. 提交 review。
  10. 获取 marimo command。
- 说明推荐 workspace：`/tmp/material-agent-ui-ws`。
- 说明推荐 model mode：`local`。
- 说明 raw 文件不会被修改、local 不发网络请求。

目的：

- 给用户一份可按步骤复现的 UI 操作说明。
- 支撑 FRONTEND_CHECK 的手工验收。

必须达到：

- README 能链接到该 walkthrough。
- 文档中不出现真实 API key。
- 不需要截图；可以预留截图路径，但不得编造截图已经存在。

限制：

- 不写营销式介绍。
- 不写尚未实现的功能。

### Step 10: README 和验收文档同步

要做什么：

- 更新 `README.md` 当前验收状态：
  - 基础 demo 闭环：ingest -> process -> review -> info。
  - Model Service Layer 已实现。
  - Streamlit Local UI 已实现。
  - pytest：写本轮真实结果。
  - L2 版本化输出已实现。
  - rerun replaces/replaced_by 已实现。
  - marimo 复核命令可生成。
- Local UI 章节补充：
  - 推荐启动命令：`python -m data_agent ui --workspace /tmp/material-agent-ui-ws`。
  - 打印命令：`python -m data_agent ui --workspace /tmp/material-agent-ui-ws --print-command`。
  - demo workspace 验收命令。
  - `FRONTEND_CHECK.md` 是前端验收记录。
  - `MODEL_LAYER_CHECK.md` 是模型服务层验收记录。
  - `docs/ui_walkthrough.md` 是 UI 操作 walkthrough。
- 更新 `MODEL_LAYER_CHECK.md`：
  - 保留模型层 2026-07-09 的 112 passed 作为历史 checkpoint。
  - 新增“前端收口后全项目测试结果”，写本轮真实 pytest 输出。
  - 明确两者时间和范围不同，避免和 README 矛盾。
- 更新 `FRONTEND_CHECK.md`：
  - 测试结果写本轮真实 pytest 输出。
  - 新增本轮变更摘要。
  - 手工验收区必须填真实验收日期、workspace、启动命令、model mode、实际 task 数、实际 pytest 结果。
  - 15 项 checkbox 必须在真实 UI 验收后才能勾选，每项后写一句实际结果。

目的：

- 消除 README、FRONTEND_CHECK、MODEL_LAYER_CHECK 之间测试数量和状态矛盾。
- 让项目状态可信。

必须达到：

- 三份文档中的测试数量不互相矛盾。
- FRONTEND_CHECK 不再是空 checkbox。
- README 的 Local UI 入口和实际 CLI 一致。

限制：

- 不伪造测试结果。
- 不伪造手工验收。
- 如果某项手工验收失败，必须保留未勾选并写明原因。

## 4. 手工 UI 验收流程

准备：

```bash
rm -rf /tmp/material-agent-ui-ws
mkdir -p /tmp/material-agent-ui-ws
```

如需先用 CLI 准备 demo workspace：

```bash
.venv/bin/python -m data_agent ingest \
  --inbox "$DEMO_INBOX" \
  --workspace /tmp/material-agent-ui-ws

.venv/bin/python -m data_agent process \
  --workspace /tmp/material-agent-ui-ws \
  --all --models local
```

启动 UI：

```bash
.venv/bin/python -m data_agent ui \
  --workspace /tmp/material-agent-ui-ws
```

必须真实检查并记录：

- 能输入 `/tmp/material-agent-ui-ws` 作为 workspace。
- 能看到 task list，实际 task 数应记录。
- 能选择 `task_0001`。
- 能看到 raw files。
- 能看到 derived files。
- 能看到 processing runs。
- 能看到 quality flags。
- 能看到 review records。
- 能看到 model profiles 状态。
- 能显示 marimo command。
- 能 process selected task。
- 能写入 review。
- 页面不显示任何真实 API key。
- `local` 模式不发网络请求。
- refresh 后数据仍正确。

附加 rerun 检查：

- 对同一 task 连续 process 两次。
- 记录 derived 文件数量增加。
- 确认旧 derived 文件仍存在。
- 确认 relationships 显示 `replaces/replaced_by`。
- 确认 raw 文件未修改。

## 5. 最终测试与交付门槛

最终必须运行：

```bash
.venv/bin/python -m pytest -q
```

如果涉及 CLI：

```bash
.venv/bin/python -m data_agent ui --workspace /tmp/material-agent-ui-ws --print-command
```

如果做了真实 UI 验收：

```bash
.venv/bin/python -m data_agent info --workspace /tmp/material-agent-ui-ws
```

交付前必须确认：

- `pytest -q` 全部通过。
- README、FRONTEND_CHECK、MODEL_LAYER_CHECK 中测试数量一致或范围差异解释清楚。
- `FRONTEND_CHECK.md` 手工验收记录包含日期、workspace、启动命令、model mode、实际 task 数、pytest 结果。
- `app.py` 不存在未经脱敏的 `st.error(...)` 展示。
- `actions.py` 异常消息不会泄露 secret。
- `data_agent ui --print-command` 不创建 workspace。
- `local` 模式验证不发网络请求。
- git diff 中没有 `.env`、`model_profiles.yaml`、真实 API key、临时 workspace、cache 文件。

## 6. 建议提交清单

预期会修改或新增：

- `data_agent/ui/app.py`
- `data_agent/ui/preview.py`
- `data_agent/ui/actions.py`
- `data_agent/reviews.py`
- `data_agent/cli.py`
- `tests/test_ui_preview.py`
- 可新增 `tests/test_ui_actions.py`
- 可新增 `tests/test_cli_ui.py`
- `README.md`
- `FRONTEND_CHECK.md`
- `MODEL_LAYER_CHECK.md`
- `docs/ui_walkthrough.md`

不得修改，除非测试暴露出本轮直接相关 bug：

- `data_agent/model_adapters/router.py`
- `data_agent/model_adapters/openai_compatible.py`
- `data_agent/process.py`
- `data_agent/db.py`
- `data_agent/schemas.py`
- `data_agent/processors/*`

## 7. 失败处理规则

如果测试失败：

- 先判断是否由本轮改动引入。
- 修复本轮相关失败。
- 不通过放宽测试来掩盖问题。
- 不删除历史测试。

如果手工 UI 某项失败：

- 不勾选该项。
- 在 `FRONTEND_CHECK.md` 写明失败步骤、实际现象、相关日志或截图路径。
- 修复后重新验收。

如果找不到 demo inbox：

- 使用 `DATA_AGENT_DEMO_INBOX` 环境变量指定。
- 文档中记录实际使用路径。
- 不硬编码个人本机路径到代码。

如果无法启动 Streamlit：

- 先确认依赖安装。
- 使用 `python -m data_agent ui --print-command` 验证命令生成。
- 不把“命令可生成”冒充为“UI 已手工验收通过”。

