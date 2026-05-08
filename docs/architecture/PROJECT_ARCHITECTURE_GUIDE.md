# SQLAgent 新项目最终架构指导文件

> 适用场景：这是一个全新 SQLAgent 项目，不再以“在旧代码上逐步迁移”为主线，而是基于最终接口和长期架构重新实现。旧项目只作为行为参考、回归基准和实现素材。

---

## 0. 核心结论

新项目的目标不是简单“自然语言生成 SQL”，而是构建一个可观察、可验证、可扩展的 NL2SQL 工作流系统。

最终架构应围绕以下原则设计：

```text
外部入口       interfaces
工作流编排     workflows
稳定业务模型   domain
业务能力       services
外部系统集成   integrations
运行平台设施   platform
依赖装配       bootstrap
```

其中，`workflows` 使用 LangGraph 表达在线 NL2SQL、schema-index、未来 QueryPlan / Human Review 等流程；`services` 保持业务能力可测试、可复用；`domain` 保存项目长期稳定的业务语言；`integrations` 只负责连接 LLM、数据库、向量库等外部系统。

---

## 1. 架构目标

新项目要解决的不是“目录美观”，而是以下长期问题：

```text
1. NL2SQL 流程有多个阶段，不适合继续写成普通脚本。
2. LLM 输出有概率性，需要明确校验、重试、反馈和失败路径。
3. schema grounding、SQL check、SQL execute 等步骤必须可观察。
4. 后续需要加入 QueryPlan、PlanValidation、ResultValidation、HumanReview。
5. 调试不应该靠额外复刻一套流程，而应该读取工作流状态和 checkpoint。
6. AI 辅助开发时，必须围绕稳定接口生成新模块，而不是在旧代码里连续 patch。
```

因此，新项目必须先定义最终接口，再实现内部流程。

---

## 2. 总体目录结构

推荐最终目录：

```text
src/sqlagent/
  interfaces/
    cli/
      main.py
      commands/
        ask.py
        schema_index.py
        inspect_run.py
        sqlite_init.py
    api/
      app.py
      routes/
        nl2sql.py
      schemas/
        nl2sql_request.py
        nl2sql_response.py
      mappers/
        nl2sql_mapper.py

  workflows/
    nl2sql/
      graph.py
      state.py
      nodes.py
      edges.py
      input.py
      output.py
      response_builder.py
    schema_index/
      graph.py
      state.py
      nodes.py
      edges.py
      input.py
      output.py
    query_plan/
      graph.py
      state.py
      nodes.py
      edges.py

  domain/
    nl2sql/
      feedback.py
      generation_input.py
      generation_output.py
      nl2sql_result.py
      question.py
    schema/
      schema_catalog.py
      schema_document.py
      grounding_context.py
      table_ref.py
      column_ref.py
      relation_hint.py
      value_hint.py
    sql/
      sql_policy.py
      sql_check_result.py
      sql_execution_result.py
      table_result.py
    semantic/
      semantic_rule.py
      semantic_catalog.py
    query_plan/
      query_plan.py
      query_plan_step.py
      query_plan_validation_result.py
      grounded_query_plan.py

  services/
    nl2sql/
      question_understanding_service.py
      question_planning_service.py
      generation_input_builder.py
      prompt_payload_builder.py
      sql_generation_service.py
      sql_check_service.py
      sql_execution_service.py
      result_validation_service.py
    schema_grounding/
      schema_grounding_service.py
      table_retrieval_service.py
      column_retrieval_service.py
      schema_expansion_service.py
      grounding_context_builder.py
      schema_catalog_provider.py
    schema_index/
      schema_catalog_loader.py
      schema_table_text_input_builder.py
      schema_table_text_generation_service.py
      schema_table_text_check_service.py
      schema_document_builder.py
      schema_index_writer.py
    semantic/
      semantic_catalog_loader.py
      semantic_rule_matcher.py
    query_plan/
      query_plan_generation_service.py
      query_plan_validation_service.py
      query_plan_grounding_service.py

  integrations/
    llm/
      model_factory.py
      chains/
        nl2sql_chain.py
        schema_table_text_chain.py
        query_plan_chain.py
      prompts/
        nl2sql.txt
        schema_table_text.txt
        query_plan.txt
    database/
      gateway_factory.py
      base.py
      sqlite/
        sqlite_schema_reader.py
        sqlite_executor.py
        sqlite_workspace_initializer.py
      dameng/
        dameng_schema_reader.py
        dameng_executor.py
    vectorstore/
      base.py
      chroma_store.py
    embedding/
      embedding_factory.py
    tracing/
      langsmith_tracer.py

  platform/
    config/
      loader.py
      models.py
    logging/
      app_logger.py
      chain_logger.py
      run_logger.py
    persistence/
      checkpointer_factory.py
      run_repository.py
    paths.py
    errors.py

  bootstrap/
    app.py
    container.py

config/
  app.yml
  env.yml
  model.yml
  sql_policy.yml
  semantic.yml
  schema_value_hints.yml
  workflow.yml

tests/
  unit/
  integration/
  workflow/
  evaluation/
  regression/

docs/
  architecture/
    PROJECT_ARCHITECTURE.md
  development/
    AI_DEVELOPMENT_RULES.md
  evaluation/
    NL2SQL_EVALUATION_GUIDE.md

langgraph.json
pyproject.toml
```

---

## 3. 分层职责

### 3.1 interfaces：外部入口层

`interfaces` 只处理外部调用方式，例如 CLI、HTTP API、未来的 MCP / Web UI。

它负责：

```text
1. 解析 CLI 参数或 HTTP 请求。
2. 将外部 request 转成 workflow input。
3. 调用 bootstrap 暴露的 app。
4. 将 workflow output 转成用户可见响应。
```

它不负责：

```text
1. schema grounding。
2. prompt 构建。
3. SQL 校验。
4. retry 控制。
5. 数据库执行。
```

### 3.2 workflows：工作流层

`workflows` 是 LangGraph 所在层。

它负责：

```text
1. 定义 graph state。
2. 定义 node。
3. 定义 edge / conditional edge。
4. 编译 graph。
5. 控制 retry、success、failed、clarification、human review 等流程分支。
```

它不负责：

```text
1. 直接拼 prompt。
2. 直接访问数据库。
3. 直接访问向量库。
4. 直接做复杂业务逻辑。
```

Node 应该很薄：

```text
node = 读取 state -> 调用 service -> 返回 partial state update
```

### 3.3 domain：稳定业务模型层

`domain` 放项目长期稳定的业务语言。

它不应该依赖：

```text
LangGraph
LangChain
FastAPI
SQLite
Chroma
具体模型供应商
CLI
```

典型模型：

```text
SchemaCatalog
GroundingContext
SchemaDocument
Feedback
GenerationInput
SqlPolicy
SqlCheckResult
TableResult
QueryPlan
GroundedQueryPlan
```

### 3.4 services：业务能力层

`services` 是项目核心业务能力所在地。

它应该可以被以下对象调用：

```text
LangGraph node
单元测试
批量评估脚本
未来 API
```

典型服务：

```text
QuestionUnderstandingService
SchemaGroundingService
SqlGenerationService
SqlCheckService
SqlExecutionService
QueryPlanGenerationService
```

### 3.5 integrations：外部系统集成层

`integrations` 只解决“怎么连接外部世界”。

例如：

```text
LLM provider
LangChain chain
SQLite / 达梦 / PostgreSQL executor
Chroma vectorstore
Embedding model
LangSmith tracing
```

不要在 integrations 里写 NL2SQL 工作流判断。

### 3.6 platform：运行平台设施层

`platform` 放项目运行设施：

```text
config loader
logging
paths
run record
checkpoint factory
统一错误类型
```

它不是业务层，也不是外部集成层。

### 3.7 bootstrap：依赖装配层

`bootstrap` 负责把所有东西接起来：

```text
1. 读取配置。
2. 创建 logger。
3. 创建 database gateway。
4. 创建 vectorstore。
5. 创建 model / embedding。
6. 创建 services。
7. 创建 workflows。
8. 暴露 SQLAgentApp。
```

业务流程判断不应该写在 container 里。

---

## 4. 在线 NL2SQL Workflow 设计

### 4.1 第一版流程

第一版不要一次性引入过多阶段。推荐先实现：

```text
START
  -> question_understanding
  -> route_after_question_understanding
      -> clarification_response
      -> schema_grounding
  -> build_generation_input
  -> generate_sql
  -> check_sql
  -> route_after_check
      -> build_generation_input    # retry
      -> failed_response
      -> execute_sql
  -> route_after_execute
      -> build_generation_input    # retry
      -> failed_response
      -> success_response
  -> END
```

### 4.2 后续增强流程

稳定后再扩展为：

```text
START
  -> question_understanding
  -> query_plan_generation
  -> query_plan_validation
  -> schema_grounding
  -> grounded_query_plan_building
  -> sql_generation
  -> sql_check
  -> optional_human_review
  -> sql_execution
  -> result_validation
  -> response
  -> END
```

不要在第一版就引入全部节点。

---

## 5. 在线 NL2SQL 最终接口

### 5.1 Workflow Input

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

### 5.2 Workflow Output

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

### 5.3 对外应用接口

```python
from typing import Protocol


class Nl2SqlWorkflow(Protocol):
    def run(self, input: Nl2SqlInput) -> Nl2SqlOutput:
        ...
```

对外入口只能依赖这个接口，不依赖内部 node、state、service。

---

## 6. Graph State 设计

Graph state 是 workflow 内部运行态，不是 API response，也不是 domain model。

推荐结构：

```python
from typing import Any, Literal, TypedDict


class Nl2SqlGraphState(TypedDict, total=False):
    task_id: str
    request_id: str | None
    user_id: str | None
    database_key: str | None

    raw_question: str
    normalized_question: str
    clarification_message: str | None

    candidate_tables: list[str]
    candidate_columns: list[str]
    grounding_context: dict[str, Any]
    semantic_context: dict[str, Any]

    generation_input: dict[str, Any]
    generated_text: str
    checked_sql: str

    check_error: str | None
    execute_error: str | None
    feedback: str | None

    result_columns: list[str]
    result_rows: list[dict[str, Any]]

    round_index: int
    max_round_count: int
    status: Literal[
        "running",
        "success",
        "needs_clarification",
        "failed",
        "rejected",
    ]

    trace_id: str | None
```

注意：

```text
1. state 可以用 dict / TypedDict，domain model 可以用 dataclass / pydantic。
2. state 中可以存可序列化快照，避免塞复杂连接对象。
3. 外部系统实例不要放进 state，通过 service / dependency 注入解决。
```

---

## 7. Node 设计规则

每个 node 必须遵守：

```text
1. 输入 state。
2. 不直接修改原 state。
3. 调用一个明确 service。
4. 返回 partial state update。
5. 不访问 CLI / HTTP request。
6. 不直接 new database / vectorstore / model。
```

示例：

```python
def check_sql_node(state: Nl2SqlGraphState) -> dict:
    result = sql_check_service.check(
        sql_text=state["generated_text"],
        grounding_context=state.get("grounding_context", {}),
    )

    if result.success:
        return {
            "checked_sql": result.sql,
            "check_error": None,
        }

    return {
        "check_error": result.error_message,
        "feedback": result.feedback,
    }
```

---

## 8. Edge 设计规则

Edge 只做路由，不做业务。

例如：

```python
def route_after_check(state: Nl2SqlGraphState) -> str:
    if not state.get("check_error"):
        return "execute_sql"

    if state["round_index"] + 1 < state["max_round_count"]:
        return "build_generation_input"

    return "failed_response"
```

不要在 edge 里：

```text
1. 调 LLM。
2. 查数据库。
3. 查向量库。
4. 拼 prompt。
5. 写日志细节。
```

---

## 9. QueryPlan 的位置

QueryPlan 不应该一开始强行加入第一版。

但目录上要预留：

```text
domain/query_plan/
services/query_plan/
workflows/query_plan/ 或 workflows/nl2sql 内部节点
```

未来推荐流程：

```text
自然语言问题
  -> QuestionUnderstanding
  -> QueryPlanGeneration
  -> QueryPlanValidation
  -> SchemaGrounding
  -> GroundedQueryPlan
  -> SQLGeneration
```

QueryPlan 的目标不是让系统变成“自由 agent”，而是把 SQL 生成前的意图、表关系、过滤条件、聚合逻辑先结构化。

---

## 10. Schema Grounding 设计

Schema Grounding 是 NL2SQL 准确率的核心。

推荐拆成：

```text
SchemaGroundingService
  -> TableRetrievalService
  -> ColumnRetrievalService
  -> SchemaExpansionService
  -> GroundingContextBuilder
  -> SchemaCatalogProvider
```

职责：

```text
TableRetrievalService:
  根据用户问题召回候选表。

ColumnRetrievalService:
  根据问题和候选表召回候选字段。

SchemaExpansionService:
  根据表、字段、关系、值提示扩展上下文。

GroundingContextBuilder:
  组装给 SQL 生成阶段使用的 GroundingContext。

SchemaCatalogProvider:
  提供当前数据库完整 schema catalog。
```

第一版可以只做 table-level retrieval + schema expansion，column-level retrieval 可以后置。

---

## 11. Schema Index Workflow 设计

schema-index 是在线 grounding 的前置知识构建流程。

推荐流程：

```text
START
  -> load_schema_catalog
  -> build_schema_table_text_inputs
  -> generate_schema_table_text
  -> check_schema_table_text
  -> build_schema_documents
  -> write_vectorstore
  -> END
```

Graph state：

```python
class SchemaIndexGraphState(TypedDict, total=False):
    database_key: str
    schema_catalog: dict
    table_text_inputs: list[dict]
    generated_text_by_table: dict[str, dict]
    checked_table_texts: dict[str, dict]
    schema_documents: list[dict]
    write_result: dict
    status: str
```

第一阶段也可以先不把 schema-index 做成 LangGraph；但新项目如果从零开始，可以直接按 workflow 方式实现。

---

## 12. SQL 安全策略

SQLAgent 必须把 SQL 安全作为一等公民。

第一版至少支持：

```text
1. 只允许 SELECT / WITH 查询。
2. 禁止多语句。
3. 禁止 DDL / DML / DCL。
4. 禁止 SELECT *。
5. 表名必须在 schema 白名单内。
6. 字段名必须在 schema 白名单内。
7. 自动补 LIMIT。
8. 限制最大返回行数。
9. 可配置高风险查询进入 human review。
```

配置示例：

```yaml
sql_policy:
  readonly_only: true
  allow_select_star: false
  require_limit: true
  default_limit: 100
  max_limit: 1000
  allow_multi_statement: false
  human_review:
    enabled: false
    require_review_for_large_scan: true
```

---

## 13. Human Review 预留设计

第一版可以不开启 Human Review，但架构要预留。

推荐放在：

```text
workflows/nl2sql/nodes.py
  human_review_node
```

触发条件可以来自：

```text
1. SQL policy 判断高风险。
2. QueryPlanValidation 置信度低。
3. ResultValidation 异常。
4. 用户配置要求执行前确认。
```

流程：

```text
check_sql
  -> route_after_check
      -> human_review
      -> execute_sql
```

Human Review 不应该写成 CLI input hack，而应该作为 workflow 的一个正式暂停点。

---

## 14. 配置设计

推荐配置文件：

```text
config/app.yml
config/env.yml
config/model.yml
config/workflow.yml
config/sql_policy.yml
config/semantic.yml
config/schema_value_hints.yml
```

### 14.1 workflow.yml

```yaml
workflow:
  nl2sql:
    max_round_count: 3
    enable_query_plan: false
    enable_result_validation: false
    enable_human_review: false
    checkpoint:
      enabled: true
      provider: memory

  schema_index:
    reset_collection_before_write: true
```

### 14.2 model.yml

```yaml
model:
  chat:
    provider: openai
    model_name: gpt-4.1-mini
    temperature: 0
  embedding:
    provider: openai
    model_name: text-embedding-3-small
```

### 14.3 env.yml

```yaml
database:
  default_key: demo
  connections:
    demo:
      provider: sqlite
      dsn: data/demo.sqlite

vectorstore:
  provider: chroma
  persist_dir: data/chroma

logging:
  run_dir: runs
```

---

## 15. Bootstrap 设计

`container.py` 是全项目最重要的装配文件之一。

推荐结构：

```python
@dataclass(frozen=True)
class SQLAgentApp:
    nl2sql_workflow: Nl2SqlWorkflow
    schema_index_workflow: SchemaIndexWorkflow
    config: AppConfig


def build_app() -> SQLAgentApp:
    config = load_config()
    logger = build_logger(config)

    database_gateway = build_database_gateway(config)
    vectorstore = build_vectorstore(config)
    chat_model = build_chat_model(config)
    embedding_model = build_embedding_model(config)

    services = build_services(
        config=config,
        logger=logger,
        database_gateway=database_gateway,
        vectorstore=vectorstore,
        chat_model=chat_model,
        embedding_model=embedding_model,
    )

    nl2sql_workflow = build_nl2sql_workflow(config, services)
    schema_index_workflow = build_schema_index_workflow(config, services)

    return SQLAgentApp(
        nl2sql_workflow=nl2sql_workflow,
        schema_index_workflow=schema_index_workflow,
        config=config,
    )
```

注意：container 负责装配，不负责业务流程。

---

## 16. 测试结构

推荐测试目录：

```text
tests/
  unit/
    services/
    domain/
  integration/
    database/
    vectorstore/
    llm_chains/
  workflow/
    nl2sql/
    schema_index/
  evaluation/
    datasets/
      demo_questions.yml
    test_nl2sql_eval.py
  regression/
    test_legacy_vs_new.py
```

### 16.1 单元测试优先级

优先测试：

```text
1. SqlCheckService
2. SchemaGroundingService
3. GenerationInputBuilder
4. ResponseBuilder
5. route_after_check / route_after_execute
```

### 16.2 Workflow 测试

测试目标：

```text
1. 空问题是否进入 clarification。
2. check 失败是否 retry。
3. execute 失败是否 retry。
4. 超过 max_round_count 是否 failed。
5. 成功时是否返回 sql、columns、rows。
```

### 16.3 Evaluation 测试

NL2SQL 不能只靠单元测试。

需要准备评估集：

```yaml
- id: q001
  question: 统计每个部门的员工数量
  expected_tables:
    - department
    - employee
  forbidden_sql:
    - DELETE
    - UPDATE
    - DROP
  expected_status: success

- id: q002
  question: 最近 30 天订单金额最高的前 10 个客户
  expected_tables:
    - orders
    - customers
  must_contain_sql:
    - LIMIT
```

评估维度：

```text
1. 是否生成只读 SQL。
2. 是否使用正确表。
3. 是否使用正确字段。
4. 是否能执行成功。
5. 结果列是否符合问题。
6. 错误时是否给出合理 clarification / failed message。
```

---

## 17. AI 辅助开发规则

新项目可以让 AI 写代码，但必须按以下规则执行。

### 17.1 禁止事项

```text
1. 禁止让 AI 在多个目录中大范围随意 patch。
2. 禁止一次同时改 workflow、service、integration、config、test。
3. 禁止在没有接口的情况下让 AI 自由发挥实现。
4. 禁止为了兼容旧代码而污染新架构。
5. 禁止让 node 直接访问外部系统。
```

### 17.2 推荐任务拆分

```text
任务 1：创建 domain model。
任务 2：创建 workflow input/output。
任务 3：创建 graph state。
任务 4：创建 edges，只写路由函数。
任务 5：创建 nodes，内部 service 先 mock。
任务 6：实现 SqlCheckService。
任务 7：实现 SchemaGroundingService。
任务 8：实现 SqlGenerationService。
任务 9：实现 SqlExecutionService。
任务 10：接入 bootstrap。
任务 11：写 workflow 测试。
任务 12：写 evaluation 测试。
```

### 17.3 每次改动必须满足

```text
1. 只改一个边界。
2. 有对应测试。
3. 不破坏最终接口。
4. 不把业务逻辑塞进 integrations。
5. 不把外部依赖塞进 domain。
```

---

## 18. 第一阶段最小可运行版本

不要第一天就做完整架构。

第一阶段只实现：

```text
interfaces/cli/commands/ask.py
workflows/nl2sql/
domain/schema/
domain/sql/
domain/nl2sql/
services/schema_grounding/
services/nl2sql/sql_check_service.py
services/nl2sql/sql_generation_service.py
services/nl2sql/sql_execution_service.py
integrations/llm/chains/nl2sql_chain.py
integrations/database/sqlite/
integrations/vectorstore/chroma_store.py
platform/config/
bootstrap/container.py
```

流程：

```text
ask
  -> schema_grounding
  -> generation_input
  -> generate_sql
  -> check_sql
  -> execute_sql
  -> response
```

暂时不做：

```text
QueryPlan
HumanReview
ResultValidation
HTTP API
达梦数据库
复杂 checkpoint 存储
复杂 inspect UI
```

---

## 19. 第二阶段增强

第二阶段加入：

```text
1. schema-index workflow。
2. workflow checkpoint。
3. inspect_run CLI。
4. query plan 初版。
5. evaluation dataset。
6. result validation。
```

---

## 20. 第三阶段增强

第三阶段加入：

```text
1. Human Review。
2. HTTP API。
3. 多数据库 provider。
4. 更细粒度 column retrieval。
5. semantic catalog。
6. LangSmith / tracing 集成。
7. 批量 benchmark。
```

---

## 21. 命名规则

### 21.1 文件命名

```text
小写 + 下划线

sql_check_service.py
schema_grounding_service.py
query_plan_generation_service.py
```

### 21.2 类命名

```text
PascalCase

SqlCheckService
SchemaGroundingService
QueryPlanGenerationService
```

### 21.3 方法命名

```text
动词 + 名词

check_sql()
ground_schema()
generate_query_plan()
build_generation_input()
```

### 21.4 不推荐命名

```text
Manager
Helper
Util
Processor
Handler
```

除非语义非常明确，否则避免使用这些泛化词。

---

## 22. 最重要的架构边界

必须长期遵守：

```text
interfaces 不知道 node。
workflows 不直接访问数据库、向量库、LLM provider。
domain 不依赖任何框架。
services 不依赖 CLI / HTTP。
integrations 不决定业务流程。
platform 不承载业务语义。
bootstrap 只装配，不判断流程。
```

一句话：

```text
workflow 控制流程，service 承载业务，integration 连接外部，domain 表达业务语言。
```

---

## 23. 推荐落地顺序

```text
1. 建目录。
2. 写 Nl2SqlInput / Nl2SqlOutput。
3. 写 Nl2SqlGraphState。
4. 写 edges。
5. 写 graph.py，node 先 mock。
6. 写 response_builder。
7. 写 SqlCheckService。
8. 写 SqlExecutionService。
9. 写 SqlGenerationService。
10. 写 SchemaGroundingService。
11. 接入 CLI ask。
12. 加 evaluation questions。
13. 加 schema-index。
14. 加 checkpoint / inspect。
15. 加 QueryPlan。
```

---

## 24. 参考资料

- LangGraph Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
- LangGraph StateGraph API Reference: https://reference.langchain.com/python/langgraph/graphs
- LangGraph Persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph Interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- LangChain Human-in-the-loop: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- Martin Fowler: Original Strangler Fig Application: https://martinfowler.com/bliki/OriginalStranglerFigApplication.html

---

## 25. 最终原则

新项目不要围绕旧代码结构写。

新项目应该围绕以下顺序建设：

```text
最终接口
  -> domain 业务语言
  -> workflow state
  -> service 能力
  -> integration 实现
  -> bootstrap 装配
  -> interface 入口
  -> evaluation 验证
```

不要把“能跑”当成最终目标。

真正目标是：

```text
可解释
可观察
可验证
可重试
可扩展
可回归
```
