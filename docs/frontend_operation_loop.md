# Frontend Operation Loop

## UI 目标

为材料研发数据处理 Agent 提供本地 Streamlit Web UI，让用户完成：
1. 选择/创建 workspace
2. 上传文件或选择 inbox → ingest
3. 查看任务列表和状态
4. 选择模式触发处理
5. 查看 raw / derived / model_result / quality_flags
6. 对结果进行 review
7. 对单个任务 rerun
8. 获取 marimo 复核命令

## 页面结构

单页 Streamlit app，6 个 tab：

| Tab | 内容 |
|-----|------|
| Overview | workspace 路径、文件数、状态分布 |
| Ingest | inbox 目录选择 + 多文件上传 + 执行 |
| Tasks | 任务列表、display_status 筛选、选择 |
| Task Detail | raw/derived/runs/flags/relationships/reviews + Process/Review 按钮 |
| Model Profiles | 模型配置状态表（不泄露 key） |
| Help | marimo 命令 + 快速参考 |

## 数据流

```
UI (app.py)
  → readers.py   → package.py (load_manifest, get_*)
                  → model_adapters/profiles.py (load_profiles, list_profile_status)
  → status.py    → 纯推导（不写回）
  → preview.py   → 纯读取文件内容
  → actions.py   → db.py (init_db)
                  → ingest.py (ingest_inbox)
                  → process.py (process_all_tasks, process_single_task)
                  → reviews.py (write_review)
```

前端**不直接**：
- 写 SQLite 业务状态
- 修改 raw 文件
- 修改 schemas
- 修改 model_adapters
- 删除旧 L2

## 哪些操作调用哪些底层函数

| UI 操作 | 底层函数 |
|---------|----------|
| 查看 workspace | `read_workspace_summary()` → `load_manifest()` per task |
| 查看 task 列表 | `read_task_list()` → `load_manifest()` + `get_quality_flags()` |
| 查看 task 详情 | `read_raw_files()` / `read_derived_files()` / `get_*()` |
| Ingest inbox | `do_ingest()` → `init_db()` + `ingest_inbox()` |
| 上传文件 | `do_upload_ingest()` → 保存到临时目录 → `ingest_inbox()` |
| Process all | `do_process_all()` → `process_all_tasks()` |
| Process task | `do_process_task()` → `process_single_task()` |
| Review | `do_review()` → `write_review()` |
| Model profiles | `read_model_profiles()` → `load_profiles()` + `list_profile_status(show_values=False)` |

## display_status 推导逻辑

在 `status.py` 中，只基于 manifest/runs/flags/reviews 推导，不写回 manifest：

```
deprecate review 存在    → deprecated
return_for_rerun 存在   → returned_for_rerun
无 processing run       → ingested
有 requires_review flag + approve review → reviewed
有 requires_review flag                   → needs_review
有 failed run 或 model_unavailable flag   → failed_or_warning
有 approve review                         → reviewed
其他                                     → processed
```

## 安全说明

- `list_profile_status(show_values=False)` 始终传 False，API key 显示 `configured/missing`
- st.error 中不包含完整 traceback
- 上传文件不进入 cloud
- local 模式不触发网络请求
- raw 文件只读、不修改
- 禁止字段不出现在 model_result 展示中

## 已知限制

- 目前是本地 Streamlit UI，不是生产级 Web App
- 没有用户登录 / 权限系统
- 没有大文件上传优化（建议 <100MB）
- 没有异步任务队列
- 没有浏览器 E2E 自动化测试
- marimo 只提供命令入口，不自动启动
- 模型 API key 仍通过环境变量配置
- 图表 digitization 未实现
- Streamlit session_state 只做临时缓存，不做业务真相源
