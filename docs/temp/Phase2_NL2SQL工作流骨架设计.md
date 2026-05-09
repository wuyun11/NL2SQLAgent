# Phase 2 NL2SQL 工作流骨架设计

> 本文是 Phase 2 的讨论设计稿。
>
> 目标不是写可交给 agent 直接执行的任务清单；真正的执行计划后续再放到 `docs/superpowers/plans/`。

## 1. 背景

当前项目已经完成：

- Phase 0：配置、路径、日志、RunContext、bootstrap、CLI startup。
- Phase 1：LangGraph checkpointer、thread_id、GraphRuntime、hello graph 验证通道。

Phase 1 解决的是：

```text
项目如何统一运行 LangGraph。
```

Phase 2 开始进入 NL2SQL，但仍然不应该进入真实业务实现。

这一阶段真正要解决的是：

```text
NL2SQL workflow 的基础流程能不能跑通。
每个节点的输入输出能不能看清楚。
最终给模型看的 prompt 能不能稳定生成和观察。
workflow facade 的输入输出边界是否稳定。
```

所以 Phase 2 仍然是**纯骨架阶段**，不是 SQL 生成质量阶段。

## 2. 核心结论

Phase 2 初版应该定位为：

```text
NL2SQL 线性工作流骨架 + final_prompt 观察能力
```

也就是说：

```text
要做：
  基础流程跑通
  build_prompt 节点
  prompt_payload / final_prompt 进入 state
  output metadata 或 stream 能看到 final_prompt

不要做：
  retry
  真实 LLM
  真实数据库
  真实 schema grounding
  旧 SQLAgent 代码迁移
```

这里的关键判断是：

```text
现在最重要的不是“失败后如何重试”，而是“第一次给模型看的最终提示词到底长什么样”。
```

如果 final_prompt 的生成、观察、调试路径还没有打通，提前加入 retry 只会增加流程复杂度，让问题更难定位。

## 3. 为什么 Phase 2 不做 retry

retry 本身后续一定会需要，但不是 Phase 2 初版最重要的能力。

retry 依赖一组前置设计稳定：

```text
上一轮 SQL 如何保存。
上一轮错误如何表达。
feedback 如何写回 prompt。
首轮 prompt 和 retry prompt 有什么区别。
最大轮数在哪里配置。
失败后的最终 response 怎么组织。
stream 中如何看清每一轮状态。
```

这些都属于后续质量闭环。

Phase 2 如果先做 retry，会把当前阶段从“看清楚单轮流程”扩大成“设计失败恢复机制”。这会偏离当前最需要验证的东西。

因此 Phase 2 明确不做：

```text
check_sql -> generate_sql
execute_sql -> generate_sql
round_index
max_round_count
feedback
```

后续等 prompt、生成、检查、执行这几个单轮边界稳定后，再加 retry。

## 4. Phase 2 范围

Phase 2 要做：

```text
1. 定义 Nl2SqlInput / Nl2SqlOutput。
2. 定义 Nl2SqlGraphState。
3. 新增 workflows/nl2sql 线性 graph。
4. 新增 build_prompt_node。
5. 用 mock 节点跑通 normalize -> build_prompt -> generate -> check -> execute -> response。
6. 通过 workflow output metadata 或 GraphRuntime.stream 看到 final_prompt。
7. 提供最薄 Nl2SqlWorkflow facade。
8. build_app 暴露 nl2sql_workflow。
```

Phase 2 不做：

```text
1. CLI ask。
2. 真实 LLM chain。
3. 真实数据库连接。
4. 真实 SQL 执行。
5. 真实 schema grounding。
6. schema-index workflow。
7. QueryPlan。
8. Human Review。
9. evaluation golden set。
10. 旧 SQLAgent 代码迁移。
11. retry。
```

`CLI ask` 可以后做。只要 `Nl2SqlWorkflow.run(input) -> output` 这个 facade 稳定，后续 CLI/API 都只是很薄的外部适配层。

## 5. 推荐工作流

Phase 2 初版 graph：

```text
START
  -> normalize_question
  -> route_after_normalize
      -> clarification_response
      -> build_prompt
  -> generate_sql
  -> check_sql
  -> route_after_check
      -> failed_response
      -> execute_sql
  -> route_after_execute
      -> failed_response
      -> success_response
  -> END
```

这个流程保留失败分支，但不做失败后的回路。

含义是：

```text
空问题：
  normalize_question
    -> clarification_response
    -> END

普通问题成功：
  normalize_question
    -> build_prompt
    -> generate_sql
    -> check_sql
    -> execute_sql
    -> success_response
    -> END

SQL 检查失败：
  normalize_question
    -> build_prompt
    -> generate_sql
    -> check_sql
    -> failed_response
    -> END

执行失败：
  normalize_question
    -> build_prompt
    -> generate_sql
    -> check_sql
    -> execute_sql
    -> failed_response
    -> END
```

## 6. State 设计

Phase 2 的 state 先服务于单轮流程和 prompt inspection。

建议结构：

```python
from typing import Any, Literal, TypedDict


class Nl2SqlGraphState(TypedDict, total=False):
    request_id: str | None
    user_id: str | None
    database_key: str | None

    raw_question: str
    normalized_question: str
    clarification_message: str | None

    prompt_payload: dict[str, Any]
    final_prompt: str | None

    generated_sql: str | None
    checked_sql: str | None
    check_error: str | None
    execute_error: str | None

    result_columns: list[str]
    result_rows: list[dict[str, Any]]

    status: Literal[
        "running",
        "success",
        "needs_clarification",
        "failed",
        "rejected",
    ]
    message: str | None
```

暂时不放：

```text
round_index
max_round_count
feedback
```

这些字段等 retry 阶段再加入。

注意：

```text
state 中只能放可序列化数据。
不要放 LLM client、database connection、vectorstore、logger 这类外部对象。
```

## 7. Input / Output 契约

### 7.1 Nl2SqlInput

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Nl2SqlInput:
    question: str
    request_id: str | None = None
    user_id: str | None = None
    database_key: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
```

`options` 只用于 Phase 2 mock 场景控制，例如：

```text
force_check_error
force_execute_error
```

它不是长期业务输入模型。

Phase 2 只固定两个 mock 选项：

```python
options={"force_check_error": True}
options={"force_execute_error": True}
```

语义：

```text
force_check_error:
  check_sql_node 直接写 check_error="mock check error"，并进入 failed 分支。

force_execute_error:
  execute_sql_node 直接写 execute_error="mock execute error"，并进入 failed 分支。
```

不要在 Phase 2 引入：

```text
scenario
fail_times
round_count
```

这些都会把线性骨架重新带回复杂流程控制问题。

### 7.2 Nl2SqlOutput

```python
from dataclasses import dataclass, field
from typing import Any, Literal


Nl2SqlStatus = Literal[
    "success",
    "needs_clarification",
    "failed",
    "rejected",
]


@dataclass(frozen=True)
class Nl2SqlOutput:
    status: Nl2SqlStatus
    message: str | None = None
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

不要给 `Nl2SqlOutput` 直接加 `final_prompt` 字段。

原因：

```text
final_prompt 是调试观察信息，不是长期业务响应字段。
```

Phase 2 可以把它放到 `metadata`：

```python
metadata={
    "prompt_payload": state.get("prompt_payload"),
    "final_prompt": state.get("final_prompt"),
}
```

后续如果担心 prompt 泄露，再加配置开关控制是否输出。

## 8. Node 设计

Phase 2 初版 nodes：

```text
normalize_question_node
  读取 raw_question。
  strip 后写 normalized_question。
  如果为空，写 clarification_message/status。

build_prompt_node
  读取 normalized_question。
  生成 mock prompt_payload。
  生成 final_prompt。
  不调用 LLM。

generate_sql_node
  读取 final_prompt。
  生成 mock SQL。
  不调用 LLM。

check_sql_node
  mock 检查 generated_sql。
  成功写 checked_sql。
  失败写 check_error/status。

execute_sql_node
  mock 执行 checked_sql。
  成功写 result_columns/result_rows。
  失败写 execute_error/status。

clarification_response_node
  写 status=needs_clarification 和 message。

failed_response_node
  写 status=failed 和 message。

success_response_node
  写 status=success 和 message。
```

Node 规则：

```text
1. 输入 state。
2. 不原地修改 state。
3. 返回 partial state update。
4. 不访问 CLI。
5. 不直接创建 LLM / database / vectorstore。
6. Phase 2 可以直接写 mock 逻辑，不抽 services。
```

Phase 2 暂时不新增 `services/` 的原因是：

```text
当前还不是业务能力实现阶段。
如果现在为了 mock 逻辑创建 services，会让目录提前膨胀。
```

## 9. Edge 与 response 细节

Phase 2 的 edge 只做路由，不做业务逻辑。

建议固定为：

```python
def route_after_normalize(state: Nl2SqlGraphState) -> str:
    if state.get("clarification_message"):
        return "clarification_response"
    return "build_prompt"
```

不要同时混用 `status` 和 `clarification_message` 判断空问题。第一版让 `normalize_question_node` 负责写清楚 `clarification_message`，edge 只读这个结果即可。

其他路由规则：

```text
route_after_check:
  如果 check_error 存在，进入 failed_response。
  否则进入 execute_sql。

route_after_execute:
  如果 execute_error 存在，进入 failed_response。
  否则进入 success_response。
```

`failed_response_node` 的 message 优先级固定为：

```text
1. check_error
2. execute_error
3. state.message
4. "NL2SQL workflow failed."
```

这样 check 失败和 execute 失败时，输出稳定，不依赖节点实现细节。

## 10. Prompt 观察方式

Phase 2 必须能看到最终提示词效果。

建议提供两条观察路径：

```text
1. workflow output metadata
   Nl2SqlOutput.metadata["final_prompt"]
   Nl2SqlOutput.metadata["prompt_payload"]

2. GraphRuntime.stream
   stream_mode="updates" 能看到 build_prompt 节点返回 final_prompt。
   stream_mode="values" 能看到每步后的完整 state。
```

这两条路径解决不同问题：

```text
output metadata：
  方便最简单地看本次最终 prompt。

stream：
  方便看 prompt 是在哪个节点产生的，以及前后 state 怎么变化。
```

Phase 2 的核心验收之一就是：

```text
普通问题跑完后，用户能从 output 或 stream 中看到 final_prompt。
```

不同路径下的 prompt 输出规则：

```text
空问题：
  不经过 build_prompt。
  metadata 可以为空，或 final_prompt 为 None。

check 失败：
  已经过 build_prompt。
  metadata 必须包含 prompt_payload / final_prompt。

execute 失败：
  已经过 build_prompt。
  metadata 必须包含 prompt_payload / final_prompt。

success：
  metadata 必须包含 prompt_payload / final_prompt。
```

原因：

```text
check / execute 失败时，最需要回看的是本轮最终提示词。
```

## 11. Workflow Facade

新增最薄 facade：

```python
@dataclass(frozen=True)
class Nl2SqlWorkflow:
    graph: object
    graph_runtime: GraphRuntime
    run_context: RunContext

    def run(
        self,
        input: Nl2SqlInput,
        *,
        thread_id: str | None = None,
    ) -> Nl2SqlOutput:
        ...

    def stream(
        self,
        input: Nl2SqlInput,
        *,
        thread_id: str | None = None,
        stream_mode: str = "updates",
    ) -> list:
        ...
```

`run()` 负责：

```text
1. 把 Nl2SqlInput 转成 graph input dict。
2. 调用 GraphRuntime.invoke。
3. 用 response_builder 转成 Nl2SqlOutput。
```

`stream()` 负责：

```text
1. 把 Nl2SqlInput 转成 graph input dict。
2. 调用 GraphRuntime.stream。
3. 原样返回 chunks。
```

外部入口不应该知道 node、edge、state 或 LangGraph config。

## 12. Bootstrap 边界

Phase 2 可以让 `build_app()` 暴露：

```text
app.nl2sql_workflow
```

原因：

```text
1. 提前验证 app 未来如何暴露业务 workflow。
2. 后续 CLI/API 只需要调用 app.nl2sql_workflow.run(...)。
3. 比现在新增 CLI ask 更重要，也更克制。
```

仍然不做：

```text
build_app 创建 hello_graph。
build_app 创建 LLM。
build_app 创建 database。
build_app 创建 vectorstore。
CLI 直接调用 graph。
```

## 13. 推荐目录

新增：

```text
src/nl2sqlagent/workflows/nl2sql/
  __init__.py
  input.py
  output.py
  state.py
  nodes.py
  edges.py
  graph.py
  response_builder.py
  workflow.py
```

修改：

```text
src/nl2sqlagent/bootstrap/app.py
src/nl2sqlagent/bootstrap/container.py
```

测试：

```text
tests/unit/workflows/nl2sql/test_edges.py
tests/unit/workflows/nl2sql/test_response_builder.py
tests/integration/test_nl2sql_workflow.py
```

不新增：

```text
src/nl2sqlagent/domain/
src/nl2sqlagent/services/
src/nl2sqlagent/integrations/
src/nl2sqlagent/interfaces/cli/commands/ask.py
```

## 14. 测试策略

Phase 2 测试重点：

```text
流程能跑。
路由正确。
final_prompt 可观察。
facade 边界稳定。
bootstrap 暴露正确。
```

建议覆盖：

```text
test_edges.py
  空问题后路由到 clarification_response。
  check_error 存在时路由到 failed_response。
  check_error 不存在时路由到 execute_sql。
  execute_error 存在时路由到 failed_response。
  execute_error 不存在时路由到 success_response。
  route_after_normalize 只根据 clarification_message 路由。

test_response_builder.py
  success state 转 success output。
  clarification state 转 needs_clarification output。
  failed state 转 failed output。
  output.metadata 包含 prompt_payload / final_prompt。
  failed message 优先级为 check_error > execute_error > message > 默认文案。

test_nl2sql_workflow.py
  普通问题返回 success。
  空问题返回 needs_clarification。
  check 失败直接 failed。
  execute 失败直接 failed。
  workflow run output 能看到 final_prompt。
  check / execute 失败时 output metadata 仍能看到 final_prompt。
  workflow stream updates 能看到 build_prompt 的 final_prompt。
  build_app 暴露 nl2sql_workflow。
  build_app 不暴露 hello_graph。
```

不测试：

```text
retry。
真实 SQL 语法。
真实数据库结果。
真实 LLM 输出。
schema grounding 准确率。
```

## 15. 与旧 SQLAgent 的关系

旧 `SQLAgent` 只作为行为参考，不作为 Phase 2 代码迁移来源。

可以参考：

```text
clarification / success / failed 的状态语义。
prepare/generate/check/execute 的阶段概念。
最终响应里包含 sql、columns、rows 的基本形状。
```

不迁移：

```text
旧 application 编排。
旧 chain。
旧 database/vectorstore。
旧 runtime token 统计。
旧 CLI ask。
旧 retry 逻辑。
```

Phase 2 完成后，后续更合理的演进顺序是：

```text
Phase 3：
  真实 prompt payload builder / prompt template
  仍然可以不接真实 LLM

Phase 4：
  LLM runtime / SQL generation chain

Phase 5：
  SQL check

Phase 6：
  SQLite execute

Phase 7：
  retry / feedback
```

这个顺序不是固定计划，只表达一个原则：

```text
先看清单轮 prompt 和 state，再做质量闭环。
```

## 16. 完成标准

Phase 2 完成时，应满足：

```text
1. workflows/nl2sql 线性 graph 可运行。
2. 普通问题可以走到 success。
3. 空问题可以走到 needs_clarification。
4. check 失败直接 failed。
5. execute 失败直接 failed。
6. build_prompt_node 生成 prompt_payload 和 final_prompt。
7. Nl2SqlOutput.metadata 能看到 final_prompt。
8. workflow.stream 能看到 build_prompt 的 final_prompt update。
9. check / execute 失败时，metadata 仍能看到 final_prompt。
10. failed_response 的 message 优先级稳定。
11. build_app 暴露 nl2sql_workflow。
12. build_app 不暴露 hello_graph。
13. 未新增 CLI ask。
14. 未新增 domain/services/integrations。
15. 既有 Phase 0 / Phase 1 测试继续通过。
```

一句话总结：

```text
Phase 2 不是“带 retry 的 NL2SQL 业务雏形”，而是“能跑通基础线性流程，并能看见最终提示词的纯工作流骨架”。
```
