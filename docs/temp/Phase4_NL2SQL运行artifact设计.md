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

Phase 4 初版有两个可选写入策略。

### 14.1 策略 A：run 后写最终 artifact

流程：

```text
Nl2SqlWorkflow.run
  -> GraphRuntime.invoke
  -> final state
  -> build Nl2SqlOutput
  -> write input/prompt_payload/final_prompt/output/manifest
  -> return output with artifact paths
```

优点：

```text
实现简单。
不需要额外调用 stream。
不会改变当前 workflow.run 行为太多。
```

缺点：

```text
拿不到完整 graph_updates.jsonl。
只能从 final state 写最终结果。
```

### 14.2 策略 B：artifact 模式下用 stream 收集 updates

流程：

```text
Nl2SqlWorkflow.run
  -> GraphRuntime.stream(stream_mode="updates")
  -> 收集每个 node update
  -> 从最后状态或二次 invoke 得到 final state
  -> 写 graph_updates.jsonl
  -> 写其他 artifact
```

问题：

```text
如果为了拿 updates 再 invoke 一次，会重复执行 graph。
```

不建议。

### 14.3 推荐策略：扩展 GraphRuntime 支持 invoke_with_updates

为了既保持 `run()` 语义，又能写 `graph_updates.jsonl`，建议后续实现时扩展：

```python
GraphRuntime.invoke_with_updates(...)
```

语义：

```text
1. 使用 graph.stream(..., stream_mode="updates") 执行一次 graph。
2. 收集 updates。
3. 从 stream 结束后的状态获取 final state。
```

如果 LangGraph 当前 API 不方便直接从 updates stream 得到 final state，则 Phase 4 初版可以退一步：

```text
1. run() 只写 final artifact，不写 graph_updates.jsonl。
2. stream() 调用时写 graph_updates.jsonl。
```

但我不推荐这个退路作为最终设计。

更好的目标是：

```text
一次 run 同时产出 final state 和 graph_updates.jsonl。
```

### 14.4 初版建议

Phase 4 初版设计目标：

```text
实现一次 run 产出完整 artifact，包括 graph_updates.jsonl。
```

执行计划阶段需要先验证 LangGraph API：

```text
能否通过 stream 或其他方式在一次执行中同时拿到 updates 和 final state。
```

如果验证发现不方便，应在执行计划中明确降级：

```text
run 产出 input/prompt_payload/final_prompt/output/manifest。
stream 产出 graph_updates.jsonl。
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
    thread_id: str,
    output: Nl2SqlOutput,
    graph_updates: list[dict[str, object]] | None = None,
    started_at: datetime,
    finished_at: datetime,
    artifact_required: bool = False,
) -> Nl2SqlArtifactResult:
    ...
```

说明：

```text
1. log_dir 来自 LoggingRuntime.log_dir。
2. thread_id 必须是 resolved thread_id。
3. output 中已有 prompt_payload/final_prompt metadata。
4. graph_updates 可以先允许为空，但目标是写入。
5. artifact_required 默认 false。
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

## 24. 测试重点

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
```

## 25. 可能的执行任务拆分

后续执行计划可以拆成：

```text
Task 1：新增 artifacts.py，先实现路径解析和 JSON/TXT/JSONL 写入工具。
Task 2：实现 write_nl2sql_artifacts 和单元测试。
Task 3：修改 Nl2SqlWorkflow.run，写入 artifact 并补 metadata。
Task 4：设计/验证 graph_updates 采集方式。
Task 5：补 app.log 摘要日志。
Task 6：集成测试和最终验证。
```

注意：

```text
执行计划阶段必须先验证 LangGraph 如何在一次执行中同时获得 updates 和 final state。
```

这是 Phase 4 最关键的技术风险点。

## 26. 完成标准

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
13. 明确测试重点。
```

一句话总结：

```text
Phase 4 artifact 系统要解决的是“每次 NL2SQL 运行自动留下可验收证据”，不是要一次性做完通用日志平台或外部观测平台。
```
