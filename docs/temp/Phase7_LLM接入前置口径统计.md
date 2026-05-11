# Phase7 LLM 接入前置口径统计

> 本文不是 Phase7 执行设计，也不是代码计划。
>
> 本文先统计参考项目 `SQLAgent` 接入 LLM 相关的东西，并换算到当前 `NL2SQLAgent` 阶段，明确：
>
> ```text
> 哪些是 LLM 接入的核心能力
> 哪些是参考项目的额外功能
> 哪些应该结合 LangGraph 框架设计
> 哪些当前可以不设计
> 当前不设计后，后续加上是否麻烦
> ```
>
> 这份口径定清楚后，再写真正的 LLM SQL 生成验证设计。

## 1. 当前项目所处阶段

当前项目已经跑通：

```text
Raw question
  -> normalize_question
  -> build_prompt
  -> generate_sql mock
  -> check_sql mock
  -> execute_sql mock
  -> response
```

其中 `build_prompt` 已经形成当前最重要的中间层消费链路：

```text
ProcessedQuestion
  + ProcessedDatabaseKnowledge
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> PromptPayload
  -> FinalPrompt
```

当前阶段真正想验证的是：

```text
人工 ProcessedQuestion
  + 人工 ProcessedDatabaseKnowledge
  -> 当前 pipeline
  -> final_prompt
  -> LLM
  -> generated_sql
```

也就是说，当前不是在做完整 NL2SQL 产品能力，而是在验证：

```text
当前中间层字段设计和 prompt 结构，能不能支撑 LLM 生成可接受的 SQL。
```

## 2. 参考项目 LLM 接入相关构件统计

参考项目位置：

```text
F:\workspace\workspace_python\SQLAgent
```

### 2.1 模型配置

相关文件：

```text
config/model.yml
src/sqlagent/runtime/config.py
src/sqlagent/runtime/config_properties.py
```

参考项目配置：

```yaml
chat_model_name: glm-5
local_embedding_model_name: qwen3-embedding:4b
```

作用：

```text
chat_model_name:
  给 NL2SQLChain / SchemaTableTextChain 使用。

local_embedding_model_name:
  给向量库 / schema 检索使用。
```

口径判断：

```text
chat_model_name 属于 LLM 接入核心能力。
local_embedding_model_name 属于知识层 / 向量召回能力，不属于当前 SQL 生成验证核心。
```

### 2.2 LLM 工厂

相关文件：

```text
src/sqlagent/infrastructure/llm/model_factory.py
```

参考项目做了：

```text
1. 从 .env / 环境变量读取 DASHSCOPE_API_KEY。
2. 使用 DashScope OpenAI-compatible base_url。
3. 构建 ChatOpenAI。
4. 构建 OllamaEmbeddings。
```

口径判断：

```text
ChatOpenAI 构建属于 LLM 接入核心能力。
API key 不写死属于安全底线。
OllamaEmbeddings 属于向量召回能力，当前不需要。
```

### 2.3 NL2SQL Chain

相关文件：

```text
src/sqlagent/engine/chains/nl2sql_chain.py
```

参考项目链路：

```text
Nl2SqlGenerationInput
  -> _build_prompt_payload
  -> PromptTemplate
  -> ChatOpenAI
  -> StrOutputParser
  -> generated text
```

同时 chain 中穿插：

```text
log_chain_input
log_chain_passthrough(prompt_text)
log_chain_model_start
log_chain_model_usage
log_chain_output
```

口径判断：

```text
final prompt 调用 chat model 属于当前核心能力。
PromptTemplate 不一定需要，因为当前项目已经有 final_prompt。
LangChain Runnable chain 不一定需要，因为当前项目已经有 LangGraph workflow。
chain 内 token usage 日志属于运行观测能力，不属于当前 SQL 生成验证核心。
```

### 2.4 GenerateStage

相关文件：

```text
src/sqlagent/application/nl2sql_orchestration/generate/generate_stage.py
```

参考项目做法：

```text
1. 从 context.nl2sql.prepare.generation_input 取输入。
2. 调 nl2sql_chain.invoke(...)。
3. 把 generated_text 写回 context.nl2sql.generate。
4. 清空 check / execute 下游结果。
```

口径判断：

```text
生成阶段调用 LLM 属于核心能力。
通过 replace(context, ...) 维护不可变上下文是参考项目自己的 orchestration 风格。
当前项目已经使用 LangGraph state，不应该照搬 context + stage 模式。
```

换算到当前项目：

```text
generate_sql 节点应该承担“生成 SQL”这个图节点职责。
节点返回 partial state update。
不要新建 GenerateStage 再绕过 LangGraph。
```

### 2.5 日志和 token usage

相关文件：

```text
src/sqlagent/runtime/agent_logging.py
src/sqlagent/runtime/token_usage.py
```

参考项目做了：

```text
1. chain input 日志。
2. prompt_text 日志。
3. model invoke_start 日志。
4. token usage 提取和聚合。
5. chain output 日志。
6. 敏感信息脱敏。
7. token_usage.log 汇总输出。
```

口径判断：

```text
prompt / output 可观察性是当前需要的。
token usage 聚合不是当前需要的。
敏感信息脱敏后续重要，但当前 artifact 主要用于本地调试，可以先不做复杂策略。
```

为什么 token usage 当前先不做：

```text
1. 当前目标是验证 SQL 生成效果，不是统计成本。
2. 当前只有一次 LLM 调用，手写聚合价值不高。
3. 后续如果引入 LangGraph stream / callback / LangSmith，token usage 应该统一放进运行观测设计。
4. 现在先手写 token_usage artifact，后续可能和 LangGraph / LangSmith 记录重复。
```

### 2.6 container 装配

相关文件：

```text
src/sqlagent/bootstrap/container.py
```

参考项目做了：

```text
1. 构建 database gateways。
2. 构建 schema grounding service。
3. 构建 vector store。
4. 构建 chat_model。
5. 构建 NL2SQLChain。
6. 构建 QuestionPlanningStage / PrepareStage / GenerateStage / CheckStage / ExecuteStage。
7. 构建 MainOrchestration。
```

口径判断：

```text
chat model / SQL generator 的装配需要吸收。
完整 stage/service/orchestration/container 接线不应该照搬。
```

原因：

```text
当前项目选择 LangGraph，就是为了让流程结构显式在 graph.py 中。
如果再引入 stage orchestration，会出现两套流程控制：
  一套在 LangGraph
  一套在 Stage / Orchestration
这会让项目重新变晕。
```

### 2.7 cloud 测试

相关文件：

```text
tests/cloud/README.md
```

参考项目约定：

```text
1. 会调用远端 LLM 的测试放 tests/cloud。
2. 显式加 @pytest.mark.cloud。
3. 默认 pytest -q 不依赖 cloud 测试。
```

口径判断：

```text
这个需要吸收。
```

原因：

```text
远端 LLM 测试依赖 API key、网络和 token 消耗。
它不应该污染普通单元测试和集成测试。
```

## 3. 换算到当前项目：能力分类

### 3.1 当前阶段必须设计并实现

这些是 `final_prompt -> LLM -> generated_sql` 的最小闭环。

| 能力 | 是否需要 | 归属 | 说明 |
|---|---:|---|---|
| 模型名称配置 | 需要 | 项目配置 | 不能把模型名写死在节点里 |
| API key 读取 | 需要 | LLM adapter / 配置层 | 从环境变量或 `.env` 读取，不进入 artifact |
| OpenAI-compatible chat model 调用 | 需要 | LLM adapter | 当前可以参考 DashScope 兼容接口 |
| SQL 生成 adapter | 需要 | workflow 内薄 adapter 或装配层 | 接收 `final_prompt`，返回 `generated_sql` |
| `generate_sql` 节点真实生成 | 需要 | LangGraph node | 节点职责仍然是“生成 SQL” |
| 生成失败分支 | 需要 | LangGraph edge | `generate_sql` 失败后进入 `failed_response` |
| generated_sql 写入 output/artifact | 需要 | artifact / response | 用于人工验收 |
| cloud 测试隔离 | 需要 | tests/cloud | 显式运行，默认测试不跑 |

### 3.2 当前阶段需要设计，但可以很薄

这些需要留边界，否则后续容易乱，但实现不必复杂。

| 能力 | 当前口径 | 后续扩展难度 |
|---|---|---|
| LLM adapter 接口 | 先定义最小 `generate(final_prompt) -> result` | 不难，后续可换 provider |
| fake LLM 实现 | 用于普通测试和本地流程测试 | 不难，反而能稳定测试 |
| LLM result 结构 | 先放 `generated_sql / model_name / raw_text` | 不难，后续可加 usage / finish_reason |
| SQL 输出清洗 | 只做去 markdown fence / strip | 不难，后续可加 parser |
| 错误对象 | 先用 `generate_error` 字符串 | 中等，后续可升级成结构化错误 |

### 3.3 当前阶段应该结合 LangGraph 设计

这些东西不应该用普通 options 或外部 orchestration 偷偷处理。

| 问题 | 应该由谁表达 | 原因 |
|---|---|---|
| 生成 SQL 成功后进入检查 | LangGraph edge | 这是工作流节点关系 |
| 生成 SQL 失败后进入失败响应 | LangGraph conditional edge | 这是流程分支 |
| 节点更新了哪些中间状态 | LangGraph state updates | 方便 stream / artifact 观察 |
| 每个节点的运行更新 | `graph.stream(..., stream_mode="updates")` | 当前 artifact 已经基于这个设计 |
| 后续中断、恢复、人工介入 | LangGraph checkpoint / interrupt | 这是选择 LangGraph 的重要原因 |
| 后续 token / 模型事件观测 | LangGraph callback / stream / LangSmith 口径 | 不应先手写分散日志体系 |

### 3.4 当前阶段不应该设计或不应该实现

这些会把当前目标扩大。

| 能力 | 当前不做原因 | 后续是否难加 |
|---|---|---|
| token usage 聚合 | 当前只验证 SQL 生成效果；后续应结合 LangGraph/LangSmith | 不难，但要等观测口径定好 |
| LangSmith | 当前还没有多模型、多节点观测需求 | 不难，通常是配置和 callback 接入 |
| retry / repair | 会改变流程复杂度，不利于观察第一版 prompt | 中等，需要新增图分支 |
| SQL 执行真实 DB | 当前只看生成 SQL，不验证执行 | 中等，后续 execute_sql 节点替换 |
| 自动生成 ProcessedQuestion | 当前要先验证手工对象字段是否有效 | 难，但和 LLM 接入不是同一步 |
| 自动生成 ProcessedDatabaseKnowledge | 当前要先验证手工知识层消费 | 难，应单独设计 |
| 向量召回 | 会影响 KnowledgeRetrievalResult 来源，不影响当前 SQL 生成 adapter | 中到难，需要知识层设计 |
| 历史 SQL 模板 | 是另一条生成路径，不应混入当前 LLM 验证 | 中等，需要图分支或前置路由 |
| embedding model | 属于知识检索，不属于 SQL 生成验证 | 不难，但依赖向量方案 |
| 完整 chain 目录 | 当前已有 final_prompt 和 LangGraph workflow | 不难，但现在加会制造重复抽象 |
| stage/service/orchestration | 会和 LangGraph 流程控制重叠 | 后续一般不需要 |

## 4. 关于 `use_llm_generate` 的口径

不建议设计：

```text
options.use_llm_generate
```

原因是它把环境/装配差异伪装成业务输入。

错误倾向：

```text
同一条业务图：
  use_llm_generate=False -> mock
  use_llm_generate=True  -> real LLM
```

这样会导致：

```text
1. graph.py 看不出真实行为差异。
2. options 逐渐变成隐藏开关集合。
3. LangGraph 只剩表面流程，关键行为藏在节点内部 if 里。
4. 后续 use_vector / use_history_sql / use_xxx 也可能继续堆进 options。
```

正确口径：

```text
generate_sql 节点永远表示“生成 SQL”。
```

不同环境通过装配不同实现解决：

```text
普通单元测试:
  FakeSqlGenerator

本地人工验证:
  OpenAICompatibleSqlGenerator

cloud 测试:
  OpenAICompatibleSqlGenerator + 真实 API key
```

也就是说：

```text
是否使用真实 LLM，不是业务分支。
生成成功 / 生成失败，才是 LangGraph 分支。
```

## 5. 当前项目有没有跑偏

当前代码主线没有明显跑偏。

理由：

```text
1. graph.py 使用 StateGraph 明确表达节点和条件边。
2. GraphRuntime 使用 graph.stream(..., stream_mode="updates") 和 get_state。
3. artifact 的 graph_updates.jsonl 来自 LangGraph updates。
4. nodes 返回 partial state update，符合 LangGraph 使用方式。
5. runtime_options 当前只用于 mock 故障注入，还没有扩散成业务开关。
```

当前需要守住的边界：

```text
1. 不要把 LLM 是否启用做成 runtime_options。
2. 不要引入 Stage / Orchestration 作为第二套流程控制。
3. 不要把 token usage 先做成项目自定义全局聚合。
4. 不要把向量、历史 SQL、retry 混进本次 LLM SQL 生成验证。
```

## 6. 当前阶段推荐最小能力边界

当前阶段只设计下面这条：

```text
build_prompt
  -> generate_sql
  -> route_after_generate
  -> check_sql / failed_response
```

其中：

```text
build_prompt:
  继续产出 final_prompt。

generate_sql:
  调用注入的 SQL generator。
  输入 final_prompt。
  输出 generated_sql / llm_result 或 generate_error。

route_after_generate:
  如果 generate_error 存在，进入 failed_response。
  否则进入 check_sql。
```

SQL generator 的最小接口可以是：

```text
generate(final_prompt: str) -> SqlGenerationResult
```

这里有一个重要边界：

```text
generate() 初版只接收 final_prompt。
```

不要把下面这些运行和供应商配置塞进每次调用参数：

```text
model_name
api_key
base_url
temperature
timeout
```

这些应该在 generator 构造或装配时确定。

也就是说，推荐口径是：

```text
OpenAICompatibleSqlGenerator(
  model_name=...,
  api_key=...,
  base_url=...,
  temperature=...,
)

generate(final_prompt)
```

而不是：

```text
generate(final_prompt, model_name, api_key, base_url, temperature, ...)
```

原因：

```text
1. generate_sql_node 保持薄，只关心“拿 final_prompt 生成 SQL”。
2. 模型供应商和鉴权细节不污染 LangGraph node。
3. 单元测试可以直接替换 FakeSqlGenerator。
4. 后续切换 provider 时，不需要改 workflow state 和节点签名。
```

结果最小字段：

```text
generated_sql
model_name
raw_text
```

暂不包含：

```text
token_usage
callbacks
LangSmith run id
retry metadata
SQL parse result
```

## 7. 后续加上当前不设计的能力会不会麻烦

### 7.1 token usage

当前不做，后续不麻烦。

前提是当前不要把 `llm_result` 设计死。

后续可以从：

```text
LangChain response metadata
LangGraph callback
LangSmith trace
```

统一进入运行观测体系。

### 7.2 LangSmith / tracing

当前不做，后续不麻烦。

前提是：

```text
LLM 调用集中在 adapter 中。
GraphRuntime 是图运行统一入口。
```

这样后续可以在两个地方接观测：

```text
1. GraphRuntime config / callbacks。
2. LLM adapter 内部模型调用。
```

### 7.3 retry / repair

当前不做，后续中等成本。

原因是 retry / repair 不是简单字段，而是流程变化：

```text
check_sql failed
  -> repair_prompt
  -> generate_sql
  -> check_sql
```

这应该作为 LangGraph 分支或循环单独设计。

当前先不做是对的。

### 7.4 向量召回

当前不做，后续中到高成本。

原因是向量召回影响的是：

```text
ProcessedDatabaseKnowledge
KnowledgeRetrievalResult
SchemaLinkingResult
```

而不是直接影响：

```text
final_prompt -> LLM
```

所以它应该属于知识层阶段，不属于 LLM SQL 生成验证阶段。

### 7.5 历史 SQL 模板

当前不做，后续中等成本。

原因是历史 SQL 模板可能是一条并行路径：

```text
question
  -> template_match
  -> fill_template
  -> check_sql
```

它不是简单塞进 prompt 的材料。

如果以后要做，应该用 LangGraph 显式表达：

```text
route_after_question_understanding
  -> template_sql_path
  -> knowledge_prompt_sql_path
```

当前不混入是合理的。

## 8. 初步结论

参考项目可以吸收的核心是：

```text
1. model.yml 管模型名。
2. API key 从环境变量或 .env 读取。
3. 使用 OpenAI-compatible ChatOpenAI。
4. 远端 LLM 测试放 tests/cloud。
5. prompt / generated_sql 可观察。
```

参考项目当前不应照搬的是：

```text
1. engine/chains 目录结构。
2. application stage / orchestration 流程控制。
3. token_usage 全局聚合。
4. embedding / vectorstore。
5. 完整 chain logging middleware。
```

当前项目下一份真正的设计文档应该围绕：

```text
LangGraph generate_sql 节点如何接入 SQL generator，
以及 generate_sql 失败如何通过条件边进入 failed_response。
```

而不是围绕：

```text
use_llm_generate 开关。
```

一句话口径：

```text
当前 LLM 接入不是新增一套 LLM 系统，
而是在 LangGraph 已有 generate_sql 节点中，
替换 mock SQL 生成实现，
并把生成结果和失败分支纳入图状态与 artifact。
```

## 9. 后续执行计划需要加入的保护口径

这份文档不是执行计划，但下一份真正的 plan 需要加入几条架构保护项，防止实现时又绕回参考项目的复杂结构。

### 9.1 禁止 `use_llm_generate`

执行计划中应该要求：

```text
代码中不新增 use_llm_generate。
```

原因：

```text
是否使用真实 LLM 是装配差异，不是业务输入分支。
```

### 9.2 禁止新增第二套流程控制

执行计划中应该明确不新增：

```text
GenerateStage
Nl2SqlChain
MainOrchestration
engine/chains
application/stages
```

原因：

```text
当前项目的流程控制应该继续收敛在 LangGraph graph.py。
```

### 9.3 `generate_sql_node` 不直接初始化模型供应商

执行计划中应该要求 `nodes.py` 不直接出现：

```text
ChatOpenAI(
DASHSCOPE_API_KEY
base_url
api_key
```

原因：

```text
LLM provider 初始化属于 adapter / container 装配职责。
generate_sql_node 只调用已注入的 SqlGenerator。
```

### 9.4 artifact 仍然从 graph state 统一输出

执行计划中应该要求：

```text
LLM adapter 不直接写 prompt.txt / raw_response.txt / token_usage.log。
```

原因：

```text
当前项目已经有 graph state + graph_updates + artifact writer。
如果 adapter 自己写文件，会形成第二套观测出口。
```
