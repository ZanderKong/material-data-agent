# Deepseek 下一步执行计划：模型服务层审计闭环

## 0. 给 Deepseek 的工作定位

你要做的是一次 **修复型收口**，不是新功能开发。

当前项目已经完成材料研发数据处理 Agent 的 MVP 主流程：

- ingest: 原始文件进入 workspace，生成 task 与 L0/L1 证据链。
- process: 按数据类型生成 L2 派生结果。
- review: 写入审核记录。
- evidence package: `manifest.json`、`logs/*.json`、SQLite 同步记录。
- rerun: 已有基础 `replaces/replaced_by` 关系。
- model service layer: 已接入模型 profile、router、OpenAI-compatible provider、本地 stub 和 `models check` CLI。

但模型服务层的审计记录还不可靠。本轮目标是让模型输出满足可追溯、可复核、不会泄密、不会破坏本地流程。

## 1. 不要做的事

本轮不要扩大范围：

- 不要引入 LangChain、CrewAI 或任何通用 agent 框架。
- 不要改 SQLite schema，不要写 migration。
- 不要重写 `ingest`、`review`、`reports` 或 evidence package 架构。
- 不要改 raw numeric、raw spectral、sample metadata 的处理行为。
- 不要实现真实 OCR、图表曲线 digitization、前端或新的 UI。
- 不要生成科研结论、机理解释或实验建议。
- 不要把真实 API key 写入仓库、SQLite、JSON、Markdown、CLI 输出或异常信息。
- `local` 模式绝对不能发起网络请求。

## 2. 当前已确认的问题

这些问题都能从当前代码或 `work/model-check` 产物中验证：

- `data_agent/process.py` 里模型 run 使用 `ProcessingRun(run_id="")`，导致 SQLite 主键冲突，多个模型 run 互相覆盖。
- `work/model-check` 当前显示：`model_result` data object 有 10 个，但 `tool_name like "model:%"` 的 processing run 只有 1 个，且存在空 `run_id`。
- 多个 `manifest.json` 的 `run_ids` 含空字符串。
- `derived/*model_result*.json` 只保存 `result.output_json`，丢失 `role/provider/model/mode/success/error/fallback/token_usage/schema_version/prompt_version` 等审计字段。
- model result 的 `derived_from` relationship metadata 目前写的是父 processor run id，不是对应的 model run id。
- `data_agent/model_adapters/local.py` 和 `cloud_stub.py` 仍导入不存在的 `ChartImageAnalyzer`，并使用旧的 `ModelResult(data=...)` 形状。
- `tests/test_model_evidence.py::test_local_makes_no_network_calls` 是空测试。
- 错误路径中的 HTTP response text / RequestException message 没有稳定 redaction。
- 现有 key 泄漏测试多搜索 `sk-`，不能覆盖非 `sk-` 格式密钥。
- `local_ocr_stub` 与 `local_vision_stub` 把不可用状态标成 `success=True`，审计语义不准确。
- `process.py` 有模块级 `_PROFILES_CACHE`，测试改 env/config 时可能读到旧配置。
- 现有 replacement 逻辑按主 processor subtype 找旧 L2，再把所有新 L2 都连过去，可能把 model result 和 chart metadata 错配。
- `.gitignore` 只忽略 `work/check-ws/`，当前 `work/` 验证产物仍会作为未跟踪文件出现。

## 3. 推荐执行顺序

严格按下面顺序做。每一步完成后先跑对应小测试，再继续。

### P0.1 修复模型 ProcessingRun run_id

涉及文件：

- `data_agent/process.py`
- `tests/test_model_evidence.py`

具体改法：

- 在 `_call_model_roles()` 中删除 `ProcessingRun(run_id="", ...)`。
- 让 `ProcessingRun` 使用默认 UUID，或显式传入新的 UUID；不要传空字符串。
- 每一个 model result L2 object 必须有一个对应的 `tool_name="model:<role>"` processing run。
- `model_run.output_data_ids` 必须包含该 model result object id。
- `manifest.run_ids` 不允许追加空字符串。

新增或更新测试：

- `count(data_objects where data_type="model_result") == count(processing_runs where tool_name like "model:%")`
- `processing_runs.run_id=""` 数量为 0。
- 所有 `manifest.json` 的 `run_ids` 中没有空字符串。

### P0.2 保存完整 ModelResult 审计 JSON

涉及文件：

- `data_agent/process.py`
- `data_agent/model_adapters/redaction.py`
- `tests/test_model_evidence.py`

具体改法：

- 不要再把 `result.output_json` 直接写入 `derived/run_*__model_result_<role>.json`。
- 写入 redacted 的完整 `result.model_dump(mode="json")`。
- 模型抽取内容必须继续放在 `output_json` 下。
- 顶层至少包含：
  - `success`
  - `role`
  - `provider`
  - `model`
  - `mode`
  - `input_type`
  - `output_json`
  - `raw_text`
  - `raw_response`
  - `confidence`
  - `warnings`
  - `error`
  - `fallback_used`
  - `fallback_from`
  - `latency_ms`
  - `token_usage`
  - `created_at`
  - `schema_version`
  - `prompt_version`
- 写入前递归移除禁止字段：
  - `final_conclusion`
  - `mechanism_explanation`
  - `experiment_recommendation`
- 写入前递归 redaction，确保 API key 不出现在任何深度。

建议实现：

- 在 `redaction.py` 中增加或增强递归函数，能同时处理 dict/list/string。
- 支持传入 `extra_secrets`，用于覆盖测试里不在环境变量中的密钥。
- `process.py` 写文件前调用这个 redaction/sanitize 层。

新增或更新测试：

- 每个 `*model_result*.json` 都有完整顶层字段。
- `output_json` 仍存在。
- 禁止字段在 JSON 任意深度都不存在。
- exact secret token 不出现在 derived JSON。

### P0.3 relationship metadata 指向正确 run

涉及文件：

- `data_agent/process.py`
- `tests/test_model_evidence.py`

具体改法：

- 普通 processor derived object 的 `derived_from` relationship metadata 保持 `{ "run_id": <processor_run_id> }`。
- model result derived object 的 `derived_from` relationship metadata 必须是 `{ "run_id": <model_run_id> }`。
- 不要弱化 L1 -> L2 的方向：仍然是 `source_id = l1_obj.object_id`，`target_id = l2_obj.object_id`。

建议实现：

- 在 `_process_task()` 中构建 `run_id_by_output_id`：
  - processor run 的所有 `output_data_ids` 映射到 `run.run_id`。
  - 每个 model run 的 `output_data_ids` 映射到对应 `model_run.run_id`。
- 插入 relationship 时根据 `derived.object_id` 取正确 run id。

新增或更新测试：

- 查询所有 model_result L2 的 `derived_from` relationship，metadata 中的 run id 必须存在于 `processing_runs`。
- 该 run 的 `tool_name` 必须以 `model:` 开头。

### P0.4 修复 replacement subtype 错配

涉及文件：

- `data_agent/process.py`
- `tests/test_model_evidence.py` 或 `tests/test_demo_pipeline.py`

具体改法：

- replacement 必须按新旧 L2 的同一 `subtype` 匹配。
- chart metadata 只能 replace 旧 chart metadata。
- `model_result_ocr` 只能 replace 旧 `model_result_ocr`。
- `model_result_vision` 只能 replace 旧 `model_result_vision`。
- 不要让 model result replace chart metadata，也不要让 chart metadata replace model result。

建议实现：

- 用 `new_obj.subtype` 分别查询旧 L2，而不是只用主 processor 的 `l2_subtype`。
- `_write_replacement_relationships()` 可以接收 `{subtype: old_l2_info}` 或在循环内按 `new_obj.subtype` 查询。
- 保留旧 L2 文件，不删除、不覆盖。

新增或更新测试：

- 对 chart image task 连续跑两次 local/auto，断言每个 subtype 只替换同 subtype 的旧对象。
- replacement relationship 两端 data object 的 subtype 必须相同。

### P1.1 修复 legacy adapter import

涉及文件：

- `data_agent/model_adapters/local.py`
- `data_agent/model_adapters/cloud_stub.py`
- `tests/test_model_provider_mock.py`

具体改法：

- 删除对 `ChartImageAnalyzer` 的依赖，或者只保留无需继承的兼容类。
- 把旧的 `ModelResult(data=...)` 改为新形状 `ModelResult(output_json=..., role=..., provider=...)`。
- 保持模块可 import。

新增测试：

```python
import data_agent.model_adapters.local
import data_agent.model_adapters.cloud_stub
```

### P1.2 补真正的 local no-network 测试

涉及文件：

- `tests/test_model_evidence.py`

具体改法：

- patch `data_agent.model_adapters.openai_compatible.requests.post`。
- 用临时 workspace 跑 `process_all_tasks(ws, "local")` 或最小任务处理。
- 断言 `requests.post` 未被调用。
- 这个测试必须在未来有人误接云端调用到 local path 时失败。

### P1.3 修复错误路径 redaction

涉及文件：

- `data_agent/model_adapters/openai_compatible.py`
- `data_agent/model_adapters/redaction.py`
- `tests/test_model_provider_mock.py`

具体改法：

- HTTP 非 200 时，`resp.text` 写入 `ModelResult.error` 前必须 redaction。
- `requests.RequestException` 的字符串写入前必须 redaction。
- `raw_text`、`raw_response`、`output_json` 中的字符串也应经过 secret redaction。
- 不要持久化 request headers、Authorization、完整 request payload。

新增测试：

- 设置一个 exact key，例如 `unit-test-secret-token-xyz`。
- mock HTTP 500 response text 包含该 key，断言 `ModelResult.model_dump_json()` 不包含 key。
- mock `RequestException` message 包含该 key，断言不包含 key。

### P1.4 强化 API key 泄漏测试

涉及文件：

- `tests/test_model_evidence.py`
- `tests/test_model_profiles.py`
- `tests/test_model_provider_mock.py`

具体改法：

- 不要只搜 `sk-`。
- 测试中使用 exact secret，例如 `unit-test-secret-token-xyz`。
- 搜索范围包括：
  - SQLite 所有相关表。
  - derived JSON。
  - logs JSON。
  - Markdown processing report。
  - `data_agent models check --verbose` 输出。

验收：

- exact secret 不出现在任何持久化文件或 CLI 输出中。

### P1.5 调整 stub 审计语义

涉及文件：

- `data_agent/model_adapters/stubs.py`
- `tests/test_model_provider_mock.py`
- `tests/test_model_evidence.py`

具体改法：

- `local_ocr_stub` 应表示 OCR 不可用：
  - `success=False`
  - `confidence=0.0`
  - `output_json.requires_review=True`
  - warnings 包含 `ocr_unavailable`
- `local_vision_stub` 应表示 vision 不可用：
  - `success=False`
  - `confidence=0.0`
  - `output_json.requires_review=True`
  - warnings 包含 `image_observation_requires_review` 或 `vision_unavailable`
- 主流程不能因为这些 model run failed 而中断。
- 可以保留通用 `local_stub` 为 `success=True`，因为它代表规则 fallback 成功生成了占位审计信息。

### P2.1 去掉 profile 全局缓存

涉及文件：

- `data_agent/process.py`

具体改法：

- 删除 `_PROFILES_CACHE`，或让 `_get_profiles()` 每次直接 `load_profiles()`。
- 本项目 config 很小，优先选择简单、可测试的 per-call load。

验收：

- 测试可以在同一进程中修改 env/config，不会读到旧 profile 状态。

### P2.2 清理 generated work artifacts 的交付边界

涉及文件：

- `.gitignore`

具体改法：

- 将 `work/` 加入 `.gitignore`。
- 保留 `.env`、`model_profiles.yaml` 忽略。
- 不要删除用户明确需要保留的文件；如果要清理本地 `work/model-check`，先确认它只是验证产物。

验收：

```bash
git status --short
```

不应再因为 `work/` 产生未跟踪验证产物。

## 4. 最小测试要求

至少补齐这些断言：

1. model run id 非空。
2. model result data object 数量等于 model processing run 数量。
3. manifest 不包含空 run id。
4. model result JSON 保存完整 `ModelResult` wrapper。
5. model result JSON 包含 `output_json`。
6. local 模式不会调用 `requests.post`。
7. exact API key 不出现在 SQLite/JSON/Markdown/CLI 输出。
8. HTTP error 和 RequestException message 会 redaction。
9. legacy adapter modules 可以 import。
10. raw numeric、raw spectral、sample metadata 在 local/cloud/auto 下仍不路由到模型。
11. replacement relationship 两端 subtype 一致。
12. model result 的 `derived_from` metadata 指向 `model:*` run。

## 5. 验收命令

如果没有虚拟环境，先创建：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

跑测试：

```bash
.venv/bin/python -m pytest -q
```

如果原始 demo inbox 可用，跑完整 demo：

```bash
rm -rf work/model-check

.venv/bin/python -m data_agent ingest \
  --inbox "/Users/zanderkong/Desktop/数据处理agent/material_data_agent_demo 测试数据/inbox" \
  --workspace work/model-check

.venv/bin/python -m data_agent process \
  --workspace work/model-check \
  --all \
  --models local

.venv/bin/python -m data_agent process \
  --workspace work/model-check \
  --all \
  --models auto

.venv/bin/python -m data_agent models check \
  --workspace work/model-check \
  --verbose
```

如果原始 demo inbox 不存在，但仓库里还有旧的 `work/model-check/tasks/*/raw`，可以临时重建 inbox：

```bash
rm -rf /tmp/material-agent-inbox /tmp/material-agent-ws
mkdir -p /tmp/material-agent-inbox
find work/model-check/tasks -path '*/raw/*' -type f -exec cp {} /tmp/material-agent-inbox/ \;

.venv/bin/python -m data_agent ingest \
  --inbox /tmp/material-agent-inbox \
  --workspace /tmp/material-agent-ws

.venv/bin/python -m data_agent process \
  --workspace /tmp/material-agent-ws \
  --all \
  --models local

.venv/bin/python -m data_agent process \
  --workspace /tmp/material-agent-ws \
  --all \
  --models auto
```

审计 SQL：

```bash
sqlite3 work/model-check/agent.sqlite '
select "model_objects", count(*) from data_objects where data_type="model_result";
select "model_runs", count(*) from processing_runs where tool_name like "model:%";
select "empty_run_ids", count(*) from processing_runs where run_id="";
'
```

期望：

- `model_objects == model_runs`
- `empty_run_ids == 0`

manifest 检查：

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

for p in sorted(Path("work/model-check/tasks").glob("task_*/manifest.json")):
    m = json.loads(p.read_text())
    empties = [r for r in m.get("run_ids", []) if not r]
    assert not empties, f"{p} contains empty run_ids"
print("manifest run_ids ok")
PY
```

model result JSON shape 检查：

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

required = {
    "success", "role", "provider", "mode", "output_json",
    "schema_version", "prompt_version"
}

for p in Path("work/model-check/tasks").glob("task_*/derived/*model_result*.json"):
    data = json.loads(p.read_text())
    missing = required - set(data)
    assert not missing, f"{p} missing {missing}"
print("model_result JSON shape ok")
PY
```

relationship 检查：

```bash
sqlite3 work/model-check/agent.sqlite '
select d.subtype, pr.tool_name, r.metadata
from relationships r
join data_objects d on r.target_id = d.object_id
join processing_runs pr on json_extract(r.metadata, "$.run_id") = pr.run_id
where d.data_type="model_result"
  and r.rel_type="derived_from"
limit 20;
'
```

期望：

- 所有 model result 的 `tool_name` 都以 `model:` 开头。

## 6. Definition of Done

本轮完成标准：

- `pytest -q` 通过。
- 无 key 的 `local` workflow 通过。
- 无 key 的 `auto` workflow 通过，允许 fallback，但主流程不能崩。
- 没有空 model run id。
- model result object 数量等于 model processing run 数量。
- model result JSON 是完整、redacted 的 `ModelResult` wrapper。
- local 模式有真实 no-network 测试。
- legacy adapter imports 不失败。
- exact API key 不出现在任何持久化证据或 CLI 输出中。
- replacement relationship 不跨 subtype 错配。
- `work/` 这类验证产物不再作为源码交付内容出现。

## 7. 最后提醒

优先小步修复，不要顺手重构。`data_agent/process.py` 是本轮主要战场；其余 processor 只要现有测试仍通过，就不要动。
