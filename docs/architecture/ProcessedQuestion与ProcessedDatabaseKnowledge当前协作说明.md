# ProcessedQuestion 与 ProcessedDatabaseKnowledge 当前协作说明

> 本文说明当前代码中 `ProcessedQuestion + ProcessedDatabaseKnowledge` 如何协作，以及为什么要这样设计。
>
> 这不是长期完整方案，也不是自动生产这两个对象的设计。
>
> 当前重点是验证：
>
> ```text
> 人工设计好的 ProcessedQuestion
>   + 人工设计好的 ProcessedDatabaseKnowledge
>   -> 当前 pipeline
>   -> final_prompt
>   -> 后续 LLM 是否能生成符合预期的 SQL
> ```

## 1. 当前代码入口

当前协作发生在：

```text
src/nl2sqlagent/workflows/nl2sql/nodes.py
```

核心入口是 `build_prompt_node()`。

当前流程是：

```text
raw_question / normalized_question
  -> build_initial_processed_question()
  -> build_sample_processed_database_knowledge()
  -> build_knowledge_retrieval_result()
  -> build_schema_linking_result()
  -> build_sql_generation_context()
  -> build_prompt_payload_from_sql_generation_context()
  -> render_final_prompt()
```

对应代码层面的数据流是：

```text
ProcessedQuestion
  + ProcessedDatabaseKnowledge
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> PromptPayload
  -> FinalPrompt
```

当前 `generate_sql_node()` 仍然是 mock：

```text
SELECT 1 AS value
```

所以本文讨论的是：

```text
final_prompt 是怎么来的。
```

不是：

```text
最终 SQL 是怎么生成的。
```

## 2. 两个输入对象分别负责什么

### 2.1 ProcessedQuestion

`ProcessedQuestion` 表示“本次用户问题已经被处理后的结构化表达”。

它是请求级对象。

当前样例由 `build_initial_processed_question()` 直接手写生成：

```python
{
    "raw": "按部门统计在职员工人数",
    "text": "按部门统计在职员工人数",
    "keywords": ["部门", "在职", "员工", "人数"],
    "business_terms": ["在职员工"],
    "metric_hints": ["employee_count"],
    "dimension_hints": ["department"],
    "filter_hints": ["active_employee"],
    "time_hints": [],
    "assumptions": [],
}
```

当前它回答的是：

```text
用户问题里有哪些词。
用户问题里有哪些业务表达。
可能涉及什么指标。
可能涉及什么维度。
可能涉及什么过滤意图。
```

它不回答：

```text
具体使用哪张表。
具体使用哪个字段。
表怎么 join。
SQL 怎么写。
```

当前实现特别要注意：

```text
build_initial_processed_question() 是临时 fixture-like builder。
它不是正式的问题理解模块。
它现在只是为了让我们可以手工验证中间层对象到 final_prompt 的链路。
```

### 2.2 ProcessedDatabaseKnowledge

`ProcessedDatabaseKnowledge` 表示“数据库被治理后的知识层”。

它是知识级对象。

当前样例由 `build_sample_processed_database_knowledge()` 直接手写生成。

它包含：

```text
dialect
tables
columns
relationships
value_bindings
business_terms
```

当前样例中，主要知识包括：

```text
tables:
  hr_emp_base
  hr_dept_dim
  finance_salary_month
  sys_user_log
  tmp_import_record(enabled=false)

columns:
  hr_emp_base.emp_id
  hr_emp_base.dept_id
  hr_emp_base.emp_stat_cd
  hr_dept_dim.dept_id
  hr_dept_dim.dept_nm

relationship:
  hr_emp_base.dept_id = hr_dept_dim.dept_id

value_binding:
  在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
```

它回答的是：

```text
有哪些表。
有哪些字段。
字段有什么语义标签。
哪些表之间有已确认关系。
哪些业务词可以绑定到具体字段和值。
哪些知识启用。
哪些知识可信。
```

它不回答：

```text
本次问题一定要选哪些表。
本次问题最终要给 LLM 哪些字段。
```

当前实现同样要注意：

```text
build_sample_processed_database_knowledge() 是临时 sample builder。
它不是正式知识加载器。
```

## 3. 为什么要拆成两个对象

拆成 `ProcessedQuestion` 和 `ProcessedDatabaseKnowledge` 的原因是：它们承载的是两类不同的不确定性。

`ProcessedQuestion` 面向本次问题：

```text
这次用户到底想问什么？
有哪些业务词？
有什么指标、维度、过滤、时间意图？
```

`ProcessedDatabaseKnowledge` 面向长期知识：

```text
数据库里有什么？
哪些表字段是什么意思？
哪些关系可信？
哪些业务词能映射成字段值条件？
```

如果不拆开，就容易变成：

```text
用户问题、表结构、业务规则、候选结果、最终选择混在一个 dict 里。
```

这样后续会很难判断：

```text
SQL 生成错了，是问题理解错了？
是数据库知识不够？
是候选召回错了？
是 schema linking 错了？
还是 prompt 表达错了？
```

当前拆分的核心目的不是追求抽象漂亮，而是为了让后续验证时能定位问题。

## 4. 当前协作的第一步：KnowledgeRetrievalResult

`build_knowledge_retrieval_result()` 输入：

```text
ProcessedQuestion
ProcessedDatabaseKnowledge
```

输出：

```text
KnowledgeRetrievalResult
```

它做的是候选召回。

### 4.1 当前 matcher 用哪些问题侧字段

当前 `_normalized_terms()` 会从下面字段收集词：

```text
keywords
business_terms
metric_hints
dimension_hints
filter_hints
time_hints
```

对于样例问题，会得到类似：

```text
部门
在职
员工
人数
在职员工
employee_count
department
active_employee
```

### 4.2 当前 matcher 匹配哪些知识

当前 structured matcher 会匹配三类知识：

```text
table
column
value_binding
```

表匹配看：

```text
table.name
table.business_name
table.description
table.aliases
```

字段匹配看：

```text
column.name
column.business_name
column.description
column.aliases
column.semantic_tags
```

值绑定匹配看：

```text
value_binding.business_term
value_binding.description
```

### 4.3 当前候选的意义

`KnowledgeRetrievalResult` 只说明：

```text
这些知识可能相关。
```

它不说明：

```text
这些知识一定进入 final_prompt。
```

这是当前设计最重要的边界之一。

原因是后续可能会出现：

```text
structured candidate
vector candidate
rule candidate
llm rerank candidate
```

这些都只能先成为候选。

候选必须经过 `SchemaLinkingResult` 才能进入 SQL 生成上下文。

### 4.4 当前样例会召回什么

对于“按部门统计在职员工人数”，当前会召回类似：

```text
table:hr_emp_base
table:hr_dept_dim
column:hr_emp_base.emp_id
column:hr_emp_base.dept_id
column:hr_emp_base.emp_stat_cd
column:hr_dept_dim.dept_id
column:hr_dept_dim.dept_nm
value:active_employee
```

同时：

```text
enabled=false 的 tmp_import_record 不会产出候选。
```

## 5. 当前协作的第二步：SchemaLinkingResult

`build_schema_linking_result()` 输入：

```text
ProcessedQuestion
ProcessedDatabaseKnowledge
KnowledgeRetrievalResult
```

输出：

```text
SchemaLinkingResult
```

它做的是最终选择。

也就是说：

```text
KnowledgeRetrievalResult:
  可能相关。

SchemaLinkingResult:
  本次 SQL 生成最终采用哪些表、字段、关系和值绑定。
```

### 5.1 表如何进入 selected_tables

当前表可以通过几种方式进入：

```text
1. table candidate 被提升。
2. column candidate 命中后，父表被提升。
3. value_binding candidate 命中后，绑定字段所在表被提升。
4. metric_hints / dimension_hints 对应的样例规则补充表。
```

当前有一个重要限制：

```text
table candidate 必须 retrieval_method=structured 且 score >= 0.5 才能直接提升。
```

这保证了伪 vector candidate 不能直接绕过 schema linking。

### 5.2 字段如何进入 relevant_columns

当前字段可以通过几种方式进入：

```text
1. column candidate 被提升。
2. value_binding candidate 命中后，绑定字段作为 filter 字段进入。
3. metric_hints=employee_count 时，hr_emp_base.emp_id 作为 measure 字段进入。
4. dimension_hints=department 时，hr_dept_dim.dept_nm 作为 dimension 字段进入。
5. relationship 被选中后，两端 join key 字段进入。
```

当前已经修复过一个重要问题：

```text
没有 candidates，也没有 metric_hints / dimension_hints 时，
不会无条件塞入 HR 样例表字段。
```

### 5.3 value_binding 如何协作

当前 value binding 是高价值知识。

样例中：

```text
在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
```

它会推动：

```text
hr_emp_base 进入 selected_tables
hr_emp_base.emp_stat_cd 进入 relevant_columns，role=filter
value binding 进入 SchemaLinkingResult.value_bindings
```

这样后续 prompt 里可以明确告诉 LLM：

```text
用户说“在职员工”时，SQL 条件应使用 hr_emp_base.emp_stat_cd = ACTIVE。
```

### 5.4 relationship 如何协作

当前 relationship 不从候选里直接来，而是从 `ProcessedDatabaseKnowledge.relationships` 中补全。

规则是：

```text
如果 selected_tables 中同时存在 relationship 两端表，
并且 relationship.verified=true，
则进入 selected_relationships。
```

样例中：

```text
hr_emp_base
hr_dept_dim
```

同时被选中，所以补入：

```text
hr_emp_base.dept_id = hr_dept_dim.dept_id
```

并且两端字段会作为 join_key 进入 relevant_columns：

```text
hr_emp_base.dept_id
hr_dept_dim.dept_id
```

### 5.5 dropped_candidates 的意义

没有被采用的候选会进入：

```text
SchemaLinkingResult.dropped_candidates
```

它只用于 artifact 和调试。

它不进入：

```text
SqlGenerationContext
PromptPayload
FinalPrompt
```

这是为了避免：

```text
LLM 看到无关表后产生误用。
```

## 6. 当前协作的第三步：SqlGenerationContext

`build_sql_generation_context()` 输入：

```text
ProcessedQuestion
ProcessedDatabaseKnowledge
SchemaLinkingResult
```

输出：

```text
SqlGenerationContext
```

它是最终给 SQL 生成模型的干净上下文。

当前结构是：

```text
question
schema_context
semantic_context
sql_policy
output_contract
```

### 6.1 question

来自 `ProcessedQuestion`：

```text
raw
text
assumptions
```

### 6.2 schema_context

来自 `ProcessedDatabaseKnowledge` 和 `SchemaLinkingResult`：

```text
dialect:
  来自 ProcessedDatabaseKnowledge.dialect

tables:
  来自 SchemaLinkingResult.selected_tables

columns:
  来自 SchemaLinkingResult.relevant_columns

relationships:
  来自 SchemaLinkingResult.selected_relationships

value_bindings:
  来自 SchemaLinkingResult.value_bindings
```

注意：

```text
value_bindings 放在 schema_context 下。
```

原因是它已经绑定到具体表、字段、操作符和值：

```text
在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
```

它直接影响 SQL 的 `WHERE` 条件。

### 6.3 semantic_context

当前主要来自 `ProcessedQuestion.business_terms`：

```text
在职员工
```

当前还没有真正的：

```text
metric_definitions
semantic_rules
```

这也是后续人工样例验证时需要观察的点：

```text
如果 LLM 不知道 employee_count 应该怎么聚合，
可能需要在 semantic_context 中补 metric definition。
```

### 6.4 sql_policy

当前固定为：

```text
readonly_only=true
allow_select_star=false
require_limit=true
default_limit=100
```

它用于约束后续 SQL 生成。

### 6.5 output_contract

当前固定为：

```text
Return only one SQL statement.
Do not include markdown fences.
Do not explain the SQL.
```

它用于约束模型只返回 SQL。

## 7. 当前协作的第四步：PromptPayload 与 FinalPrompt

`build_prompt_payload_from_sql_generation_context()` 输入：

```text
SqlGenerationContext
```

输出：

```text
PromptPayload
```

然后 `render_final_prompt()` 把 `PromptPayload` 渲染为文本。

### 7.1 columns 如何进入 prompt

`SqlGenerationContext.schema_context.columns` 是平铺列表。

当前 prompt payload 会把它按 table 分组：

```text
hr_emp_base:
  emp_stat_cd
  emp_id
  dept_id

hr_dept_dim:
  dept_nm
  dept_id
```

并按字段角色排序：

```text
filter
measure
dimension
time
join_key
identifier
display
```

这样做是为了让 LLM 先看到更直接影响 SQL 语义的字段：

```text
过滤字段
度量字段
维度字段
join 字段
```

### 7.2 哪些内容不会进入 final_prompt

当前明确不会进入 final_prompt：

```text
KnowledgeRetrievalResult 全量候选
dropped_candidates
retrieval_method
vector_score
chunk_id
raw_ref
debug.prompt_version
```

这些内容应该留在 artifact / metadata 中调试。

原因是：

```text
LLM 生成 SQL 时应该看到干净上下文，
不应该被未采用候选或召回细节干扰。
```

## 8. 根据当前算法生成的 final_prompt

以当前样例问题：

```text
按部门统计在职员工人数
```

当前算法生成的 final_prompt 是：

```text
You are an NL2SQL assistant.

Task:
Generate a read-only SQL query for the user question.

User Question:
按部门统计在职员工人数

Schema Context:
Dialect: sqlite
Allowed tables:
- Table: hr_emp_base
  Description: promoted from table candidate
  Columns:
  - emp_stat_cd (filter): required by value binding
  - emp_id (measure): metric hint employee_count
  - dept_id (join_key): join key from selected relationship
- Table: hr_dept_dim
  Description: promoted from table candidate
  Columns:
  - dept_nm (dimension): dimension hint department
  - dept_id (join_key): join key from selected relationship
Relationships:
- hr_emp_base.dept_id = hr_dept_dim.dept_id
Value Bindings:
- 在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE

Semantic Context:
- Term 在职员工: 

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

这个 prompt 当前已经能告诉 LLM：

```text
1. 用户问题是什么。
2. 只能使用哪些表。
3. 每张表有哪些相关字段。
4. 哪个字段用于过滤。
5. 哪个字段用于度量。
6. 哪个字段用于分组维度。
7. 两张表怎么 join。
8. “在职员工”如何变成 SQL 条件。
9. SQL 输出格式有什么约束。
```

## 9. 为什么当前设计适合下一步验证 LLM SQL

当前设计的价值在于，它把问题拆成了可观察的几层：

```text
ProcessedQuestion:
  我们手工表达用户问题意图。

ProcessedDatabaseKnowledge:
  我们手工表达数据库知识。

KnowledgeRetrievalResult:
  系统先找可能相关的知识。

SchemaLinkingResult:
  系统决定最终使用哪些表字段关系和值绑定。

SqlGenerationContext:
  系统清洗成 SQL LLM 应该看到的上下文。

FinalPrompt:
  人能直接检查最终提示词是否合理。
```

这样下一阶段接 LLM 后，如果 SQL 生成不好，可以反推：

```text
ProcessedQuestion 设计是否缺字段？
ProcessedDatabaseKnowledge 是否缺注释、别名、value binding？
SchemaLinkingResult 是否选错表字段？
SqlGenerationContext 是否丢了必要信息？
FinalPrompt 是否表达不清楚？
```

这比直接把原始问题和一堆 schema 丢给 LLM 更可控。

## 10. 当前设计不解决什么

当前设计不解决：

```text
RawUserQuestion 如何自动变成 ProcessedQuestion。
RawDatabaseSchema 如何自动变成 ProcessedDatabaseKnowledge。
真实数据库如何读取。
真实 SQL 如何执行。
真实向量召回如何做。
历史 SQL 模板如何消费。
SQL 生成失败如何 retry / repair。
```

这些都重要，但不是当前要先解决的问题。

当前最重要的问题是：

```text
如果这两个中间层对象由人工设计好，
它们能不能支撑 LLM 生成正确 SQL？
```

只有这个验证成立后，再讨论：

```text
这两个对象如何自动生产。
```

才更稳。

## 11. 当前实现的限制

当前实现仍然很初版。

需要明确限制：

```text
1. ProcessedQuestion 是固定样例，不是真正解析用户问题。
2. ProcessedDatabaseKnowledge 是固定样例，不是真正知识库。
3. structured matcher 只是简单字符串匹配。
4. schema linking 里仍有样例规则，例如 employee_count -> hr_emp_base.emp_id。
5. semantic_context 还没有 metric definition。
6. generate_sql_node 仍然是 mock。
7. check_sql_node / execute_sql_node 仍然是 mock。
```

这些限制不阻塞下一步。

因为下一步要验证的是：

```text
人工中间层样例 + 当前 prompt 结构 -> LLM SQL 输出效果。
```

不是验证完整自动化 NL2SQL。

## 12. 下一步建议

下一步建议围绕这条链路做最小验证：

```text
人工 ProcessedQuestion
人工 ProcessedDatabaseKnowledge
当前 knowledge pipeline
当前 final_prompt
LLM generated_sql
artifact 观察
```

建议先准备 2-3 组人工样例：

```text
1. 按部门统计在职员工人数。
2. 统计最近 30 天每个客户的有效订单金额。
3. 单表按状态或时间过滤聚合。
```

每组样例都应记录：

```text
ProcessedQuestion
ProcessedDatabaseKnowledge
期望 final_prompt 重点
LLM generated_sql
人工判断 SQL 是否符合预期
```

这样可以直接回答：

```text
当前中间层对象字段设计是否够用？
当前 prompt 是否足够清楚？
后续是否需要补 metric_definitions、字段描述、表角色、value binding 表达方式？
```
