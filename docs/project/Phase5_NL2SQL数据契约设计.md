# Phase 5 NL2SQL 数据契约设计

> 本文是 Phase 5 的讨论设计稿。
>
> 目标不是新增一套重型分层，也不是直接接入真实 LLM / 数据库；真正的执行计划后续再放到 `docs/superpowers/plans/`。

## 1. 背景

当前项目已经完成：

```text
Phase 0：最小运行底座。
Phase 1：LangGraph 运行底座。
Phase 2：NL2SQL 工作流骨架。
Phase 3：结构化 prompt_payload 和 final_prompt 渲染。
Phase 4：NL2SQL 运行 artifact。
```

Phase 4 完成后，项目已经能稳定看到：

```text
input.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
output.json
manifest.json
```

这解决了“运行过程能不能看见”的问题。

但下一步如果要进入真实 LLM、真实 schema、真实 SQL check / execute，会遇到另一个问题：

```text
哪些数据只是 LangGraph state？
哪些数据是 prompt payload？
哪些数据是运行选项？
哪些数据是业务输出？
哪些数据只是 artifact metadata？
哪些地方允许 dict[str, Any]？
哪些地方必须有稳定字段？
```

如果这些边界不先收敛，后续很容易出现：

```text
1. options 里不断增加 magic key。
2. prompt_payload、metadata、graph state 互相污染。
3. artifact 字段被多个模块重复拼接。
4. mock 字段和正式字段混在一起。
5. 只能靠读完整流程才能知道当前数据是什么。
```

Phase 5 要解决的是这个问题。

## 2. 核心结论

Phase 5 推荐定位为：

```text
轻量数据契约收敛
```

也就是说：

```text
要做：
  收敛 options / prompt_payload / output metadata / graph state 的字段边界。
  明确 raw dict 允许出现的位置。
  明确哪些跨模块数据必须有 TypedDict / dataclass。
  给后续真实 LLM、schema、DB 接入留出稳定落点。

不要做：
  新增 stage/service/protocol 三件套。
  新增 Nl2SqlContext + 各阶段 Result model。
  引入 domain/services/integrations 大目录。
  接真实 LLM。
  接真实数据库。
  接真实 schema grounding。
  引入 retry。
```

一句话：

```text
Phase 5 先让数据“有形状”，但不让架构“长壳”。
```

## 3. 设计原则

Phase 5 遵守下面几条原则：

```text
1. 轻类型，少抽象。
2. LangGraph 负责流程，类型负责数据形状。
3. 有第二个真实实现前，不加 Protocol。
4. 有真实复杂逻辑前，不加 Service 层。
5. 有重复业务语义前，再考虑 Domain model。
6. mock 可以存在，但必须有明确边界。
7. raw dict 只能停留在框架边界和 JSON 边界。
8. 跨模块返回值优先使用 dataclass / TypedDict。
```

这些原则的目标是同时避免两个极端：

```text
过松：
  到处 dict[str, Any]，后续不知道数据是什么。

过重：
  stage + service + protocol + context result 全部提前出现，业务主线被壳淹没。
```

## 4. 与参考项目的关系

参考项目 `SQLAgent` 有一个重要经验：

```text
真实 NL2SQL 一旦接入 schema grounding、semantic、SQL check、SQL execution，
中间数据会快速变多。
```

参考项目通过这些模型控制复杂度：

```text
Nl2SqlContext
Nl2SqlGenerationInput
QuestionInput
SchemaInput
SemanticInput
FeedbackInput
Nl2SqlPrepareResult
Nl2SqlGenerateResult
Nl2SqlCheckResult
Nl2SqlExecuteResult
```

这说明一个事实：

```text
复杂 NL2SQL 系统需要明确数据形状。
```

但参考项目也暴露了代价：

```text
1. 抽象数量偏早、偏细。
2. stage / service / protocol / result model 同时存在。
3. 一次主线阅读要跨很多文件。
4. container 容易变成手工接线中心。
5. 临时 mock 与目标实现容易长期共存。
```

所以当前项目不应照搬参考项目。

Phase 5 只吸收参考项目的优点：

```text
数据有明确形状。
阶段产物有清晰含义。
业务输出和调试输出分开。
```

不复制参考项目的重型结构：

```text
不新增 stage 类。
不新增 stage protocol。
不新增 Nl2SqlContext。
不新增每个节点一个 result model。
不提前创建 service 空壳。
```

## 5. 当前主要风险点

### 5.1 options 过于自由

当前输入中有：

```python
options: dict[str, Any]
```

当前节点里已经使用：

```text
force_check_error
force_execute_error
```

这在 mock 阶段可以接受，但如果继续放任，后续可能变成：

```text
options["dialect"]
options["limit"]
options["model"]
options["temperature"]
options["debug"]
options["schema"]
options["policy"]
```

最终会混淆：

```text
运行调试选项
业务输入
模型参数
SQL policy
schema 选择
```

### 5.2 prompt_payload 结构没有类型约束

当前 `prompt_payload.py` 已经集中构建 payload，这是好的。

但返回值仍然是：

```python
dict[str, Any]
```

后续一旦增加 schema、semantic、policy 字段，缺少契约会让测试只能检查零散 key。

### 5.3 output.metadata 同时承担业务和调试

当前 output metadata 里可能包含：

```text
prompt_payload
final_prompt
artifact_manifest_path
input_path
prompt_payload_path
final_prompt_path
graph_updates_path
output_path
token_usage_path
artifact_error
```

这对早期验收很方便。

但长期看，metadata 至少有两类：

```text
调试材料：
  prompt_payload
  final_prompt

artifact 索引：
  artifact_manifest_path
  prompt_payload_path
  final_prompt_path
  graph_updates_path
```

Phase 5 不需要马上移除旧字段，但要明确边界，避免后续把业务数据继续塞进 metadata。

### 5.4 graph state 既是流程状态又像数据仓库

LangGraph state 天然适合用 `TypedDict(total=False)`。

问题不在于 state 是 dict，而在于：

```text
所有中间数据都直接以松散字段进入 state。
```

Phase 5 应让 state 的字段来源更清楚：

```text
input fields
runtime options
prompt fields
sql fields
execution fields
response fields
```

但不需要创建 `Nl2SqlContext` 再包一层。

## 6. Phase 5 范围

Phase 5 要做：

```text
1. 新增 runtime_options 契约，替代裸 options 在节点里散用。
2. 为 prompt_payload 增加 TypedDict 契约。
3. 为 output.metadata 增加 TypedDict / 构造函数边界。
4. 明确 graph state 字段分组和 raw dict 允许范围。
5. 调整 tests，让测试围绕契约字段断言。
6. 保持 LangGraph graph 结构不变。
7. 保持 nodes.py 不写文件、不接外部系统。
8. 保持 artifacts.py 仍是 artifact 字段唯一出口。
```

Phase 5 不做：

```text
1. 不接真实 LLM。
2. 不接真实数据库。
3. 不接真实 schema grounding。
4. 不新增 retry / feedback loop。
5. 不新增 QueryPlan。
6. 不新增 CLI ask。
7. 不新增 domain/services/integrations 目录。
8. 不新增 stage/protocol/result-model 架构。
9. 不改 artifact 文件格式，除非为了字段边界做最小调整。
```

## 7. 推荐文件变化

Phase 5 推荐只在 `workflows/nl2sql/` 下做轻量收敛：

```text
src/nl2sqlagent/workflows/nl2sql/
  runtime_options.py   # 新增：运行选项契约
  prompt_payload.py    # 补充 TypedDict
  output.py            # 可补充 metadata 契约或导出类型
  state.py             # 整理字段注释/类型，不引入 context wrapper
  response_builder.py  # metadata 构造边界收敛
  nodes.py             # 使用 runtime_options 读取 mock 开关
  artifacts.py         # 继续作为 artifact metadata 唯一来源
```

暂不新增：

```text
domain/
services/
integrations/
workflows/nl2sql/stages/
workflows/nl2sql/models/
```

原因：

```text
Phase 5 的问题是数据契约，不是业务能力拆分。
```

## 8. runtime_options 契约

### 8.1 目标

把当前自由的 `options: dict[str, Any]` 收敛成明确结构：

```text
外部输入仍可接受 options。
workflow 入口把 options 规范化为 runtime_options。
nodes 只读取 runtime_options，不直接读取原始 options。
```

### 8.2 建议结构

```python
class Nl2SqlRuntimeOptions(TypedDict, total=False):
    force_check_error: bool
    force_execute_error: bool
```

并提供规范化函数：

```python
def normalize_runtime_options(options: Mapping[str, object] | None) -> Nl2SqlRuntimeOptions:
    ...
```

### 8.3 设计原因

```text
1. 当前 force_check_error / force_execute_error 是 mock 调试选项，不是业务输入。
2. 节点不应该理解任意 options key。
3. 后续新增 dialect、limit、model_config 时，必须先判断它属于 runtime_options、input、policy 还是 config。
4. 规范化函数是唯一允许读取原始 options 的地方。
```

### 8.4 state 中如何保存

Phase 5 推荐：

```text
保留 options 字段一小段时间用于 input.json 兼容。
新增 runtime_options 字段给 nodes 使用。
```

长期目标：

```text
nodes 不再读取 state["options"]。
```

## 9. prompt_payload 契约

### 9.1 目标

当前 payload 的结构已经稳定为：

```text
task
question
schema_context
semantic_context
sql_policy
output_contract
debug
```

Phase 5 应在 `prompt_payload.py` 中补 TypedDict，让结构从“文档约定”变成“代码约定”。

### 9.2 建议结构

```python
class PromptTask(TypedDict):
    type: str
    goal: str

class PromptQuestion(TypedDict):
    raw: str
    normalized: str

class PromptColumn(TypedDict):
    name: str
    type: str
    description: str

class PromptTable(TypedDict):
    name: str
    description: str
    columns: list[PromptColumn]

class PromptSchemaContext(TypedDict):
    dialect: str
    tables: list[PromptTable]
    relationships: list[dict[str, object]]

class PromptSemanticTerm(TypedDict):
    name: str
    description: str

class PromptSemanticContext(TypedDict):
    business_terms: list[PromptSemanticTerm]
    rules: list[str]
    assumptions: list[str]

class PromptSqlPolicy(TypedDict):
    readonly_only: bool
    allow_select_star: bool
    require_limit: bool
    default_limit: int

class PromptOutputContract(TypedDict):
    format: str
    requirements: list[str]

class PromptDebug(TypedDict):
    prompt_version: str
    source: str

class Nl2SqlPromptPayload(TypedDict):
    task: PromptTask
    question: PromptQuestion
    schema_context: PromptSchemaContext
    semantic_context: PromptSemanticContext
    sql_policy: PromptSqlPolicy
    output_contract: PromptOutputContract
    debug: PromptDebug
```

### 9.3 为什么先用 TypedDict，不用 dataclass / Pydantic

```text
1. prompt_payload 最终要写 JSON，也要给 prompt_builder 渲染。
2. TypedDict 能表达字段形状，又不会引入对象转换成本。
3. 当前没有运行时校验需求，Pydantic 过重。
4. dataclass 嵌套后写 JSON 需要额外转换，当前收益不高。
```

### 9.4 relationships 为什么暂时仍可宽松

`relationships` 后续可能包含：

```text
from_table
from_column
to_table
to_column
description
cardinality
```

Phase 5 可以暂时保留为：

```python
list[dict[str, object]]
```

原因：

```text
当前仍是空列表，尚未接真实 schema relation。
```

但文档要明确：

```text
真实 schema grounding 接入前，需要单独收敛 relationship 契约。
```

## 10. graph state 契约

### 10.1 保持 TypedDict(total=False)

LangGraph state 继续使用：

```python
class Nl2SqlGraphState(TypedDict, total=False):
    ...
```

原因：

```text
1. LangGraph node 返回 partial update。
2. total=False 更符合节点逐步填充状态的模型。
3. 强行把 state 改成 dataclass 会和 LangGraph 使用方式冲突。
```

### 10.2 字段分组

Phase 5 推荐把 state 字段按责任分组：

```text
Input identity:
  request_id
  user_id
  database_key

Question:
  raw_question
  normalized_question
  clarification_message

Runtime:
  options
  runtime_options

Prompt:
  prompt_payload
  final_prompt

SQL:
  generated_sql
  checked_sql
  check_error
  execute_error

Execution result:
  result_columns
  result_rows

Response:
  status
  message
```

### 10.3 state 里允许的 dict

允许：

```text
prompt_payload:
  Nl2SqlPromptPayload，JSON-like dict。

options:
  原始外部 options，保留用于 artifact input.json。

runtime_options:
  Nl2SqlRuntimeOptions，节点使用的规范化选项。

result_rows:
  list[dict[str, object]]，因为表格结果天然是动态列。
```

不允许：

```text
在 state 中新增含义不明的 data/context/info/detail/meta 临时 dict。
```

如果要新增字段，必须先判断属于：

```text
Question / Runtime / Prompt / SQL / Execution / Response
```

## 11. output metadata 契约

### 11.1 当前问题

`Nl2SqlOutput.metadata` 仍然是：

```python
dict[str, Any]
```

这可以保留，因为 metadata 是扩展字段。

但写入 metadata 的模块必须收敛。

### 11.2 推荐分组

Phase 5 先把 metadata 分成两类：

```text
Prompt debug metadata:
  prompt_payload
  final_prompt

Artifact metadata:
  artifact_manifest_path
  input_path
  prompt_payload_path
  final_prompt_path
  graph_updates_path
  output_path
  token_usage_path
  artifact_error
```

### 11.3 写入规则

```text
1. response_builder 只负责 prompt debug metadata。
2. artifacts.py 只负责 artifact metadata。
3. workflow.py 只做 metadata 合并，不手写具体 metadata 字段。
4. nodes.py 不写 metadata。
5. GraphRuntime 不写 metadata。
```

### 11.4 后续迁移目标

长期可以考虑：

```text
Nl2SqlOutput.debug:
  prompt_payload
  final_prompt

Nl2SqlOutput.artifacts:
  paths...
```

但 Phase 5 不做这个 breaking change。

原因：

```text
当前 Phase 3 / Phase 4 测试和 artifact output.json 已经依赖 metadata。
Phase 5 只收敛构造边界，不改对外输出形状。
```

## 12. result rows 契约

`rows: list[dict[str, Any]]` 可以继续保留。

原因：

```text
1. SQL 查询结果列是动态的。
2. 当前没有固定业务表格 schema。
3. 强行给 rows 建模会过早。
```

但需要明确：

```text
rows 只表示最终结果表格。
不要把调试信息、执行计划、错误详情塞进 rows。
```

如果后续需要更丰富的执行结果，应新增：

```text
execution_summary
row_count
truncated
```

而不是污染 `rows`。

## 13. artifact 契约

Phase 4 已经在 `artifacts.py` 中定义：

```text
Nl2SqlArtifactPaths
Nl2SqlArtifactResult
Nl2SqlArtifactMetadata
NormalizedGraphUpdate
```

Phase 5 不重写 artifact 设计，只强化规则：

```text
1. artifact path 只能由 artifacts.py 构造。
2. output.metadata 中的 artifact 字段只能由 Nl2SqlArtifactResult.metadata 提供。
3. graph_updates 原始 chunk 只在 GraphRuntime -> workflow -> artifacts.py 之间短暂流转。
4. NormalizedGraphUpdate 只用于写 graph_updates.jsonl，不回流 state。
5. manifest dict 不跨模块传递。
```

## 14. 数据流

Phase 5 后推荐数据流：

```text
Nl2SqlInput
  -> workflow._graph_input
      -> options 原样保留
      -> runtime_options 规范化
  -> LangGraph state
  -> nodes
      -> 读取 runtime_options
      -> 构建 Nl2SqlPromptPayload
      -> 返回 partial update
  -> GraphRunResult
      -> final_state
      -> raw updates
  -> response_builder
      -> Nl2SqlOutput
      -> prompt debug metadata
  -> artifacts.py
      -> artifact files
      -> artifact metadata
  -> workflow
      -> 合并 metadata
      -> return Nl2SqlOutput
```

关键点：

```text
workflow 可以搬运数据，但不解释 prompt_payload 内部字段。
nodes 可以生成 state update，但不写文件。
artifacts.py 可以写文件，但不修改 prompt_payload。
GraphRuntime 可以收集 updates，但不理解 NL2SQL 字段。
```

## 15. 禁止事项

Phase 5 实现时禁止：

```text
1. 新增 stage/protocol/context result 架构。
2. 在 nodes.py 中继续直接读取 options["xxx"]。
3. 在多个模块中重复定义 artifact metadata 字段。
4. 在 workflow.py 中手写 artifact_manifest_path 等字段。
5. 在 GraphRuntime 中读取 prompt_payload / final_prompt / sql / rows。
6. 在 prompt_builder.py 中读取外部配置或访问文件系统。
7. 在 state 中新增 data/context/info/meta 这类泛化字段。
8. 为 mock 逻辑提前创建 service 层。
9. 把 mock 字段命名成正式业务能力。
10. 为了类型完整引入 Pydantic 或复杂运行时校验。
```

## 16. 测试重点

Phase 5 测试应该证明：

```text
1. normalize_runtime_options 只保留明确允许的字段。
2. force_check_error / force_execute_error 从 runtime_options 生效。
3. nodes 不再直接依赖原始 options。
4. build_mock_prompt_payload 返回 Nl2SqlPromptPayload 约定字段。
5. render_final_prompt 继续接受结构化 payload。
6. output metadata 中 prompt debug 字段仍由 response_builder 产生。
7. artifact metadata 仍由 artifacts.py 产生。
8. workflow.py 不手写 artifact path metadata。
9. Phase 4 artifact 文件格式不回退。
10. 原有成功、澄清、check error、execute error 路径继续通过。
```

不需要测试：

```text
1. 真实 schema relation。
2. 真实 semantic catalog。
3. 真实 SQL 执行结果 schema。
4. Pydantic 运行时校验。
5. 复杂配置加载。
```

## 17. 可能的执行任务拆分

后续执行计划可以拆成：

```text
Task 1：新增 runtime_options.py，定义 Nl2SqlRuntimeOptions 和 normalize_runtime_options。
Task 2：workflow._graph_input 同时写入 options 和 runtime_options。
Task 3：nodes.py 改为读取 runtime_options，不直接读取 options。
Task 4：prompt_payload.py 补充 TypedDict 契约，并让 builder 返回 Nl2SqlPromptPayload。
Task 5：state.py 补充 runtime_options / Nl2SqlPromptPayload 类型引用，并按字段分组整理。
Task 6：梳理 response_builder / artifacts.py 的 metadata 构造边界，必要时补 TypedDict。
Task 7：补单元测试和集成测试，确认原有 Phase 3 / Phase 4 行为不回退。
Task 8：做边界检查，确认没有新增 services/stages/protocol/context result。
```

## 18. 完成标准

Phase 5 完成时，应满足：

```text
1. options 的使用被收敛到 normalize_runtime_options。
2. nodes 使用 runtime_options，不直接读取原始 options。
3. prompt_payload 有明确 TypedDict 契约。
4. graph state 中 prompt_payload / runtime_options 类型明确。
5. output.metadata 的 prompt debug 与 artifact metadata 来源清晰。
6. artifacts.py 仍是 artifact path / metadata 的唯一构造点。
7. workflow.py 只做编排和 metadata 合并，不解释 artifact 字段。
8. GraphRuntime 仍不依赖任何 NL2SQL 业务字段。
9. 不新增 stage/service/protocol/context result 重型抽象。
10. 不新增 domain/services/integrations 目录。
11. Phase 3 final_prompt 效果不回退。
12. Phase 4 artifact 文件不回退。
13. 原有测试继续通过。
```

一句话总结：

```text
Phase 5 要交付的是“下一阶段真实能力接入前的数据边界”，不是“下一阶段真实能力本身”。
```
