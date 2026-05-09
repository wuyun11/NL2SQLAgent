# Phase 3 NL2SQL 提示词结构设计

> 本文是 Phase 3 的讨论设计稿。
>
> 目标不是写可交给 agent 直接执行的任务清单；真正的执行计划后续再放到 `docs/superpowers/plans/`。

## 1. 背景

当前项目已经完成：

- Phase 0：最小运行底座。
- Phase 1：LangGraph 运行底座。
- Phase 2：NL2SQL 线性工作流骨架。

Phase 2 已经能做到：

```text
normalize_question
  -> build_prompt
  -> generate_sql
  -> check_sql
  -> execute_sql
  -> response
```

并且已经能通过：

```text
Nl2SqlOutput.metadata["final_prompt"]
workflow.stream(..., stream_mode="updates")
```

看到 `final_prompt`。

但 Phase 2 的 prompt 仍然是 mock：

```python
prompt_payload = {
    "question": question,
    "schema": "mock_schema",
    "semantic_rules": ["mock_semantic_rule"],
    "instruction": "Generate a read-only SQL query.",
}
```

Phase 3 的目标，就是把这个 mock prompt 向真实 NL2SQL prompt 推进一步。

## 2. 核心结论

Phase 3 应定位为：

```text
结构化 prompt_payload + 模板渲染 final_prompt
```

也就是说：

```text
要做：
  定义 prompt_payload 的正式字段结构。
  解释每个字段的含义和设计原因。
  用 prompt builder / prompt template 生成 final_prompt。
  保持 workflow 仍然线性。
  保持 generate/check/execute 仍然 mock。

不要做：
  真实 LLM 调用。
  真实数据库连接。
  真实 schema grounding。
  retry。
  QueryPlan。
  CLI ask。
```

Phase 3 的价值是：

```text
让“最终给模型看的提示词”变得接近真实使用场景，同时仍然不引入外部依赖复杂度。
```

## 3. 为什么 Phase 3 先做 prompt payload

NL2SQL 的质量很大程度取决于模型到底看到了什么。

如果现在直接接 LLM，会马上遇到这些问题：

```text
模型生成错了，是 prompt 结构问题？
schema 上下文不够？
SQL policy 没写清楚？
输出格式约束不明确？
还是模型能力问题？
```

如果 prompt payload 没有先结构化，调试会变成反复改大段字符串。

Phase 3 先做 prompt payload 的好处是：

```text
1. 每类上下文有明确字段。
2. final_prompt 可重复渲染。
3. 后续 schema grounding / semantic rules / sql policy 都有稳定落点。
4. 未来接 LLM 时，可以先判断输入质量，而不是直接怀疑模型。
```

一句话：

```text
Phase 3 先解决“要喂给模型的材料怎么组织”，不是解决“模型怎么生成 SQL”。
```

## 4. Phase 3 范围

Phase 3 要做：

```text
1. 定义 prompt_payload 的字段结构。
2. 替换 Phase 2 的简陋 mock prompt_payload。
3. 新增 prompt builder 或 prompt template renderer。
4. build_prompt_node 使用结构化 payload 渲染 final_prompt。
5. output metadata 和 stream 继续能看到 prompt_payload / final_prompt。
6. 测试覆盖 prompt_payload 字段含义、final_prompt 关键片段和字段顺序。
```

Phase 3 不做：

```text
1. 真实 LLM。
2. 真实 SQL 生成。
3. 真实 SQL 执行。
4. 真实 schema 读取。
5. 真实 schema grounding。
6. semantic.yml 真实加载。
7. sql_policy.yml 真实加载。
8. retry。
9. CLI ask。
10. QueryPlan。
```

## 5. 推荐目录

在 Phase 2 已有目录基础上，建议新增：

```text
src/nl2sqlagent/workflows/nl2sql/prompt_payload.py
src/nl2sqlagent/workflows/nl2sql/prompt_builder.py
```

继续放在 `workflows/nl2sql/` 下，而不是新增 `services/`。

原因：

```text
Phase 3 仍然是 workflow skeleton 的 prompt 结构阶段。
当前 prompt payload 仍然使用 mock schema / mock semantic / mock policy。
还没有真正形成可复用业务能力。
```

后续当 prompt payload 开始接入真实 schema grounding、semantic catalog、sql policy 配置时，再考虑把构建逻辑下沉到：

```text
services/nl2sql/prompt_payload_builder.py
```

Phase 3 不提前创建 `services/`，避免为了 mock 结构制造长期目录。

## 6. prompt_payload 总体结构

建议 Phase 3 的 `prompt_payload` 结构如下：

```python
prompt_payload = {
    "task": {...},
    "question": {...},
    "schema_context": {...},
    "semantic_context": {...},
    "sql_policy": {...},
    "output_contract": {...},
    "debug": {...},
}
```

它的设计原则：

```text
1. 每个字段对应一种上下文责任。
2. 字段名表达业务含义，不表达 prompt 排版。
3. payload 只保存结构化材料，不保存最终拼接文本。
4. final_prompt 由 prompt_builder 统一渲染。
5. 后续真实能力接入时，优先填充已有字段，而不是不断新增平级杂项。
```

## 6.1 与参考项目的对应关系

当前 `prompt_payload` 结构参考了原参考项目的 NL2SQL 输入链路，但不是一比一复制。

参考项目中的核心链路是：

```text
Nl2SqlGenerationInput
  -> _build_prompt_payload(...)
  -> PromptTemplate 渲染 nl2sql.txt
```

对应文件是：

```text
F:\workspace\workspace_python\SQLAgent\src\sqlagent\application\nl2sql_orchestration\models\generation_input.py
F:\workspace\workspace_python\SQLAgent\src\sqlagent\engine\chains\nl2sql_chain.py
F:\workspace\workspace_python\SQLAgent\src\sqlagent\engine\chains\prompts\nl2sql.txt
```

参考项目的 prompt payload 更偏向模板变量：

```python
{
    "question": "...",
    "prepared_tables": "...",
    "prepared_knowledge": "...",
    "feedback_section": "...",
}
```

Phase 3 的设计是在这个基础上做结构化升级：

```text
参考项目字段/模型                         Phase 3 字段
QuestionInput.raw_question                question.raw
QuestionInput.normalized_question         question.normalized
SchemaInput.summary_lines                 schema_context
SchemaInput.grounding_context             schema_context 后续扩展来源
SemanticInput.summary_lines               semantic_context
FeedbackInput                             Phase 3 暂不引入
prepared_tables                           schema_context 渲染结果
prepared_knowledge                        semantic_context 渲染结果
feedback_section                          后续 retry/repair 阶段再引入
```

为什么不直接沿用参考项目的四个模板变量：

```text
1. prepared_tables / prepared_knowledge 已经是渲染后的文本，不利于测试字段含义。
2. Phase 3 的目标是让用户能看到最终提示词效果，同时也能检查提示词材料来源。
3. schema、semantic、policy、output contract 后续会分别接入真实能力，提前结构化更利于扩展。
4. 当前阶段明确不做 retry，所以不把 FeedbackInput / feedback_section 放进 payload。
```

为什么新增 `task`、`sql_policy`、`output_contract`、`debug`：

```text
1. task：参考项目把任务目标写在 prompt 模板正文里；当前项目把它显式化，便于后续支持 explain、validate、repair 等任务。
2. sql_policy：参考项目的只读、SQLite、SELECT 等约束主要写在 prompt 文本里；当前项目把生成约束作为独立上下文，方便后续与 SQL check 规则对齐。
3. output_contract：参考项目 prompt 要求生成 SQL，但输出格式没有独立结构；当前项目提前固定输出契约，方便后续接真实 LLM。
4. debug：参考项目已经会记录 prompt payload 和最终 prompt；当前项目把 prompt_version/source 显式放入 payload，便于比较不同版本提示词效果。
```

因此，Phase 3 的 `prompt_payload` 可以理解为：

```text
保留参考项目的 question/schema/semantic 主干，
暂时移除 retry feedback，
并把原本散落在 prompt 文本里的任务、SQL 约束、输出契约和调试信息结构化。
```

## 7. prompt_payload 字段说明与设计原因

这一节是 Phase 3 的重点。

### 7.1 task

建议结构：

```python
"task": {
    "type": "nl2sql",
    "goal": "Generate a read-only SQL query for the user question.",
}
```

含义：

```text
告诉模型当前任务类型和总体目标。
```

为什么需要：

```text
1. 把“你要做什么”从自然语言问题里分离出来。
2. 后续同一套 workflow 可能支持 explain、validate、repair 等任务类型。
3. 任务目标单独成字段后，prompt builder 可以稳定放在开头。
```

为什么现在只保留 `type` 和 `goal`：

```text
Phase 3 不做多任务编排，不需要复杂 task config。
```

### 7.2 question

建议结构：

```python
"question": {
    "raw": "  统计员工数量  ",
    "normalized": "统计员工数量",
}
```

含义：

```text
保存用户原始问题和规整后的问题。
```

为什么需要：

```text
1. raw 保留用户原话，便于调试和未来追问。
2. normalized 是后续 prompt、schema retrieval、QueryPlan 的稳定输入。
3. 两者分开后，normalize_question_node 的产物可以被明确检查。
```

为什么不直接只放一个字符串：

```text
NL2SQL 后续会遇到改写、补全、歧义消解。
只放一个 question 会丢掉“用户原话”和“系统规整结果”的差异。
```

### 7.3 schema_context

建议结构：

```python
"schema_context": {
    "dialect": "sqlite",
    "tables": [
        {
            "name": "employee",
            "description": "mock employee table",
            "columns": [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "description": "employee id",
                },
                {
                    "name": "name",
                    "type": "TEXT",
                    "description": "employee name",
                },
            ],
        }
    ],
    "relationships": [],
}
```

含义：

```text
描述模型允许使用的数据库结构。
```

范围约定：

```text
Phase 3 中，schema_context.tables 就是模型允许使用的表范围。
模型不应使用未出现在 tables 中的表。
```

为什么需要：

```text
1. NL2SQL 不能让模型凭字段名猜数据库。
2. schema 是 SQL 生成的主要约束。
3. 后续 schema grounding 的结果可以直接填入这里。
4. dialect 单独保留，可以影响 SQL 方言、LIMIT、函数等生成规则。
```

为什么现在用 mock schema：

```text
Phase 3 只验证 prompt 结构和 final_prompt 效果。
真实 schema 读取和 grounding 后续再接。
```

为什么不把 schema 做成一大段字符串：

```text
结构化 tables/columns/relationships 更容易测试，也方便后续按表、字段、关系分别替换成真实数据。
```

### 7.4 semantic_context

建议结构：

```python
"semantic_context": {
    "business_terms": [
        {
            "name": "员工",
            "description": "mock business term for employee",
        }
    ],
    "rules": [
        "Use only active records when such flag is available."
    ],
    "assumptions": [
        "No extra business filter is applied in Phase 3 mock prompt."
    ],
}
```

含义：

```text
描述业务语义、规则、默认假设。
```

与 `sql_policy` 的边界：

```text
semantic_context.rules 放业务规则。
例如：有效客户指 status = 'ACTIVE'。

sql_policy 放 SQL 生成安全与格式规则。
例如：只能 SELECT、不允许 SELECT *、必须 LIMIT。
```

为什么需要：

```text
1. 用户问题通常不是数据库语言，而是业务语言。
2. 业务术语和 SQL schema 不是一回事。
3. 后续 semantic.yml、业务词典、指标定义都可以进入这里。
4. assumptions 可以让最终回答说明哪些规则是系统默认加的。
```

为什么 Phase 3 不做真实语义加载：

```text
现在目标是 prompt payload 结构，不是语义召回质量。
```

### 7.5 sql_policy

建议结构：

```python
"sql_policy": {
    "readonly_only": True,
    "allow_select_star": False,
    "require_limit": True,
    "default_limit": 100,
}
```

含义：

```text
描述模型生成 SQL 时必须遵守的安全与格式约束。
```

为什么需要：

```text
1. SQL 安全不是后置 check 才需要，生成阶段也应该被约束。
2. readonly、select star、limit 这类规则应该明确进入 prompt。
3. 后续真实 SQL check service 可以复用同一组 policy 概念。
```

为什么现在只放少量字段：

```text
Phase 3 不做完整 SQL policy 系统。
先放最影响 SQL 形状的规则，避免配置模型提前膨胀。
```

### 7.6 output_contract

建议结构：

```python
"output_contract": {
    "format": "sql_only",
    "requirements": [
        "Return only one SQL statement.",
        "Do not include markdown fences.",
        "Do not explain the SQL.",
    ],
}
```

含义：

```text
告诉模型输出应该长什么样。
```

为什么需要：

```text
1. LLM 输出不稳定，必须尽早约束格式。
2. check_sql_node 后续需要拿到干净 SQL，而不是混杂解释文本。
3. format 和 requirements 分开，方便未来支持 json、sql_with_reasoning 等格式。
```

为什么现在选择 `sql_only`：

```text
Phase 3 仍然不接真实 LLM。
但未来第一版 LLM 生成 SQL 时，最容易处理的是纯 SQL 输出。
```

### 7.7 debug

建议结构：

```python
"debug": {
    "prompt_version": "phase3.mock.v1",
    "source": "mock_prompt_payload_builder",
}
```

含义：

```text
记录 prompt payload 的版本和来源。
```

为什么需要：

```text
1. 用户现在重点关注最终提示词效果，必须能知道这是哪一版 prompt。
2. 后续 prompt 迭代时，版本信息能帮助对比效果。
3. source 能区分 mock、config、schema grounding、QueryPlan 等不同来源。
```

为什么 debug 不进入业务字段：

```text
debug 是观察信息，不是模型必须理解的业务语义。
Phase 3 默认不把 debug 渲染进 final_prompt。
debug 只保留在 prompt_payload 中，供 metadata、stream 和日志观察使用。
```

## 8. final_prompt 渲染规则

Phase 3 推荐由 `prompt_builder.py` 统一把 `prompt_payload` 渲染成 `final_prompt`。

渲染顺序建议固定：

```text
1. Task
2. User Question
3. Schema Context
4. Semantic Context
5. SQL Policy
6. Output Contract
```

原因：

```text
1. 先告诉模型任务，再给问题。
2. 再给 schema 和语义材料。
3. 最后给 SQL 约束和输出格式。
4. 顺序稳定后，测试可以断言关键段落存在并按顺序出现。
```

渲染范围：

```text
final_prompt 默认只渲染：
  Task
  User Question
  Schema Context
  Semantic Context
  SQL Policy
  Output Contract

不渲染：
  debug
```

原因：

```text
debug.prompt_version 和 debug.source 是给人和系统观察用的。
它们不是模型完成 NL2SQL 任务所必需的上下文。
```

示例 final_prompt：

```text
You are an NL2SQL assistant.

Task:
Generate a read-only SQL query for the user question.

User Question:
统计员工数量

Schema Context:
- Table: employee
  Description: mock employee table
  Columns:
  - id (INTEGER): employee id
  - name (TEXT): employee name

Semantic Context:
- Term 员工: mock business term for employee
- Rule: Use only active records when such flag is available.
- Assumption: No extra business filter is applied in Phase 3 mock prompt.

SQL Policy:
- Readonly only: true
- SELECT * allowed: false
- LIMIT required: true
- Default LIMIT: 100

Output Contract:
- Return only one SQL statement.
- Do not include markdown fences.
- Do not explain the SQL.
```

## 8.1 prompt builder 函数边界

Phase 3 的 prompt payload builder 和 prompt builder 应尽量保持纯函数。

建议边界：

```python
def build_mock_prompt_payload(...) -> dict[str, object]:
    ...


def render_final_prompt(prompt_payload: dict[str, object]) -> str:
    ...
```

约束：

```text
1. 不依赖 graph state 对象内部结构，只接收明确参数。
2. 不依赖 logger。
3. 不读取外部配置。
4. 不调用外部客户端。
5. 不做真实 schema/semantic/policy 加载。
```

原因：

```text
Phase 3 的重点是 prompt 结构和 final_prompt 效果。
纯函数更容易单测，也更容易在后续迁移到 services/ 时保持行为稳定。
```

## 9. Workflow 调整

Phase 3 不改变 Phase 2 的 graph 形状。

仍然是：

```text
normalize_question
  -> build_prompt
  -> generate_sql
  -> check_sql
  -> execute_sql
  -> response
```

只改 `build_prompt_node` 内部：

```text
Phase 2:
  在 node 里直接拼 mock prompt_payload 和 final_prompt。

Phase 3:
  node 调用 prompt_payload builder / prompt_builder。
  生成结构化 prompt_payload。
  再渲染 final_prompt。
```

`generate_sql_node` 仍然 mock：

```text
return {"generated_sql": "SELECT 1 AS value"}
```

这个 mock 输出要和 `output_contract.format = "sql_only"` 保持一致：

```text
1. 只返回一条 SQL。
2. 不包含 markdown fences。
3. 不包含解释文本。
```

这样可以确保 Phase 3 的变化集中在 prompt 构建边界，不影响流程控制。

## 10. 是否新增 services

Phase 3 仍然建议不新增 `services/`。

原因：

```text
1. 仍然没有真实 schema grounding。
2. 仍然没有真实 semantic catalog。
3. 仍然没有真实 sql policy config。
4. 当前 payload builder 主要服务于 workflow prompt inspection。
```

如果现在新增 `services/nl2sql/prompt_payload_builder.py`，会让它看起来像长期业务能力，但里面仍然是 mock 数据。

更合适的做法：

```text
Phase 3:
  workflows/nl2sql/prompt_payload.py
  workflows/nl2sql/prompt_builder.py

后续真实上下文接入后:
  再迁移或抽取到 services/nl2sql/
```

## 11. 测试重点

Phase 3 测试应该证明：

```text
1. prompt_payload 字段结构稳定。
2. 每个字段都有预期内容。
3. final_prompt 按固定顺序渲染。
4. output metadata 仍能看到 prompt_payload / final_prompt。
5. stream updates 仍能看到 build_prompt 返回结构化 payload。
6. Phase 2 原有成功、澄清、失败路径不回退。
```

建议测试：

```text
test_prompt_payload.py
  build_mock_prompt_payload 返回 task/question/schema_context/semantic_context/sql_policy/output_contract/debug。
  question.raw 和 question.normalized 正确。
  schema_context 包含 dialect/tables/columns/relationships。
  sql_policy 包含 readonly_only/allow_select_star/require_limit/default_limit。

test_prompt_builder.py
  render_final_prompt 包含 Task/User Question/Schema Context/Semantic Context/SQL Policy/Output Contract。
  关键段落顺序稳定。
  不输出 markdown fences。
  不把 debug 渲染进 final_prompt。

test_nodes.py
  build_prompt_node 使用结构化 payload。
  build_prompt_node 返回 final_prompt。
  build_prompt_node 返回的 final_prompt 与 output_contract.format = "sql_only" 保持一致。

test_nl2sql_workflow.py
  workflow run output metadata 包含结构化 prompt_payload。
  workflow stream updates 能看到 build_prompt.prompt_payload。
  mock generated_sql 不包含 markdown fences 和解释文本。
```

不测试：

```text
真实 SQL 生成质量。
真实 schema 准确率。
真实业务规则召回。
真实配置加载。
```

## 12. 与后续阶段的关系

Phase 3 完成后，后续可以有两条路线：

### 路线 A：继续完善 prompt

```text
Phase 4:
  接入 prompt template 文件。
  引入更像真实业务的 mock schema / semantic examples。
  仍然不接 LLM。
```

优点：

```text
继续打磨最终提示词效果。
适合用户主要想看 prompt。
```

### 路线 B：开始接 LLM runtime

```text
Phase 4:
  新增 integrations/llm。
  generate_sql_node 调用真实 chain。
  check/execute 仍然 mock。
```

优点：

```text
可以开始看模型对当前 final_prompt 的真实反应。
```

我更推荐路线 A 或一个很小的 A+B 折中：

```text
先让 prompt template 文件化，再接 LLM。
```

因为 prompt 还在快速变化时，直接接 LLM 会把调试面扩大。

## 13. 完成标准

Phase 3 完成时，应满足：

```text
1. prompt_payload 从简单 mock 字典升级为结构化 payload。
2. 文档中定义的 task/question/schema_context/semantic_context/sql_policy/output_contract/debug 都有稳定含义。
3. build_prompt_node 不再直接手写全部 prompt 内容，而是通过 builder 生成 payload 和 final_prompt。
4. final_prompt 段落顺序稳定。
5. final_prompt 默认不渲染 debug。
6. output metadata 能看到结构化 prompt_payload 和 final_prompt。
7. stream updates 能看到 build_prompt 返回的 prompt_payload 和 final_prompt。
8. schema_context.tables 被明确视为允许使用的表范围。
9. semantic_context.rules 和 sql_policy 的边界清晰。
10. prompt builder 保持纯函数边界。
11. 不接真实 LLM。
12. 不接真实数据库。
13. 不新增 retry。
14. 不新增 CLI ask。
15. Phase 2 原有测试继续通过。
```

一句话总结：

```text
Phase 3 要交付的是“更接近真实 NL2SQL 的提示词输入结构”，不是“真实 SQL 生成能力”。
```
