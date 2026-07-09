# FRONTEND_CHECK.md：前端操作闭环验收报告

## 1. 本轮目标

为材料研发数据处理 Agent 增加 Streamlit 本地前端操作闭环。

## 2. 本轮不做事项

- 不重写 ingest / process / review 主流程
- 不改 SQLite schema
- 不扩展模型路由
- 不做用户登录/权限
- 不做 API key 加密存储
- 不做浏览器 E2E 测试
- 不替换 marimo

## 3. 新增文件列表

```
data_agent/ui/
  __init__.py          # 包初始化
  app.py               # Streamlit 主入口（6 tab）
  readers.py           # 读取 workspace/tasks/manifest/logs helpers
  status.py            # display_status 推导逻辑
  preview.py           # 文件预览（image/csv/json/text/model_result）
  actions.py           # ingest/process/review 操作封装

tests/
  test_ui_status.py    # display_status 推导逻辑测试（14 tests）
  test_ui_readers.py   # readers 单元测试（10 tests）
  test_ui_preview.py   # preview 单元测试（14 tests）

docs/
  frontend_iteration_audit.md   # 审计文档
  frontend_operation_loop.md    # 完整前端文档
```

## 4. UI 功能列表

| 功能 | 实现 | 说明 |
|------|------|------|
| workspace 输入 | sidebar text_input | 支持任意本地路径 |
| workspace 状态 | sidebar metric + Overview tab | task 数、status 分布 |
| Ingest inbox | Ingest tab | 输入路径 + Ingest 按钮 |
| 文件上传 | Ingest tab | 多文件 uploader → 临时 inbox → ingest |
| Task 列表 | Tasks tab | dataframe + display_status + 筛选 |
| Task Detail | Task Detail tab | raw/derived/runs/flags/relationships/reviews |
| Process task | Task Detail tab | 选 mode + Process 按钮 |
| Process all | Task Detail tab | Process All 按钮 |
| Review | Task Detail tab | 4 actions + reviewer + comment |
| deprecate 确认 | Task Detail tab | 二次确认 checkbox |
| Model Profiles | Model Profiles tab | 表格（不泄露 key） |
| Marimo 命令 | Help tab | 命令展示 |
| Model mode 选择 | sidebar | local/auto/cloud |
| Refresh | sidebar | 重新扫描 |

## 5. 测试结果

```bash
.venv/bin/python -m pytest -q
```

```
158 passed in 2.75s
```

新增 38 个 tests（14 status + 10 readers + 14 preview），原有 112 个全部通过。

## 6. Demo Workflow 命令

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

## 7. UI 启动命令

```bash
.venv/bin/python -m streamlit run data_agent/ui/app.py
```

## 8. 手工 UI 验收检查项

- [ ] 能输入 /tmp/material-agent-ui-ws 作为 workspace
- [ ] 能看到 task list（9 tasks）
- [ ] 能选择 task_0001
- [ ] 能看到 raw files
- [ ] 能看到 derived files
- [ ] 能看到 processing runs
- [ ] 能看到 quality flags
- [ ] 能看到 review records
- [ ] 能看到 model profiles 状态
- [ ] 能显示 marimo command
- [ ] 能 process selected task
- [ ] 能写入 review
- [ ] 页面不显示任何真实 API key
- [ ] local 模式不发网络请求
- [ ] refresh 后数据仍正确

## 9. 安全性确认

- API key 始终显示 `configured/missing`，不泄露值
- `list_profile_status(show_values=False)` 传 False
- raw 文件只读，不可变
- 禁止字段在 model_result 展示中不存在
- 错误消息不包含 API key

## 10. 已知限制

- 目前是本地 Streamlit UI，不是生产级 Web App
- 没有用户登录
- 没有权限系统
- 没有大文件上传优化
- 没有异步任务队列
- 没有浏览器 E2E 自动化测试
- marimo 只提供命令入口，不自动启动
- 模型 API key 仍通过环境变量配置
- 图表 digitization 未实现

## 11. 下一步建议

- 增加 `python -m data_agent ui --workspace <path>` CLI 命令快捷启动
- 增加任务执行进度条
- 增加 model_result 对比视图（rerun 前后）
- 增加批量 approve 操作
- 考虑 FastAPI + React 为生产环境迁移
