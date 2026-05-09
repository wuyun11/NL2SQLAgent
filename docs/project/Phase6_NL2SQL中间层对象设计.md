# Phase 6 NL2SQL 中间层对象设计

> 本文是 Phase 6 的核心设计稿。
>
> 前置文档：
>
> ```text
> docs/project/Phase6_NL2SQL不确定性与中间层策略.md
> ```
>
> 本文只设计中间层对象和它们之间的转换关系；不设计 raw user question 如何处理，也不设计 raw database schema 如何治理。

## 1. 核心结论

Phase 6 初版要先把下面四个对象设计清楚：

```text
ProcessedQuestion
ProcessedDatabaseKnowledge
SchemaLinkingResult
SqlGenerationContext
```

它们分别代表：

```text
ProcessedQuestion:
  用户问题被处理后的结构。

ProcessedDatabaseKnowledge:
  数据库被治理后的长期知识。

SchemaLinkingResult:
  本次问题和数据库知识匹配后的完整过程结果。

SqlGenerationContext:
  最终给 SQL LLM 的干净输入上下文。
```

这四个对象解决的是同一个问题：

```text
不要把用户问题和数据库结构中的所有不确定性，直接押注给最后一个 SQL LLM。
```

Phase 6 初版测试数据应直接从中间层开始：

```text
手写 ProcessedQuestion
手写 ProcessedDatabaseKnowledge
运行 schema linking / context building
得到 SchemaLinkingResult
得到 SqlGenerationContext
渲染 final_prompt
检查 prompt 是否符合预期
```

暂时不处理：

```text
RawUserQuestion -> ProcessedQuestion
RawDatabaseSchema -> ProcessedDatabaseKnowledge
SqlGenerationContext -> LLM -> SQL
```

这些外层以后再接。

## 2. 为什么先从中间层开始

现在真正需要验证的是：

```text
给定一个“处理后的问题”和一个“处理后的数据库知识”，
系统能不能稳定、可解释地构造出最终给 LLM 的上下文。
```

如果一开始就同时处理：

```text
用户问题理解
数据库自动提取
LLM 生成注释
向量召回
SQL 生成
```

调试会立刻变得很混乱。

因为一旦最终 prompt 不对，很难判断问题出在：

```text
用户问题没理解好？
数据库知识不完整？
表定位算法错？
字段筛选错？
关系补全错？
prompt builder 渲染错？
```

所以 Phase 6 初版先人为固定两端：

```text
ProcessedQuestion 是可信输入。
ProcessedDatabaseKnowledge 是可信输入。
```

然后只验证中间链路：

```text
ProcessedQuestion + ProcessedDatabaseKnowledge
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> final_prompt
```

这能把调试范围压缩到最关键的一段。

## 3. 总体数据流

完整长期链路是：

```text
Raw User Question
  -> Question Processing
  -> ProcessedQuestion

Raw Database Schema / Manual Metadata / LLM Candidate / History SQL
  -> Database Knowledge Processing
  -> ProcessedDatabaseKnowledge

ProcessedQuestion + ProcessedDatabaseKnowledge
  -> Schema Linking / Context Building
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> Prompt Payload
  -> Final Prompt
  -> SQL LLM
```

Phase 6 初版只覆盖中间部分：

```text
ProcessedQuestion + ProcessedDatabaseKnowledge
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> Prompt Payload
  -> Final Prompt
```

## 4. 四个对象的边界

### 4.1 ProcessedQuestion

`ProcessedQuestion` 是用户问题处理后的结果。

它不关心数据库里有哪些表，也不直接包含 SQL。

它回答：

```text
用户想问什么？
问题里有哪些关键词？
可能涉及哪些业务词、指标、维度、过滤条件？
有哪些已知假设？
```

建议初版结构：

```python
class ProcessedQuestion(TypedDict, total=False):
    raw: str
    text: str
    keywords: list[str]
    business_terms: list[str]
    metric_hints: list[str]
    dimension_hints: list[str]
    filter_hints: list[str]
    time_hints: list[str]
    assumptions: list[str]
```

字段说明：

```text
raw:
  用户原始问题。初版可以和 text 相同。

text:
  处理后的问题文本，是 schema linking 的主要输入。

keywords:
  用于表字段匹配的关键词。

business_terms:
  业务词，例如“在职员工”“有效订单”。

metric_hints:
  指标暗示，例如 employee_count、order_amount。

dimension_hints:
  维度暗示，例如 department、customer、month。

filter_hints:
  过滤暗示，例如 active_employee、paid_order。

time_hints:
  时间暗示，例如 last_30_days、current_month。

assumptions:
  问题处理层产生的假设。初版可以为空。
```

Phase 6 初版不实现自动问题理解。

测试中直接手写：

```json
{
  "raw": "按部门统计在职员工人数",
  "text": "按部门统计在职员工人数",
  "keywords": ["部门", "在职", "员工", "人数"],
  "business_terms": ["在职员工"],
  "metric_hints": ["employee_count"],
  "dimension_hints": ["department"],
  "filter_hints": ["active_employee"]
}
```

### 4.2 ProcessedDatabaseKnowledge

`ProcessedDatabaseKnowledge` 是数据库被治理后的长期知识。

它不是针对某一次问题的结果。

它回答：

```text
这个数据库里有哪些可用表？
这些表字段是什么意思？
哪些字段值代表什么业务含义？
哪些表之间可以关联？
哪些业务词可以映射到哪些表字段？
哪些知识是人工确认的，哪些只是候选？
```

建议初版结构：

```python
class ProcessedDatabaseKnowledge(TypedDict):
    dialect: str
    tables: list[KnowledgeTable]
    columns: list[KnowledgeColumn]
    relationships: list[KnowledgeRelationship]
    value_hints: list[KnowledgeValueHint]
    business_terms: list[KnowledgeBusinessTerm]
```

#### 4.2.1 KnowledgeTable

```python
class KnowledgeTable(TypedDict, total=False):
    name: str
    description: str
    aliases: list[str]
    table_type: str
    enabled: bool
    source: str
    verified: bool
```

字段说明：

```text
name:
  物理表名。

description:
  表的业务含义。

aliases:
  表的业务别名，用于匹配用户问题。

table_type:
  entity / fact / dimension / lookup / bridge / other。

enabled:
  是否允许进入 NL2SQL。

source:
  database / manual / llm_candidate / history_sql。

verified:
  是否已确认可信。
```

#### 4.2.2 KnowledgeColumn

```python
class KnowledgeColumn(TypedDict, total=False):
    table_name: str
    name: str
    data_type: str
    description: str
    aliases: list[str]
    semantic_tags: list[str]
    source: str
    verified: bool
```

字段说明：

```text
table_name:
  所属表名。

name:
  物理字段名。

data_type:
  字段类型。

description:
  字段业务含义。

aliases:
  字段别名。

semantic_tags:
  metric / dimension / filter / time / join_key / identifier 等。

source / verified:
  来源和确认状态。
```

#### 4.2.3 KnowledgeRelationship

```python
class KnowledgeRelationship(TypedDict, total=False):
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    relationship_type: str
    description: str
    source: str
    verified: bool
```

字段说明：

```text
relationship_type:
  many_to_one / one_to_many / one_to_one / many_to_many / unknown。

source:
  database / manual / llm_candidate / history_sql。

verified:
  是否确认可用于 join。
```

数据库没有外键时，关系可以来自人工维护或 LLM 候选，但进入正式 prompt 前最好是 verified。

#### 4.2.4 KnowledgeValueHint

```python
class KnowledgeValueHint(TypedDict, total=False):
    business_term: str
    table_name: str
    column_name: str
    operator: str
    value: object
    description: str
    source: str
    verified: bool
```

示例：

```json
{
  "business_term": "在职员工",
  "table_name": "hr_emp_base",
  "column_name": "emp_stat_cd",
  "operator": "=",
  "value": "ACTIVE",
  "description": "ACTIVE 表示当前在职状态",
  "source": "manual",
  "verified": true
}
```

#### 4.2.5 KnowledgeBusinessTerm

```python
class KnowledgeBusinessTerm(TypedDict, total=False):
    term: str
    description: str
    related_tables: list[str]
    related_columns: list[str]
    related_value_hints: list[str]
    source: str
    verified: bool
```

它用于把用户问题中的业务词映射到数据库知识。

### 4.3 SchemaLinkingResult

`SchemaLinkingResult` 是本次问题匹配过程的完整结果。

它不是长期知识，也不是最终给 LLM 的干净输入。

它回答：

```text
本次问题选中了哪些表？
哪些字段相关？
哪些关系被使用？
哪些业务值绑定被命中？
为什么选它们？
哪些候选被丢弃？
有哪些不确定或警告？
```

建议结构：

```python
class SchemaLinkingResult(TypedDict):
    selected_tables: list[SelectedTable]
    relevant_columns: list[RelevantColumn]
    selected_relationships: list[SelectedRelationship]
    value_bindings: list[SelectedValueBinding]
    evidence: list[SelectionEvidence]
    dropped_candidates: list[DroppedCandidate]
    warnings: list[str]
```

#### 4.3.1 SelectedTable

```python
class SelectedTable(TypedDict, total=False):
    table_name: str
    role: str
    score: float
    matched_terms: list[str]
    reason: str
```

`role` 建议初版支持：

```text
primary
join_support
lookup
filter_support
```

### 4.3.2 RelevantColumn

```python
class RelevantColumn(TypedDict, total=False):
    table_name: str
    column_name: str
    role: str
    score: float
    matched_terms: list[str]
    reason: str
```

`role` 建议初版支持：

```text
measure
dimension
filter
join_key
time
display
identifier
```

### 4.3.3 SelectedRelationship

```python
class SelectedRelationship(TypedDict, total=False):
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    reason: str
```

关系只记录本次问题需要的关系，不把所有关系都塞进结果。

### 4.3.4 SelectedValueBinding

```python
class SelectedValueBinding(TypedDict, total=False):
    business_term: str
    table_name: str
    column_name: str
    operator: str
    value: object
    reason: str
```

它说明业务词如何变成 SQL 过滤条件。

### 4.3.5 SelectionEvidence

```python
class SelectionEvidence(TypedDict, total=False):
    target_type: str
    target_name: str
    evidence_type: str
    matched_terms: list[str]
    source: str
    detail: str
```

`target_type` 可以是：

```text
table
column
relationship
value_binding
```

`evidence_type` 可以是：

```text
keyword_match
alias_match
description_match
business_term_match
relationship_expansion
manual_hint
```

### 4.3.6 DroppedCandidate

```python
class DroppedCandidate(TypedDict, total=False):
    target_type: str
    target_name: str
    reason: str
    score: float
```

`dropped_candidates` 主要用于 artifact，不建议进入最终 prompt。

### 4.4 SqlGenerationContext

`SqlGenerationContext` 是最终给 SQL LLM 的干净输入。

它从 `SchemaLinkingResult` 转换而来，但不等于 `SchemaLinkingResult`。

它回答：

```text
本次 SQL 生成到底允许使用哪些表？
哪些字段和问题有关？
表之间如何关联？
业务值绑定是什么？
SQL 生成必须遵守哪些规则？
```

建议结构：

```python
class SqlGenerationContext(TypedDict):
    question: SqlGenerationQuestion
    schema_context: SqlGenerationSchemaContext
    semantic_context: SqlGenerationSemanticContext
    sql_policy: SqlGenerationPolicy
    output_contract: SqlGenerationOutputContract
```

其中：

```python
class SqlGenerationQuestion(TypedDict, total=False):
    text: str
    assumptions: list[str]


class SqlGenerationSchemaContext(TypedDict):
    dialect: str
    tables: list[SqlGenerationTable]
    columns: list[SqlGenerationColumn]
    relationships: list[SqlGenerationRelationship]


class SqlGenerationSemanticContext(TypedDict):
    business_terms: list[str]
    value_bindings: list[SelectedValueBinding]
    rules: list[str]
    assumptions: list[str]
```

注意：

```text
SqlGenerationContext 不应该包含全部 evidence、dropped_candidates、debug details。
这些信息进 artifact，不进 final prompt。
```

## 5. SchemaLinkingResult 与 SqlGenerationContext 的区别

这两个对象必须分开。

`SchemaLinkingResult` 是完整匹配过程：

```text
候选
分数
证据
丢弃项
警告
来源
原因
```

主要用途：

```text
artifact
调试
评审
回归测试
```

`SqlGenerationContext` 是最终生成上下文：

```text
最终表
最终字段
最终关系
业务值绑定
SQL policy
输出契约
```

主要用途：

```text
prompt_payload
final_prompt
SQL LLM 输入
```

不能把它们混成一个对象。

否则会出现两个问题：

```text
1. final_prompt 里塞入太多调试噪声，干扰 SQL 生成。
2. artifact 里缺少完整证据，难以排查为什么选了这些表字段。
```

## 6. 初版测试数据策略

Phase 6 初版测试数据完全按照中间层来。

也就是说，测试不从：

```text
Raw User Question
Raw Database Schema
```

开始。

而是直接提供：

```text
ProcessedQuestion
ProcessedDatabaseKnowledge
```

测试目标是验证：

```text
SchemaLinkingResult 是否合理。
SqlGenerationContext 是否合理。
final_prompt 是否符合预期。
artifact 是否能看到中间结果。
```

## 7. 推荐初版测试场景

### 7.1 员工部门统计

ProcessedQuestion：

```json
{
  "raw": "按部门统计在职员工人数",
  "text": "按部门统计在职员工人数",
  "keywords": ["部门", "在职", "员工", "人数"],
  "business_terms": ["在职员工"],
  "metric_hints": ["employee_count"],
  "dimension_hints": ["department"],
  "filter_hints": ["active_employee"]
}
```

ProcessedDatabaseKnowledge：

```text
hr_emp_base:
  员工基础信息表
  aliases: 员工, 人员, 雇员
  columns:
    emp_id: 员工唯一标识
    dept_id: 所属部门 ID
    emp_stat_cd: 员工状态编码

hr_dept_dim:
  部门维表
  aliases: 部门, 组织
  columns:
    dept_id: 部门 ID
    dept_nm: 部门名称

relationship:
  hr_emp_base.dept_id = hr_dept_dim.dept_id

value_hint:
  在职员工 -> hr_emp_base.emp_stat_cd = 'ACTIVE'
```

期望 SchemaLinkingResult：

```text
selected_tables:
  hr_emp_base role=primary
  hr_dept_dim role=join_support

relevant_columns:
  hr_emp_base.emp_id role=measure
  hr_emp_base.dept_id role=join_key
  hr_emp_base.emp_stat_cd role=filter
  hr_dept_dim.dept_id role=join_key
  hr_dept_dim.dept_nm role=dimension

selected_relationships:
  hr_emp_base.dept_id = hr_dept_dim.dept_id

value_bindings:
  在职员工 -> hr_emp_base.emp_stat_cd = 'ACTIVE'
```

期望 final_prompt 包含：

```text
Processed Question:
按部门统计在职员工人数

Selected Tables:
hr_emp_base
hr_dept_dim

Relevant Columns:
hr_emp_base.emp_id
hr_emp_base.emp_stat_cd
hr_dept_dim.dept_nm

Relationships:
hr_emp_base.dept_id = hr_dept_dim.dept_id

Business Rules / Value Bindings:
在职员工: hr_emp_base.emp_stat_cd = 'ACTIVE'
```

### 7.2 订单金额统计

用于验证：

```text
事实表
金额字段
时间字段
客户维度
状态值绑定
```

示例问题：

```text
统计最近 30 天每个客户的有效订单金额
```

期望涉及：

```text
biz_order_main
crm_customer_profile
```

关键字段：

```text
order_id
customer_id
order_amount
order_status
order_time
customer_name
```

业务值绑定：

```text
有效订单 -> biz_order_main.order_status = 'PAID'
```

### 7.3 无关表被丢弃

用于验证：

```text
dropped_candidates
warnings
schema budget
```

例如数据库知识里有：

```text
sys_user_log
tmp_import_record
finance_salary_month
```

但员工部门统计问题不应该选它们。

这些信息应进入：

```text
SchemaLinkingResult.dropped_candidates
```

不进入：

```text
SqlGenerationContext
final_prompt
```

## 8. 初版算法边界

Phase 6 初版可以先不实现复杂算法。

如果后续进入实现，可以先使用简单可解释规则：

```text
1. keywords / business_terms 命中 table aliases / description。
2. keywords / hints 命中 column aliases / description / semantic_tags。
3. value_hints 命中后提升对应表和字段。
4. selected tables 之间存在 relationship 时补 join_key columns。
5. enabled=false 的表不进入候选。
6. 未选中但有一定匹配的对象进入 dropped_candidates。
```

暂不做：

```text
向量库
embedding
LLM rerank
复杂 query plan
多跳 join path 搜索
```

原因：

```text
现在要先验证对象边界和最终 prompt 形态。
算法可以后续替换。
```

## 9. Artifact 设计影响

Phase 6 后，artifact 应能看到更多中间层结果。

建议新增或扩展：

```text
processed_question.json
processed_database_knowledge_snapshot.json
schema_linking_result.json
sql_generation_context.json
```

也可以先只写入现有 `prompt_payload.json` 的扩展字段。

但从调试角度看，最好至少能单独看到：

```text
SchemaLinkingResult
SqlGenerationContext
```

原因：

```text
SchemaLinkingResult 用来看“为什么选这些表字段”。
SqlGenerationContext 用来看“最终给 LLM 的上下文是什么”。
```

## 10. Prompt Payload 升级方向

当前 prompt_payload 已经有：

```text
task
question
schema_context
semantic_context
sql_policy
output_contract
debug
```

Phase 6 后可以升级为：

```text
task
question
schema_context
semantic_context
sql_policy
output_contract
debug
```

字段名可以保持不变，但内容变得更真实：

```text
question:
  来自 ProcessedQuestion / SqlGenerationQuestion

schema_context:
  来自 SqlGenerationSchemaContext

semantic_context:
  来自 SqlGenerationSemanticContext

debug:
  可以记录 schema_linking_version、knowledge_snapshot_id 等。
```

不建议把 `SchemaLinkingResult` 全部塞进 prompt_payload。

更好的做法是：

```text
prompt_payload 保存 LLM 需要的干净上下文。
artifact 保存完整 linking 过程。
```

## 11. 现阶段不做的事情

Phase 6 中间层对象设计不做：

```text
1. 不设计原始问题如何自动变成 ProcessedQuestion。
2. 不设计真实数据库如何自动变成 ProcessedDatabaseKnowledge。
3. 不接真实 LLM。
4. 不接真实数据库。
5. 不接向量库。
6. 不做 retry。
7. 不做完整 QueryPlan。
8. 不引入重型 stage/service/protocol 架构。
```

这些不做不是因为不重要，而是因为：

```text
先把中间层对象和最终 prompt 调稳，后面外层接入才有明确目标。
```

## 12. 完成标准

Phase 6 设计通过时，应能回答：

```text
1. ProcessedQuestion 是什么，不是什么？
2. ProcessedDatabaseKnowledge 是什么，不是什么？
3. SchemaLinkingResult 是什么，不是什么？
4. SqlGenerationContext 是什么，不是什么？
5. 哪些信息进入 final_prompt？
6. 哪些信息只进入 artifact？
7. 初版测试数据如何直接从中间层开始？
8. 缺外键、缺注释的问题如何通过知识层表达？
9. 为什么暂时不处理 raw question 和 raw database？
10. 后续外层接入时应该对齐哪个对象？
```

一句话总结：

```text
Phase 6 初版先把“处理后的问题 × 处理后的数据库知识 -> 本次 SQL 生成上下文”设计清楚。
等这条链路稳定后，再处理 raw question 和 raw database 到中间层的转换。
```
