# Phase 2 NL2SQL Workflow Skeleton Design

## 1. 背景

当前项目已经完成两层底座：

- Phase 0：配置、路径、日志、RunContext、bootstrap、CLI startup。
- Phase 1：LangGraph checkpointer、thread_id、GraphRuntime、hello graph 验证通道。

旧项目 `F:\workspace\workspace_python\SQLAgent` 已经提供完整 NL2SQL 参考能力，包括 schema-index、question planning、prepare、generate、check、execute 和 retry。但新项目不是简单迁移旧代码，而是围绕 LangGraph workflow 重新建立长期边界。

Phase 2 的目标是先把 NL2SQL 工作流的形状立住。它不追求真实业务效果，而是验证后续业务能力接入时不会推倒重来。

## 2. 核心判断

Phase 2 最重要的是降低未来重构成本，而不是尽快跑出真实 SQL。

因此本阶段应该优先建立：

1. 外部工作流契约：`Nl2SqlInput` / `Nl2SqlOutput`。
2. 内部 graph state：`Nl2SqlGraphState`。
3. LangGraph 流程骨架：nodes、edges、graph builder。
4. 统一响应构建：`response_builder`。
5. 最薄 workflow facade：外部只调用 `run(input) -> output`。
6. bootstrap 装配：app 暴露 `nl2sql_workflow`，但不新增 CLI `ask`。

这些边界现在立住，后续接 LLM、数据库、schema grounding、QueryPlan、CLI/API 时都可以复用。

## 3. 本阶段目标

Phase 2 实现一个 mock NL2SQL LangGraph workflow。

它应该能验证：

- 空问题进入 `needs_clarification`。
- 普通问题走成功路径。
- mock check 失败后能 retry。
- 超过最大轮次后进入 failed。
- workflow facade 能通过当前 `GraphRuntime` 运行 compiled graph。
- `build_app()` 暴露 `nl2sql_workflow`，但不暴露 hello graph。

## 4. 非目标

Phase 2 不做：

- CLI `ask` 命令。
- 真实 LLM chain。
- 真实数据库连接或 SQL 执行。
- 真实 schema grounding。
- 旧项目代码迁移。
- QueryPlan。
- Human Review。
- schema-index workflow。
- evaluation golden set。
- HTTP API。

这些能力后续都重要，但现在引入会让 Phase 2 从“工作流骨架”膨胀成“最小业务系统”，不利于验证边界。

## 5. 推荐目录

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

tests/unit/workflows/nl2sql/
  test_edges.py
  test_response_builder.py

tests/integration/
  test_nl2sql_workflow.py
```

修改：

```text
src/nl2sqlagent/bootstrap/app.py
src/nl2sqlagent/bootstrap/container.py
```

暂不新增：

```text
src/nl2sqlagent/domain/
src/nl2sqlagent/services/
src/nl2sqlagent/integrations/
src/nl2sqlagent/interfaces/cli/commands/ask.py
```

## 6. 数据契约

### 6.1 Nl2SqlInput

`Nl2SqlInput` 是外部入口传给 workflow 的稳定契约。

建议字段：

```python
@dataclass(frozen=True)
class Nl2SqlInput:
    question: str
    request_id: str | None = None
    user_id: str | None = None
    database_key: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
```

现在不引入复杂 request model。未来 CLI、API、批量评估都可以复用这个输入。

### 6.2 Nl2SqlOutput

`Nl2SqlOutput` 是 workflow facade 返回给外部入口的稳定契约。

建议字段：

```python
Nl2SqlStatus = Literal["success", "needs_clarification", "failed", "rejected"]

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

Phase 2 的 rows/sql 可以是 mock。重点是契约稳定，不是结果真实。

### 6.3 Nl2SqlGraphState

Graph state 是 LangGraph 内部运行态，不是 API response。

建议用 `TypedDict(total=False)`：

```python
class Nl2SqlGraphState(TypedDict, total=False):
    request_id: str | None
    user_id: str | None
    database_key: str | None
    raw_question: str
    normalized_question: str
    clarification_message: str | None
    generated_sql: str | None
    checked_sql: str | None
    check_error: str | None
    execute_error: str | None
    feedback: str | None
    result_columns: list[str]
    result_rows: list[dict[str, Any]]
    round_index: int
    max_round_count: int
    status: Literal["running", "success", "needs_clarification", "failed", "rejected"]
    message: str | None
```

状态字段先覆盖 Phase 2 mock 流程和后续真实能力接入点。不要把 LLM client、数据库连接、vectorstore 等外部对象放进 state。

## 7. Workflow 流程

Phase 2 graph 推荐流程：

```text
START
  -> normalize_question
  -> route_after_normalize
      -> clarification_response
      -> generate_sql
  -> check_sql
  -> route_after_check
      -> generate_sql
      -> failed_response
      -> execute_sql
  -> route_after_execute
      -> generate_sql
      -> failed_response
      -> success_response
  -> END
```

Phase 2 的节点全部 mock：

- `normalize_question_node`：strip question；空问题设置 clarification。
- `generate_sql_node`：生成 mock SQL；如果 options 指定场景，也可生成 mock bad SQL。
- `check_sql_node`：根据 mock SQL 或 options 模拟成功/失败。
- `execute_sql_node`：返回 mock columns/rows，或根据 options 模拟执行失败。
- `success_response_node` / `failed_response_node` / `clarification_response_node`：只写最终 status/message 字段。

重要规则：

- node 不直接修改原 state，只返回 partial update。
- edge 只做路由，不做业务处理。
- retry 只基于 state 中的 `round_index` 和 `max_round_count`。

## 8. Workflow Facade

新增 `Nl2SqlWorkflow`，对外只暴露：

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
```

Facade 负责：

1. 把 `Nl2SqlInput` 转成 graph input dict。
2. 调用 `GraphRuntime.invoke(...)`。
3. 调用 `response_builder` 把 final state 转成 `Nl2SqlOutput`。

外部入口不应该知道 graph state、nodes、edges 或 LangGraph config。

## 9. Bootstrap 边界

Phase 2 推荐让 `build_app()` 暴露 `nl2sql_workflow`。

原因：

- 这能提前验证 app 未来如何暴露业务 workflow。
- 后续 CLI/API 只需要调用 `app.nl2sql_workflow.run(...)`。
- 比新增 CLI `ask` 更重要，也更克制。

仍然禁止：

- `build_app()` 创建 hello graph。
- `build_app()` 创建 LLM、database、vectorstore。
- CLI 直接调用 graph 或拼 LangGraph config。

## 10. 测试策略

Phase 2 测试重点是流程控制和边界，不是业务准确率。

建议覆盖：

1. `test_edges.py`
   - check 成功路由到 execute。
   - check 失败且可重试路由到 generate。
   - check 失败且超过轮次路由到 failed。
   - execute 成功路由到 success。
   - execute 失败且可重试路由到 generate。
   - execute 失败且超过轮次路由到 failed。

2. `test_response_builder.py`
   - success state 转成 success output。
   - clarification state 转成 needs_clarification output。
   - failed state 转成 failed output。

3. `test_nl2sql_workflow.py`
   - 普通问题返回 success。
   - 空问题返回 needs_clarification。
   - mock check 一次失败后 retry 并成功。
   - mock check 一直失败后 failed。
   - `build_app()` 暴露 `nl2sql_workflow`。
   - `build_app()` 不暴露 `hello_graph`。

测试不应依赖真实 LLM、数据库、网络或旧项目资源。

## 11. 与旧 SQLAgent 的关系

旧 `SQLAgent` 在 Phase 2 中只作为行为参考，不作为代码迁移来源。

可参考：

- 在线流程的阶段顺序。
- retry/failed/success/clarification 语义。
- 对外输出 status 的基本形状。

不迁移：

- `application` 目录结构。
- 旧 container 装配。
- 旧 runtime token/logging/run record。
- 旧 LangChain chain。
- 旧 SQLite/vectorstore 实现。

后续迁移时应按新项目边界逐块引入：

```text
SQL check -> SQLite executor -> schema grounding -> LLM chain -> schema-index
```

## 12. 完成标准

Phase 2 完成时应满足：

1. `workflows/nl2sql` 存在，并包含 input/output/state/nodes/edges/graph/response_builder/workflow。
2. `build_app()` 暴露 `nl2sql_workflow`。
3. 没有新增 CLI `ask`。
4. 没有新增 `domain/services/integrations`。
5. 所有 NL2SQL workflow 测试通过。
6. Phase 0/Phase 1 既有测试继续通过。
7. `compileall src/nl2sqlagent` 无语法错误。

一句话总结：

Phase 2 要交付的是一个可运行、可测试、可扩展的 NL2SQL LangGraph 工作流外壳，而不是一个能真实回答业务问题的 SQLAgent。
