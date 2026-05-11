# Phase7 NL2SQL LLM 接入设计

> 本文基于 `docs/temp/Phase7_LLM接入前置口径统计.md`，设计当前阶段如何把真实 LLM 接入 `generate_sql` 节点。
>
> 本阶段目标不是完成完整 NL2SQL，而是验证：
>
> ```text
> 人工 ProcessedQuestion
>   + 人工 ProcessedDatabaseKnowledge
>   -> 当前 knowledge pipeline
>   -> final_prompt
>   -> LLM
>   -> generated_sql
>   -> artifact 人工观察
> ```

## 1. 当前状态

当前 workflow 已经是 LangGraph 主流程：

```text
normalize_question
  -> build_prompt
  -> generate_sql
  -> check_sql
  -> execute_sql
  -> response
```

其中 `build_prompt` 已经跑通：

```text
ProcessedQuestion
  + ProcessedDatabaseKnowledge
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> PromptPayload
  -> FinalPrompt
```

当前 `generate_sql_node` 仍是 mock：

```python
return {"generated_sql": "SELECT 1 AS value"}
```

本阶段只替换这一段：

```text
final_prompt -> generated_sql
```

## 2. 设计目标

本阶段完成后，应该满足：

```text
1. generate_sql 节点调用真实 SQL generator。
2. SQL generator 只接收 final_prompt，返回 generated_sql。
3. LLM 失败时，LangGraph 通过条件边进入 failed_response。
4. output / artifact 能看到 final_prompt、generated_sql、llm_result 或 generate_error。
5. 普通测试不访问远端 LLM。
6. 远端 LLM 测试放 tests/cloud，显式运行。
```

本阶段不做：

```text
use_llm_generate
token usage
LangSmith
retry / repair
真实数据库执行
向量召回
历史 SQL 模板
自动生成 ProcessedQuestion
自动生成 ProcessedDatabaseKnowledge
engine/chains
GenerateStage
MainOrchestration
```

## 3. 核心原则

### 3.1 LangGraph 负责流程

流程分支必须继续体现在 `graph.py`：

```text
generate_sql
  -> route_after_generate
  -> check_sql / failed_response
```

不能把关键流程藏到：

```text
options.use_llm_generate
```

或新的：

```text
Stage / Orchestration / Chain
```

中。

### 3.2 generator 负责模型调用

`generate_sql_node` 只负责：

```text
1. 从 state 读取 final_prompt。
2. 调用注入的 SqlGenerator。
3. 把生成结果写回 partial state update。
4. 捕获生成失败，写入 generate_error。
```

它不负责：

```text
读取 API key。
初始化 ChatOpenAI。
判断 provider。
写 artifact 文件。
记录 token usage。
执行 retry。
```

### 3.3 装配差异不是业务分支

是否使用 fake generator 或真实 generator，由装配决定：

```text
单元测试 / 普通集成测试:
  FakeSqlGenerator

本地人工 LLM 验证 / cloud 测试:
  OpenAICompatibleSqlGenerator
```

这不是用户输入，也不进入 `runtime_options`。

## 4. 目标流程

目标 LangGraph 流程：

```text
START
  -> normalize_question
  -> route_after_normalize
       -> clarification_response
       -> build_prompt
  -> generate_sql
  -> route_after_generate
       -> failed_response
       -> check_sql
  -> route_after_check
       -> failed_response
       -> execute_sql
  -> route_after_execute
       -> failed_response
       -> success_response
  -> END
```

变化点只有一个：

```text
generate_sql -> check_sql
```

改成：

```text
generate_sql -> route_after_generate -> check_sql / failed_response
```

## 5. 文件设计

### 5.1 新增文件

建议新增：

```text
config/model.yml
src/nl2sqlagent/workflows/nl2sql/sql_generator.py
tests/cloud/README.md
tests/cloud/test_nl2sql_llm_generate.py
tests/unit/workflows/nl2sql/test_sql_generator.py
```

### 5.2 修改文件

建议修改：

```text
pyproject.toml
src/nl2sqlagent/platform/config/models.py
src/nl2sqlagent/platform/config/loader.py
src/nl2sqlagent/bootstrap/container.py
src/nl2sqlagent/workflows/nl2sql/graph.py
src/nl2sqlagent/workflows/nl2sql/edges.py
src/nl2sqlagent/workflows/nl2sql/nodes.py
src/nl2sqlagent/workflows/nl2sql/state.py
src/nl2sqlagent/workflows/nl2sql/response_builder.py
tests/integration/test_nl2sql_workflow.py
tests/unit/workflows/nl2sql/test_nodes.py
tests/unit/workflows/nl2sql/test_edges.py
tests/unit/workflows/nl2sql/test_contracts.py
```

不新增：

```text
src/nl2sqlagent/engine/chains/
src/nl2sqlagent/application/stages/
src/nl2sqlagent/infrastructure/llm/
```

原因：

```text
当前 LLM 调用只服务 NL2SQL workflow 的 generate_sql 节点。
等多个 workflow 复用 LLM provider 后，再考虑迁移公共基础设施。
```

## 6. 配置设计

新增：

```yaml
# config/model.yml
model:
  sql_generator:
    provider: openai_compatible
    chat_model_name: glm-5
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
    temperature: 0
    timeout_seconds: 60
```

字段含义：

```text
provider:
  SQL generator provider。
  初版只支持 openai_compatible。

chat_model_name:
  远端 chat model 名称。

base_url:
  OpenAI-compatible 接口地址。

api_key_env:
  API key 环境变量名。
  真实 key 不写入 yml。

temperature:
  初版建议 0，便于比较 SQL 生成效果。

timeout_seconds:
  远端调用超时时间。
```

说明：

```text
provider 是部署/装配配置，不是业务输入开关。
它不进入 Nl2SqlInput.options，也不进入 runtime_options。
```

如果 API key 缺失：

```text
1. 应用启动不必失败。
2. 真正调用 OpenAICompatibleSqlGenerator.generate() 时失败。
3. generate_sql_node 捕获异常并写入 generate_error。
4. LangGraph 进入 failed_response。
```

这样普通启动检查不会因为没有 key 失败，但真实 LLM 运行会给出明确错误。

## 7. SqlGenerator 设计

新增：

```text
src/nl2sqlagent/workflows/nl2sql/sql_generator.py
```

核心类型：

```python
@dataclass(frozen=True)
class SqlGenerationResult:
    generated_sql: str
    model_name: str
    raw_text: str
```

```python
class SqlGenerator(Protocol):
    def generate(self, final_prompt: str) -> SqlGenerationResult: ...
```

### 7.1 generate 参数边界

`generate()` 初版只接收：

```text
final_prompt
```

不接收：

```text
model_name
api_key
base_url
temperature
timeout
request_id
run_id
```

这些信息的归属：

```text
model_name / api_key / base_url / temperature / timeout:
  generator 构造时确定。

request_id / run_id:
  后续如果观测需要，优先从 LangGraph config / runtime / callback 设计，不塞进 prompt。
```

### 7.2 FakeSqlGenerator

用途：

```text
1. 普通单元测试。
2. 普通集成测试。
3. 验证 graph 分支和 artifact，不访问网络。
```

行为：

```text
输入 final_prompt。
返回固定 SQL 或测试传入 SQL。
model_name = fake-sql-generator。
raw_text = generated_sql。
```

### 7.3 OpenAICompatibleSqlGenerator

职责：

```text
1. 构造时接收 chat_model_name / base_url / api_key_env / temperature / timeout。
2. generate(final_prompt) 时解析 API key。
3. 懒加载 langchain_openai.ChatOpenAI。
4. 调用 chat model。
5. 提取返回文本。
6. 做最小 SQL 文本清洗。
7. 返回 SqlGenerationResult。
```

不负责：

```text
构造 prompt。
检查 SQL。
执行 SQL。
写 artifact。
记录 token usage。
retry / repair。
```

### 7.4 API key 读取

参考项目 `SQLAgent`，但保持克制：

```text
1. 先读取项目 .env。
2. 再用 os.environ 覆盖 .env。
3. 从 api_key_env 指定的变量名取值。
```

真实 key 不进入：

```text
config/model.yml
graph state
artifact
app.log
```

## 8. SQL 文本清洗

LLM 可能返回：

````text
```sql
SELECT ...
```
````

初版只做最小清洗：

```text
strip()
去掉开头结尾 markdown fence
```

如果清洗后为空：

```text
raise SqlGenerationError("LLM returned empty SQL")
```

本阶段不做：

```text
SQL parser
SQL formatter
多语句拆分
危险 SQL 检测
自动 repair
```

这些属于后续 check / policy / repair 阶段。

## 9. Graph 接入设计

### 9.1 graph.py

当前：

```python
graph.add_node("generate_sql", generate_sql_node)
graph.add_edge("generate_sql", "check_sql")
```

目标：

```python
graph.add_node(
    "generate_sql",
    partial(generate_sql_node, sql_generator=sql_generator),
)
graph.add_conditional_edges(
    "generate_sql",
    route_after_generate,
    {
        "failed_response": "failed_response",
        "check_sql": "check_sql",
    },
)
```

`build_nl2sql_graph` 签名建议改为：

```python
def build_nl2sql_graph(*, checkpointer, sql_generator: SqlGenerator):
    ...
```

原因：

```text
1. 依赖显式注入。
2. 测试可以传 FakeSqlGenerator。
3. graph.py 仍然清楚表达流程。
4. 不需要 use_llm_generate。
```

### 9.2 edges.py

新增：

```python
def route_after_generate(
    state: Nl2SqlGraphState,
) -> Literal["failed_response", "check_sql"]:
    if state.get("generate_error"):
        return "failed_response"
    return "check_sql"
```

### 9.3 nodes.py

`generate_sql_node` 改为：

```python
def generate_sql_node(
    state: Nl2SqlGraphState,
    *,
    sql_generator: SqlGenerator,
) -> dict:
    final_prompt = state.get("final_prompt") or ""
    if not final_prompt.strip():
        return {
            "generate_error": "final_prompt is required before SQL generation",
            "status": "failed",
        }
    try:
        result = sql_generator.generate(final_prompt)
    except Exception as exc:
        return {
            "generate_error": str(exc),
            "status": "failed",
        }
    return {
        "generated_sql": result.generated_sql,
        "llm_result": {
            "model_name": result.model_name,
            "raw_text": result.raw_text,
        },
        "generate_error": None,
    }
```

说明：

```text
nodes.py 不直接 import ChatOpenAI。
nodes.py 不读取 DASHSCOPE_API_KEY。
nodes.py 不写文件。
nodes.py 不记录 token usage。
```

### 9.4 failed_response_node

失败消息优先级建议改成：

```text
generate_error
check_error
execute_error
message
默认失败文案
```

因为生成失败后不会继续 check / execute。

## 10. State 与 Output 设计

### 10.1 state.py

新增：

```python
llm_result: dict[str, object]
generate_error: str | None
```

说明：

```text
llm_result 是给 artifact / debug 使用的模型结果摘要。
generate_error 是 LangGraph route_after_generate 的判断依据。
```

### 10.2 response_builder.py

`build_prompt_debug_metadata` 增加：

```text
llm_result
generate_error
```

失败消息增加：

```text
generate_error
```

`output.sql` 继续从：

```text
checked_sql or generated_sql
```

取值。

## 11. Artifact 设计

当前 artifact 已经包括：

```text
input.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
output.json
manifest.json
```

本阶段不新增独立文件。

LLM 相关信息进入：

```text
graph_updates.jsonl
output.json.metadata.llm_result
output.json.metadata.generate_error
```

`llm_result` 初版只包含：

```text
model_name
raw_text
```

不包含：

```text
token_usage
LangSmith run id
provider secret
api_key
```

原因：

```text
1. 当前目标是人工观察 SQL 生成效果。
2. token usage 后续和 LangGraph / LangSmith / callback 统一设计。
3. adapter 不直接写文件，避免第二套观测出口。
```

## 12. 测试设计

### 12.1 单元测试

新增或修改：

```text
tests/unit/workflows/nl2sql/test_sql_generator.py
tests/unit/workflows/nl2sql/test_nodes.py
tests/unit/workflows/nl2sql/test_edges.py
tests/unit/workflows/nl2sql/test_response_builder.py
```

覆盖：

```text
1. FakeSqlGenerator 返回固定 SQL。
2. SQL fence 清洗。
3. 空 SQL 返回错误。
4. generate_sql_node 成功时写 generated_sql / llm_result。
5. generate_sql_node 失败时写 generate_error / status=failed。
6. route_after_generate 根据 generate_error 路由。
7. failed_response 优先展示 generate_error。
```

### 12.2 集成测试

修改：

```text
tests/integration/test_nl2sql_workflow.py
```

用 `FakeSqlGenerator` 构建 graph：

```text
build_nl2sql_graph(checkpointer=..., sql_generator=FakeSqlGenerator(...))
```

验证：

```text
1. workflow output.sql 是 fake SQL。
2. graph_updates.jsonl 中有 generate_sql update。
3. output.json.metadata 中有 llm_result。
4. final_prompt 仍然写入 artifact。
5. 普通集成测试不访问网络。
```

### 12.3 cloud 测试

新增：

```text
tests/cloud/test_nl2sql_llm_generate.py
tests/cloud/README.md
```

约定：

```text
1. 显式标记 @pytest.mark.cloud。
2. 只在手动命令中运行。
3. 需要 DASHSCOPE_API_KEY。
4. 不进入默认 pytest -q。
```

运行方式：

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/cloud -q -m cloud
```

需要在 `pyproject.toml` 增加 marker：

```toml
[tool.pytest.ini_options]
markers = [
    "cloud: tests that call remote LLM services and consume token",
]
```

### 12.4 架构保护测试

为了防止后续实现跑偏，建议增加静态保护测试：

```text
1. src/ 中不出现 use_llm_generate。
2. src/ 中不新增 engine/chains。
3. src/ 中不新增 application/stages。
4. nodes.py 中不出现 ChatOpenAI / DASHSCOPE_API_KEY / base_url / api_key。
5. artifacts.py / response_builder.py 输出中不出现真实 API key。
```

这些测试不是业务测试，而是架构护栏。

第 5 条的目标不是禁止出现环境变量名：

```text
DASHSCOPE_API_KEY
```

而是禁止真实 secret value 进入：

```text
graph state
output.json
graph_updates.jsonl
app.log
```

可以用测试构造一个假 key，例如：

```text
sk-test-secret-should-not-leak
```

然后断言 artifact / output / graph update 中不包含这个真实值。

## 13. 依赖设计

新增最小依赖：

```toml
dependencies = [
    "PyYAML>=6.0",
    "langgraph>=1.0",
    "langchain-core>=0.3",
    "langchain-openai>=0.3",
]
```

不引入：

```text
langchain
langchain-ollama
python-dotenv
```

说明：

```text
1. 当前只需要 ChatOpenAI。
2. .env 解析可以先用小函数完成。
3. embedding / ollama 属于后续知识层能力。
```

## 14. 错误处理

### 14.1 配置错误

例如：

```text
不支持的 provider。
缺少 chat_model_name。
缺少 base_url。
```

应该在 config / container 构建阶段报错。

### 14.2 运行错误

例如：

```text
缺少 API key。
网络失败。
模型返回空内容。
模型调用超时。
```

应该在 `generate_sql_node` 捕获后写入：

```text
generate_error
status=failed
```

然后通过：

```text
route_after_generate -> failed_response
```

结束本次 workflow。

不应该：

```text
伪造 SQL。
继续 check_sql。
继续 execute_sql。
```

## 15. 验收标准

完成后应满足：

```text
1. 默认单元测试和普通集成测试不访问远端 LLM。
2. 使用 FakeSqlGenerator 时，workflow 完整通过。
3. 使用 OpenAICompatibleSqlGenerator 时，final_prompt 能发送给真实 LLM。
4. LLM 生成的 SQL 写入 output.sql / output.json / graph_updates.jsonl。
5. LLM 失败时进入 failed_response，不继续 check_sql。
6. final_prompt.txt 仍然是人工验收 prompt 的主要入口。
7. 不出现 use_llm_generate。
8. 不新增 Stage / Chain / Orchestration 第二套流程。
9. nodes.py 不直接初始化 ChatOpenAI。
10. 不实现 token usage。
11. 真实 API key 不进入 graph state / artifact / app.log。
```

## 16. 后续不在本阶段处理的问题

本阶段完成后，再根据生成效果决定是否调整：

```text
ProcessedQuestion 字段
ProcessedDatabaseKnowledge 字段
SchemaLinkingResult 规则
SqlGenerationContext 结构
PromptPayload 渲染方式
```

如果 SQL 生成效果不好，优先回看：

```text
final_prompt.txt
prompt_payload.json
schema_linking_result
sql_generation_context
```

而不是马上引入：

```text
retry
向量
历史 SQL
LangSmith
token usage
```

## 17. 一句话总结

当前 LLM 接入的正确形状是：

```text
LangGraph 继续管流程；
generate_sql 节点继续表示“生成 SQL”；
SqlGenerator 只管把 final_prompt 发给模型并返回 SQL；
失败通过 LangGraph 条件边进入 failed_response；
观察结果继续走 graph state 和 artifact。
```
