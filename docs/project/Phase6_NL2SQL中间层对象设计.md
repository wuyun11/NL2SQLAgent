# NL2SQL 知识层消费与中间层对象设计

> 本文是当前 NL2SQL 项目的核心设计稿。
>
> 文件名保留 `Phase6` 是为了沿用项目阶段文档命名；正文按长期架构口径描述，不把设计绑定到某个阶段编号。
>
> 前置讨论：
>
> ```text
> docs/project/Phase6_NL2SQL不确定性与中间层策略.md
> docs/architecture/ProcessedQuestion与KnowledgeLayer协作模式讨论.md
> docs/architecture/NL2SQL 后续知识层处理方案.md
> ```

## 1. 核心结论

当前项目要先把下面这条链路跑通：

```text
ProcessedQuestion
  + ProcessedDatabaseKnowledge
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> PromptPayload
  -> FinalPrompt
```

这里的重点不是接入真实 LLM，也不是接入真实数据库。

重点是回答：

```text
给定一个处理后的用户问题，
以及一个治理后的数据库知识层，
系统如何稳定、可解释地选出本次 SQL 生成需要的表、字段、关系和值绑定？
```

初版目标：

```text
1. 使用手写 ProcessedQuestion。
2. 使用手写 ProcessedDatabaseKnowledge。
3. 用 structured matcher 产出 KnowledgeRetrievalResult。
4. 用明确规则把候选转成 SchemaLinkingResult。
5. 用 SchemaLinkingResult 构造 SqlGenerationContext。
6. 让 final_prompt 来自 SqlGenerationContext。
7. 在 artifact 中看到 retrieval / linking / sql context。
```

暂不处理：

```text
RawUserQuestion -> ProcessedQuestion
RawDatabaseSchema -> ProcessedDatabaseKnowledge
真实向量库
真实辅助 LLM
真实 SQL LLM
真实数据库执行
复杂 QueryPlan
retry
```

这些不是不重要，而是当前必须先把中间链路的对象边界和 prompt 形态稳定下来。

## 2. 为什么要增加 KnowledgeRetrievalResult

原先只有：

```text
ProcessedQuestion + ProcessedDatabaseKnowledge
  -> SchemaLinkingResult
```

这个链路还不够清楚。

因为中间其实有两个不同问题：

```text
1. 可能相关的知识有哪些？
2. 最终应该选哪些表、字段、关系和值绑定？
```

所以需要增加：

```text
KnowledgeRetrievalResult
```

它只表达候选召回，不表达最终选择。

也就是说：

```text
KnowledgeRetrievalResult:
  可能相关。
  可以有噪声。
  可以包含 structured / vector / rule / llm_rerank 等不同来源。

SchemaLinkingResult:
  最终选择。
  需要可解释。
  需要记录 evidence、dropped_candidates、warnings。

SqlGenerationContext:
  给 SQL LLM 的干净输入。
  不包含完整召回细节。
```

这条边界非常重要：

```text
任何召回方式都只能产出 KnowledgeCandidate。
KnowledgeCandidate 不能直接进入 final_prompt。
```

后续即使引入向量或辅助 LLM，也只是在 `KnowledgeRetrievalResult` 这层增加候选来源，而不是改掉主链路。

## 3. 总体数据流

长期完整链路是：

```text
Raw User Question
  -> Question Processing
  -> ProcessedQuestion

Raw Database Schema / Manual Metadata
  -> Database Knowledge Processing
  -> ProcessedDatabaseKnowledge

ProcessedQuestion + ProcessedDatabaseKnowledge
  -> Knowledge Retrieval
  -> KnowledgeRetrievalResult
  -> Schema Linking
  -> SchemaLinkingResult
  -> SQL Context Builder
  -> SqlGenerationContext
  -> Prompt Payload
  -> Final Prompt
  -> SQL LLM
```

当前本地项目初版只覆盖：

```text
ProcessedQuestion + ProcessedDatabaseKnowledge
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> Prompt Payload
  -> Final Prompt
```

测试数据也从中间层开始：

```text
手写 ProcessedQuestion
手写 ProcessedDatabaseKnowledge
检查 retrieval / linking / context / prompt / artifact
```

注意：

```text
历史 SQL 消费可以作为独立路线后续讨论。
例如把高频历史 SQL 治理成模板，再由问题匹配和参数抽取来填充模板。
但这不是当前知识层消费初版的核心内容。
当前设计不依赖历史 SQL，也不把 SQL 模板纳入 ProcessedDatabaseKnowledge。
```

## 4. 对象总览

当前设计包含六个核心对象：

```text
ProcessedQuestion:
  用户问题被处理后的结构。

ProcessedDatabaseKnowledge:
  数据库被治理后的长期知识层。

KnowledgeCandidate:
  某个知识对象被召回为候选的记录。

KnowledgeRetrievalResult:
  本次问题的候选召回结果。

SchemaLinkingResult:
  本次问题最终选择表字段关系的完整过程结果。

SqlGenerationContext:
  最终给 SQL LLM 的干净上下文。
```

它们的关系是：

```text
ProcessedQuestion
  + ProcessedDatabaseKnowledge
  -> KnowledgeCandidate[]
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
```

## 5. ProcessedQuestion

`ProcessedQuestion` 是用户问题处理后的结果。

它不直接包含 SQL，也不直接指定物理表字段。

它回答：

```text
用户想问什么？
有哪些关键词？
有哪些业务词？
可能涉及哪些指标、维度、过滤、时间条件？
有哪些假设？
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
  用户原始问题。当前初版可以和 text 相同。

text:
  处理后的问题文本，是 matcher 的主要输入。

keywords:
  可用于表字段匹配的关键词。

business_terms:
  用户问题里的业务表达，偏自然语言或业务语言，例如“在职员工”“有效订单”。

metric_hints:
  指标暗示，例如 employee_count、order_amount。
  它只作为 retrieval / linking 线索，不代表已经完成指标口径解析。
  例如 employee_count 可以帮助寻找员工表和员工 ID，但当前不直接推导 COUNT(DISTINCT emp_id)。

dimension_hints:
  维度暗示，例如 department、customer、month。

filter_hints:
  过滤暗示，例如 active_employee、paid_order。
  它是问题处理层归一化后的过滤意图，和 business_terms 不完全等价。
  例如“在职员工”可以是 business_term，active_employee 可以是 filter_hint。

time_hints:
  时间暗示，例如 last_30_days、current_month。

assumptions:
  问题处理层形成的假设。当前初版可以为空。
```

当前不实现自动问题理解。

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

## 6. ProcessedDatabaseKnowledge

`ProcessedDatabaseKnowledge` 是数据库被治理后的长期知识层。

它不是原始 schema，也不是某次问题的结果。

它回答：

```text
有哪些可用表？
表字段是什么意思？
哪些表之间可以关联？
哪些字段值代表什么业务含义？
哪些业务词可以映射到表字段？
哪些知识可信，哪些只是候选？
```

建议初版结构：

```python
class ProcessedDatabaseKnowledge(TypedDict):
    dialect: str
    tables: list[KnowledgeTable]
    columns: list[KnowledgeColumn]
    relationships: list[KnowledgeRelationship]
    value_bindings: list[KnowledgeValueBinding]
    business_terms: list[KnowledgeBusinessTerm]
```

这里统一使用 `value_bindings`，不再使用 `value_hints` 作为主字段名。

### 6.1 KnowledgeTable

```python
class KnowledgeTable(TypedDict, total=False):
    id: str
    name: str
    business_name: str
    description: str
    aliases: list[str]
    table_type: str
    enabled: bool
    source: str
    verified: bool
```

字段说明：

```text
id:
  稳定知识对象 ID，例如 table:hr_emp_base。

name:
  物理表名。

business_name:
  业务名称。

description:
  表的业务含义。

aliases:
  表别名，用于结构化匹配。

table_type:
  entity / fact / dimension / lookup / bridge / other。

enabled:
  是否允许进入 NL2SQL。

source:
  database / manual。

verified:
  是否已确认可信。
```

### 6.2 KnowledgeColumn

```python
class KnowledgeColumn(TypedDict, total=False):
    id: str
    table_name: str
    name: str
    business_name: str
    data_type: str
    description: str
    aliases: list[str]
    semantic_tags: list[str]
    source: str
    verified: bool
```

字段说明：

```text
id:
  稳定知识对象 ID，例如 column:hr_emp_base.emp_stat_cd。

table_name:
  所属表名。

name:
  物理字段名。

business_name:
  业务名称。

data_type:
  字段类型。

description:
  字段业务含义。

aliases:
  字段别名。

semantic_tags:
  metric / dimension / filter / time / join_key / identifier / display 等。

source / verified:
  来源和确认状态。
```

### 6.3 KnowledgeRelationship

```python
class KnowledgeRelationship(TypedDict, total=False):
    id: str
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    relationship_type: str
    description: str
    source: str
    verified: bool
```

数据库没有外键时，关系应来自人工维护或后续独立治理流程。

但进入 `SqlGenerationContext` 前，初版只采用：

```text
verified=true
```

当前设计不从历史 SQL 或 SQL 模板中反推关系。
如果未来独立的治理流程引入历史 SQL 分析，也应先形成被确认的知识，再作为人工治理后的结果进入 `ProcessedDatabaseKnowledge`。

### 6.4 KnowledgeValueBinding

```python
class KnowledgeValueBinding(TypedDict, total=False):
    id: str
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
  "id": "value:active_employee",
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

`value_bindings` 是高价值知识，因为它把业务词直接映射成 SQL 条件。

### 6.5 KnowledgeBusinessTerm

```python
class KnowledgeBusinessTerm(TypedDict, total=False):
    id: str
    term: str
    description: str
    related_tables: list[str]
    related_columns: list[str]
    related_value_bindings: list[str]
    source: str
    verified: bool
```

它用于把问题里的业务词映射到数据库知识。

当前初版可以先定义这个类型，但不强制让 matcher 使用它。

第一版最小实现可以只让下面四类知识参与 structured matcher：

```text
tables
columns
relationships
value_bindings
```

原因是 `value_bindings.business_term` 已经足够覆盖最关键的业务词到字段值条件映射，例如：

```text
在职员工 -> hr_emp_base.emp_stat_cd = 'ACTIVE'
```

`KnowledgeBusinessTerm` 后续再用于更复杂的术语解释、同义词扩展、指标口径关联。

## 7. KnowledgeCandidate 与 KnowledgeRetrievalResult

### 7.1 KnowledgeCandidate

`KnowledgeCandidate` 是某个知识对象被召回为候选的记录。

它不是最终选择结果。

建议结构：

```python
class KnowledgeCandidate(TypedDict, total=False):
    kind: str
    knowledge_id: str
    score: float
    matched_terms: list[str]
    retrieval_method: str
    match_source: str
    evidence_text: str
    reason: str
    raw_ref: dict[str, object]
```

字段说明：

```text
kind:
  table / column / relationship / value_binding / business_term / metric。

knowledge_id:
  指向 ProcessedDatabaseKnowledge 中的稳定对象 ID。

score:
  候选分数，只用于排序和调试。

matched_terms:
  命中的问题侧词语。

retrieval_method:
  structured / vector / rule / llm_rerank / manual_hint。

match_source:
  name / alias / description / semantic_tag / value / document / example_sql。

evidence_text:
  解释为什么召回这个候选。

reason:
  面向 artifact 的简短原因。

raw_ref:
  实现细节引用，例如 chunk_id、document_id、vector_score。
```

当前初版只需要：

```text
retrieval_method = structured
```

但结构上要允许后续加入：

```text
retrieval_method = vector
retrieval_method = llm_rerank
```

### 7.2 KnowledgeRetrievalResult

`KnowledgeRetrievalResult` 是本次问题的候选召回结果。

建议结构：

```python
class KnowledgeRetrievalResult(TypedDict, total=False):
    candidates: list[KnowledgeCandidate]
    warnings: list[str]
    metadata: dict[str, object]
```

它主要进入 artifact，用来回答：

```text
本次有哪些候选？
候选来自哪里？
为什么被召回？
后续哪些被选中，哪些被丢弃？
```

它不直接进入 final_prompt。

## 8. Structured Matcher

当前初版只实现 structured matcher。

输入：

```text
ProcessedQuestion
ProcessedDatabaseKnowledge
```

输出：

```text
KnowledgeRetrievalResult
```

匹配规则保持简单、可解释：

```text
1. keywords / business_terms 命中 table name / business_name / aliases / description。
2. keywords / hints 命中 column name / business_name / aliases / description / semantic_tags。
3. business_terms / filter_hints 命中 value_bindings.business_term / description。
4. 命中 value_binding 时，同时产出 value_binding candidate。
5. enabled=false 的知识对象不产出候选。
```

structured matcher 只负责召回候选。

它不负责：

```text
最终选表
最终字段角色
join 关系补全
上下文预算裁剪
prompt_payload 构造
```

这些都属于后续的 schema linking / context building。

## 9. SchemaLinkingResult

`SchemaLinkingResult` 是本次问题匹配后的完整过程结果。

它回答：

```text
本次问题最终选中了哪些表？
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

### 9.1 SelectedTable

```python
class SelectedTable(TypedDict, total=False):
    table_name: str
    role: str
    score: float
    matched_terms: list[str]
    reason: str
```

表角色：

```text
primary:
  承载主要指标或事实的表。

join_support:
  为 primary 表补充维度、名称、分组字段的表。

filter_support:
  主要用于过滤条件的表。

lookup:
  编码、状态、类型解释类表。
```

### 9.2 RelevantColumn

```python
class RelevantColumn(TypedDict, total=False):
    table_name: str
    column_name: str
    role: str
    score: float
    matched_terms: list[str]
    reason: str
```

字段角色：

```text
measure
dimension
filter
time
join_key
identifier
display
```

### 9.3 SelectedRelationship

```python
class SelectedRelationship(TypedDict, total=False):
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    reason: str
```

只记录本次问题需要的关系。

### 9.4 SelectedValueBinding

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

### 9.5 SelectionEvidence

```python
class SelectionEvidence(TypedDict, total=False):
    target_type: str
    target_name: str
    evidence_type: str
    matched_terms: list[str]
    source: str
    detail: str
```

`evidence` 主要用于 artifact。

它可以记录：

```text
keyword_match
alias_match
description_match
semantic_tag_match
business_term_match
value_binding_match
relationship_expansion
manual_hint
```

### 9.6 DroppedCandidate

```python
class DroppedCandidate(TypedDict, total=False):
    target_type: str
    target_name: str
    reason: str
    score: float
```

建议 reason 枚举：

```text
score_too_low
disabled_knowledge
duplicate
covered_by_higher_confidence_candidate
missing_required_table
missing_verified_relationship
budget_exceeded
unresolved_conflict
```

`dropped_candidates` 只进入 artifact，不进入 final_prompt。

## 10. Candidate -> SchemaLinkingResult 规则

### 10.1 基本原则

```text
1. 不让任何 KnowledgeCandidate 直接进入 final_prompt。
2. 所有候选先归并、去重、过滤，再晋升为 selected_*。
3. enabled=false 的知识对象不能进入最终上下文。
4. verified=true / source=manual 的知识优先级更高。
5. vector / llm_rerank 候选必须经过结构化知识校验。
```

### 10.2 表晋升

表可以通过三类方式进入 `selected_tables`：

```text
1. table candidate 直接命中。
2. column candidate 命中后，所属 table 被提升。
3. value_binding candidate 命中后，绑定字段所属 table 被提升。
```

示例：

```text
命中 hr_emp_base.emp_stat_cd，因为用户问题有“在职员工”
=> hr_emp_base 进入 selected_tables
=> hr_emp_base.emp_stat_cd 进入 relevant_columns
=> 在职员工 value_binding 进入 value_bindings
```

### 10.3 字段晋升

字段可以通过以下方式进入 `relevant_columns`：

```text
1. column candidate 直接命中。
2. value_binding 命中后，绑定字段自动进入。
3. relationship 被选中后，join key 字段自动进入。
4. 表被选中后，必要 display / identifier 字段可按规则补充。
```

字段角色结合这些信息判断：

```text
ProcessedQuestion hints
KnowledgeColumn.semantic_tags
value_binding
relationship
字段数据类型
```

### 10.4 Value Binding 优先

`value_binding` 是高价值候选。

如果命中：

```text
在职员工 -> hr_emp_base.emp_stat_cd = 'ACTIVE'
```

则同时推动：

```text
1. hr_emp_base 进入 selected_tables。
2. hr_emp_base.emp_stat_cd 进入 relevant_columns，role=filter。
3. value_binding 进入 SchemaLinkingResult.value_bindings。
4. value_binding 后续进入 SqlGenerationContext.schema_context.value_bindings。
```

如果多个 value binding 冲突，优先级是：

```text
verified=true
source=manual
match_source=business_term / value
score 更高
```

无法消歧时记录 warning。

### 10.5 Relationship 补全

当最终选中两张或更多表时，必须尝试补全关系。

初版规则：

```text
1. 从 ProcessedDatabaseKnowledge.relationships 中查 selected_tables 之间的 verified relationship。
2. 找到后加入 selected_relationships。
3. relationship 两端 join key columns 自动加入 relevant_columns。
4. 没有 verified relationship 时，不让 SQL LLM 自己猜 join。
5. 缺 join 时记录 warning，并保留 artifact 证据。
```

后续可以支持多跳 join path，当前不做复杂图搜索。

### 10.6 候选冲突与裁剪

候选冲突时，不只看分数。

建议排序优先级：

```text
1. enabled=true。
2. verified=true。
3. source=manual。
4. value_binding 命中优先于普通 description 命中。
5. exact alias / business_term 命中优先于模糊 description 命中。
6. structured / rule 命中优先于单独 vector 命中。
7. score 只作为同优先级内的排序因素。
```

如果候选太多，保留优先级：

```text
1. value_bindings 相关字段。
2. selected_relationships 的 join key 字段。
3. primary table 的 measure / filter 字段。
4. dimension / time 字段。
5. join_support table 的必要 display 字段。
6. 低分、未验证、仅向量召回的候选。
```

被裁剪的候选进入 `dropped_candidates`，reason 为 `budget_exceeded`。

## 11. SqlGenerationContext

`SqlGenerationContext` 是最终给 SQL LLM 的干净输入。

它从 `SchemaLinkingResult` 转换而来，但不等于 `SchemaLinkingResult`。

建议结构：

```python
class SqlGenerationContext(TypedDict):
    question: SqlGenerationQuestion
    schema_context: SqlGenerationSchemaContext
    semantic_context: SqlGenerationSemanticContext
    sql_policy: SqlGenerationPolicy
    output_contract: SqlGenerationOutputContract
```

### 11.1 归属口径

`SqlGenerationContext` 内部归属固定为：

```text
schema_context:
  selected_tables
  relevant_columns
  selected_relationships
  value_bindings

semantic_context:
  business_terms
  metric_definitions
  semantic_rules
  assumptions

sql_policy:
  SQL 方言、只读约束、禁止事项、聚合规则等生成策略。
```

`value_bindings` 放在 `schema_context` 下。

原因是它通常已经绑定到具体表、字段、操作符和值：

```text
在职员工 -> hr_emp_base.emp_stat_cd = 'ACTIVE'
```

它直接影响 SQL 的 `WHERE` 条件，和表字段使用强相关。

而更抽象的业务术语、指标口径、语义规则，放在 `semantic_context` 下。

### 11.2 SqlGenerationSchemaContext

```python
class SqlGenerationSchemaContext(TypedDict):
    dialect: str
    tables: list[SqlGenerationTable]
    columns: list[SqlGenerationColumn]
    relationships: list[SqlGenerationRelationship]
    value_bindings: list[SelectedValueBinding]
```

### 11.3 SqlGenerationSemanticContext

```python
class SqlGenerationSemanticContext(TypedDict, total=False):
    business_terms: list[str]
    metric_definitions: list[dict[str, object]]
    semantic_rules: list[str]
    assumptions: list[str]
```

### 11.4 不允许进入 SqlGenerationContext 的内容

下面内容不进入 `SqlGenerationContext`：

```text
KnowledgeRetrievalResult 全量候选
retrieval_method
vector_score
chunk_id
raw_ref
完整 evidence_text
dropped_candidates
LLM rerank 原始输出
```

这些进入 artifact。

## 12. SchemaLinkingResult -> SqlGenerationContext

转换规则：

```text
1. ProcessedQuestion.text -> SqlGenerationContext.question.text。
2. ProcessedQuestion.assumptions -> question.assumptions / semantic_context.assumptions。
3. selected_tables -> schema_context.tables。
4. relevant_columns -> schema_context.columns。
5. selected_relationships -> schema_context.relationships。
6. value_bindings -> schema_context.value_bindings。
7. 必要 business_terms / metric_definitions -> semantic_context。
8. SQL 方言和安全规则 -> sql_policy。
9. 输出格式要求 -> output_contract。
```

保留到 prompt 的 reason 应该短：

```text
table role
column role
short reason
join relationship
value binding
必要 warning
```

完整 evidence 只进 artifact。

## 13. Prompt Payload 升级方向

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

后续字段名可以保持不变，但来源要收敛为：

```text
question:
  来自 SqlGenerationContext.question。

schema_context:
  来自 SqlGenerationContext.schema_context。

semantic_context:
  来自 SqlGenerationContext.semantic_context。

sql_policy:
  来自 SqlGenerationContext.sql_policy。

output_contract:
  来自 SqlGenerationContext.output_contract。

debug:
  只放轻量追踪信息，例如 schema_linking_version、knowledge_snapshot_id。
```

明确禁止：

```text
prompt_payload 直接从 KnowledgeRetrievalResult 拼装。
prompt_payload 直接包含 dropped_candidates。
prompt_payload 直接包含 vector_score / chunk_id / raw_ref。
```

也就是说：

```text
FinalPrompt 只来自 SqlGenerationContext。
```

## 14. Artifact 设计影响

当前知识层消费链路最终希望能看到：

```text
processed_question.json
processed_database_knowledge_snapshot.json
knowledge_retrieval_result.json
schema_linking_result.json
sql_generation_context.json
prompt_payload.json
final_prompt.txt
```

但初版实现不要求一次性拆出所有独立文件。

初版最低要求是：

```text
1. final_prompt.txt 能看到最终提示词。
2. prompt_payload.json 能看到最终结构化输入。
3. output.json 或 graph_updates.jsonl 能看到 processed_question、knowledge_retrieval_result、schema_linking_result、sql_generation_context。
```

如果 artifact writer 已经支持稳定写多个文件，可以直接拆出：

```text
knowledge_retrieval_result.json
schema_linking_result.json
sql_generation_context.json
```

否则先放进现有 artifact 结构中，后续再拆文件。

观察要求：

```text
KnowledgeRetrievalResult:
  看候选召回。

SchemaLinkingResult:
  看为什么选这些表字段、为什么丢弃候选。

SqlGenerationContext:
  看最终给 SQL LLM 的干净上下文。
```

artifact 边界：

```text
进入 artifact:
  candidates
  retrieval_method
  match_source
  vector_score
  chunk_id
  evidence_text
  dropped_candidates
  warnings
  sql_generation_context

进入 final_prompt:
  question
  selected tables
  relevant columns
  selected relationships
  schema_context.value_bindings
  semantic_context 中必要业务语义
  sql_policy
  output_contract
```

`dropped_candidates` 不进入 final_prompt。

## 15. 伪 vector candidate 扩展点

当前不接真实向量库。

但建议测试中手工构造一个：

```text
retrieval_method = vector
```

的 `KnowledgeCandidate`。

验证：

```text
1. 它只能作为候选进入 KnowledgeRetrievalResult。
2. 它不能绕过 SchemaLinkingResult。
3. 如果没有被 linking 规则采纳，它不能进入 SqlGenerationContext。
4. 它的 vector_score / chunk_id 只能进入 artifact。
5. 它不能直接出现在 final_prompt。
```

这能提前证明扩展点存在，但不引入真实向量复杂度。

## 16. 初版测试场景

### 16.1 员工部门统计

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

value_binding:
  在职员工 -> hr_emp_base.emp_stat_cd = 'ACTIVE'
```

期望：

```text
KnowledgeRetrievalResult:
  有 hr_emp_base / hr_dept_dim / emp_stat_cd / active_employee 候选。

SchemaLinkingResult:
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

SqlGenerationContext:
  schema_context.value_bindings 包含在职员工绑定。

FinalPrompt:
  包含选中的表、字段、关系和值绑定。
  不包含 dropped_candidates。
```

### 16.2 订单金额统计

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

业务值绑定：

```text
有效订单 -> biz_order_main.order_status = 'PAID'
```

### 16.3 无关表被丢弃

用于验证：

```text
dropped_candidates
artifact 边界
final_prompt 干净
```

例如知识层里有：

```text
sys_user_log
tmp_import_record
finance_salary_month
```

但员工部门统计问题不应该选它们。

它们可以进入：

```text
SchemaLinkingResult.dropped_candidates
```

但不能进入：

```text
SqlGenerationContext
FinalPrompt
```

### 16.4 伪 vector candidate

用于验证：

```text
vector candidate 不能绕过 SchemaLinkingResult。
```

构造一个未被 structured 规则采纳的 candidate：

```text
retrieval_method = vector
raw_ref.vector_score = 0.88
```

期望：

```text
它可以出现在 KnowledgeRetrievalResult。
它可以出现在 dropped_candidates。
它不能直接进入 SqlGenerationContext。
它不能出现在 FinalPrompt。
```

## 17. 落地任务拆分

建议执行顺序：

```text
Task 1:
  定义 KnowledgeLayer / ProcessedQuestion / KnowledgeCandidate 类型。

Task 2:
  定义 SchemaLinkingResult / SqlGenerationContext 类型。

Task 3:
  实现 structured matcher，产出 KnowledgeRetrievalResult。

Task 4:
  实现 Candidate -> SchemaLinkingResult 的初版规则。

Task 5:
  实现 SchemaLinkingResult -> SqlGenerationContext。

Task 6:
  修改 build_prompt_node / prompt_payload，使 final_prompt 来自 SqlGenerationContext。

Task 7:
  artifact 中记录 KnowledgeRetrievalResult / SchemaLinkingResult / SqlGenerationContext。
  初版可以先写入现有 artifact 文件；如果 writer 支持，再拆成独立 json。

Task 8:
  测试 dropped_candidates 不进入 final_prompt。

Task 9:
  测试伪 vector candidate 不能绕过 SchemaLinkingResult。
```

这些任务是执行计划的骨架。

真正写 `docs/superpowers/plans` 时，应再补充：

```text
具体文件路径
测试文件路径
每一步验收命令
每个任务的提交边界
```

## 18. 不做的事情

当前知识层消费初版不做：

```text
1. 不设计原始问题如何自动变成 ProcessedQuestion。
2. 不设计真实数据库如何自动变成 ProcessedDatabaseKnowledge。
3. 不接真实 LLM。
4. 不接真实数据库。
5. 不接真实向量库。
6. 不做 retry。
7. 不做完整 QueryPlan。
8. 不引入重型 stage/service/protocol 架构。
9. 不让辅助 LLM 直接决定最终 prompt。
```

## 19. 完成标准

这份设计被认为清楚时，应能回答：

```text
1. ProcessedQuestion 是什么，不是什么？
2. ProcessedDatabaseKnowledge 是什么，不是什么？
3. KnowledgeCandidate 是什么，不是什么？
4. KnowledgeRetrievalResult 和 SchemaLinkingResult 有什么区别？
5. SchemaLinkingResult 和 SqlGenerationContext 有什么区别？
6. value_bindings 为什么属于 schema_context？
7. 哪些信息进入 final_prompt？
8. 哪些信息只进入 artifact？
9. structured matcher 负责什么，不负责什么？
10. Candidate 如何晋升为 selected table / relevant column / value binding？
11. dropped_candidates 为什么不能进入 final_prompt？
12. 伪 vector candidate 为什么不能绕过 SchemaLinkingResult？
```

一句话总结：

```text
当前项目要先把“处理后的问题 × 治理后的数据库知识 -> 候选召回 -> 最终 SQL 生成上下文 -> final_prompt”这条链路稳定下来。
后续接入真实问题理解、真实数据库、向量或 LLM，都必须对齐这条链路，而不是绕过它。
```
