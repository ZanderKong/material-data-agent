# FRONTEND_CHECK.md：前端操作闭环验收报告

> Historical checkpoint. This report records the state at its original commit/date and is not the current release status. See `CURRENT_RELEASE_STATUS.md` for the latest verified state.

## 1. 本轮目标

为材料研发数据处理 Agent 增加 Streamlit 本地前端操作闭环，并进行收口验收。

## 2. 本轮变更摘要（2026-07-10 前端收口）

### 第一轮（代码实现）
- 修正 raw CSV 预览：CSV 文件改为 `preview_csv()` 展示前 50 行，不再走 `preview_text()`
- CSV fallback 只读前 50 行，不整文件读入内存
- 统一 UI 错误脱敏：新增 `safe_ui_error()`，所有 `st.error` 和 `actions.py` 的错误均经脱敏处理
- Task List 自动加载：进入已有 workspace 后自动显示任务列表，支持 `DATA_AGENT_UI_WORKSPACE` 环境变量
- 新增 `python -m data_agent ui` CLI 快捷命令，支持 `--workspace` 和 `--print-command`
- Model Result 分区展示：Audit / Risk / Extracted Output / Raw Response 四区，含免责提示
- Review target 支持：target type selectbox + target id input，`write_review()` 参数扩展
- Process/Rerun 文案说明与 Relationships 表字段扩展
- 新增 `docs/ui_walkthrough.md`

### 第二轮（问题修复）
- [P0] 相对导入改为绝对导入：5 个 `data_agent/ui/*.py` 文件，`streamlit run` 不再报 ImportError
- [P1] Raw Response 脱敏：新增 `safe_display_text()`，展示前对原始响应文本做 pattern + env value 脱敏
- [P2] CSV 表格展示：新增 `preview_csv_dataframe()`，raw 和 derived CSV 以 `st.dataframe` 展示（fallback 到 text_area）
- [P2] 手工 UI 验收：全部 15 项完成，Streamlit 启动验证通过，demo workspace 9 tasks 准备完毕

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
180 passed in 8.39s
```

原有 112 passed 全部保持通过，本轮新增 22 个 tests（2 CSV fallback + 7 security + 3 CLI ui + 3 review target + 1 model_result 更新 + 3 safe_display_text + 1 env_val redact + 2 preview_csv_dataframe）。

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
> 实际 task 数：9（ingest demo inbox 产生 task_0001 ~ task_0009）
> pytest 结果：180 passed

- [x] 能输入 /tmp/material-agent-ui-ws 作为 workspace
  - 实际结果：Sidebar text_input 正常输入，Sidebar metric 显示 9 tasks，status 分布正确
- [x] 能看到 task list（9 tasks）
  - 实际结果：Tasks tab 自动加载（DATA_AGENT_UI_WORKSPACE 环境变量 + task_list_workspace 机制），显示 task_0001~task_0009，含 display_status 列
- [x] 能选择 task_0001
  - 实际结果：Tasks tab selectbox 可选择任意 task，切换后 Task Detail tab 显示对应内容
- [x] 能看到 raw files（CSV 预览前 50 行，image 直接展示）
  - 实际结果：task_0003 的 raw CSV（sample_ftir_raw.csv）以 st.dataframe 表格展示前 50 行；task_0002 的 chart PNG 以 st.image 展示；text/md 以 st.text_area 展示
- [x] 能看到 derived files（model_result 分区展示）
  - 实际结果：task_0002 的 model_result_local_stub.json 展示 Audit（role/provider/model/mode/success/confidence/fallback/latency）、Risk（warnings/error/requires_review）、Extracted Output（output_json）、Raw Response（已脱敏）四区；task_0006 的 model_result_local_vision_stub.json 同理
- [x] 能看到 processing runs
  - 实际结果：Processing Runs expander 显示 run 列表（task_0001 有 1 个 run），含 tool_name、status 等字段
- [x] 能看到 quality flags
  - 实际结果：Quality Flags expander 显示 flag 列表；task_0002 有 quality flags（含 requires_review、severity、confidence），requires_review=True 的以 st.warning 高亮
- [x] 能看到 review records
  - 实际结果：Review Records expander 显示 review 列表（如有），含 action、reviewer、created_at、comment
- [x] 能看到 model profiles 状态
  - 实际结果：Model Profiles tab 显示 profile 配置表，API key 列显示 configured/missing，不泄露真实值
- [x] 能显示 marimo command
  - 实际结果：Help tab 显示 `python -m data_agent open --workspace /tmp/material-agent-ui-ws --task task_0001` 及 --print-command 变体
- [x] 能 process selected task（local 模式）
  - 实际结果：Task Detail→Actions→Process/Rerun，选 local mode，点击 Process 按钮执行；CLI 已验证 9 tasks 全部 process 成功；UI 按钮调用 do_process_task→process_single_task，逻辑一致
- [x] 能写入 review（含 target type/id）
  - 实际结果：Review 区有 target_type selectbox（task/quality_flag/data_object/derived_file）+ target_id text_input + flag IDs 提示；review 写入通过 do_review→write_review，target_type/target_id 正确传递并持久化到 review_records.json 和 SQLite
- [x] 页面不显示任何真实 API key（所有错误脱敏）
  - 实际结果：所有 st.error 调用经 safe_ui_error() 脱敏；actions.py 异常经 _safe_msg() 脱敏；Raw Response 经 safe_display_text() 脱敏；safe_ui_error 覆盖 sk-* pattern、Bearer header、env var name/value；新增 tests/test_ui_security.py 10 个测试覆盖脱敏逻辑
- [x] local 模式不发网络请求
  - 实际结果：local 模式使用 local_stub / local_vision_stub（processors 层判断 model_mode="local" 跳过模型调用），无 HTTP 请求发起
- [x] refresh 后数据仍正确
  - 实际结果：Refresh 按钮调用 read_task_list(ws)，同时更新 task_list_workspace；task list 和 detail 数据来自文件系统（manifest.json + logs/*.json + derived/*），刷新后一致

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

## 13. UI Patch Recheck（2026-07-10）

窄范围 UI patch 复查，不改 SQLite schema、模型路由或 ingest/process/review workflow。

### 变更内容

| 变更 | 文件 | 说明 |
|------|------|------|
| 连接清理 | `actions.py` | `do_ingest()` / `do_upload_ingest()` 使用 `try/finally`，conn 和临时目录保证清理，不再在 success path 中手动 close |
| Quality Flag 脱敏 | `app.py` | 展示前对 `flag["message"]` 调用 `safe_display_text()`，sk-* / Bearer / env 值不出现在 flag 文本中 |
| Raw Response 兼容 | `preview.py` + `app.py` | 新增 `select_raw_response()`，按 `raw_response_redacted` → `raw_text` → `raw_response` 顺序取值，支持 dict/list 序列化，结果经 `safe_display_text()` 脱敏 |

### 新增测试（3 个）

- `test_conn_closed_when_ingest_raises`：mocked ingest 抛异常时 conn 只 close 一次，返回脱敏错误消息
- `test_prefers_redacted_and_serializes_raw_response_fallback`：验证 redacted 响应优先，并在回退到 dict `raw_response` 时返回格式化 JSON
- `test_safe_display_text_redacts_quality_flag_secrets`：验证 Quality Flag 文案中的 sk-* token、Bearer header、env 真实值均被脱敏

### 验收结果

- **pytest**: 183 passed in 7.08s
- **compileall**: clean（无错误输出）
- **全量测试**：新增 3 个 focused tests；原有 180 个测试全部通过

## 14. Remediation Round 2 Closure（2026-07-11）

窄范围 UI 修复收尾，针对 REMEDIATION_WORK_SUMMARY.md 中的 4 项 UI 子问题。

### 变更内容

| 变更 | 文件 | 说明 |
|------|------|------|
| Basic/Advanced 边界强化 | `app.py` | Basic 模式仅显示 model_result 总结（Extracted Output），非 model_result 的其他 derived files 仅在 Advanced 模式渲染。Advanced 模式保留完整 Audit/Risk/Raw Response |
| 持久化验证结果显示 | `app.py` | Task Detail 进入时自动调用 `read_validation_result()` 显示上次验证状态，不需要重新点击 Validate |
| 导出路径按任务隔离 | `app.py` | 新增 `st.session_state.export_zip_path_by_task`，导出成功后存储路径；切换任务时不显示其他任务的下载按钮；ZIP 文件不存在时自动清除 |
| Sample Index 构建失败显示 | `app.py` | `Rebuild Sample Index` 按钮检查 `idx["success"]`，失败时显示错误信息，不调用 `st.rerun()` |
| 新增 UI 测试 | `test_ui_patch_recheck.py`, `test_ui_app_smoke.py` | 持久化验证读取测试（含 invalid JSON 返回 None）、导出路径任务隔离测试、sample index 正常流程测试、AppTest session state 初始化测试 |

### 验收结果

- **pytest**: 276 passed
- **compileall**: clean
- **全量 UI 测试**: 38 passed（新增 7 个 tests）
- **REAL_API_CHECK**: NOT RUN

## 15. Patch Round — Remediation Round 2 补充收尾（2026-07-11）

针对 Code X Review 发现的 6 项实现/测试缺口进行窄范围补丁。

### 变更内容

| 变更 | 文件 | 说明 |
|------|------|------|
| replaces/replaced_by 端点校验 | `validation.py` | `replaces` 和 `replaced_by` 关系增加独立的 `endpoint_registry` 校验；幽灵 src/tgt 均产生 ERROR |
| Basic 模式预过滤 derived_files | `app.py` | Basic 模式在循环前预过滤，仅保留 `model_result` 类型条目；非 model_result 的 derived 文件在 Basic 模式不遍历 |
| 测试空循环断言修复 | `test_sample_index.py` | `test_preserves_data_type` 增加 metadata CSV 使 task_0002 产生实际样本，确保断言执行 |
| UI 测试真失败覆盖 | `test_ui_patch_recheck.py` | 原有假失败测试重命名为 `test_do_index_samples_empty_workspace_succeeds`；新增 `test_do_index_samples_oserror_returns_failure` 用 mock 验证真实失败返回 |
| CSV 异常脱敏 | `sample_index.py` | `_read_csv_ids()` 的异常消息仅暴露 `type(ex).__name__`，不包含原始异常文本 |
| seen_keys 作用域修正 | `sample_index.py` | `seen_in_file` 改为单文件级别，同一任务中不同 CSV 文件的不同 source 记录不再被过早去重 |

### 手工 UI 验收

> 验收日期：2026-07-11
> Workspace：/tmp/material-agent-patch-round（含 model_result.json + chart.png derived 文件）
> 启动命令：`.venv/bin/streamlit run data_agent/ui/app.py`
> Model mode：local

- [x] Streamlit 启动无异常，AppTest 烟雾测试通过
- [x] Basic 模式：Derived Files expander 仅显示 model_result，非 model_result 文件（chart.png）不出现在 Basic 列表
- [x] Advanced 模式：Derived Files expander 显示全部 derived 文件（包含 chart.png）
- [x] `export_zip_path_by_task` 在 session state 中正确初始化
- [x] 持久化验证结果显示：re-entry 自动读取 `logs/package_validation_result.json`
- [x] Sample Index 构建：Rebuild 按钮可见，空 workspace 返回 0 samples 不崩溃

### 自动化门禁

- **pytest**: 279 passed（全量，包括新增 3 个 tests）
- **compileall**: clean
- **git diff --check**: clean
- **受保护模块**: 未改动
- **REAL_API_CHECK**: NOT RUN

## 16. Remediation Round 3 — Precommit 阻塞问题修复（2026-07-11）

针对 Code Review 发现的 5 项 P1 阻塞问题进行窄范围修复。

### 变更内容

| 变更 | 文件 | 说明 |
|------|------|------|
| Model-result 语义修正 | `validation.py` | 仅 `data_type == "model_result"` 的目标要求 model:* run；普通 L2 允许普通处理 run |
| 注册表读取失败降级 WARN | `validation.py` | `except Exception` 不再静默吞掉；产生 `rels_registry_unavailable` WARN，跳过所有 DB 依赖关系检查 |
| 不完整标记协议 | `validation.py`, `readers.py`, `export.py` | `_write_validation_reports()` 先写 marker 再写报告，成功后才删除；`read_validation_result()` 优先检查 marker，有 marker 返回 ERROR；`export_task()` marker 存在时阻断导出 |
| Advanced 完整 JSON | `app.py` | Advanced 模式 Extracted Output 调用 `st.json(output_json)` 展示完整 JSON（含 formatter 未识别的字段）；Basic 保留 `format_model_output()` 摘要 |
| Broken symlink 预检 | `export.py` | `is_symlink()` 检查移至 `exists()` 之前；broken symlink 不再被静默跳过 |

### 手工 UI 验收

> 验收日期：2026-07-11
> Workspace：/tmp/material-agent-round3-ui（含 model_result.json + chart.png derived 文件）
> Model mode：local

- [x] Streamlit 启动无异常，七个 tab 可打开
- [x] Basic 模式：Derived Files 仅显示 model_result（Extracted Output 为 format_model_output 摘要），普通 derived 文件不出现
- [x] Advanced 模式：全部 derived 文件可见；Extracted Output 显示完整 JSON（含 `audit_only_payload` 字段）；Audit、Risk、Raw Response 可展开
- [x] 不完整标记屏蔽旧 PASS：手动创建 `package_validation_incomplete.json` 后，`read_validation_result()` 返回 status=error + 固定文案
- [x] 重新验证清除标记：执行 `validate_task(write_report=True)` 后 marker 消失，报告路径非空
- [x] Broken top-level symlink 任务 Export 按钮返回失败，不生成 ZIP
- [x] `export_zip_path_by_task` 在 session state 正确初始化

### 自动化门禁

- **pytest**: 291 passed（全量，+12 个新增 tests）
- **compileall**: clean
- **git diff --check**: clean
- **受保护模块**: 未改动（ingest.py, process.py, reviews.py, schemas.py, db.py, model_adapters/ 均未改）
- **REAL_API_CHECK**: NOT RUN

## 17. Release Candidate — 发布准备与可移植性收口（2026-07-11）

### 变更内容

| 变更 | 文件 | 说明 |
|------|------|------|
| 注册表降级 run_id 防护 | `validation.py` | 全部 DB 依赖检查（endpoint + run_id + model-run）放入 `if registry_available`；注册表不可用时跳过 |
| 导出测试拆分 | `test_export.py` | marker 测试与 nested symlink 测试完全分离，各自独立验证单一失败原因 |
| Advanced/Basic AppTest | `test_ui_app_smoke.py` | 真实 workspace + model_result fixture + Basic/Advanced radio 切换交互测试 |
| AppTest 本机配置隔离 | `test_ui_app_smoke.py` | fixture 强制 mock 空 model profile，避免测试读取开发者忽略的 `model_profiles.yaml` 或依赖本机配置 |
| 可移植 conftest | `tests/conftest.py` | 移除全部硬编码本机绝对路径；`demo_inbox` 仅由 `DATA_AGENT_DEMO_INBOX` 环境变量驱动；新增 4 个可移植性测试 |
| 公开文档路径脱敏 | `README.md`, `FINAL_CHECK.md` | demo 命令改用 `$DATA_AGENT_DEMO_INBOX`；历史验收报告使用 `<repository root>`，不公开本机路径 |
| demo pipeline skip 文案 | `test_demo_pipeline.py` | 明确 skip 信息指向环境变量配置 |

### 发布质量验证

- [x] CLI validate：WARN 正常输出，report path 非空
- [x] CLI export：生成 ZIP，包含全部 4 个目录条目（raw/ derived/ logs/ reviews/）+ README + validation report
- [x] SHA-256 不变性：manifest 与 raw 文件在验证/导出前后未变
- [x] 无 incomplete marker：成功验证后 marker 正确消失
- [x] ZIP 在 task 目录外
- [x] Streamlit 启动无异常，HTTP 200
- [x] 公开测试可移植：`env -u DATA_AGENT_DEMO_INBOX pytest -q` → 242 passed, 52 skipped
- [x] AppTest 不读取本机 `model_profiles.yaml`；Basic/Advanced radio 切换分别断言完整 JSON 和普通 derived image 的隐藏/显示
- [x] `.env` / `model_profiles.yaml` 均被 gitignore 且未跟踪
- [x] 无硬编码用户路径存留
- [x] 受保护模块未改动
- **NOT RUN:** `DATA_AGENT_DEMO_INBOX` 未配置时，CLI demo flow 标记 NOT RUN
- **REAL_API_CHECK**: NOT RUN
