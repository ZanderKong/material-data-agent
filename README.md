# Material R&D Data Processing Agent MVP

本地材料研发数据处理 Agent，接收 demo 数据，生成可追溯 evidence package。

## 环境要求

- Python >= 3.10

## 安装

```bash
python3.10 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## 当前验收状态

- **基础 demo 闭环**：ingest → process → review → info
- **Model Service Layer 已实现**：可配置模型角色、路由、fallback
- **Streamlit Local UI 已实现**：6-tab 前端，支持 ingest/upload/process/review/查看
- **pytest**：180 passed（2026-07-10 全量运行结果）
- **L2 版本化输出**：已实现（run 前缀）
- **Rerun replaces/replaced_by**：已实现
- **Marimo 复核命令**：可生成
- **FRONTEND_CHECK.md**：前端验收记录
- **MODEL_LAYER_CHECK.md**：模型服务层验收记录（历史 checkpoint: 2026-07-09, 112 passed）
- **docs/ui_walkthrough.md**：UI 操作 walkthrough

## 快速开始

```bash
# 查看命令
.venv/bin/python -m data_agent --help

# 初始化 ingest
.venv/bin/python -m data_agent ingest \
  --inbox "/Users/zanderkong/Desktop/数据处理agent/material_data_agent_demo 测试数据/inbox" \
  --workspace work/check-ws

# 处理全部任务
.venv/bin/python -m data_agent process \
  --workspace work/check-ws \
  --all \
  --models local

# 查看任务信息
.venv/bin/python -m data_agent info --workspace work/check-ws

# 审核任务
.venv/bin/python -m data_agent review \
  --workspace work/check-ws \
  --task task_0001 \
  --action approve \
  --reviewer ZQ \
  --comment "demo approval"

# 打开 marimo 复核工作台
.venv/bin/python -m data_agent open \
  --workspace work/check-ws \
  --task task_0001

# 重跑任务（验证 L2 版本化）
.venv/bin/python -m data_agent process \
  --workspace work/check-ws \
  --task task_0007 \
  --models local
```

## 运行测试

```bash
.venv/bin/python -m pytest -q
```

## 完整验收命令

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
```

## Local UI

项目提供 Streamlit 本地 Web UI，可替代 CLI 进行日常操作。

### 启动 UI

```bash
# 推荐：CLI 快捷命令
.venv/bin/python -m data_agent ui --workspace /tmp/material-agent-ui-ws

# 打印命令（不启动）
.venv/bin/python -m data_agent ui --workspace /tmp/material-agent-ui-ws --print-command

# 直接使用 Streamlit
.venv/bin/python -m streamlit run data_agent/ui/app.py
```

### Demo workspace 验收命令

```bash
# 准备工作区
rm -rf /tmp/material-agent-ui-ws
mkdir -p /tmp/material-agent-ui-ws

# CLI ingest
.venv/bin/python -m data_agent ingest \
  --inbox "$DEMO_INBOX" \
  --workspace /tmp/material-agent-ui-ws

# CLI process (local mode)
.venv/bin/python -m data_agent process \
  --workspace /tmp/material-agent-ui-ws \
  --all --models local

# 启动 UI
.venv/bin/python -m data_agent ui \
  --workspace /tmp/material-agent-ui-ws
```

### UI 功能

- **workspace 输入**：选择或输入本地路径，支持 `DATA_AGENT_UI_WORKSPACE` 环境变量预设
- **ingest / upload**：从 inbox 目录或直接上传文件
- **task 列表**：按 display_status 筛选和排序，进入 workspace 后自动加载
- **task detail**：查看 raw/derived/runs/flags/relationships/reviews
  - raw CSV 预览前 50 行（表格形式）
  - model_result 分区展示（Audit / Risk / Extracted Output / Raw Response）
- **review**：支持 target type（task / quality_flag / data_object / derived_file），可选 target id
- **model profiles**：查看配置状态（不泄露 API key）
- **marimo command**：查看 marimo 复核工作台启动命令
- **错误脱敏**：所有 UI 错误提示经过安全脱敏，不泄露 API key、Bearer token 或环境变量值

### UI 模式

UI 中可选择 `local` / `auto` / `cloud` 模式，行为与 CLI 一致：
- `local`：零网络调用
- `auto`：优先云端、自动降级
- `cloud`：仅云端

### 相关文档

- `FRONTEND_CHECK.md`：前端验收记录
- `MODEL_LAYER_CHECK.md`：模型服务层验收记录
- `docs/ui_walkthrough.md`：UI 操作 walkthrough

## 项目结构

```
data_agent/
  ui/                # Streamlit 前端
  schemas.py         # Pydantic 数据模型
  db.py              # SQLite 注册系统
  package.py         # Evidence package 读写
  classify.py        # 文件类型识别
  ingest.py          # 输入文件注册
  process.py         # 统一处理编排
  reviews.py         # 审核记录
  reports.py         # 处理报告生成
  processors/        # 各类型数据处理
  model_adapters/    # 模型适配器 (本地/云端)
marimo_apps/         # Marimo 复核工作台
tests/               # 测试
```

## 生命周期模型

- **L0**: 原始文件登记（inbox 源路径记录）
- **L1**: 不可变归档副本（raw/ 下文件）
- **L2**: 派生处理结果（derived/ 下带 run 前缀文件）
- **L3**: 废弃/失败/替代状态（标记，不删除）

## Model Service Layer

### 配置模型服务

1. 复制模板文件：
```bash
cp .env.example .env
cp model_profiles.yaml.example model_profiles.yaml
```

2. 编辑 `.env`，填入真实的 API 地址和密钥（**切勿提交到仓库**）：
```bash
BEST_MODEL_BASE_URL=https://api.openai.com/v1
BEST_MODEL_API_KEY=sk-xxxxxxxx
BEST_MODEL_NAME=gpt-4
# ... 其他模型类似
```

3. 检查模型配置状态：
```bash
python3 -m data_agent models check --workspace work/check-ws
python3 -m data_agent models check --workspace work/check-ws --verbose
```

### 三种模型模式

| 模式 | 说明 |
|------|------|
| `local` | 仅使用本地规则和 stub，不发起任何网络请求（默认） |
| `cloud` | 尝试调用已配置的云端模型，失败时记录错误但不崩溃 |
| `auto` | 优先使用云端模型，自动降级至本地 stub（推荐生产环境） |

```bash
python3 -m data_agent process --workspace work/check-ws --all --models local
python3 -m data_agent process --workspace work/check-ws --all --models cloud
python3 -m data_agent process --workspace work/check-ws --all --models auto
```

### 模型角色与路由

| 数据类型 | local 模式 | cloud/auto 模式 |
|----------|-----------|-----------------|
| 样品元数据 | 无模型 | 无模型 |
| 原始数值 | 无模型 | 无模型 |
| 原始光谱 | 无模型 | 无模型 |
| 图表截图 | local_stub | OCR + Vision |
| 表面照片 | local_vision_stub | Vision + OCR |
| 观测文本 | 无模型 | Fast |
| 结构化观测 | 无模型 | 无模型 |

### 无密钥降级

当 `model_profiles.yaml` 缺失或 API 密钥未配置时：
- `local` 模式正常运行
- `cloud` 模式记录 "model_unavailable"，处理继续
- `auto` 模式自动降级至本地 stub

### OpenAI 兼容端点（中国大陆用户示例）

支持任何 OpenAI 兼容 API，如 DeepSeek、智谱 GLM、通义千问、Kimi 等。在 `.env` 中配置相应 endpoint 即可。

## 注意事项

- 不修改原始 demo 文件
- 重跑不覆盖旧 L2，生成新 L2 + replaces relationship
- 不输出科研结论或机理解释
- 云端模型为可选增强，本地流程必须可完整跑完
- **严禁将真实 API Key 写入仓库文件**，仅存储在 `.env`
- `model_profiles.yaml` 和 `.env` 已加入 `.gitignore`
