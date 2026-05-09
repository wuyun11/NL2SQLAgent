这份《Phase4_NL2SQL 运行 artifact 设计》整体上**方向正确，而且已经比“日志分类设计”更落地**。它很好地承接了前一份分类文档：不是继续空谈日志，而是具体落到了目录、文件、写入时机、失败策略、metadata、app.log 和测试重点。

我的结论是：

```text
设计可以通过。
但还不能直接写执行计划。
需要先解决一个关键技术风险：
如何在一次 LangGraph 执行中同时拿到 updates 和 final state。
```

这份文档自己也意识到了这一点，并把它列为执行计划阶段必须先验证的技术风险。 这是全篇最关键的点。

---

## 1. 总体评价

这份设计比前一份“日志分类设计”更进一步，已经回答了这些问题：

```text
artifact 放哪里
每次 NL2SQL 调用怎么隔离
写哪些文件
每个文件记录什么
output.metadata 增加哪些路径
app.log 写什么摘要
写入失败怎么办
token_usage 现在做不做
artifact writer 放在哪里
nodes 是否写文件
```

我认为这些大方向都是对的。尤其是这几条：

```text
1. 节点不直接写文件。
2. checkpoint 不作为人工验收日志。
3. app.log 只放摘要和 artifact 路径。
4. final_prompt.txt 默认完整写出。
5. graph_updates.jsonl 来自 LangGraph stream updates。
6. artifact 写入失败默认不影响主流程。
7. 当前阶段不做真实 token 统计。
```

这些原则都和前一份分类文档一致。

---

## 2. 放在 `workspace/logs/.../artifacts` 下是可以接受的

文档建议目录为：

```text
workspace/logs/<run_date>/<run_id>/artifacts/nl2sql/<artifact_id>/
```

而不是新增 `workspace/runs`。理由是当前项目已经有 `LoggingRuntime.log_dir`，Phase 4 是日志/观测能力，不需要马上扩展 `ProjectPaths` 和 `env.yml`。

我认为这可以接受。

我之前更倾向过：

```text
workspace/runs/<run_date>/<run_id>/nl2sql/<thread_id>/
```

但在你当前项目阶段，复用 `LoggingRuntime.log_dir` 更克制。只要文档明确：

```text
logs 下的 artifacts 是“调试观测文件”，不是业务数据存储。
```

就没有问题。

后续如果你真的需要长期归档、查询、清理策略，再拆成 `workspace/runs` 也不迟。

---

## 3. `artifact_id = request_id else resolved_thread_id` 合理

一个 `run_id` 下可能有多次 NL2SQL 调用，所以必须有单次调用目录。文档建议：

```text
artifact_id = request_id if request_id else resolved_thread_id
```

并要求目录名做文件名安全处理。

这个规则合理。

不过我建议在下一版里补一句：

```text
manifest 中必须同时保留 request_id 和 thread_id。
artifact_id 只是目录名，不替代 thread_id。
```

原因是：`request_id` 和 `thread_id` 的语义不同。

```text
request_id:
  外部业务请求标识

thread_id:
  LangGraph checkpoint / stream / 状态线程标识
```

artifact 目录可以优先用 `request_id`，但 `manifest.json` 必须保留真实 `thread_id`，否则后续查 checkpoint 或 stream history 时会断链。

LangGraph persistence 文档也明确，checkpointer 使用 `thread_id` 作为保存和恢复 checkpoint 的主键。([LangChain 文档][1])

---

## 4. 文件清单合理

文档建议单次运行生成：

```text
input.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
output.json
manifest.json
```

这是一个很好的最小集合。

它们分别回答：

```text
input.json:
  这次输入是什么

prompt_payload.json:
  提示词材料是什么

final_prompt.txt:
  最终给模型看的提示词是什么

graph_updates.jsonl:
  每个节点返回了什么 update

output.json:
  workflow 最终输出是什么

manifest.json:
  本次运行有哪些文件、状态、耗时、大小、错误
```

这个设计正好解决你上个项目的问题：**最终 prompt 不再藏在 chain log 或控制台里，而是独立成为可读、可 diff 的文件。**

---

## 5. `graph_updates.jsonl` 的定位非常好

文档把 LangGraph `stream_mode="updates"` 的原始 chunk 标准化为：

```json
{"node":"build_prompt","update":{"final_prompt":"..."}}
```

如果一个 chunk 里有多个 node，每个 node 写一行。

这个设计非常实用。

LangGraph 文档说明，`updates` 会流式输出每一步之后的 state update，`values` 会输出每一步之后的完整 state。([LangChain 文档][2]) LangGraph reference 也说明，`updates` 发出的是节点或任务名以及节点返回的更新。([LangChain 参考文档][3])

所以你的 `graph_updates.jsonl` 是很自然的派生 artifact：它不是 checkpoint，不是 app.log，而是把 stream update 变成可读文件。

JSON Lines 也适合这个场景，因为它的基本规则就是 UTF-8 编码、每行一个合法 JSON 值、用 `\n` 分隔。([JSON Lines][4]) 每个节点 update 一行，后续人看、脚本筛、agent 读都方便。

---

## 6. `output.metadata` 继续保留完整 prompt，同时新增路径，合理

文档建议 Phase 4 初版继续保留：

```text
metadata.prompt_payload
metadata.final_prompt
```

同时新增：

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

这个我支持。

原因是：

```text
1. 不破坏 Phase 3 既有测试。
2. 现在还是 mock 数据，重复保存成本可控。
3. artifact 机制刚引入，不要马上把 metadata 瘦身。
4. 后面真实数据接入前，再决定是否只留路径。
```

不过下一版执行计划要注意一个细节：**`output.json` 里如果保存完整 `metadata`，里面会包含 `output_path` 指向自己。**

这不是错误，但要避免出现不可序列化对象或循环引用。你当前 metadata 都是字符串/字典/None，问题不大。

---

## 7. `token_usage` 当前只预留、不生成文件，是对的

文档明确：

```text
metadata.token_usage_path = null
manifest.artifact_files.token_usage = null
不创建空 token_usage.json
```

理由是当前没有真实 LLM，空文件容易让人误以为已经统计。

这个判断很好。

后续真实 LLM 接入后，再从 `AIMessage.usage_metadata`、`response_metadata` 或 trace 中归一化 token 信息即可。现在先占位路径，不造假数据，是正确的。

---

## 8. artifact writer 放在 `workflows/nl2sql/artifacts.py`，阶段性合理

文档比较了三个方案：

```text
A. workflows/nl2sql/artifacts.py
B. platform/observation/artifacts.py
C. 通用 writer + NL2SQL adapter
```

最后推荐 A。

我同意。

原因是 Phase 4 的 artifact 明显理解 NL2SQL 字段：

```text
prompt_payload
final_prompt
graph_updates
Nl2SqlOutput
```

放在 platform 层会让 platform 理解业务字段，反而不干净。

等未来真的有第二个 workflow 也需要类似机制，再抽取公共 JSON/TXT/JSONL 写入工具即可。现在放在 `workflows/nl2sql/artifacts.py` 更符合 YAGNI。

---

## 9. 最大技术风险：一次执行同时拿到 updates 和 final state

这是这份文档最需要小心的地方。

你希望：

```text
一次 run 同时产出 final state 和 graph_updates.jsonl
```

文档提出扩展：

```python
GraphRuntime.invoke_with_updates(...)
```

用 `graph.stream(..., stream_mode="updates")` 执行一次 graph，收集 updates，再从 stream 结束后获取 final state。

方向对，但执行前必须验证 LangGraph API。

因为：

```text
stream_mode="updates" 只给每步 update，不一定直接给最终完整 state。
stream_mode="values" 给每步完整 state，但 chunk 形态和 updates 不同。
```

LangGraph reference 说明 `stream_mode` 可以传 list，并且 streamed outputs 会是 `(mode, data)` tuple。([LangChain 参考文档][5])

所以我建议执行计划第一步专门做一个 Spike：

```text
Spike：验证 graph.stream(..., stream_mode=["updates", "values"])
目标：
  1. 一次执行拿到 updates
  2. 一次执行拿到 final full state
  3. 不重复 invoke
```

如果可行，`invoke_with_updates` 可以这样设计：

```python
@dataclass(frozen=True)
class GraphRunResult:
    final_state: dict[str, Any]
    updates: list[dict[str, Any]]
```

如果不可行，退路也要明确：

```text
Phase 4 初版：
  run() 先只写 final artifact；
  stream() 再写 graph_updates；
  或者暂时不承诺 graph_updates.jsonl 一定存在。
```

但我建议优先尝试 `stream_mode=["updates", "values"]`，因为这最符合“一次执行”的目标。

---

## 10. 写入失败策略合理，但要补一个关键细节

你现在设计：

```text
artifact 写入失败默认不影响主流程
artifact_required=true 时可以抛异常
```

这个对。

但有一个细节需要补：

```text
如果写到一半失败，是否保留部分文件？
manifest 是否写 artifact_error？
```

建议下一版明确：

```text
1. 尽量先写 input/prompt/output 等文件。
2. manifest 最后写。
3. 如果 manifest 写成功但部分文件失败，manifest.artifact_error 记录错误。
4. 如果 manifest 也失败，output.metadata.artifact_error 记录错误，artifact_manifest_path 为 null。
5. 不做事务性回滚，不删除已写文件。
```

原因：artifact 是调试材料，部分文件也有价值。强行回滚反而会丢证据。

---

## 11. app.log 设计正确，但要明确 logger 从哪里来

文档要求 app.log 只写摘要：

```text
workflow started
workflow finished
artifact write failed
```

不写完整 prompt/payload/updates。

这个对。

但执行设计里要明确：

```text
Nl2SqlWorkflow 需要拿到 logger 或 logging_runtime 吗？
```

现在 `Nl2SqlWorkflow` 已经有：

```text
graph
graph_runtime
run_context
```

如果你要在 workflow started/finished 写 app.log，可能需要再注入：

```python
logger: logging.Logger
```

或者注入一个很薄的 `Nl2SqlRunLogger`。

我建议 Phase 4 初版可以简单注入 logger：

```python
@dataclass(frozen=True)
class Nl2SqlWorkflow:
    graph: object
    graph_runtime: GraphRuntime
    run_context: RunContext
    log_dir: Path
    logger: Logger
```

但不要让 nodes 拿 logger。logger 只在 facade 层写摘要。

---

## 12. artifact writer 接口还差两个参数

文档建议接口：

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

这个基本可以，但我建议补两个参数：

```python
final_state: dict[str, Any] | None = None
artifact_id: str | None = None
```

原因：

```text
1. prompt_payload/final_prompt 的最权威来源其实是 final_state。
   output.metadata 也有，但 output 可能后续被瘦身。

2. artifact_id 显式传入有利于测试 request_id/thread_id 优先级。
   writer 内部也可以计算，但测试时更容易验证。
```

更推荐：

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

artifact_id 可以内部按 `input.request_id or resolved_thread_id` 计算。

---

## 13. 还需要补一个“路径是字符串还是 Path”的规则

`output.metadata` 和 JSON 文件里应该保存字符串路径，而不是 `Path` 对象。

建议明确：

```text
artifact writer 内部使用 Path。
写入 JSON / metadata 时统一转成 str。
```

否则后面 `json.dump` 会遇到 `Path` 不可序列化的问题。

---

## 14. 关于覆盖策略，我建议稍微保守一点

文档说同一个 `artifact_id` 再次写入时默认覆盖同名文件，这是可接受的，因为同一个 `thread_id` 代表同一条线程。

我理解这个逻辑，但我建议加一个小保护：

```text
Phase 4 初版允许覆盖。
但 manifest 中记录 overwritten=true 或 write_mode="overwrite"。
```

或者更简单：

```text
manifest.write_mode = "overwrite"
```

原因是调试时你可能会误以为看到的是第一次运行，实际已经被覆盖。哪怕不引入 attempt_index，也应该让 manifest 表示当前写入策略。

---

## 15. 最终评价

这份设计**可以通过**，而且已经非常接近 implementation plan 的前置设计了。

它最强的地方是：

```text
1. 没有把 checkpoint 当日志。
2. 没有让 node 写文件。
3. 没有把完整 prompt 塞进 app.log。
4. 有单次运行 artifact 目录。
5. 有 final_prompt.txt、prompt_payload.json、graph_updates.jsonl。
6. 有 manifest 索引。
7. 有 artifact 写入失败策略。
8. token_usage 只预留，不造假。
```

但执行前必须先解决：

```text
如何一次执行同时拿到 graph_updates 和 final_state。
```

这是唯一会影响实现路线的关键技术点。

我的建议是：**下一步先写一个很小的 LangGraph stream spike 文档或测试，验证 `stream_mode=["updates", "values"]` 是否能满足需求；验证通过后，再写 Phase 4 artifact implementation plan。**

[1]: https://docs.langchain.com/oss/python/langgraph/persistence?utm_source=chatgpt.com "Persistence - Docs by LangChain"
[2]: https://docs.langchain.com/oss/python/langgraph/streaming?utm_source=chatgpt.com "Streaming - Docs by LangChain"
[3]: https://reference.langchain.com/python/langgraph/types/StreamMode?utm_source=chatgpt.com "StreamMode | langgraph"
[4]: https://jsonlines.org/?utm_source=chatgpt.com "JSON Lines"
[5]: https://reference.langchain.com/python/langgraph/pregel/main/Pregel/stream?utm_source=chatgpt.com "stream | langgraph"
