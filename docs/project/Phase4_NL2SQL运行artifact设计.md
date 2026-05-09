# Phase 4 NL2SQL 运行 artifact 设计

> 本文是 Phase 4 的第二份讨论设计稿。
>
> 前置文档：`docs/temp/Phase4_NL2SQL日志分类设计.md`
>
> 本文在日志分类已经确定的前提下，具体设计 NL2SQL 单次运行 artifact 的目录、文件、写入时机、LangGraph 适配、错误策略和测试方向。
>
> 本文仍然不是执行计划；执行计划后续再放到 `docs/superpowers/plans/`。

## 1. 背景

Phase 3 已经能在运行结果中看到：

```text
metadata.prompt_payload
metadata.final_prompt
stream updates 中的 build_prompt 更新
```

但这个方式仍然依赖调用方或 AI 把控制台内容转述出来。

Phase 4 的目标是让一次 NL2SQL 运行自动生成稳定文件：

```text
不用看控制台。
不用翻 app.log。
不用解析 checkpoint。
不用依赖 AI 转述。
```

直接打开本次运行目录，就能看到：

```text
输入是什么。
prompt_payload 是什么。
final_prompt 是什么。
LangGraph 每个关键节点更新了什么。
最终输出是什么。
本次 artifact 是否写成功。
```

## 1.1 LangGraph stream spike 结论

本文依赖下面的技术验证：

```text
docs/temp/Phase4_LangGraph_stream_spike.md
```

验证结论：

```text
1. stream_mode="updates" 可获得每个节点的 state update。
2. build_prompt update 中包含 prompt_payload 和 final_prompt。
3. stream_mode="values" 可用，最后一个 values chunk 是 final state。
4. stream_mode=["updates", "values"] 可用，返回 (mode, chunk) 结构。
5. stream_mode="updates" 执行结束后，可以通过 graph.get_state(config) 获取 final state。
6. stream + get_state 的 final state 与 invoke 的最终 state 一致。
```

因此 Phase 4 不需要为了 artifact 重复执行 graph。

后续设计采用：

```text
GraphRuntime.invoke_with_updates
  -> graph.stream(..., stream_mode="updates")
  -> 收集 update chunks
  -> graph.get_state(config).values 作为 final state
```

## 2. 核心结论

Phase 4 初版应实现：

```text
NL2SQL run artifact writer
```

它不是通用日志平台，也不是 LangSmith 替代品。

它的定位是：

```text
为每一次 NL2SQL workflow 调用生成本地、稳定、可读、可验收的运行材料。
```

建议输出：

```text
input.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
output.json
manifest.json
```

暂不输出真实：

```text
token_usage.json
token_summary.json
```

原因：

```text
当前仍然没有真实 LLM 调用，不会产生真实 token usage。
Phase 4 只在 manifest / metadata 中预留 token_usage_path 的设计位置。
```

## 3. 范围

Phase 4 artifact 设计要做：

```text
1. 定义 artifact 目录结构。
2. 定义每个 artifact 文件的内容和格式。
3. 定义写入时机。
4. 定义 LangGraph invoke / stream 如何被观测。
5. 定义写入失败策略。
6. 定义 output.metadata 中新增哪些路径。
7. 定义 app.log 写哪些摘要。
8. 定义测试重点。
```

Phase 4 artifact 设计不做：

```text
1. 真实 LLM。
2. 真实 token 统计。
3. LangSmith 接入。
4. OpenTelemetry 接入。
5. 真实 DB。
6. 真实 schema grounding。
7. 真实 SQL execution。
8. 复杂脱敏。
9. 日志查询 UI。
10. 通用平台级 tracing 系统。
```

## 4. 设计原则

```text
1. 节点不直接写文件。
2. checkpoint 不作为人工验收日志。
3. app.log 只放摘要和 artifact 路径。
4. final_prompt.txt 默认完整写出。
5. prompt_payload.json 使用结构化 JSON。
6. graph_updates.jsonl 来自 LangGraph stream updates。
7. artifact 写入失败默认不影响主流程。
8. 字段名在 manifest、metadata、app.log、未来 token_usage 中保持一致。
9. 当前阶段先不实现真实 token 统计。
10. 当前阶段先不实现复杂脱敏，但保留后续扩展点。
11. 原始 dict 只允许停留在 LangGraph 边界和 JSON 序列化边界，跨模块返回值优先使用 dataclass / TypedDict。
```

## 5. 推荐目录结构

当前项目已有日志根目录：

```text
workspace/logs/<run_date>/<run_id>/app.log
```

Phase 4 初版建议把 NL2SQL artifact 放在同一个 `log_dir` 下：

```text
workspace/logs/<run_date>/<run_id>/artifacts/nl2sql/<artifact_id>/
```

示例：

```text
workspace/logs/20260509/run-phase4/artifacts/nl2sql/thread-phase4-review/
  input.json
  prompt_payload.json
  final_prompt.txt
  graph_updates.jsonl
  output.json
  manifest.json
```

为什么放在 `logs` 下，而不是新增 `workspace/runs`：

```text
1. 当前项目已经有 LoggingRuntime.log_dir。
2. Phase 4 是日志/观测能力，不是业务数据落盘。
3. 不需要马上扩展 ProjectPaths 和 env.yml。
4. 可以避免同时维护 logs/runs 两套根目录。
5. 后续如果项目需要长期运行档案，再考虑新增 runs 根目录。
```

这与分类文档中的 `workspace/runs/...` 不冲突。

分类文档讨论的是概念边界：

```text
run_date / run_id / nl2sql / 单次调用目录
```

本设计落到当前代码时，先复用：

```text
LoggingRuntime.log_dir
```

## 6. artifact_id 规则

一个 `run_id` 下可能有多次 NL2SQL 调用，因此目录必须区分到单次调用。

建议：

```text
artifact_id = request_id if request_id else resolved_thread_id
```

其中：

```text
request_id:
  外部业务请求 id，如果存在，优先使用。

resolved_thread_id:
  由 GraphRuntime / thread_id 规则解析后的 LangGraph thread_id。
```

注意：

```text
artifact_id 只是目录名，不替代 thread_id。
manifest.json、input.json、output.metadata 中必须同时保留 request_id 和 thread_id。
```

原因：

```text
request_id 是外部业务请求标识。
thread_id 是 LangGraph checkpoint / stream / state 线程标识。
两者语义不同，不能互相覆盖。
```

如果两者都为空，应使用和当前 GraphRuntime 一致的 fallback：

```text
thread_id = run_id
```

目录名需要做文件名安全处理：

```text
只保留 0-9 A-Z a-z _ -
其他字符替换为 _
去掉首尾 _
空字符串回退为 run_id
```

避免覆盖原则：

```text
1. 同一个 artifact_id 再次写入时，默认覆盖同名文件。
2. 这是可接受的，因为同一个 thread_id 在 LangGraph 语义上代表同一条线程。
3. 如果后续需要同 thread 多次独立验收，可再引入 attempt_index 或 timestamp。
```

manifest 中应记录：

```text
write_mode = "overwrite"
```

原因：

```text
Phase 4 初版允许覆盖，但 manifest 必须让人知道当前写入策略。
```

Phase 4 初版不引入 attempt_index。

原因：

```text
当前主要目标是稳定看到一次 run 的 prompt 和 output。
过早引入 attempt 会扩大命名和清理复杂度。
```

## 7. 文件清单

单次 NL2SQL artifact 目录包含：

```text
input.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
output.json
manifest.json
```

后续真实 LLM 阶段再增加：

```text
token_usage.json
token_usage.jsonl
token_summary.json
```

## 8. input.json

### 8.1 内容

```json
{
  "run_id": "run-phase4",
  "run_date": "20260509",
  "thread_id": "thread-phase4-review",
  "request_id": null,
  "user_id": null,
  "database_key": null,
  "raw_question": "统计员工数量",
  "options": {}
}
```

字段含义：

```text
run_id / run_date:
  来自 RunContext。

thread_id:
  本次 LangGraph 调用使用的 resolved thread id。

request_id:
  外部业务请求 id，可能为空。

raw_question:
  用户原始问题。

options:
  当前 mock 控制选项，例如 force_check_error。
```

### 8.2 格式

```text
JSON
indent=2
ensure_ascii=false
```

## 9. prompt_payload.json

### 9.1 内容

写入 Phase 3 的完整结构化 payload：

```text
task
question
schema_context
semantic_context
sql_policy
output_contract
debug
```

来源：

```text
最终 graph state 中的 prompt_payload
```

如果本次运行走 clarification 路径，没有进入 build_prompt：

```text
不写 prompt_payload.json
manifest.artifact_files.prompt_payload 为空
```

原因：

```text
空问题不应该生成 prompt。
```

### 9.2 格式

```text
JSON
indent=2
ensure_ascii=false
```

## 10. final_prompt.txt

### 10.1 内容

写入最终给模型看的完整提示词。

来源：

```text
最终 graph state 中的 final_prompt
```

如果本次运行没有 final_prompt：

```text
不写 final_prompt.txt
manifest.artifact_files.final_prompt 为空
```

### 10.2 格式

```text
纯文本
UTF-8
默认完整写出
不默认截断
```

### 10.3 manifest 记录

manifest 中记录：

```text
final_prompt_size_bytes
final_prompt_size_chars
```

原因：

```text
后续 prompt 变大时，可以快速从 manifest 观察体积变化。
```

## 11. graph_updates.jsonl

### 11.1 内容

记录 LangGraph `stream_mode="updates"` 产生的节点更新。

LangGraph 原始 chunk 形态通常类似：

```python
{"build_prompt": {"final_prompt": "..."}}
```

写入 JSONL 时标准化为：

```json
{"node":"build_prompt","update":{"final_prompt":"..."}}
```

如果一个 chunk 中包含多个 node：

```text
每个 node 写一行。
```

### 11.2 格式

```text
JSONL
每行 compact JSON
ensure_ascii=false
```

### 11.3 是否包含完整 prompt

Phase 4 初版允许 `graph_updates.jsonl` 中包含完整 `final_prompt`。

原因：

```text
1. 当前没有真实敏感数据。
2. 这是为了验证 stream updates 与 final state 的一致性。
3. 后续真实数据接入前再评审 redaction_policy。
```

## 12. output.json

### 12.1 内容

记录 `Nl2SqlOutput` 的可序列化结构：

```json
{
  "status": "success",
  "message": "NL2SQL workflow succeeded.",
  "sql": "SELECT 1 AS value",
  "columns": ["value"],
  "rows": [{"value": 1}],
  "trace_id": null,
  "metadata": {
    "prompt_payload": {},
    "final_prompt": "...",
    "artifact_manifest_path": "...",
    "final_prompt_path": "...",
    "prompt_payload_path": "..."
  }
}
```

Phase 4 初版继续保留：

```text
metadata.prompt_payload
metadata.final_prompt
```

同时新增 artifact 路径：

```text
metadata.artifact_manifest_path
metadata.input_path
metadata.prompt_payload_path
metadata.final_prompt_path
metadata.graph_updates_path
metadata.output_path
metadata.token_usage_path
metadata.artifact_error
```

注意：

```text
output.json 中的 metadata.output_path 会指向 output.json 自身。
这是允许的，但必须是字符串路径，不能是 Path 对象，也不能引入不可 JSON 序列化对象。
```

### 12.2 token_usage_path

当前无真实 LLM，因此：

```text
metadata.token_usage_path = null
```

后续真实 LLM 阶段再写入路径。

### 12.3 格式

```text
JSON
indent=2
ensure_ascii=false
```

## 13. manifest.json

manifest 是本次 artifact 的索引文件。

### 13.1 内容

建议结构：

```json
{
  "run_id": "run-phase4",
  "run_date": "20260509",
  "thread_id": "thread-phase4-review",
  "request_id": null,
  "artifact_id": "thread-phase4-review",
  "workflow": "nl2sql",
  "write_mode": "overwrite",
  "status": "success",
  "started_at": "2026-05-09T09:00:00",
  "finished_at": "2026-05-09T09:00:01",
  "duration_ms": 12,
  "artifact_dir": "...",
  "artifact_files": {
    "input": ".../input.json",
    "prompt_payload": ".../prompt_payload.json",
    "final_prompt": ".../final_prompt.txt",
    "graph_updates": ".../graph_updates.jsonl",
    "output": ".../output.json",
    "token_usage": null
  },
  "sizes": {
    "final_prompt_size_bytes": 1024,
    "final_prompt_size_chars": 900
  },
  "artifact_error": null
}
```

### 13.2 格式

```text
JSON
indent=2
ensure_ascii=false
```

## 14. 写入时机

根据 spike 结论，Phase 4 采用单次执行策略。

### 14.1 推荐策略：GraphRuntime.invoke_with_updates

为了既保持 `run()` 语义，又能写 `graph_updates.jsonl`，后续实现时扩展：

```python
GraphRuntime.invoke_with_updates(...)
```

语义：

```text
1. 使用 graph.stream(..., stream_mode="updates") 执行一次 graph。
2. 收集 updates。
3. stream 结束后调用 graph.get_state(config)。
4. 使用 graph.get_state(config).values 作为 final state。
```

实现约束：

```text
stream 和 get_state 必须使用同一个 config 对象。
尤其必须使用同一个 resolved thread_id。
```

原因：

```text
get_state(config) 依赖 thread_id 定位 checkpoint state。
如果 stream 和 get_state 使用了不同 config，就可能拿不到刚才那次执行的 final state。
```

建议返回结构：

```python
@dataclass(frozen=True)
class GraphRunResult:
    final_state: dict[str, Any]
    updates: list[dict[str, Any]]
    thread_id: str
```

其中：

```text
final_state:
  dict(graph.get_state(config).values)。

updates:
  stream_mode="updates" 的原始 chunks。

thread_id:
  resolved thread id，来自 GraphRuntime 的 config。
```

注意：

```text
GraphRuntime 只返回 LangGraph 原始 update chunks。
GraphRuntime 不负责把 updates 标准化成 {"node": ..., "update": ...}。
标准化由 NL2SQL artifact writer 负责。
```

### 14.2 Nl2SqlWorkflow.run 流程

Phase 4 初版推荐流程：

```text
Nl2SqlWorkflow.run
  -> 记录 started_at
  -> GraphRuntime 解析或返回 resolved_thread_id
  -> app.log 记录 started 摘要
  -> GraphRuntime.invoke_with_updates
  -> final_state + update_chunks + resolved_thread_id
  -> build Nl2SqlOutput(final_state)
  -> write_nl2sql_artifacts(...)
  -> 把 artifact metadata 合并进 Nl2SqlOutput.metadata
  -> app.log 记录 finished 摘要
  -> return output
```

这个流程只执行一次 graph。

started 日志中的 thread_id 口径：

```text
started 和 finished 应使用同一个 resolved_thread_id。
```

推荐方式：

```text
GraphRuntime 提供统一的 config/thread_id 解析能力。
Nl2SqlWorkflow 不自行拼 thread_id。
```

### 14.3 多 stream mode 的定位

spike 已证明：

```text
stream_mode=["updates", "values"] 可用。
```

但 Phase 4 初版仍推荐：

```text
updates stream + get_state(config)
```

原因：

```text
1. artifact 只需要节点 updates 和最终 state。
2. values stream 会产生每步完整 state，内容更大。
3. get_state(config) 已经验证可拿最终 state。
4. 更符合 graph_updates.jsonl 的最小需求。
```

## 15. Nl2SqlWorkflow 如何接入

推荐接入位置：

```text
Nl2SqlWorkflow facade 层
```

理由：

```text
1. 它知道 Nl2SqlInput。
2. 它知道 RunContext。
3. 它接收 thread_id。
4. 它能拿到 final state / output。
5. 它是 workflow 对外边界，适合补充 metadata。
6. 它可以保持 nodes 纯净。
```

Phase 4 初版需要向 `Nl2SqlWorkflow` 注入：

```text
log_dir
logger
```

建议形态：

```python
@dataclass(frozen=True)
class Nl2SqlWorkflow:
    graph: object
    graph_runtime: GraphRuntime
    run_context: RunContext
    log_dir: Path
    logger: Logger
```

说明：

```text
log_dir:
  来自 LoggingRuntime.log_dir，用于 artifact 根目录。

logger:
  来自 LoggingRuntime.logger，只在 workflow facade 层记录 started/finished/error 摘要。
```

不推荐在 node 中写 artifact：

```text
1. 节点会依赖文件系统。
2. 节点测试会变重。
3. 后续换输出格式要改多个节点。
4. 破坏 LangGraph state update 的清晰边界。
```

## 16. artifact writer 放在哪里

有三个候选方案。

### 16.1 方案 A：放在 workflows/nl2sql/artifacts.py

```text
src/nl2sqlagent/workflows/nl2sql/artifacts.py
```

优点：

```text
1. 当前 artifact 只服务 NL2SQL。
2. 能理解 prompt_payload/final_prompt/output。
3. 不提前创建通用平台抽象。
```

缺点：

```text
后续其他 workflow 需要类似能力时，可能要抽取。
```

### 16.2 方案 B：放在 platform/observation/

```text
src/nl2sqlagent/platform/observation/artifacts.py
```

优点：

```text
1. 看起来更通用。
2. 后续其他 workflow 可复用。
```

缺点：

```text
1. 当前只有 NL2SQL 需要。
2. 平台层不应该理解 prompt_payload/final_prompt。
3. 容易过早抽象。
```

### 16.3 方案 C：拆成通用 writer + NL2SQL adapter

```text
platform/observation/json_writer.py
workflows/nl2sql/artifacts.py
```

优点：

```text
边界最干净。
```

缺点：

```text
Phase 4 初版过重。
```

### 16.4 推荐

Phase 4 初版推荐方案 A：

```text
src/nl2sqlagent/workflows/nl2sql/artifacts.py
```

原因：

```text
1. YAGNI。
2. NL2SQL artifact 字段具有明显业务含义。
3. 后续如果第二个 workflow 也需要 artifact，再抽平台层。
```

## 17. artifact writer 建议接口

建议定义：

```python
@dataclass(frozen=True)
class Nl2SqlArtifactPaths:
    artifact_dir: Path
    input_path: Path
    prompt_payload_path: Path
    final_prompt_path: Path
    graph_updates_path: Path
    output_path: Path
    manifest_path: Path
    token_usage_path: Path | None = None


@dataclass(frozen=True)
class Nl2SqlArtifactResult:
    paths: Nl2SqlArtifactPaths
    metadata: dict[str, object]
    artifact_error: str | None = None
```

核心函数：

```python
def write_nl2sql_artifacts(
    *,
    log_dir: Path,
    run_context: RunContext,
    input: Nl2SqlInput,
    resolved_thread_id: str,
    final_state: dict[str, Any],
    output: Nl2SqlOutput,
    graph_updates: list[dict[str, object]],
    started_at: datetime,
    finished_at: datetime,
    artifact_required: bool = False,
) -> Nl2SqlArtifactResult:
    ...
```

说明：

```text
1. log_dir 来自 LoggingRuntime.log_dir。
2. resolved_thread_id 必须是 GraphRuntime 解析后的 thread id。
3. final_state 是 prompt_payload/final_prompt 的权威来源。
4. output 是对外返回结构，用于 output.json。
5. graph_updates 是 stream_mode="updates" 的原始 chunks。
6. artifact_id 在 writer 内部按 input.request_id or resolved_thread_id 计算。
7. artifact_required 默认 false。
```

路径规则：

```text
writer 内部使用 Path。
写入 JSON 和 output.metadata 时统一转成 str。
```

## 18. 写入失败策略

默认策略：

```text
artifact 写入失败不影响主流程。
```

行为：

```text
1. 捕获 artifact writer 异常。
2. app.log 记录 error 摘要。
3. output.metadata.artifact_error 写入错误信息。
4. artifact_manifest_path 为空或不写入。
5. 原始 Nl2SqlOutput.status 不因为 artifact 失败改成 failed。
```

部分写入失败策略：

```text
1. 不做事务性回滚。
2. 不删除已经写成功的文件。
3. manifest 尽量最后写。
4. 如果部分文件失败但 manifest 写成功，manifest.artifact_error 记录错误。
5. 如果 manifest 也失败，output.metadata.artifact_error 记录错误，artifact_manifest_path 为 null。
```

原因：

```text
artifact 是调试材料。
部分文件也可能有排查价值，强行回滚会丢失证据。
```

开发/验收模式：

```text
artifact_required = true
```

行为：

```text
artifact 写入失败可以抛出异常，让测试失败。
```

Phase 4 初版可以先不暴露配置项。

执行计划中可先把 `artifact_required` 作为 writer 参数，在测试里直接传入。

## 19. app.log 记录内容

app.log 只记录摘要。

workflow 开始：

```text
NL2SQL workflow started run_id=... thread_id=... request_id=...
```

workflow 结束：

```text
NL2SQL workflow finished run_id=... thread_id=... status=success duration_ms=... artifact_manifest_path=...
```

artifact 写入失败：

```text
NL2SQL artifact write failed run_id=... thread_id=... error=...
```

不写入 app.log：

```text
完整 prompt_payload
完整 final_prompt
完整 graph_updates
完整 rows
```

## 20. output.metadata 新增字段

Phase 4 初版建议在 `Nl2SqlOutput.metadata` 中新增：

```text
artifact_manifest_path
input_path
prompt_payload_path
final_prompt_path
graph_updates_path
output_path
token_usage_path
artifact_error
```

说明：

```text
artifact_manifest_path:
  manifest.json 路径。

input_path:
  input.json 路径。

prompt_payload_path:
  prompt_payload.json 路径，没有 prompt 时为 null。

final_prompt_path:
  final_prompt.txt 路径，没有 prompt 时为 null。

graph_updates_path:
  graph_updates.jsonl 路径。

output_path:
  output.json 路径。

token_usage_path:
  当前为 null，后续真实 LLM 接入后写入。

artifact_error:
  artifact 写入失败摘要，成功时为 null。
```

继续保留 Phase 3 字段：

```text
prompt_payload
final_prompt
```

原因：

```text
不破坏 Phase 3 测试和早期使用方式。
```

## 21. graph_updates 如何生成

目标结构：

```json
{"node":"build_prompt","update":{"final_prompt":"..."}}
```

来源：

```text
GraphRuntime.invoke_with_updates 返回的 updates。
```

标准化规则：

```text
1. 输入是 LangGraph stream updates chunk。
2. 每个 chunk 是一个 dict。
3. chunk 的 key 是 node name。
4. chunk 的 value 是 node update。
5. 每个 node update 写一行 JSONL。
```

例如：

```python
{"build_prompt": {"final_prompt": "...", "prompt_payload": {...}}}
```

写为：

```json
{"node":"build_prompt","update":{"final_prompt":"...","prompt_payload":{}}}
```

如果 update 中包含不可 JSON 序列化对象：

```text
Phase 4 初版应转换为字符串，或在 artifact_error 中记录序列化失败。
```

当前 Phase 2/3 state 都是可序列化值，理论上不会遇到。

## 22. token_usage 设计

Phase 4 初版不生成真实 token usage。

manifest 中：

```json
"artifact_files": {
  "token_usage": null
}
```

metadata 中：

```python
"token_usage_path": None
```

不创建空 `token_usage.json`。

原因：

```text
1. 当前没有真实 LLM，空文件容易让人误以为已经统计。
2. 分类设计已经预留 token usage。
3. 后续 LLM 阶段再从 AIMessage.usage_metadata / response_metadata 接入。
```

## 23. 敏感信息与脱敏

Phase 4 初版：

```text
不实现复杂脱敏。
```

原因：

```text
当前仍是 mock schema / mock SQL / mock rows。
```

但设计上预留：

```text
redaction_policy
```

后续真实数据接入前必须重新评审：

```text
1. raw_question 是否脱敏。
2. prompt_payload 是否脱敏。
3. final_prompt 是否脱敏。
4. graph_updates 是否脱敏。
5. output rows 是否截断或脱敏。
```

## 24. 结构化数据边界与防混乱规则

Phase 4 增加 artifact 后，最大的长期风险不是多几个文件，而是：

```text
原始 LangGraph chunk、prompt_payload、metadata、manifest dict 在多个模块之间随意流转。
```

因此实现时必须明确哪些地方允许使用原始 dict，哪些地方必须收束成结构化对象。

### 24.1 允许使用 dict 的边界

允许保留 dict 的地方：

```text
1. LangGraph state。
2. LangGraph stream updates 原始 chunk。
3. prompt_payload 本身。
4. 写入 JSON / JSONL 前后的序列化边界。
5. Nl2SqlOutput.metadata。
```

说明：

```text
这些位置本身就是框架边界或 JSON 边界，强行完全对象化会增加复杂度。
```

### 24.2 不应四处传递的原始数据

不推荐在多个模块之间直接传递：

```text
1. 原始 LangGraph stream chunk。
2. 临时拼出来的 artifact path dict。
3. 临时拼出来的 manifest dict。
4. 临时拼出来的 output.metadata path dict。
5. 未规范化的 graph update 行。
```

这些数据应在明确的模块内收束。

### 24.3 结构化类型归属

建议在固定位置定义结构化类型：

```text
GraphRunResult:
  放在 workflows/runtime/graph_runtime.py。
  表示一次 LangGraph 运行结果。

Nl2SqlArtifactPaths:
  放在 workflows/nl2sql/artifacts.py。
  表示一次 NL2SQL artifact 的所有文件路径。

Nl2SqlArtifactResult:
  放在 workflows/nl2sql/artifacts.py。
  表示 artifact writer 对外返回结果。

Nl2SqlArtifactMetadata:
  放在 workflows/nl2sql/artifacts.py，使用 TypedDict 或明确构造函数。
  表示要合并进 output.metadata 的 artifact 字段。

NormalizedGraphUpdate:
  放在 workflows/nl2sql/artifacts.py，使用 TypedDict 或 dataclass。
  表示写入 graph_updates.jsonl 的单行结构。
```

推荐的 `NormalizedGraphUpdate` 形态：

```python
class NormalizedGraphUpdate(TypedDict):
    node: str
    update: dict[str, Any]
```

### 24.4 原始 LangGraph update 的流转规则

原始 update chunk 的生命周期必须足够短：

```text
GraphRuntime.invoke_with_updates
  -> 返回 GraphRunResult.updates
  -> write_nl2sql_artifacts 接收 graph_updates
  -> artifact writer 内部标准化为 NormalizedGraphUpdate
  -> 写入 graph_updates.jsonl
```

规则：

```text
1. GraphRuntime 只负责收集原始 update chunks，不理解 NL2SQL 字段。
2. Nl2SqlWorkflow 只把原始 update chunks 传给 artifact writer，不解析 chunk 内容。
3. artifact writer 是唯一负责把 chunk 标准化为 {"node": ..., "update": ...} 的地方。
4. 标准化后的结构只用于写 JSONL，不再回流到 workflow state。
```

### 24.5 metadata 与路径规则

artifact path 的构造与转换必须集中：

```text
1. Path 对象只在 artifact writer 内部和 Nl2SqlArtifactPaths 中存在。
2. 写入 manifest.json、output.json、output.metadata 前统一转成 str。
3. output.metadata 中的 artifact 字段只能由 Nl2SqlArtifactResult.metadata 提供。
4. Nl2SqlWorkflow 不手写 artifact_manifest_path、final_prompt_path 等字段。
```

这样后续要判断“当前有哪些 artifact 字段”，只需要看：

```text
workflows/nl2sql/artifacts.py
```

### 24.6 禁止事项

实现时禁止：

```text
1. 在 nodes.py 中写文件。
2. 在 nodes.py 中记录 artifact 日志。
3. 在 GraphRuntime 中读取 prompt_payload / final_prompt / sql / rows。
4. 在 Nl2SqlWorkflow.run 中直接 json.dumps/json.dump artifact 内容。
5. 在多个模块中重复拼接 artifact 路径。
6. 在 output.metadata 中放入 Path、datetime、Exception 等不可 JSON 序列化对象。
7. 把 manifest dict 作为长期内部数据结构跨模块传递。
```

### 24.7 prompt_payload 的边界

`prompt_payload` 本身仍按 Phase 3 设计保留为结构化 JSON dict。

原因：

```text
1. prompt_payload 本质上就是要给人审阅和给模型渲染的结构化 payload。
2. 当前 Phase 3 已经集中在 prompt_payload.py 构建。
3. Phase 4 的重点是保存和观测，不重新设计 prompt schema。
```

但实现时必须遵守：

```text
1. prompt_payload 的权威来源仍是 final_state["prompt_payload"]。
2. artifact writer 只读取并写出 prompt_payload，不修改 prompt_payload 内容。
3. 如果后续 prompt_payload 结构继续变复杂，再在 prompt_payload.py 中补 TypedDict / schema，而不是在 artifacts.py 中临时解释字段。
```

## 25. 测试重点

Phase 4 artifact 测试应该证明：

```text
1. artifact_id 优先 request_id，否则 thread_id。
2. artifact 目录按 run_date/run_id/nl2sql/artifact_id 隔离。
3. input.json 内容正确。
4. prompt_payload.json 内容正确。
5. final_prompt.txt 完整写出且不包含 debug。
6. graph_updates.jsonl 是合法 JSONL。
7. output.json 内容正确。
8. manifest.json 包含所有路径、状态、大小、耗时。
9. output.metadata 新增 artifact 路径。
10. app.log 只记录摘要和路径。
11. artifact 写入失败默认不改变 Nl2SqlOutput.status。
12. artifact_required=true 时写入失败会让测试捕获异常。
13. token_usage_path 当前为 null。
14. GraphRuntime.invoke_with_updates 单次执行返回 updates 和 final_state。
15. output.metadata 和 JSON 文件中的路径都是字符串，不是 Path 对象。
16. manifest 保留 request_id、thread_id、artifact_id 和 write_mode。
17. stream 和 get_state 使用同一个 config / resolved_thread_id。
18. final_state 是普通 dict，不直接暴露 StateSnapshot.values。
19. GraphRuntime 返回原始 update chunks，artifact writer 负责标准化 JSONL。
20. started 和 finished app.log 使用同一个 resolved_thread_id。
21. nodes.py 不包含 artifact 文件写入逻辑。
22. GraphRuntime 不引用 prompt_payload、final_prompt、sql、rows 等 NL2SQL 业务字段。
23. output.metadata 和 manifest 中的 artifact 路径全部来自 artifact writer。
24. graph_updates.jsonl 中每行都是标准化后的 node/update 结构。
25. artifact writer 内部可以使用 Path，但写入 JSON/metadata 时必须转成字符串。
```

## 26. 可能的执行任务拆分

后续执行计划可以拆成：

```text
Task 1：新增 GraphRunResult 和 GraphRuntime.invoke_with_updates。
Task 2：测试 invoke_with_updates 单次执行返回 updates + final_state，并验证 stream/get_state 使用同一 resolved_thread_id。
Task 3：新增 artifacts.py，先实现路径解析和 JSON/TXT/JSONL 写入工具。
Task 4：在 artifacts.py 中定义 Nl2SqlArtifactPaths、Nl2SqlArtifactResult、Nl2SqlArtifactMetadata、NormalizedGraphUpdate 等结构化边界。
Task 5：实现 write_nl2sql_artifacts 和单元测试。
Task 6：修改 Nl2SqlWorkflow.run，写入 artifact 并补 metadata。
Task 7：向 Nl2SqlWorkflow 注入 log_dir/logger，并补 app.log 摘要日志。
Task 8：集成测试和最终验证，确认 nodes / GraphRuntime / workflow 的职责没有越界。
```

注意：

```text
LangGraph stream spike 已验证：
  stream_mode="updates" + graph.get_state(config) 可在一次执行中获得 updates 和 final state。
```

因此执行计划不需要再做探索性 spike，但需要把该行为固化成自动化测试。

## 27. 完成标准

Phase 4 artifact 设计通过时，应满足：

```text
1. 明确 artifact 目录结构。
2. 明确 artifact_id 规则。
3. 明确每个 artifact 文件内容和格式。
4. 明确 final_prompt.txt 默认完整写出。
5. 明确 prompt_payload.json 独立结构化保存。
6. 明确 graph_updates.jsonl 来自 LangGraph stream updates。
7. 明确 output.metadata 新增路径字段。
8. 明确 app.log 只写摘要。
9. 明确 artifact 写入失败默认不影响主流程。
10. 明确 token_usage 当前只预留，不生成真实文件。
11. 明确 artifact writer 初版放在 workflows/nl2sql/artifacts.py。
12. 明确 nodes 不写文件。
13. 明确 GraphRuntime.invoke_with_updates 用单次执行返回 updates 和 final_state。
14. 明确 manifest 同时保留 request_id、thread_id、artifact_id 和 write_mode。
15. 明确 JSON/metadata 路径统一为字符串。
16. 明确 stream 和 get_state 必须使用同一个 config / resolved_thread_id。
17. 明确 GraphRuntime 返回原始 update chunks，由 artifact writer 标准化。
18. 明确 started/finished 日志使用同一个 resolved_thread_id。
19. 明确 dict 只允许存在于 LangGraph 边界、JSON 序列化边界、prompt_payload 和 metadata 边界。
20. 明确跨模块返回值使用 GraphRunResult、Nl2SqlArtifactPaths、Nl2SqlArtifactResult 等结构化类型。
21. 明确 output.metadata 的 artifact 字段只能由 artifact writer 统一生成。
22. 明确测试重点。
```

一句话总结：

```text
Phase 4 artifact 系统要解决的是“每次 NL2SQL 运行自动留下可验收证据”，不是要一次性做完通用日志平台或外部观测平台。
```
