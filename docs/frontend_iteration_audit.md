# Frontend Iteration Audit

## 1. 当前已有 CLI 能力

| CLI 命令 | 底层函数 | 用途 |
|----------|----------|------|
| `ingest --inbox` | `ingest_inbox()` | 扫描目录、创建 task、复制 L0→L1 |
| `process --all \| --task` | `process_all_tasks()` / `process_single_task()` | 分发处理 + 模型调用 |
| `review` | `write_review()` | 写入审核记录到 DB + JSON |
| `info` | `load_manifest()` per task | 读取所有 task 摘要表格 |
| `models check` | `load_profiles()` + `list_profile_status()` | 显示模型配置状态（不泄露 key） |
| `open --print-command` | subprocess | 打印 marimo 启动命令 |

## 2. 当前已有 evidence package 结构

```
task_XXXX/
  raw/          → L1 归档副本
  derived/      → L2 派生文件（带 run_<short>__ 前缀）
  logs/         → processing_runs.json, quality_flags.json, relationships.json, processing_report.md
  reviews/      → review_records.json
  manifest.json → 索引
```

## 3. 当前已有 model layer 能力

- 4 个角色：fast / best / vision / ocr
- 3 种模式：local（零网络）/ cloud（直连）/ auto（自动降级）
- Router 规则表
- Fallback 链
- ModelResult 完整 wrapper + 审计字段
- Quality flags（fallback / unavailable / low_confidence / forbidden_keys）
- 递归 redaction + forbidden key sanitize

## 4. 前端可以复用的函数

**只读（前端直接调用）：**
- `load_manifest(task_dir) → TaskManifest`
- `get_processing_runs(task_dir) → list[dict]`
- `get_quality_flags(task_dir) → list[dict]`
- `get_relationships(task_dir) → list[dict]`
- `get_review_records(task_dir) → list[dict]`
- `load_profiles() → dict[str, ModelProfile]`
- `list_profile_status(profile, show_values=False) → dict`
- `is_profile_available(profile) → bool`

**写操作（前端通过 actions.py 封装）：**
- `init_db(ws) → Connection`
- `ingest_inbox(inbox, ws, conn) → list[str]`
- `process_all_tasks(ws, mode) → int`
- `process_single_task(ws, tid, mode) → bool`
- `write_review(ws, tid, action, reviewer, comment) → ReviewRecord`

## 5. 本轮不应该改的底层模块

- `data_agent/process.py`
- `data_agent/processors/*`
- `data_agent/model_adapters/*`
- `data_agent/ingest.py`
- `data_agent/db.py`（schema 不变）
- `data_agent/schemas.py`
- `data_agent/reviews.py`
- `marimo_apps/`

## 6. 本轮最终 UI 页面列表

单页 Streamlit app，6 个 tab：

1. **Overview** — workspace 状态摘要
2. **Ingest** — inbox 路径选择 + 文件上传 + 执行 ingest
3. **Tasks** — task 列表（可筛选、可选择）
4. **Task Detail** — 选中 task 的完整详情 + process / review 操作
5. **Model Profiles** — 模型配置状态
6. **Help** — marimo 命令 + 启动说明
