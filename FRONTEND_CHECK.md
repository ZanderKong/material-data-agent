# FRONTEND_CHECK.md：前端操作闭环验收报告

## 1. 本轮目标

为材料研发数据处理 Agent 增加 Streamlit 本地前端操作闭环，并进行收口验收。

## 2. 本轮变更摘要（2026-07-10 前端收口）

- 修正 raw CSV 预览：CSV 文件改为 `preview_csv()` 展示前 50 行，不再走 `preview_text()`
- CSV fallback 只读前 50 行，不整文件读入内存
- 统一 UI 错误脱敏：新增 `safe_ui_error()`，所有 `st.error` 和 `actions.py` 的错误均经脱敏处理
- Task List 自动加载：进入已有 workspace 后自动显示任务列表，支持 `DATA_AGENT_UI_WORKSPACE` 环境变量
- 新增 `python -m data_agent ui` CLI 快捷命令，支持 `--workspace` 和 `--print-command`
- Model Result 分区展示：Audit / Risk / Extracted Output / Raw Response 四区，含免责提示
- Review target 支持：target type selectbox + target id input，`write_review()` 参数扩展
- Process/Rerun 文案说明与 Relationships 表字段扩展
- 新增 `docs/ui_walkthrough.md`

## 3. 本轮不做事项

- 不重写 ingest / process / review 主流程
- 不改 SQLite schema
- 不扩展模型路由
- 不做用户登录/权限
- 不做 API key 加密存储
- 不做浏览器 E2E 测试
- 不替换 marimo

## 4. 新增/修改文件列表

```
data_agent/ui/
  __init__.py          # 包初始化
  app.py               # Streamlit 主入口（6 tab）[修改]
  readers.py           # 读取 workspace/tasks/manifest/logs helpers
  status.py            # display_status 推导逻辑
  preview.py           # 文件预览（image/csv/json/text/model_result）[修改]
  actions.py           # ingest/process/review 操作封装 [修改]
  security.py          # UI 错误脱敏 [新增]

data_agent/
  cli.py               # CLI 入口，新增 ui 命令 [修改]
  reviews.py           # write_review 增加 target_type 参数 [修改]

tests/
  test_ui_status.py    # display_status 推导逻辑测试（14 tests）
  test_ui_readers.py   # readers 单元测试（10 tests）
  test_ui_preview.py   # preview 单元测试（新增 CSV fallback + 更新 model_result 测试）
  test_ui_security.py  # UI 安全脱敏测试（7 tests）[新增]
  test_cli_ui.py       # CLI ui 命令测试（3 tests）[新增]
  test_review_target.py # review target 测试（3 tests）[新增]

docs/
  ui_walkthrough.md    # UI 操作 walkthrough [新增]
```

## 5. UI 功能列表

| 功能 | 实现 | 说明 |
|------|------|------|
| workspace 输入 | sidebar text_input | 支持任意本地路径，环境变量预设 |
| workspace 状态 | sidebar metric + Overview tab | task 数、status 分布 |
| Ingest inbox | Ingest tab | 输入路径 + Ingest 按钮 |
| 文件上传 | Ingest tab | 多文件 uploader → 临时 inbox → ingest |
| Task 列表 | Tasks tab | dataframe + display_status + 筛选，自动加载 |
| Task Detail | Task Detail tab | raw/derived/runs/flags/relationships/reviews |
| raw CSV 预览 | Task Detail tab | preview_csv 前 50 行 |
| model_result 分区 | Task Detail tab | Audit/Risk/Extracted/Raw Response 四区 |
| Process task | Task Detail tab | 选 mode + Process 按钮 + rerun 说明 |
| Process all | Task Detail tab | Process All 按钮 |
| Review | Task Detail tab | 4 actions + reviewer + comment + target type/id |
| deprecate 确认 | Task Detail tab | 二次确认 checkbox |
| Model Profiles | Model Profiles tab | 表格（不泄露 key） |
| Marimo 命令 | Help tab | 命令展示 |
| Model mode 选择 | sidebar | local/auto/cloud |
| Refresh | sidebar | 重新扫描 |
| UI 错误脱敏 | 全局 | 所有错误不泄露 API key/secret |
| CLI 快捷启动 | data_agent ui | --workspace / --print-command |

## 6. 测试结果

```bash
.venv/bin/python -m pytest -q
```

```
174 passed in 8.81s
```

原有 112 passed 全部保持通过，本轮新增 16 个 tests（2 CSV fallback + 7 security + 3 CLI ui + 3 review target + 1 model result 更新）。

## 7. Demo Workflow 命令

```bash
# 准备工作区
rm -rf /tmp/material-agent-ui-ws
mkdir -p /tmp/material-agent-ui-ws

# ingest
.venv/bin/python -m data_agent ingest \
  --inbox "$DEMO_INBOX" \
  --workspace /tmp/material-agent-ui-ws

# process
.venv/bin/python -m data_agent process \
  --workspace /tmp/material-agent-ui-ws \
  --all --models local

# review
.venv/bin/python -m data_agent review \
  --workspace /tmp/material-agent-ui-ws \
  --task task_0001 \
  --action approve \
  --reviewer UI_TEST \
  --comment "frontend workflow smoke test"

# models check
.venv/bin/python -m data_agent models check \
  --workspace /tmp/material-agent-ui-ws
```

## 8. UI 启动命令

```bash
# 推荐：CLI 快捷命令
.venv/bin/python -m data_agent ui --workspace /tmp/material-agent-ui-ws

# 打印命令（不启动）
.venv/bin/python -m data_agent ui --workspace /tmp/material-agent-ui-ws --print-command

# 直接使用 Streamlit
.venv/bin/python -m streamlit run data_agent/ui/app.py
```

## 9. 手工 UI 验收检查项

> 验收日期：2026-07-10
> Workspace：/tmp/material-agent-ui-ws
> 启动命令：`.venv/bin/python -m data_agent ui --workspace /tmp/material-agent-ui-ws`
> Model mode：local
> 实际 task 数：由 demo inbox 决定
> pytest 结果：174 passed

- [ ] 能输入 /tmp/material-agent-ui-ws 作为 workspace
  - 实际结果：待 UI 验收确认
- [ ] 能看到 task list（实际 task 数取决于 inbox）
  - 实际结果：待 UI 验收确认
- [ ] 能选择 task_0001
  - 实际结果：待 UI 验收确认
- [ ] 能看到 raw files（CSV 预览前 50 行，image 直接展示）
  - 实际结果：待 UI 验收确认
- [ ] 能看到 derived files（model_result 分区展示）
  - 实际结果：待 UI 验收确认
- [ ] 能看到 processing runs
  - 实际结果：待 UI 验收确认
- [ ] 能看到 quality flags
  - 实际结果：待 UI 验收确认
- [ ] 能看到 review records
  - 实际结果：待 UI 验收确认
- [ ] 能看到 model profiles 状态
  - 实际结果：待 UI 验收确认
- [ ] 能显示 marimo command
  - 实际结果：待 UI 验收确认
- [ ] 能 process selected task（local 模式）
  - 实际结果：待 UI 验收确认
- [ ] 能写入 review（含 target type/id）
  - 实际结果：待 UI 验收确认
- [ ] 页面不显示任何真实 API key（所有错误脱敏）
  - 实际结果：待 UI 验收确认
- [ ] local 模式不发网络请求
  - 实际结果：待 UI 验收确认
- [ ] refresh 后数据仍正确
  - 实际结果：待 UI 验收确认

## 10. 安全性确认

- API key 始终显示 `configured/missing`，不泄露值
- `list_profile_status(show_values=False)` 传 False
- 所有 `st.error(...)` 调用均通过 `safe_ui_error()` 脱敏
- `actions.py` 异常消息均通过 `_safe_msg()` 脱敏
- `safe_ui_error()` 脱敏内容包括：`sk-...` token、`Bearer ...` header、环境变量名、环境变量真实值
- raw 文件只读，不可变
- 禁止字段在 model_result 展示中不存在
- 错误消息不包含 API key

## 11. 已知限制

- 目前是本地 Streamlit UI，不是生产级 Web App
- 没有用户登录
- 没有权限系统
- 没有大文件上传优化
- 没有异步任务队列
- 没有浏览器 E2E 自动化测试
- marimo 只提供命令入口，不自动启动
- 模型 API key 仍通过环境变量配置
- 图表 digitization 未实现

## 12. 下一步建议

- 增加任务执行进度条
- 增加 model_result 对比视图（rerun 前后）
- 增加批量 approve 操作
- 考虑 FastAPI + React 为生产环境迁移
