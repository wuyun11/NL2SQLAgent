# ProcessedQuestion 与 KnowledgeLayer 协作模式讨论

> 本文是讨论稿，用来回答一个关键问题：
>
> ```text
> ProcessedQuestion 和 KnowledgeLayer 到底应该如何协作？
> ```
>
> 这个问题会直接影响字段设计、模块边界、是否引入向量、以及最终 prompt 的可解释性。

## 1. 背景

当前项目已经把一个重要边界先拆出来：

```text
Raw User Question
  -> ProcessedQuestion

Raw Database Schema
  -> ProcessedDatabaseKnowledge / KnowledgeLayer

ProcessedQuestion + KnowledgeLayer
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> FinalPrompt
```

现在真正需要讨论的是中间这一段：

```text
ProcessedQuestion + KnowledgeLayer
  -> ?
  -> SchemaLinkingResult
```

这不是一个简单的“要不要加向量”的问题。

因为一旦加入向量，系统设计会发生变化：

```text
KnowledgeLayer 不再只是结构化表字段集合。
它还要能生成可检索文本、索引文档、chunk、embedding。

ProcessedQuestion 不再只是关键词和业务 hint。
它还要考虑 search query、query variants、召回意图。

SchemaLinkingResult 也不能只记录结构化匹配原因。
它还要记录 vector hit、chunk_id、score、召回来源和过滤原因。
```

所以这里不能用“先 MVP，后面再说向量”来糊过去。

更好的方式是：

```text
先把协作模式分清楚。
字段设计为可扩展的候选召回链路预留位置。
初版实现可以不用向量。
但结构上不能把向量堵死，也不能让向量结果直接污染 final_prompt。
```

## 2. 推荐总链路

建议把协作链路固定为：

```text
ProcessedQuestion
  + KnowledgeLayer
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> FinalPrompt
```

其中：

```text
KnowledgeRetrievalResult:
  候选召回结果。
  可以来自结构化匹配、向量检索、规则、LLM rerank 等。

SchemaLinkingResult:
  本次问题最终选中的表字段关系，以及证据、丢弃项、warning。

SqlGenerationContext:
  最终给 SQL LLM 的干净上下文。
```

一个关键原则：

```text
任何召回方式都只能产出候选。
候选不能直接进入 final_prompt。
```

也就是说：

```text
vector hits
  -> KnowledgeCandidate
  -> Schema Linking / Filtering
  -> SqlGenerationContext
```

而不是：

```text
vector hits
  -> FinalPrompt
```

## 3. 协作方式一：纯结构化匹配

### 3.1 数据流

```text
ProcessedQuestion.keywords / business_terms / hints
  -> 匹配 KnowledgeLayer 中的 name / aliases / description / semantic_tags / value_bindings
  -> KnowledgeCandidate
  -> SchemaLinkingResult
```

示例：

```text
ProcessedQuestion:
  keywords: ["部门", "在职", "员工", "人数"]
  business_terms: ["在职员工"]
  metric_hints: ["employee_count"]
  dimension_hints: ["department"]

KnowledgeLayer:
  hr_emp_base aliases: ["员工", "人员"]
  hr_dept_dim aliases: ["部门", "组织"]
  value_binding: 在职员工 -> hr_emp_base.emp_stat_cd = 'ACTIVE'
```

匹配结果：

```text
hr_emp_base:
  命中 员工 / 在职员工

hr_dept_dim:
  命中 部门

hr_emp_base.emp_stat_cd:
  命中 在职员工 value binding
```

### 3.2 优点

```text
1. 可解释性强。
2. 容易写单元测试。
3. 不依赖向量库、embedding 模型、召回参数。
4. 输出稳定，适合作为当前知识层消费初版。
5. 对没有外键、没有注释的数据库，只要人工维护 KnowledgeLayer，就能跑通。
```

### 3.3 缺点

```text
1. 依赖 KnowledgeLayer 的别名、描述、业务词维护质量。
2. 用户表达和知识层表达差异很大时，召回能力有限。
3. 同义词、长问题、隐含意图处理较弱。
4. 如果 ProcessedQuestion 质量差，结构化匹配会明显受影响。
```

### 3.4 适用阶段

```text
适合当前初版。
```

因为当前项目的核心目标是：

```text
跑通 ProcessedQuestion + KnowledgeLayer -> FinalPrompt。
能看到最终 prompt 长什么样。
能解释为什么选这些表字段。
```

此时最重要的是边界清楚，而不是召回能力最强。

## 4. 协作方式二：结构化匹配为主，向量召回补充

### 4.1 数据流

```text
ProcessedQuestion
  -> structured matcher
  -> structured candidates

ProcessedQuestion
  -> vector retriever
  -> vector candidates

structured candidates + vector candidates
  -> candidate merge / rerank / filter
  -> SchemaLinkingResult
```

这里向量不是主裁判，而是补充候选来源。

### 4.2 优点

```text
1. 结构化匹配保证稳定性和可解释性。
2. 向量召回补充同义表达、长描述、隐含业务语义。
3. 能兼容未来更复杂的 KnowledgeLayer。
4. 不会把所有不确定性都押注给最终 SQL LLM。
```

### 4.3 缺点

```text
1. 需要设计 KnowledgeLayer 如何生成 searchable_text / documents / chunks。
2. 需要记录 vector_score、chunk_id、retrieval_method 等调试信息。
3. 需要处理向量召回噪声。
4. 需要定义结构化分数和向量分数如何合并。
5. 工程复杂度明显高于纯结构化匹配。
```

### 4.4 适用阶段

```text
适合作为目标架构。
不建议作为当前第一版直接实现。
```

当前可以先在字段上预留：

```text
KnowledgeCandidate.retrieval_method
KnowledgeCandidate.match_source
KnowledgeCandidate.score
KnowledgeCandidate.evidence_text
KnowledgeCandidate.raw_ref
```

但初版 `retrieval_method` 可以只有：

```text
structured
```

后续再增加：

```text
vector
llm_rerank
manual_hint
```

## 5. 协作方式三：向量召回主导

### 5.1 数据流

```text
ProcessedQuestion
  -> embedding
  -> vector search over schema docs / business docs / examples
  -> top-k chunks
  -> prompt or schema context
```

### 5.2 优点

```text
1. 看起来实现快。
2. 对自然语言表达的相似性更敏感。
3. 可以复用 DDL、注释、文档、历史 SQL、问答样例。
```

### 5.3 缺点

```text
1. 召回结果不等于可用 schema。
2. top-k chunk 可能包含无关表、相似但错误的字段。
3. join 关系、value binding、字段角色不一定能从 chunk 中稳定恢复。
4. 分数难解释，调试困难。
5. 容易把噪声塞进 final_prompt。
6. 数据库没有注释、字段名很差时，向量也不一定能救回来。
```

### 5.4 风险判断

不建议把这种方式作为当前项目主线。

原因是它会让系统重新变成：

```text
用户问题 + 召回文本
  -> SQL LLM 自己猜
```

这和当前项目想避免的问题是一样的：

```text
把不确定性押注给一个 LLM。
```

向量可以用于召回候选，但不应该绕过 schema linking。

## 6. 协作方式四：LLM 参与候选解释或重排

### 6.1 数据流

```text
ProcessedQuestion
  + KnowledgeCandidate[]
  -> LLM rerank / explain / classify
  -> reranked candidates
  -> SchemaLinkingResult
```

### 6.2 优点

```text
1. 可以处理更复杂的语义判断。
2. 可以解释为什么某些候选相关。
3. 对用户问题表达不规范时有帮助。
```

### 6.3 缺点

```text
1. 成本更高。
2. 输出稳定性更差。
3. 需要约束输出格式。
4. 仍然需要结构化校验，不能直接相信。
5. 如果候选池本身很差，LLM rerank 也会被误导。
```

### 6.4 适用阶段

```text
可以作为后续增强。
不适合作为当前知识层消费初版。
```

如果以后加入，也应该限制在：

```text
候选重排
候选解释
冲突判断
缺失信息提示
```

而不是让它直接生成最终 schema context。

## 7. 推荐路线

推荐采用：

```text
目标架构：结构化匹配为主，向量候选可插拔补充。
初版实现：纯结构化匹配。
```

也就是：

```text
现在先实现方式一。
字段设计兼容方式二。
避免方式三成为主线。
方式四以后再考虑。
```

这能同时满足两个目标：

```text
1. 当前复杂度可控。
2. 后续加入向量时不需要推翻数据契约。
```

## 8. 对字段设计的影响

### 8.1 ProcessedQuestion

建议不要把 ProcessedQuestion 设计成只服务关键词匹配。

它至少要能表达：

```text
text:
  处理后的问题文本。

keywords:
  可用于精确匹配的词。

business_terms:
  业务术语，例如“在职员工”“有效订单”。

metric_hints:
  指标暗示，例如 employee_count、order_amount。

dimension_hints:
  维度暗示，例如 department、customer、month。

filter_hints:
  过滤暗示，例如 active_employee、paid_order。

time_hints:
  时间暗示，例如 current_month、last_30_days。

assumptions:
  问题处理层形成的假设。
```

如果未来支持向量，可以再加：

```text
search_queries:
  为检索生成的查询表达。

query_variants:
  用户问题的同义改写。
```

但这两个不建议初版就加入。

### 8.2 KnowledgeLayer

KnowledgeLayer 不应该只存物理表字段。

它要同时支持：

```text
结构化匹配
可解释输出
未来可检索文档生成
```

建议保留：

```text
id:
  稳定知识对象 ID。

name:
  物理名称。

business_name:
  业务名称。

description:
  业务描述。

aliases:
  别名。

semantic_tags:
  metric / dimension / filter / time / join_key 等标签。

source:
  database / manual / llm_candidate / history_sql。

verified:
  是否人工确认或可信。

enabled:
  是否允许进入 NL2SQL。
```

如果未来支持向量，可以再加：

```text
searchable_text:
  由结构化字段拼出的检索文本。

document_refs:
  指向可检索文档或 chunk 的引用。
```

注意：

```text
searchable_text / document_refs 是索引辅助信息。
不是最终 prompt 的主数据源。
```

### 8.3 KnowledgeCandidate

建议引入一个独立候选对象。

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

字段含义：

```text
kind:
  table / column / relationship / value_binding / business_term / metric。

knowledge_id:
  指向 KnowledgeLayer 中的稳定对象。

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
  存放实现细节引用，例如 chunk_id、document_id、vector_score。
```

有了这个对象后，向量是否加入就不会改变主链路。

区别只是：

```text
纯结构化阶段：
  KnowledgeCandidate.retrieval_method = "structured"

向量增强阶段：
  KnowledgeCandidate.retrieval_method = "vector"
  raw_ref.chunk_id = "..."
  raw_ref.vector_score = 0.82
```

### 8.4 SchemaLinkingResult

SchemaLinkingResult 应该接收候选，但输出选中结果。

它要记录：

```text
selected_tables
relevant_columns
selected_relationships
value_bindings
evidence
dropped_candidates
warnings
```

其中：

```text
evidence / dropped_candidates / warnings
```

进入 artifact。

而：

```text
selected_tables / relevant_columns / selected_relationships / value_bindings
```

转换为 SqlGenerationContext。

### 8.5 SqlGenerationContext

SqlGenerationContext 不应该知道向量、chunk、召回算法。

它只关心：

```text
本次 SQL 生成允许使用哪些表？
哪些字段是指标、维度、过滤、时间、join key？
表之间如何关联？
业务词如何变成 SQL 条件？
有哪些 SQL policy 和 output contract？
```

这能保证：

```text
召回算法可以变化。
最终 prompt 形态保持稳定。
```

SqlGenerationContext 内部归属建议固定为：

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

其中 `value_bindings` 放在 `schema_context` 下。

原因是它通常已经绑定到具体表、字段、操作符和值：

```text
在职员工 -> hr_emp_base.emp_stat_cd = 'ACTIVE'
```

它直接影响 SQL 的 `WHERE` 条件，和表字段使用强相关。

而更抽象的业务术语、指标口径、语义规则，放在 `semantic_context` 下。

这条口径应作为长期设计约束，避免后续出现：

```text
value_bindings 有时在 schema_context。
value_bindings 有时在 semantic_context。
value_bindings 有时又被写进 sql_policy。
```

## 9. Candidate 到 SchemaLinkingResult 的初版决策规则

`KnowledgeRetrievalResult` 只回答：

```text
可能相关的知识有哪些？
```

`SchemaLinkingResult` 才回答：

```text
本次问题最终选哪些表、字段、关系和值绑定？
为什么选？
为什么丢？
有什么不确定？
```

所以这里需要有一组明确、可测试的初版规则。

### 9.1 基本原则

候选可以有噪声，但最终选择必须可解释。

初版规则应保持简单：

```text
1. 不让任何 KnowledgeCandidate 直接进入 final_prompt。
2. 所有候选先归并、去重、过滤，再晋升为 selected_*。
3. enabled=false 的知识对象不能进入最终上下文。
4. verified=true / source=manual 的知识优先级更高。
5. LLM / vector 召回的候选必须经过结构化知识校验。
```

### 9.2 表晋升规则

表可以通过三类方式进入 `selected_tables`：

```text
1. table candidate 直接命中。
2. column candidate 命中后，所属 table 被提升。
3. value_binding candidate 命中后，绑定字段所属 table 被提升。
```

示例：

```text
命中 hr_emp_base.emp_stat_cd，因为用户问题有“在职员工”
=> hr_emp_base 至少进入 selected_tables
=> hr_emp_base.emp_stat_cd 进入 relevant_columns
=> 在职员工 value_binding 进入 value_bindings
```

建议初版表角色：

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

### 9.3 字段晋升规则

字段可以通过以下方式进入 `relevant_columns`：

```text
1. column candidate 直接命中。
2. value_binding 命中后，绑定字段自动进入。
3. relationship 被选中后，join key 字段自动进入。
4. 表被选中后，必要 display / identifier 字段可以按规则补充。
```

字段角色不应只靠召回来源决定，而应结合：

```text
ProcessedQuestion hints
KnowledgeLayer semantic_tags
value_binding
relationship
字段数据类型
```

建议初版字段角色：

```text
measure:
  指标计算字段，例如 count id、amount。

dimension:
  分组或展示维度，例如 department name、customer name。

filter:
  过滤字段，例如 status、date range。

time:
  时间字段。

join_key:
  join 关系字段。

identifier:
  主键、业务 ID。

display:
  辅助展示字段。
```

### 9.4 Value Binding 优先规则

`value_binding` 是高价值候选，因为它把业务词变成了 SQL 条件。

如果命中：

```text
在职员工 -> hr_emp_base.emp_stat_cd = 'ACTIVE'
```

则应同时推动：

```text
1. hr_emp_base 进入 selected_tables。
2. hr_emp_base.emp_stat_cd 进入 relevant_columns，role=filter。
3. value_binding 进入 SchemaLinkingResult.value_bindings。
4. value_binding 进入 SqlGenerationContext.schema_context.value_bindings。
```

如果存在多个同名业务词绑定，优先级建议：

```text
verified=true
source=manual
match_source=business_term / value
score 更高
```

无法消歧时，不要硬选，应进入 warnings。

### 9.5 Relationship 补全规则

当最终选中两张或更多表时，必须尝试补全关系。

初版规则：

```text
1. 从 KnowledgeLayer.relationships 中查 selected_tables 之间的 verified relationship。
2. 找到后加入 selected_relationships。
3. relationship 两端 join key columns 自动加入 relevant_columns。
4. 如果没有 verified relationship，不让 SQL LLM 自己猜 join。
5. 缺 join 时记录 warning，并保留 artifact 证据。
```

示例 warning：

```text
missing_verified_relationship:
  selected tables hr_emp_base and hr_dept_dim have no verified relationship.
```

后续可以支持多跳 join path，但初版不建议做复杂图搜索。

### 9.6 候选冲突与优先级

候选冲突时，不要只看分数。

建议初版排序优先级：

```text
1. enabled=true。
2. verified=true。
3. source=manual。
4. value_binding 命中优先于普通 description 命中。
5. exact alias / business_term 命中优先于模糊 description 命中。
6. structured / rule 命中优先于单独 vector 命中。
7. score 只作为同优先级内的排序因素。
```

这条规则的目的不是否定向量，而是避免：

```text
vector_score 高
=> 直接压过人工确认的业务规则
```

### 9.7 上下文预算裁剪规则

如果候选太多，裁剪顺序也要稳定。

建议保留优先级：

```text
1. value_bindings 相关字段。
2. selected_relationships 的 join key 字段。
3. primary table 的 measure / filter 字段。
4. dimension / time 字段。
5. join_support table 的必要 display 字段。
6. 低分、未验证、仅向量召回的候选。
```

被裁剪的候选进入 `dropped_candidates`，原因使用：

```text
budget_exceeded
```

### 9.8 dropped_candidates 原因

`dropped_candidates` 不应该只有名字和分数。

建议初版 reason 枚举：

```text
score_too_low:
  分数低于阈值。

disabled_knowledge:
  知识对象被禁用。

duplicate:
  被更高优先级候选覆盖。

covered_by_higher_confidence_candidate:
  被人工确认或更可信候选覆盖。

missing_required_table:
  字段所属表没有进入最终上下文。

missing_verified_relationship:
  缺少可信 join 关系。

budget_exceeded:
  超过上下文预算。

unresolved_conflict:
  多个候选冲突且无法自动消歧。
```

这些原因主要进入 artifact，不进入 final_prompt。

### 9.9 warnings 规则

warnings 用来表达“系统没有足够把握，但仍然需要继续产出 artifact”。

建议初版 warning 类型：

```text
missing_verified_relationship
ambiguous_table_candidates
ambiguous_value_binding
no_metric_column_found
no_dimension_column_found
only_unverified_candidates
context_budget_truncated
```

其中部分 warning 可以进入 final_prompt 的简短说明，但完整细节仍然只进入 artifact。

## 10. reason 与 evidence 的边界

当前文档已经区分了：

```text
SchemaLinkingResult:
  完整过程结果。

SqlGenerationContext:
  最终给 SQL LLM 的干净输入。
```

还需要进一步区分：

```text
reason:
  简短、面向 SQL LLM 或人类审阅的选择原因。

evidence:
  完整、面向 artifact 的召回和筛选证据。
```

建议进入 final_prompt 的内容：

```text
table role
column role
short reason
join relationship
value binding
必要 warning
```

只进入 artifact 的内容：

```text
retrieval_method
match_source
vector_score
chunk_id
raw_ref
candidate merge history
dropped_candidates
完整 evidence_text
LLM rerank 原始输出
```

这样可以保持：

```text
final_prompt 干净。
artifact 可复盘。
```

如果后续加入辅助 LLM，它的输出也应该按这个边界处理：

```text
LLM 产生的候选解释:
  进入 evidence。

被 Schema Linking 采纳后的简短原因:
  可以进入 reason。
```

## 11. 辅助 LLM 的位置

后续确实可以在这里加入一个辅助 LLM。

但它不是最终 SQL LLM，也不是最终裁决者。

它可以承担：

```text
candidate proposer:
  根据 ProcessedQuestion 和 KnowledgeLayer 摘要提出候选。

reranker:
  对已有 KnowledgeCandidate 排序。

explanation generator:
  为候选补充解释。

missing-context detector:
  判断是否缺少指标字段、时间字段或 join 关系。
```

它不应该承担：

```text
直接生成 SqlGenerationContext。
直接决定最终 selected_tables。
直接把候选内容写入 final_prompt。
绕过 SchemaLinkingResult。
```

也就是说，辅助 LLM 的输出仍然应该被收敛成：

```text
KnowledgeCandidate
reranked KnowledgeCandidate
SelectionEvidence
warnings
```

然后继续经过：

```text
SchemaLinkingResult
  -> SqlGenerationContext
  -> FinalPrompt
```

## 12. 开源项目佐证

### 12.1 Wren AI：语义层先于 SQL 生成

Wren AI 的 MDL 思路和这里的 KnowledgeLayer 很接近。

公开文档中，Wren Engine 用 Modeling Definition Language 描述业务数据，包括模型、关系、计算字段、视图等，让 AI agent 基于结构化业务上下文工作，而不是只面对 raw tables / columns。

参考：

```text
https://docs.getwren.ai/oss/engine/concept/what_is_mdl
https://docs.getwren.ai/oss/engine/guide/modeling/overview
```

对当前项目的启发：

```text
1. 原始 schema 不适合直接给 LLM。
2. 需要一个业务化、可维护、可复用的知识层。
3. 关系、指标、计算口径应该沉淀在知识层，而不是每次靠 LLM 猜。
```

### 12.2 Dataherald：Context Store 作为中间上下文层

Dataherald 文档中有 Context Store 模块，用来存储和检索数据库及业务逻辑上下文，Text-to-SQL 模块会使用这些上下文做 prompt engineering。

参考：

```text
https://dataherald.readthedocs.io/en/latest/context_store.html
https://dataherald.readthedocs.io/en/latest/text_to_sql_engine.html
```

对当前项目的启发：

```text
1. Text-to-SQL 不是只靠 DB schema。
2. 上下文存储和 SQL 生成应该分层。
3. few-shot、表字段信息、业务逻辑可以作为可检索上下文存在。
```

但当前项目不应该直接复制它的做法。

我们的重点是：

```text
候选召回和最终 SqlGenerationContext 要分开。
```

### 12.3 Vanna：RAG 可以有用，但要警惕“召回即上下文”

Vanna 的文档展示了用 DDL、documentation、question-SQL pair 训练 / 检索来辅助 SQL 生成的思路。

参考：

```text
https://vanna.ai/docs/vanna.html
https://vanna.ai/docs/sqlite-other-llm-other-vectordb.html
```

对当前项目的启发：

```text
1. DDL、业务文档、样例 SQL 都可以变成检索材料。
2. RAG 对 Text-to-SQL 有现实价值。
3. 向量库适合做候选召回。
```

但它也提醒我们：

```text
如果只把召回文本直接塞给 LLM，
系统会越来越依赖 prompt 和 LLM 自己判断。
```

所以当前项目应吸收 RAG 的候选召回能力，而不是把 RAG 当成最终上下文结构。

## 13. 对当前知识层消费初版的建议

当前知识层消费初版不建议马上实现真实向量库。

但建议在设计上明确增加：

```text
KnowledgeRetrievalResult
KnowledgeCandidate
```

推荐初版链路：

```text
ProcessedQuestion
  + ProcessedDatabaseKnowledge
  -> structured KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> PromptPayload
  -> FinalPrompt
```

初版测试应覆盖：

```text
1. 结构化关键词 / aliases / business_terms 命中候选。
2. value_binding 能把“在职员工”转成字段条件。
3. relationship 能补出 join key。
4. dropped_candidates 只进入 artifact，不进入 final_prompt。
5. SqlGenerationContext 不包含 vector/chunk/retrieval raw data。
```

可以额外设计一个“伪向量候选”测试，但不接真实向量库：

```text
手工构造 retrieval_method = "vector" 的 KnowledgeCandidate。
验证它只能作为候选进入 SchemaLinkingResult。
验证它不能绕过 linking 直接进入 SqlGenerationContext。
```

这样可以提前验证扩展点，而不引入真实向量复杂度。

## 14. 结论

ProcessedQuestion 和 KnowledgeLayer 的协作，不应该设计成：

```text
问题文本 + 数据库文本
  -> LLM 猜 SQL
```

也不应该设计成：

```text
向量 top-k
  -> 直接拼 prompt
```

更合理的结构是：

```text
ProcessedQuestion
  + KnowledgeLayer
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> FinalPrompt
```

当前最推荐的取舍是：

```text
1. 初版使用纯结构化匹配。
2. 数据契约预留向量候选扩展。
3. 向量未来只做候选召回，不做最终裁决。
4. 最终 prompt 只来自 SqlGenerationContext。
5. 完整候选、召回证据、丢弃原因进入 artifact。
```

一句话总结：

```text
向量可以提高召回，但不能替代知识层治理；
LLM 可以辅助判断，但不能吞掉数据契约；
最终 SQL LLM 看到的应该是被筛选后的上下文，而不是未经处理的不确定性。
```
