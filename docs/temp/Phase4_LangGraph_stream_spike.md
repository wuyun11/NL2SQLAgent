# Phase 4 LangGraph stream spike

> 本文是 Phase 4 artifact 设计的技术验证 spike。
>
> 目标不是实现日志系统，而是验证一个关键问题：
>
> ```text
> 能否在一次 LangGraph 执行中同时拿到 stream updates 和 final state？
> ```
>
> 这个结论会决定后续 `graph_updates.jsonl` 如何实现。

## 1. 背景

当前 artifact 设计希望一次 `Nl2SqlWorkflow.run(...)` 自动产出：

```text
input.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
output.json
manifest.json
```

其中：

```text
prompt_payload.json / final_prompt.txt / output.json
  需要最终 graph state 或 Nl2SqlOutput。

graph_updates.jsonl
  需要 LangGraph stream_mode="updates" 的节点更新。
```

当前未知点是：

```text
graph.stream(..., stream_mode="updates") 是否能在一次执行中同时提供 final state？
```

如果不能，就会出现选择：

```text
1. 为了 graph_updates 再执行一次 graph。
2. run 只写 final artifact，stream 才写 graph_updates。
3. 使用 LangGraph 其他 API 或 checkpoint 获取 final state。
```

因此必须先做一个 spike。

## 2. 要回答的问题

这个 spike 只回答下面几个问题：

```text
Q1. stream_mode="updates" 返回的 chunk 具体形态是什么？
Q2. stream_mode="values" 返回的 chunk 具体形态是什么？
Q3. stream_mode=["updates", "values"] 是否可用？
Q4. 如果多 stream mode 可用，返回结构是什么？
Q5. stream 执行结束后，是否可以通过 graph.get_state(config) 拿到 final state？
Q6. 使用 checkpointer 时，get_state(config) 的 values 是否等于 graph.invoke(...) 的最终 state？
Q7. 对当前 NL2SQL graph，stream updates 是否包含 build_prompt 的 prompt_payload/final_prompt？
Q8. 是否能避免为了 artifact 重复执行 graph？
```

不回答：

```text
1. 不设计 artifact writer。
2. 不改 Nl2SqlWorkflow。
3. 不改 GraphRuntime 正式接口。
4. 不接 LangSmith。
5. 不接真实 LLM。
```

## 3. 实验原则

```text
1. 使用当前项目已有 NL2SQL graph。
2. 使用 memory checkpointer。
3. 使用真实 GraphRuntime config 规则。
4. 不修改生产代码。
5. spike 代码可以放在 docs/temp 或临时测试文件中。
6. 结论写回本文档。
```

推荐优先用临时 pytest 文件。

原因：

```text
pytest 更容易断言行为，也能避免只看控制台。
```

## 4. 建议临时文件

建议创建临时 spike 测试：

```text
tests/spikes/test_langgraph_stream_behavior.py
```

注意：

```text
spike 文件用于技术验证。
验证完成后，可以保留为文档化测试，也可以在执行计划前删除。
如果保留，需要确保它稳定且不依赖临时输出。
```

## 5. spike 准备代码

建议测试文件中复用当前集成测试的 runtime 构造方式：

```python
from __future__ import annotations

from datetime import datetime

from nl2sqlagent.platform.config import CheckpointerSection, WorkflowSection
from nl2sqlagent.platform.persistence import build_checkpointer
from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql import build_nl2sql_graph
from nl2sqlagent.workflows.runtime import GraphRuntime


def _runtime() -> tuple[GraphRuntime, object, RunContext]:
    return (
        GraphRuntime(),
        build_checkpointer(
            WorkflowSection(checkpointer=CheckpointerSection(provider="memory"))
        ),
        RunContext(
            run_id="run-stream-spike",
            run_date="20260509",
            started_at=datetime(2026, 5, 9, 9, 0, 0),
        ),
    )
```

## 6. 实验 A：观察 updates stream

目的：

```text
确认当前 NL2SQL graph 的 stream_mode="updates" chunk 形态。
```

建议测试：

```python
def test_stream_updates_shape() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    chunks = runtime.stream(
        graph=graph,
        input={"raw_question": "统计员工数量", "options": {}},
        run_context=run_context,
        thread_id="thread-stream-updates",
        stream_mode="updates",
    )

    assert chunks
    assert all(isinstance(chunk, dict) for chunk in chunks)
    assert any("build_prompt" in chunk for chunk in chunks)
    build_prompt_chunk = next(chunk for chunk in chunks if "build_prompt" in chunk)
    assert "prompt_payload" in build_prompt_chunk["build_prompt"]
    assert "final_prompt" in build_prompt_chunk["build_prompt"]
```

预期：

```text
updates chunk 形态接近：
{"build_prompt": {"prompt_payload": {...}, "final_prompt": "..."}}
```

## 7. 实验 B：观察 values stream

目的：

```text
确认 stream_mode="values" 是否能拿到每步后的完整 state，并且最后一个 chunk 是否是 final state。
```

建议测试：

```python
def test_stream_values_last_chunk_is_final_state() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    chunks = runtime.stream(
        graph=graph,
        input={"raw_question": "统计员工数量", "options": {}},
        run_context=run_context,
        thread_id="thread-stream-values",
        stream_mode="values",
    )

    assert chunks
    final_state = chunks[-1]
    assert final_state["status"] == "success"
    assert final_state["checked_sql"] == "SELECT 1 AS value"
    assert final_state["prompt_payload"]["question"]["normalized"] == "统计员工数量"
    assert "User Question:\n统计员工数量" in final_state["final_prompt"]
```

预期：

```text
如果最后一个 values chunk 是 final state，则可以用 values stream 获取 final state。
```

## 8. 实验 C：多 stream mode 是否可用

目的：

```text
验证 stream_mode=["updates", "values"] 是否可以在一次执行中同时拿到 updates 和 values。
```

建议测试：

```python
def test_stream_multiple_modes_shape() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    chunks = runtime.stream(
        graph=graph,
        input={"raw_question": "统计员工数量", "options": {}},
        run_context=run_context,
        thread_id="thread-stream-multi",
        stream_mode=["updates", "values"],
    )

    assert chunks
    # Intentionally inspect shape first.
    # Update assertions after seeing actual LangGraph return structure.
    print(chunks)
```

执行方式：

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/spikes/test_langgraph_stream_behavior.py::test_stream_multiple_modes_shape -v -s
```

这个测试第一轮允许使用 `print`，因为它是 spike。

验证后应把 `print` 替换成具体断言。

可能结果：

```text
1. 支持 list stream_mode，并返回 (mode, chunk) 或类似结构。
2. 不支持 list stream_mode，抛出异常。
3. 支持但结构与预期不同。
```

## 9. 实验 D：stream 后 get_state

目的：

```text
验证在 stream_mode="updates" 执行结束后，能否通过 graph.get_state(config) 获取 final state。
```

因为当前 `GraphRuntime._config(...)` 是内部方法，spike 可以直接调用它，或者在测试中手工构造同样 config。

建议测试：

```python
def test_get_state_after_updates_stream() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)
    config = runtime._config(
        run_context=run_context,
        thread_id="thread-stream-get-state",
    )

    chunks = list(
        graph.stream(
            {"raw_question": "统计员工数量", "options": {}},
            config=config,
            stream_mode="updates",
        )
    )
    snapshot = graph.get_state(config)

    assert chunks
    assert snapshot.values["status"] == "success"
    assert snapshot.values["checked_sql"] == "SELECT 1 AS value"
    assert snapshot.values["prompt_payload"]["question"]["normalized"] == "统计员工数量"
```

预期：

```text
如果可行，则后续 GraphRuntime.invoke_with_updates 可以：
  1. stream updates 收集 chunks。
  2. stream 结束后 graph.get_state(config) 获取 final state。
```

注意：

```text
如果 get_state API 不存在或返回结构不同，记录实际行为。
```

## 10. 实验 E：invoke final state 对照

目的：

```text
验证 stream 后 get_state 得到的 final state 与 invoke 得到的 final state 是否一致。
```

建议：

```python
def test_stream_get_state_matches_invoke_result() -> None:
    runtime, checkpointer, run_context = _runtime()

    graph_for_stream = build_nl2sql_graph(checkpointer=checkpointer)
    config = runtime._config(
        run_context=run_context,
        thread_id="thread-stream-compare",
    )
    list(
        graph_for_stream.stream(
            {"raw_question": "统计员工数量", "options": {}},
            config=config,
            stream_mode="updates",
        )
    )
    streamed_state = graph_for_stream.get_state(config).values

    graph_for_invoke = build_nl2sql_graph(checkpointer=checkpointer)
    invoked_state = runtime.invoke(
        graph=graph_for_invoke,
        input={"raw_question": "统计员工数量", "options": {}},
        run_context=run_context,
        thread_id="thread-stream-compare-invoke",
    )

    assert streamed_state["status"] == invoked_state["status"]
    assert streamed_state["checked_sql"] == invoked_state["checked_sql"]
    assert streamed_state["final_prompt"] == invoked_state["final_prompt"]
```

注意：

```text
不要用同一个 thread_id 对同一个 checkpointer 连续 stream 和 invoke。
否则 checkpoint 历史可能影响判断。
```

## 11. 判定标准

### 11.1 最理想结果

```text
stream_mode="updates" + graph.get_state(config) 可行。
```

后续设计结论：

```text
新增 GraphRuntime.invoke_with_updates:
  returns final_state + update_chunks
```

artifact writer 可以一次 run 产出：

```text
graph_updates.jsonl
output.json
manifest.json
```

### 11.2 次优结果

```text
stream_mode=["updates", "values"] 可行。
```

后续设计结论：

```text
GraphRuntime.invoke_with_updates 使用多 stream mode：
  从 updates 提取 graph_updates。
  从 values 最后一个 chunk 提取 final_state。
```

### 11.3 降级结果

```text
只能拿 updates，不能拿 final state。
```

后续设计结论：

```text
Phase 4 初版不要为了 artifact 重复执行 graph。
run() 先写 final artifact。
stream() 再单独支持 graph_updates artifact。
```

或：

```text
Phase 4 先不交付 graph_updates.jsonl，只在 manifest 中标记未生成。
```

这会降低 artifact 完整性，但避免重复执行。

## 12. spike 后需要更新的文档

spike 完成后，需要回写：

```text
docs/temp/Phase4_NL2SQL运行artifact设计.md
```

重点更新：

```text
1. 第 14 节写入时机。
2. 第 21 节 graph_updates 如何生成。
3. 第 25 节执行任务拆分。
```

如果 spike 证明 `invoke_with_updates` 可行，还需要在后续计划中加入：

```text
Task：新增 GraphRuntime.invoke_with_updates
Task：测试 updates + final_state 同时返回
```

如果 spike 证明不可行，则执行计划必须明确降级方案，不能假设完整 graph_updates。

## 13. spike 完成标准

完成时应得到明确结论：

```text
1. updates stream chunk 形态是什么。
2. values stream 是否能拿 final state。
3. 多 stream mode 是否可用。
4. stream 后 get_state 是否可用。
5. 是否能一次执行同时拿 updates 和 final state。
6. 后续 artifact 设计应采用哪种策略。
```

一句话总结：

```text
这个 spike 是 Phase 4 的技术闸门：不先验证 LangGraph stream 行为，就不应该写 artifact 执行计划。
```
