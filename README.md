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

- 基础 demo 闭环已通过：ingest → process → review → info
- 全部 `pytest -q` 通过
- L2 版本化输出（run 前缀）已实现
- Rerun 替代关系（replaces/replaced_by）已实现
- Marimo 复核工作台可启动（`--print-command` 可 dry-run）
- **最终交付以 `DELIVERY_PLAN.md` 为准**

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

## 项目结构

```
data_agent/          # 核心处理逻辑
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

## 注意事项

- 不修改原始 demo 文件
- 重跑不覆盖旧 L2，生成新 L2 + replaces relationship
- 不输出科研结论或机理解释
- 云端模型为可选增强，本地流程必须可完整跑完
