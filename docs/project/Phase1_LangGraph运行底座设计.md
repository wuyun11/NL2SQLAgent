# Phase 1 LangGraph 运行底座设计

> 本文是 Phase 1 设计文档，用于给其他 AI / 开发者评审。
>
> Phase 0 已完成最小运行底座：配置、路径、日志、RunContext、bootstrap、CLI startup。
>
> Phase 1 的目标不是实现 NL2SQL 业务，而是先搭建 LangGraph 运行底座：thread_id、checkpointer、graph runtime，以及一个最小 hello graph 验证通道。

## 1. 为什么下一步先做 LangGraph 运行底座

新项目的长期目标是用 LangGraph 承载 NL2SQL 工作流。

但如果下一步直接做 `ask`，会一次性引入：

```text
LangGraph
LLM
prompt
database
schema grounding
SQL check
SQL execute
运行记录
错误处理
中间态调试
```

这会重新落入旧项目的问题：每个点都合理，但组合起来太大，导致实现和调试都卡住。

因此 Phase 1 先只解决一个更小的问题：

```text
项目如何以统一方式运行 LangGraph。
```

具体包括：

```text
1. 如何生成 / 接收 thread_id。
2. 如何创建 checkpointer。
3. 如何统一调用 graph.invoke。
4. 如何统一调用 graph.stream。
5. 如何把 RunContext 转成 LangGraph RunnableConfig 所需 metadata。
6. 如何在不接业务的情况下验证 graph runtime 可用。
```

这一步完成后，后续 NL2SQL graph、schema-index graph、debug stream、checkpoint、interrupt 才有稳定落点。

## 2. Phase 1 的核心目标

Phase 1 只做 LangGraph 运行底座。

目标：

```text
1. 新增 workflows/runtime/thread_id.py。
2. 新增 workflows/runtime/graph_runtime.py。
3. 新增 platform/persistence/checkpointer_factory.py。
4. 新增 workflows/hello/，用于验证 graph invoke / stream。
5. bootstrap 能装配 checkpointer 和 GraphRuntime。
6. 测试能证明 invoke / stream / thread_id / checkpointer 正常工作。
```

Phase 1 不做：

```text
NL2SQL 业务流程
LLM
数据库
向量库
embedding
token usage
LangSmith
schema grounding
SQL 生成
SQL 执行
业务 run record
HTTP API
Human Review
```

## 2.1 LangGraph 依赖与 API 边界

Phase 1 必须显式加入 LangGraph 依赖。

建议依赖：

```text
langgraph>=1.0
```

内存 checkpointer 使用官方导入路径：

```python
from langgraph.checkpoint.memory import InMemorySaver
```

StateGraph 使用：

```python
from langgraph.graph import END, START, StateGraph
```

执行计划中不要使用不确定名称，例如：

```text
MemorySaver
InMemoryCheckpointSaver
SqliteSaver
```

除非当时项目实际安装的 LangGraph 版本明确要求修改。

## 3. Phase 1 目录结构

建议新增：

```text
src/nl2sqlagent/
  platform/
    persistence/
      __init__.py
      checkpointer_factory.py

  workflows/
    __init__.py
    runtime/
      __init__.py
      thread_id.py
      graph_runtime.py
    hello/
      __init__.py
      graph.py
      state.py
      nodes.py

tests/
  unit/
    workflows/
      runtime/
        test_thread_id.py
        test_graph_runtime.py
    platform/
      test_checkpointer_factory.py
  integration/
    test_hello_graph_runtime.py
```

不新增：

```text
domain/
services/
integrations/
```

原因：

```text
Phase 1 仍然不是业务阶段。
hello graph 只是验证 LangGraph 运行通道，不代表业务 domain。
```

## 4. 配置变更

Phase 1 需要在配置中加入 workflow runtime 的最小配置。

建议新增 `config/workflow.yml`：

```yaml
workflow:
  checkpointer:
    provider: memory
```

对应新增配置模型：

```python
@dataclass(frozen=True)
class CheckpointerSection:
    provider: str


@dataclass(frozen=True)
class WorkflowSection:
    checkpointer: CheckpointerSection
```

`AppConfig` 增加：

```python
workflow: WorkflowSection
```

配置兼容规则：

```text
1. 默认 config/workflow.yml 必须创建。
2. load_app_config 必须读取 workflow.yml。
3. 所有测试里临时 config 目录也必须写 workflow.yml。
4. 缺失 workflow.yml 时抛 ConfigurationError。
5. 不为 workflow.yml 提供静默默认值。
```

原因：

```text
Phase 1 之后 build_app 会创建 checkpointer 和 GraphRuntime，其中 checkpointer 依赖 workflow.yml 配置。
如果 workflow.yml 缺失时偷偷使用默认值，后续配置行为会变得不透明。
```

暂时不支持：

```text
sqlite checkpointer
postgres checkpointer
per-workflow checkpoint config
复杂 workflow 参数
```

Phase 1 只允许：

```text
provider: memory
```

## 5. Thread ID 设计

`thread_id` 是 LangGraph checkpoint / resume 的核心标识。

Phase 0 已经有：

```text
RunContext.run_id
```

但 `run_id` 不等于 `thread_id`。

区别：

```text
run_id
  表示一次 CLI/app 启动或命令运行。

thread_id
  表示一个 LangGraph 会话 / checkpoint 线程。
```

Phase 1 先定义最小规则：

```text
1. 如果外部传入 thread_id，则使用外部值。
2. 如果没有传入，则从 run_id 派生。
3. 默认格式：thread-{run_id}
4. 如果 run_id 已经以 run- 开头，保留原样拼接，例如 thread-run-a1b2c3d4。
```

建议文件：

```text
workflows/runtime/thread_id.py
```

建议函数：

```python
def resolve_thread_id(
    *,
    run_id: str,
    thread_id: str | None = None,
) -> str:
    ...
```

规则：

```text
1. thread_id 不能为空。
2. 显式传入的 thread_id 会 strip。
3. strip 后为空则回退为 thread-{run_id}。
```

后续接入 ask 时，可以基于 request_id / conversation_id 生成 thread_id，但 Phase 1 不引入这些概念。

## 6. Checkpointer 设计

`platform/persistence/checkpointer_factory.py` 负责创建 LangGraph checkpointer。

Phase 1 只支持 memory。

建议函数：

```python
def build_checkpointer(config: WorkflowSection):
    ...
```

行为：

```text
provider == "memory"
  返回 InMemorySaver。

其他 provider
  抛 ConfigurationError。
```

注意：

```text
即使是 memory checkpointer，也必须强制通过 thread_id 调用 graph。
不要因为第一版是内存而跳过 thread_id。
```

这样后续从 memory 切到 sqlite/postgres 时，调用接口不会改变。

## 7. GraphRuntime 设计

`workflows/runtime/graph_runtime.py` 负责统一调用 LangGraph graph。

它解决的问题：

```text
1. CLI / API / 测试不直接拼 LangGraph config。
2. thread_id 注入规则统一。
3. graph.invoke / graph.stream 入口统一。
4. RunContext metadata 注入统一。
5. graph 异常后续可以统一转换为 WorkflowError。
```

Phase 1 建议模型：

```python
@dataclass(frozen=True)
class GraphRuntime:
    """Runs compiled LangGraph graphs with project-standard config."""
```

`GraphRuntime` 不持有 checkpointer。

职责边界：

```text
platform/persistence/checkpointer_factory.py
  创建 checkpointer。

bootstrap/container.py
  装配并暴露 checkpointer。

workflows/hello/graph.py
  compile graph 时接收 checkpointer。

workflows/runtime/graph_runtime.py
  只负责 invoke / stream 和 RunnableConfig 构造。
```

不要让 `GraphRuntime` 同时负责创建 checkpointer、compile graph、运行 graph。否则它会变成新的 workflow container。

建议方法：

```python
def invoke(
    self,
    *,
    graph,
    input: dict,
    run_context: RunContext,
    thread_id: str | None = None,
) -> dict:
    ...


def stream(
    self,
    *,
    graph,
    input: dict,
    run_context: RunContext,
    thread_id: str | None = None,
    stream_mode: str = "updates",
) -> list:
    ...
```

返回值规则：

```text
GraphRuntime.invoke
  返回 dict(graph.invoke(...))。

GraphRuntime.stream
  返回 list(graph.stream(...))。
```

Phase 1 不对 stream chunk 做二次解释或业务事件封装。

原因：

```text
1. Phase 1 只验证运行通道。
2. LangGraph 不同 stream_mode 的 chunk 形态不同。
3. 业务级 stream event 等 Phase 2/3 真的有 CLI/API 输出需求时再设计。
```

`GraphRuntime` 应负责构造 RunnableConfig：

```python
{
    "configurable": {
        "thread_id": resolved_thread_id,
    },
    "metadata": {
        "run_id": run_context.run_id,
        "run_date": run_context.run_date,
    },
}
```

Phase 1 不加入：

```text
callbacks
tags
LangSmith metadata
request_id
user_id
database_key
```

这些等业务或观测阶段再加。

## 8. Hello Graph 设计

Phase 1 需要一个最小 graph 验证 GraphRuntime。

不要用 NL2SQL 业务做验证。

建议目录：

```text
workflows/hello/
  state.py
  nodes.py
  graph.py
```

### 8.1 State

```python
from typing import TypedDict


class HelloGraphState(TypedDict, total=False):
    name: str
    message: str
    step_count: int
```

### 8.2 Node

```python
def greet_node(state: HelloGraphState) -> dict:
    name = state.get("name") or "world"
    return {
        "message": f"hello, {name}",
        "step_count": state.get("step_count", 0) + 1,
    }
```

### 8.3 Graph

```python
def build_hello_graph(*, checkpointer):
    graph = StateGraph(HelloGraphState)
    graph.add_node("greet", greet_node)
    graph.add_edge(START, "greet")
    graph.add_edge("greet", END)
    return graph.compile(checkpointer=checkpointer)
```

这个 graph 只验证：

```text
StateGraph 能创建。
checkpointer 能传入。
GraphRuntime.invoke 能返回 state。
GraphRuntime.stream 能返回 updates。
```

不要给 hello graph 加复杂分支。

测试规则：

```text
1. 基本 invoke / stream 测试使用不同 thread_id，避免 checkpoint 状态互相影响。
2. Phase 1 不测试 checkpoint resume 语义。
3. 不要断言多次复用同一 thread_id 时 step_count 的累计行为。
```

原因：

```text
hello graph 是运行通道测试工具，不是业务状态恢复示例。
checkpoint resume 语义后续单独设计和测试。
```

## 9. Bootstrap 变更

Phase 0 的 app 当前包含：

```text
config
paths
logging
run_context
```

Phase 1 建议增加：

```text
graph_runtime
checkpointer
```

建议：

```python
@dataclass(frozen=True)
class NL2SQLAgentApp:
    config: AppConfig
    paths: ProjectPaths
    logging: LoggingRuntime
    run_context: RunContext
    checkpointer: object
    graph_runtime: GraphRuntime
```

`checkpointer` 应显式暴露在 app 上。

原因：

```text
1. checkpointer 是 graph compile 阶段依赖，不是 graph invoke 阶段依赖。
2. hello graph 和未来业务 graph 都应在各自 builder 中接收 checkpointer。
3. GraphRuntime 只运行 compiled graph，不负责持有或分发 checkpointer。
```

`build_app()` 新流程：

```text
load config
create run context
resolve paths
build logger
build checkpointer
build graph runtime
return app
```

注意：

```text
build_app 仍然不创建 NL2SQL graph。
build_app 只创建 graph runtime，不创建业务 workflow。
build_app 也不创建 hello graph。
build_app 创建并暴露 checkpointer，但不使用它 compile 任何 graph。
```

hello graph 只在测试中显式 build。

原因：

```text
hello graph 是验证 GraphRuntime 的测试 graph，不是应用功能。
如果 build_app 创建 hello graph，它会污染 app 的正式边界。
```

## 10. CLI 是否需要新增命令

Phase 1 不强制新增 CLI 命令。

推荐先只用测试验证 hello graph。

可选增加：

```text
python -m nl2sqlagent.interfaces.cli.main hello-graph --name Alice
```

但我建议暂缓。

原因：

```text
CLI 现在只负责 startup。
hello graph 是运行底座测试工具，不是用户功能。
把它放到 CLI 可能让 Phase 1 范围变宽。
```

因此 Phase 1 推荐：

```text
只写测试，不扩 CLI。
```

## 11. 测试设计

### 11.1 thread_id 测试

覆盖：

```text
显式 thread_id 会被使用。
显式 thread_id 会 strip。
空 thread_id 回退为 thread-{run_id}。
未传 thread_id 回退为 thread-{run_id}。
```

### 11.2 checkpointer_factory 测试

覆盖：

```text
provider=memory 能返回 checkpointer。
未知 provider 抛 ConfigurationError。
```

不要测试 LangGraph 内部类细节过多。

### 11.3 graph_runtime invoke 测试

用 hello graph 验证：

```text
GraphRuntime.invoke 返回 message。
GraphRuntime.invoke 注入 thread_id 后能正常执行。
```

### 11.4 graph_runtime stream 测试

用 hello graph 验证：

```text
GraphRuntime.stream(stream_mode="updates") 能返回 node update。
GraphRuntime.stream(stream_mode="values") 能返回 state values。
```

### 11.5 startup 旧测试

Phase 0 startup 测试应继续通过。

## 12. Phase 1 完成标准

Phase 1 完成时，应满足：

```text
1. AppConfig 能读取 workflow.yml。
2. checkpointer_factory 能创建 memory checkpointer。
3. resolve_thread_id 规则稳定。
4. GraphRuntime.invoke 能运行 hello graph。
5. GraphRuntime.stream 能返回 hello graph 中间状态。
6. build_app 能装配 checkpointer 和 GraphRuntime。
7. Phase 0 startup CLI 仍然通过。
8. 未创建 domain/services/integrations。
9. 未接入 LLM/database/vectorstore/token/LangSmith。
10. build_app 不创建 hello graph。
11. GraphRuntime.stream 原样返回 LangGraph stream chunks。
12. GraphRuntime 不持有 checkpointer，不负责 compile graph。
```

## 13. 为什么 Phase 1 不做 NL2SQL

如果现在直接做 NL2SQL graph，会同时面临：

```text
1. graph state 设计。
2. NL2SQL input/output 设计。
3. LLM runtime 设计。
4. prompt 设计。
5. database abstraction。
6. schema grounding。
7. SQL check / execute。
8. retry edge。
9. run record。
10. graph stream / checkpoint。
```

这会让每个问题互相影响。

Phase 1 先做 LangGraph 运行底座，是为了把第 10 项单独解决。

后续做 NL2SQL graph 时，只需要关心业务 state / node / edge，不再同时纠结 thread_id、checkpointer、graph invoke / stream 怎么接。

## 14. Phase 2 预告

Phase 2 可以开始设计最小业务骨架，但仍建议克制。

可能目标：

```text
domain/nl2sql input/output
workflows/nl2sql graph skeleton
mock nodes
response builder
```

仍然可以暂缓：

```text
真实 LLM
真实 database
真实 schema grounding
```

这样项目会一步一步把地基铺稳，而不是一次性把所有复杂度拉进来。
