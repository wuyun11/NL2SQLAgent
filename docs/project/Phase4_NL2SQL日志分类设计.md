# Phase 4 NL2SQL 日志分类设计

> 本文是 Phase 4 的第一份讨论设计稿。
>
> 目标不是马上设计具体 artifact writer，也不是写执行计划。
> 本文只解决一个前置问题：在 LangGraph Agent 项目中，哪些信息归 LangGraph 运行机制负责，哪些信息归项目代码负责，哪些信息要单独输出便于调试，哪些信息进入总输出。

## 1. 背景

当前项目已经完成：

```text
Phase 0：最小运行底座
Phase 1：LangGraph 运行底座
Phase 2：NL2SQL 线性工作流骨架
Phase 3：结构化 prompt_payload + final_prompt 渲染
```

Phase 3 已经能通过：

```text
Nl2SqlOutput.metadata["prompt_payload"]
Nl2SqlOutput.metadata["final_prompt"]
workflow.stream(..., stream_mode="updates")
```

看到提示词材料和最终提示词。

但这种验收方式仍然依赖：

```text
1. 由 AI 或开发者执行命令。
2. 把控制台输出复制出来。
3. 人再从控制台文本里判断 prompt 是否正确。
```

这不适合后续接入真实 LLM、schema grounding、SQL check、SQL execution 后的问题排查。

因此 Phase 4 不应该直接“随便加日志”，而是应该先把日志和观测信息分类清楚。

## 2. 核心结论

在当前项目里，日志和观测信息应分成四类：

```text
1. LangGraph 运行机制负责的信息
2. 项目代码负责的系统日志
3. NL2SQL 单次运行调试 artifact
4. 面向用户/验收的总输出摘要
```

一句话：

```text
LangGraph 负责运行事实的产生和状态流转；
项目代码负责把关键运行事实转成稳定、可读、可验收的日志与 artifact。
```

## 3. 为什么先分类

如果不先分类，后续很容易出现这些问题：

```text
1. 把 checkpoint 当成人类可读日志。
2. 把 prompt_payload/final_prompt 混进 app.log，后续很难定位。
3. 每个 node 都自己写文件，破坏节点纯度。
4. 总输出塞太多调试细节，反而不利于快速判断结果。
5. 控制台输出、app.log、artifact、metadata 之间重复且口径不一致。
```

分类的目标是：

```text
1. 先确定每类信息的责任归属。
2. 再确定每类信息的输出位置。
3. 最后再设计具体文件结构和实现方案。
```

## 4. 分类总览

建议采用以下分类：

| 类别 | 主要负责人 | 典型内容 | 主要用途 | 是否给人直接看 |
|---|---|---|---|---|
| LangGraph 运行机制 | LangGraph + GraphRuntime | thread_id、metadata、checkpoint、state、stream updates | 状态流转、恢复、调试来源 | 间接看 |
| 系统日志 | 项目 logging 层 | app 启动、workflow 开始/结束、错误摘要、artifact 路径 | 运维和运行摘要 | 可以看 |
| 调试 artifact | 项目 NL2SQL 观测层 | input、prompt_payload、final_prompt、graph_updates、output | prompt 验收和问题复盘 | 直接看 |
| 总输出摘要 | workflow/output 层 | status、message、sql、行列、artifact 路径摘要 | API/CLI/UI 消费 | 直接看 |

这四类不能互相替代。

```text
checkpoint 不能替代 artifact。
app.log 不能替代 final_prompt.txt。
metadata 不能替代稳定落盘文件。
总输出不能承载全部调试细节。
```

## 5. LangGraph 运行机制负责什么

LangGraph 更像运行引擎，不是面向用户的日志系统。

它负责或天然提供：

```text
1. graph 节点执行顺序。
2. 每个 node 返回的 state update。
3. 最终 graph state。
4. stream_mode="updates" 下的节点更新 chunk。
5. configurable.thread_id。
6. config.metadata，例如 run_id、run_date。
7. checkpointer 持久化的中间状态。
```

当前项目已经在 `GraphRuntime` 中传入：

```python
{
    "configurable": {
        "thread_id": ...
    },
    "metadata": {
        "run_id": ...,
        "run_date": ...,
    },
}
```

这部分应继续保留。

但需要明确：

```text
LangGraph checkpoint 是恢复/追踪状态用的，不是给人验收 prompt 的文件。
LangGraph stream updates 是观测来源，不是最终日志格式。
LangGraph final state 是结果来源，不是完整运行报告。
```

所以 LangGraph 负责“产生运行事实”，项目代码负责“整理运行事实”。

## 6. 项目代码负责什么

项目代码负责把 LangGraph 的运行事实转成稳定输出。

项目代码应负责：

```text
1. 决定哪些字段要记录。
2. 决定记录到 app.log、artifact 还是 output metadata。
3. 决定文件路径和命名规则。
4. 决定写入失败是否影响主流程。
5. 决定敏感信息如何处理。
6. 决定长文本是否截断。
7. 决定最终输出中暴露哪些 artifact 路径。
```

项目代码不应该做：

```text
1. 直接解析 LangGraph checkpoint 内部结构作为用户日志。
2. 在每个 node 里散落文件写入逻辑。
3. 让控制台输出成为唯一验收入口。
4. 把所有调试信息都塞进 Nl2SqlOutput 顶层字段。
```

## 7. 哪些进入系统日志

系统日志指当前项目已有的：

```text
workspace/logs/<run_date>/<run_id>/app.log
```

它适合记录摘要事件，不适合承载完整 prompt。

建议进入 app.log 的内容：

```text
1. 应用启动和配置加载摘要。
2. NL2SQL workflow started。
3. NL2SQL workflow finished。
4. status / request_id / thread_id / run_id。
5. 运行耗时。
6. 错误摘要。
7. artifact 目录路径。
```

不建议进入 app.log 的内容：

```text
1. 完整 prompt_payload。
2. 完整 final_prompt。
3. 完整 graph_updates。
4. 大量 result rows。
5. 后续真实 schema catalog 全量内容。
```

原因：

```text
app.log 是运行摘要日志。
它应该帮助人快速知道“发生了什么”和“去哪里看细节”，而不是承担全部细节。
```

## 8. 哪些单独输出方便调试

单独输出的内容称为 NL2SQL run artifact。

它的目标是：

```text
不用依赖控制台，不用翻 app.log，直接打开固定文件就能看本次 NL2SQL 的关键材料。
```

建议单次 NL2SQL 运行生成：

```text
input.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
output.json
manifest.json
```

### 8.1 input.json

记录外部输入和运行身份：

```text
run_id
run_date
thread_id
request_id
user_id
database_key
raw_question
options
```

用途：

```text
复现这次运行的入口条件。
```

### 8.2 prompt_payload.json

记录 Phase 3 结构化 payload：

```text
task
question
schema_context
semantic_context
sql_policy
output_contract
debug
```

用途：

```text
检查喂给 prompt builder 的材料是否正确。
```

### 8.3 final_prompt.txt

记录最终给模型看的提示词。

要求：

```text
1. 默认完整输出。
2. 不放在 app.log 中作为唯一来源。
3. 文件内容适合直接人工阅读和 diff。
4. Phase 3/4 中不包含 debug 字段。
```

用途：

```text
验收最终提示词效果。
```

### 8.4 graph_updates.jsonl

记录 LangGraph `stream_mode="updates"` 产生的节点更新。

每行建议是一条 JSON：

```json
{
  "node": "build_prompt",
  "update": {
    "prompt_payload": "...",
    "final_prompt": "..."
  }
}
```

用途：

```text
观察每个节点产生了什么 state update。
```

注意：

```text
graph_updates.jsonl 是从 LangGraph stream updates 整理出来的 artifact。
它不是 checkpoint，也不是 app.log。
```

### 8.5 output.json

记录 workflow 输出：

```text
status
message
sql
columns
rows
metadata
```

用途：

```text
检查对外返回结果。
```

注意：

```text
如果 rows 很大，后续需要设计截断策略。
Phase 4 初版仍然是 mock rows，可以完整写出。
```

### 8.6 manifest.json

记录本次 artifact 的索引：

```text
run_id
run_date
thread_id
request_id
status
started_at
finished_at
artifact_files
error
```

用途：

```text
让 app.log 和总输出只需要指向 manifest.json。
人或 AI 再从 manifest 找到具体文件。
```

## 9. 哪些放到总输出中

总输出指：

```text
Nl2SqlOutput
```

后续也可能包括 CLI/API/UI 返回。

总输出应该保留业务结果和少量可追踪信息：

```text
status
message
sql
columns
rows
trace_id 或 thread_id
metadata.artifact_manifest_path
metadata.final_prompt_path
metadata.prompt_payload_path
```

是否继续保留完整 `prompt_payload` / `final_prompt` 在 metadata 中，需要单独决策。

Phase 3 已经把它们放在 metadata 中，方便测试和早期验收。

Phase 4 可以有两种选择：

```text
选择 A：继续保留完整 metadata，同时新增 artifact 路径。
选择 B：metadata 中只保留 artifact 路径，完整内容只落盘。
```

我倾向 Phase 4 初版采用选择 A：

```text
保留完整 metadata，新增 artifact 路径。
```

原因：

```text
1. 不破坏 Phase 3 已有测试和使用方式。
2. artifact 机制成熟后，再决定是否瘦身 metadata。
3. 当前 mock prompt 和 mock rows 不大，重复保存风险可控。
```

## 10. 哪些不应该算日志

下面这些不应被当成日志系统本身：

```text
1. 控制台输出：
   只适合临时观察，不适合验收依据。

2. pytest 输出：
   只证明测试结果，不保存运行材料。

3. LangGraph checkpoint：
   用于恢复和状态持久化，不是人工验收文件。

4. Python exception traceback：
   是错误信号，不是结构化运行报告。

5. AI 对控制台输出的转述：
   只能作为说明，不能作为系统事实来源。
```

## 11. 与参考项目的关系

参考项目有几个值得保留的思路：

```text
1. 按 run_date/run_id 组织运行目录。
2. 有 main log。
3. 有 chain/detail log。
4. 有 run_record.json。
5. 有 token_summary.json。
6. 有日志脱敏和长文本控制意识。
```

但参考项目也暴露出一些问题：

```text
1. prompt_payload 和 prompt_text 主要混在 chain log 文本中。
2. 人要找最终 prompt 时，需要翻日志。
3. payload 是模板变量，不是后续可扩展的结构化上下文。
4. chain log 对 LangChain Runnable 很自然，但不完全贴合 LangGraph 节点状态流。
5. 日志文本适合阅读，不适合作为稳定 artifact 被其他 agent 读取。
6. full text / preview 控制如果用在 final_prompt 验收上，会让验收不稳定。
```

当前项目应该吸收：

```text
1. 保留 run_date/run_id 的目录组织方式。
2. 保留 app.log 作为摘要日志。
3. 保留 run record / manifest 的思想。
4. 后续接 LLM 后再引入 token summary。
5. 保留脱敏意识。
```

当前项目应该避免：

```text
1. 只把 prompt 写进普通日志文本。
2. 依赖控制台输出进行验收。
3. 让每个节点直接写文件。
4. 把 checkpoint 当成可读日志。
5. 在 final_prompt.txt 中默认截断文本。
```

## 12. token 消耗如何分类

token 消耗不应简单归到普通日志里，也不应完全等到 LangSmith 后再考虑。

更准确的分类是：

```text
LangGraph / LangChain：
  负责在 LLM 调用、message stream、run trace 中暴露 token 使用信息。

项目代码：
  负责把 token 使用信息归一化、汇总，并写入本项目稳定 artifact。

LangSmith：
  负责后续更完整的 trace、成本统计、dashboard 和跨 run 聚合。
```

也就是说：

```text
LangGraph/LangChain 是 token 信息来源之一。
LangSmith 是后续观测平台。
项目本地 artifact 才是当前阶段可验收、可复现的稳定文件。
```

### 12.1 token 信息来源

后续接真实 LLM 后，token 信息主要可能来自：

```text
1. LangChain AIMessage.usage_metadata。
2. AIMessage.response_metadata 中的 provider 原始 token_usage。
3. LangGraph stream_mode="messages" 的 message chunk / metadata。
4. LangSmith trace 中自动统计的 token 和 cost。
```

注意：

```text
Phase 3/4 当前还没有真实 LLM 调用，所以不会产生真实 token usage。
本阶段只需要把 token 消耗预留进分类，不要为了 token 提前接 LangSmith。
```

### 12.2 token 信息不应该放哪里

不建议把完整 token 明细只放在：

```text
1. 控制台输出。
2. app.log 大段文本。
3. checkpoint 内部结构。
4. Nl2SqlOutput 顶层字段。
```

原因：

```text
token 消耗既是调试信息，也是成本信息。
它需要能被机器聚合，也要能被人快速查看。
普通日志文本不适合作为唯一来源。
```

### 12.3 token 信息应该放哪里

建议后续真实 LLM 接入后新增：

```text
token_usage.json
```

或在多模型/多节点场景中使用：

```text
token_usage.jsonl
token_summary.json
```

初版可以先设计成：

```json
{
  "run_id": "run-xxx",
  "thread_id": "thread-xxx",
  "total": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0
  },
  "by_node": []
}
```

后续接 LLM 后，再扩展：

```json
{
  "node": "generate_sql",
  "model": "gpt-x",
  "input_tokens": 123,
  "output_tokens": 45,
  "total_tokens": 168,
  "provider_metadata": {}
}
```

### 12.4 app.log 中如何记录 token

app.log 只记录摘要和路径：

```text
NL2SQL workflow finished status=success total_tokens=168 artifact=...
```

不要把每次 LLM 调用的完整 usage metadata 全量写进 app.log。

原因：

```text
app.log 用来快速定位问题。
token_usage.json / token_summary.json 用来做明细和聚合。
```

### 12.5 总输出中如何记录 token

`Nl2SqlOutput.metadata` 后续可以放 token 摘要和文件路径：

```python
metadata = {
    "token_usage": {
        "input_tokens": 123,
        "output_tokens": 45,
        "total_tokens": 168,
    },
    "token_usage_path": ".../token_usage.json",
}
```

但不建议在总输出中放所有 provider 原始明细。

### 12.6 是否等 LangSmith

不建议把本地 token 分类完全推迟到 LangSmith。

原因：

```text
1. 当前阶段需要本地、稳定、可验收的文件。
2. LangSmith 是外部观测平台，不应成为本地调试的唯一入口。
3. 后续是否启用 LangSmith，可能受配置、网络、权限影响。
4. 本地 token_usage.json 能作为 LangSmith 之外的兜底事实来源。
```

更合适的路线：

```text
Phase 4：
  先在日志分类中预留 token_usage artifact。
  不接真实 LLM，不实现真实 token 统计。

后续 LLM phase：
  从 AIMessage.usage_metadata / response_metadata 中提取 token。
  写入 token_usage.json。
  app.log 和 Nl2SqlOutput 只放摘要与路径。

后续 observability phase：
  再接 LangSmith。
  用 LangSmith 做 trace、dashboard、成本聚合。
```

一句话：

```text
token 消耗属于“成本与模型调用观测”分类。
它和日志系统有关，但不应该只作为普通日志；
它也和 LangSmith 有关，但不应该完全等 LangSmith 才设计。
```

## 13. 推荐责任边界

推荐边界如下：

```text
GraphRuntime:
  继续负责 invoke/stream 的 LangGraph config。
  提供 run_id/run_date/thread_id。
  不负责写业务 artifact。

Nl2SqlWorkflow:
  适合成为 artifact 写入的编排入口。
  因为它同时知道 input、run_context、thread_id、最终 output。

NL2SQL nodes:
  继续只返回 state update。
  不直接写 app.log。
  不直接写 artifact。

logging platform:
  继续负责 app.log。
  可扩展 artifact 根目录信息，但不理解 NL2SQL 业务字段。

future artifact writer:
  负责写 input.json、prompt_payload.json、final_prompt.txt、graph_updates.jsonl、output.json、manifest.json。
  后续接真实 LLM 后，负责写 token_usage.json / token_summary.json。
  可以放在 workflow 附近或 platform observation 下，后续再定。
```

## 14. 初版分类决策

Phase 4 初版建议先确认以下分类：

```text
1. LangGraph 负责：
   thread_id、metadata、checkpoint、state updates、final state。

2. 项目 app.log 负责：
   workflow started/finished/failed、status、耗时、artifact manifest path。

3. NL2SQL artifact 负责：
   input.json、prompt_payload.json、final_prompt.txt、graph_updates.jsonl、output.json、manifest.json。
   token_usage.json 先预留，等真实 LLM 接入后再产生真实内容。

4. Nl2SqlOutput 负责：
   业务输出 + artifact 路径摘要。
```

### 14.1 进入 artifact 设计前的补充原则

以下原则仍然属于“分类边界”，不是具体实现方案。

#### 14.1.1 artifact 写入失败策略

artifact 属于调试与验收设施，不应默认让 NL2SQL 主流程失败。

初版原则：

```text
artifact 写入失败默认不影响 NL2SQL 主流程。
```

但必须保留错误可见性：

```text
1. app.log 记录 artifact 写入失败摘要。
2. Nl2SqlOutput.metadata 记录 artifact_error。
3. 如果 manifest 写入失败，则 artifact_manifest_path 为空。
```

后续可以考虑开发/验收模式：

```text
artifact_required = true
```

在这种模式下，artifact 写入失败可以让测试或验收失败。

#### 14.1.2 artifact 目录不能只按 run_id 组织

一个 `run_id` 下可能有多次 NL2SQL 调用。

因此 artifact 目录不能只到：

```text
workspace/runs/<run_date>/<run_id>/
```

后续 artifact 设计应至少区分到单次 workflow 调用：

```text
workspace/runs/<run_date>/<run_id>/nl2sql/<thread_id-or-request_id>/
```

原则：

```text
1. 优先使用 request_id 表达业务请求。
2. 没有 request_id 时使用 thread_id。
3. 不允许同一 run_id 下多次 NL2SQL 调用互相覆盖 artifact。
```

#### 14.1.3 final_prompt.txt 默认完整，但 manifest 记录大小

`final_prompt.txt` 是验收最终提示词效果的核心文件。

初版原则：

```text
1. final_prompt.txt 默认完整写出。
2. 不默认截断。
3. manifest.json 记录 final_prompt_size_bytes。
```

这样后续 prompt 变大时，可以先从 manifest 中看到体积变化。

#### 14.1.4 JSON 文件格式要按用途区分

给人看的 JSON 应可读。

建议：

```text
prompt_payload.json:
  indent=2
  ensure_ascii=false

output.json:
  indent=2
  ensure_ascii=false

manifest.json:
  indent=2
  ensure_ascii=false
```

按行追加、给机器消费的 JSONL 应稳定。

建议：

```text
graph_updates.jsonl:
  每行一条 compact JSON
  ensure_ascii=false

token_usage.jsonl:
  每行一条 compact JSON
  ensure_ascii=false
```

#### 14.1.5 敏感信息策略先分类，真实数据接入前再实现

当前 Phase 4 仍然不接真实 DB、真实 schema、真实 LLM。

因此初版不实现复杂脱敏，但必须保留阶段性原则：

```text
1. Phase 4 mock 阶段不做复杂脱敏实现。
2. artifact writer 后续应预留 redaction_policy 或等价扩展点。
3. 真实 DB / 用户数据 / schema grounding 接入前，必须重新评审脱敏策略。
4. final_prompt.txt 是否脱敏，需要在真实数据接入前单独决策。
```

这个原则吸收参考项目的脱敏意识，但避免当前阶段过度设计。

#### 14.1.6 关键字段命名必须一致

后续 app.log、manifest.json、output.metadata、token_usage.json 中应复用同一组字段名。

建议固定这些字段名：

```text
run_id
run_date
thread_id
request_id
status
started_at
finished_at
artifact_manifest_path
final_prompt_path
prompt_payload_path
token_usage_path
artifact_error
```

不要在不同输出中混用：

```text
thread / thread_id
trace_id / thread_id
conversation_id / thread_id
manifest / artifact_manifest_path
```

字段名一致可以降低后续查询、自动评审和跨文件关联成本。

这个分类确认后，再进入下一份文档：

```text
Phase4_NL2SQL运行artifact设计.md
```

那份文档再具体讨论：

```text
1. artifact 目录路径。
2. 文件格式。
3. 写入时机。
4. 写入失败策略。
5. 如何从 LangGraph stream 生成 graph_updates.jsonl。
6. token_usage.json 在无真实 LLM 阶段是否只预留、不写入。
7. artifact 目录如何避免多次 workflow 调用互相覆盖。
8. manifest 如何记录文件大小和错误。
9. JSON / JSONL 的格式规则。
10. redaction_policy 是否只预留不实现。
11. 字段命名如何保持一致。
12. 如何测试。
```

## 15. 暂不决定的问题

以下问题先不在本文解决：

```text
1. artifact writer 具体放在哪个目录。
2. 是否新增 services/ 或 platform/observation。
3. 是否引入 JSON schema。
4. 是否对 final_prompt 做脱敏。
5. metadata 未来是否移除完整 prompt_payload/final_prompt。
6. token summary 何时真正实现。
7. 是否接入 LangSmith。
8. 真实 LLM 调用日志如何分类。
```

原因：

```text
这些属于 artifact 设计或 LLM 接入设计。
本文只负责日志分类。
```

## 16. 完成标准

这份日志分类设计通过时，应满足：

```text
1. 清楚区分 LangGraph 运行机制与项目日志。
2. 清楚区分 app.log、artifact、总输出。
3. 明确 checkpoint 不是人工验收日志。
4. 明确 final_prompt 应有独立可读文件。
5. 明确 prompt_payload 应有独立结构化 JSON 文件。
6. 明确 graph_updates 来自 LangGraph stream updates。
7. 明确参考项目哪些做法要吸收，哪些问题要避免。
8. 明确 token 消耗属于成本与模型调用观测，不只是普通日志。
9. 明确 token_usage 本地 artifact 不需要等待 LangSmith。
10. 明确 artifact 写入失败默认不影响主流程，但错误必须可见。
11. 明确 artifact 目录必须区分单次 NL2SQL 调用，不能只按 run_id。
12. 明确 final_prompt.txt 默认完整，manifest 记录大小。
13. 明确 JSON/JSONL 格式按用途区分。
14. 明确敏感信息策略先预留，真实数据接入前再评审。
15. 明确关键字段命名要在 app.log、manifest、metadata、token usage 中保持一致。
16. 不提前设计完整日志平台。
17. 不提前接入真实 LLM / DB / schema grounding。
```

一句话总结：

```text
Phase 4 的第一步不是写日志代码，而是先把“谁负责什么信息、信息去哪、谁来看”分类清楚。
```
