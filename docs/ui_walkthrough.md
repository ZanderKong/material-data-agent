# UI Walkthrough: Streamlit 本地前端操作指南

## 概述

本文档指导用户通过 Streamlit 本地 UI 完成 `ingest → process → review` 的完整操作闭环，并验收各功能区域是否正常工作。

## 推荐环境

- **Workspace**: `/tmp/material-agent-ui-ws`
- **Model mode**: `local`（零网络调用，不发送外部请求）
- **Python 环境**: 项目 `.venv`

## 操作步骤

### 1. 启动 UI

```bash
# 方式 A：CLI 快捷命令
.venv/bin/python -m data_agent ui \
  --workspace /tmp/material-agent-ui-ws

# 方式 B：打印启动命令（不启动）
.venv/bin/python -m data_agent ui \
  --workspace /tmp/material-agent-ui-ws \
  --print-command

# 方式 C：直接使用 Streamlit
.venv/bin/python -m streamlit run data_agent/ui/app.py
```

启动后在浏览器中打开 Streamlit 提示的地址（默认 `http://localhost:8501`）。

### 2. 输入 workspace

- 在左侧 Sidebar 的 "Workspace path" 文本框中输入 `/tmp/material-agent-ui-ws`。
- 如果 workspace 尚未初始化，Sidebar 会显示 "Not initialized"。

### 3. Ingest demo inbox

- 切换到 "Ingest" tab。
- 选择 "Inbox directory"，输入 demo inbox 路径。
- 点击 "Ingest Inbox" 按钮。
- 成功后右侧会显示创建的 task ID 列表。

或者使用 "Upload files" 直接上传文件。

### 4. 查看 task list

- 切换到 "Tasks" tab。
- 如果已有 `tasks/` 目录，task list 会自动加载（无需手动点击 Refresh）。
- 可以使用 status filter 或 "Only show needs_review" 筛选。
- 点击 task ID 可在下方 selectbox 中选择查看详情。

### 5. 打开 task detail

- 在 Tasks tab 选择某个 task ID 后，切换到 "Task Detail" tab。
- 可以看到以下区域（均可展开/折叠）：
  - **Raw Files**: 原始文件。CSV 以表格形式预览前 50 行；image 直接展示；text/md 文本预览。
  - **Derived Files**: 派生处理结果。model_result 以为 Audit/Risk/Extracted/Raw Response 四个分区展示。
  - **Processing Runs**: 处理运行记录。
  - **Quality Flags**: 质量标记。
  - **Relationships**: 文件间关系（含 `derived_from`、`replaces`、`replaced_by`）。
  - **Review Records**: 审阅记录。

### 6. Process selected task

- 在 Task Detail tab 底部 "Actions" 区域，选择 Model mode（建议 `local`）。
- 点击 "Process / Rerun Task" 按钮。
- 处理完成后页面自动刷新，derived files 和 runs 等会更新。

**Rerun 说明**：
- Rerun 会创建新的 L2 derived files，旧 L2 保持不变。
- 替换关系会记录为 `replaces`/`replaced_by`。
- Raw files 不会被修改。

### 7. 查看 model_result

- 在 Derived Files 区域找到 `*model_result*.json` 文件。
- 展开后分为四个区域：
  - **Audit**（默认展开）：role、provider、model、mode、success、confidence、fallback、latency、token_usage 等信息。
  - **Risk**（默认折叠）：warnings、error、requires_review、ocr_unavailable、vision_unavailable。
  - **Extracted Output**（默认展开）：模型提取的可读结果（output_json）。
  - **Raw Response**（默认折叠，已脱敏）：原始模型响应文本。

页面上方有免责提示：
- model_result 是模型辅助提取结果，不是科研结论。
- requires_review=True 时必须人工确认。
- success=False 表示模型不可用、fallback 或 stub，不代表分析成功。

### 8. 查看 quality_flags

- 在 Quality Flags 区域查看所有质量标记。
- `requires_review=True` 的 flag 会以 warning 样式高亮显示。
- 可以看到 severity、confidence、message 等信息。

### 9. 提交 review

- 在 Actions 区域的 "Review" 部分：
  - 选择 Action（approve / return_for_rerun / mark_low_confidence / deprecate）。
  - 输入 Reviewer 名称和 Comment。
  - 选择 Target type（task / quality_flag / data_object / derived_file）。
  - 输入 Target ID，留空则默认为当前 task。
  - 如果有 quality flags，会自动列出可用的 flag IDs。
  - 选择 deprecate 时需勾选二次确认。
  - 点击 "Submit Review" 提交。

### 10. 获取 marimo command

- 切换到 "Help" tab。
- 可以看到 marimo 复核工作台的启动命令，可直接复制执行。
- 添加 `--print-command` 可仅打印命令而不启动。

## 安全说明

- UI 中所有错误提示均经过脱敏处理，不会显示真实的 API key、Bearer token 或环境变量值。
- 错误信息中 `sk-...` 格式的 key 会被替换为 `[REDACTED]`。
- `local` 模式下不会发起任何网络请求。

## Raw 文件说明

- Raw files 不会被 UI 修改。
- CSV raw 文件预览仅展示前 50 行数据。
- 大文件不会被完整加载到内存中。

## 截图路径

（可在此处插入 UI 各区域的截图）

- Sidebar: `docs/screenshots/sidebar.png`
- Ingest tab: `docs/screenshots/ingest.png`
- Tasks tab: `docs/screenshots/tasks.png`
- Task Detail: `docs/screenshots/detail.png`
- Model Result: `docs/screenshots/model_result.png`
- Review: `docs/screenshots/review.png`
- Help tab: `docs/screenshots/help.png`
