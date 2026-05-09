下面是一份可以直接放进项目里的 **Markdown 设计文档草稿**。我会刻意把范围分清楚：**当前本地项目只设计 KnowledgeLayer 的形态与消费方式，不处理真实数据库如何生成 KnowledgeLayer。**

# NL2SQL 后续知识层处理方案

## 1. 背景

当前 NL2SQL 项目的核心问题不是“如何调用最后的 SQL LLM”，而是：

```text
用户问题进来后，
系统凭什么知道应该把哪些表、字段、关系、业务规则传给 SQL LLM？
```

因此后续结构不应该直接设计成：

```text
用户问题 + 原始数据库结构
  -> SQL LLM
  -> SQL
```

而应该设计成：

```text
真实数据库
  -> DB Agent
  -> KnowledgeLayer

ProcessedQuestion
  + KnowledgeLayer
  -> Knowledge Retrieval / Schema Linking
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> FinalPrompt
  -> SQL LLM
```

这里要特别区分两件事：

```text
DB Agent：
  负责把真实数据库处理成 KnowledgeLayer。
  这是非常后面的事情。

当前本地项目：
  假设 KnowledgeLayer 已经存在。
  只设计如何消费 KnowledgeLayer，并把它转成 SQL LLM 需要的上下文。
```

Text-to-SQL 领域里，这种先做 schema linking / schema selection，再进入 SQL generation 的思路是常见路线。DIN-SQL 就把 Text-to-SQL 拆成 schema linking、query classification/decomposition、SQL generation、self-correction 等子任务，而不是让一个 LLM 一次性完成所有判断。([arXiv][1]) CHESS 也采用 entity/context retrieval、schema selection、query generation 的多阶段流程，并强调先检索相关上下文、选择有效 schema，再生成 SQL。([arXiv][2])

---

## 2. 总体结构

推荐后续整体结构如下：

```text
┌────────────────────┐
│ 真实数据库          │
│ Raw Database        │
└─────────┬──────────┘
          │
          │ 未来阶段，不属于当前本地项目
          ▼
┌────────────────────┐
│ DB Agent            │
│ 数据库知识处理 Agent │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ KnowledgeLayer      │
│ 处理后的知识层       │
└─────────┬──────────┘
          │
          │ 当前本地项目从这里开始消费
          ▼
┌────────────────────┐
│ ProcessedQuestion   │
│ 已处理后的用户问题   │
└─────────┬──────────┘
          │
          ▼
┌──────────────────────────────┐
│ Knowledge Retrieval           │
│ 从 KnowledgeLayer 中召回候选   │
└─────────┬────────────────────┘
          │
          ▼
┌──────────────────────────────┐
│ Schema Linking / Context Build│
│ 候选筛选、补关系、生成证据      │
└─────────┬────────────────────┘
          │
          ▼
┌────────────────────┐
│ SchemaLinkingResult │
│ 本次问题的选表结果   │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ SqlGenerationContext│
│ 给 SQL LLM 的标准输入│
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ FinalPrompt         │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ SQL LLM             │
└────────────────────┘
```

RAG 在这个结构里的位置不是“真实数据库直接向量化后拼 prompt”，而是：**从已经处理过的 KnowledgeLayer 中召回相关候选材料**。RAG 的基本思想是在推理时检索外部上下文增强生成；在 Text-to-SQL 场景中，这些上下文不只包括表结构，还可能包括字段描述、样例、领域术语等。([nilenso blog][3])

---

## 3. 各层职责

## 3.1 真实数据库

真实数据库是原始数据源，可能包含：

```text
表名
字段名
字段类型
索引
外键
已有注释
样例值
历史 SQL
```

但真实数据库本身通常不是一个适合直接给 LLM 的输入。真实数据库可能存在：

```text
没有外键
没有注释
字段名不表达业务含义
表名不表达业务含义
历史表 / 临时表 / 冗余表很多
字段值编码不透明
```

因此真实数据库后续需要被处理成 KnowledgeLayer。

当前本地项目暂时不处理这一步。

---

## 3.2 DB Agent

DB Agent 是未来阶段的组件。

它的目标不是“建立向量库”，而是：

```text
把真实数据库处理成 NL2SQL 可消费的 KnowledgeLayer。
```

它未来可能负责：

```text
读取真实数据库 schema
读取已有表字段注释
采样低基数字段值
发现或推断表关系
结合历史 SQL 统计常见 join
用 LLM 辅助生成表字段说明候选
输出结构化知识对象
生成可检索文档
建立向量索引 / 关键词索引
```

但这些都不是当前本地项目要做的事情。

当前项目只需要假设：

```text
KnowledgeLayer 已经存在。
```

---

## 3.3 KnowledgeLayer

KnowledgeLayer 是已经被处理过的数据库知识层。

它不是：

```text
原始数据库 schema
prompt 字符串
向量库本身
```

它应该是结构化知识对象的集合。

推荐包含：

```text
TableKnowledge
ColumnKnowledge
RelationshipKnowledge
ValueBindingKnowledge
BusinessTermKnowledge
MetricKnowledge
```

### 示例结构

```json
{
  "dialect": "sqlite",
  "tables": [
    {
      "id": "table:hr_emp_base",
      "name": "hr_emp_base",
      "business_name": "员工基础信息表",
      "description": "记录员工基础资料、所属部门、员工状态、入职离职时间。",
      "aliases": ["员工", "人员", "雇员"],
      "enabled": true,
      "source": "manual",
      "verified": true
    }
  ],
  "columns": [
    {
      "id": "column:hr_emp_base.emp_stat_cd",
      "table": "hr_emp_base",
      "name": "emp_stat_cd",
      "business_name": "员工状态",
      "description": "员工状态编码，ACTIVE 表示在职。",
      "aliases": ["员工状态", "在职状态", "是否在职"],
      "semantic_tags": ["filter", "employee_status"],
      "source": "manual",
      "verified": true
    }
  ],
  "relationships": [
    {
      "id": "rel:hr_emp_base.dept_id->hr_dept_dim.dept_id",
      "left_table": "hr_emp_base",
      "left_column": "dept_id",
      "right_table": "hr_dept_dim",
      "right_column": "dept_id",
      "description": "员工表通过 dept_id 关联部门维表。",
      "source": "manual",
      "verified": true
    }
  ],
  "value_bindings": [
    {
      "id": "value:active_employee",
      "business_term": "在职员工",
      "table": "hr_emp_base",
      "column": "emp_stat_cd",
      "operator": "=",
      "value": "ACTIVE",
      "description": "ACTIVE 表示当前在职员工。",
      "source": "manual",
      "verified": true
    }
  ]
}
```

KnowledgeLayer 的关键点是：

```text
它是可检索的。
它是可解释的。
它是可维护的。
它不是最终 prompt。
```

---

## 3.4 ProcessedQuestion

ProcessedQuestion 是已处理后的用户问题。

当前阶段可以不设计完整用户意图识别节点，而是直接把测试问题写得像“已处理后的问题”。

例如：

```json
{
  "text": "按部门统计在职员工人数",
  "keywords": ["部门", "在职", "员工", "人数"],
  "metric_hints": ["员工人数"],
  "dimension_hints": ["部门"],
  "filter_hints": ["在职"],
  "time_hints": []
}
```

ProcessedQuestion 的作用不是生成 SQL，而是作为检索 KnowledgeLayer 的输入。

它回答：

```text
这次问题要围绕哪些业务对象、指标、维度、过滤条件去找知识？
```

---

## 4. KnowledgeLayer 如何与 ProcessedQuestion 协作

这是后续真正的难点。

推荐拆成四步：

```text
ProcessedQuestion
  -> Knowledge Retrieval
  -> Schema Linking
  -> SchemaLinkingResult
  -> SqlGenerationContext
```

---

## 4.1 Knowledge Retrieval：从知识层召回候选

输入：

```text
ProcessedQuestion
KnowledgeLayer
```

输出：

```text
KnowledgeRetrievalResult
```

它负责从 KnowledgeLayer 中找出候选知识对象。

召回方式可以有多种：

```text
关键词匹配
别名匹配
描述匹配
语义标签匹配
向量检索
混合检索
规则匹配
```

当前本地项目可以先只设计接口，不绑定具体算法。

### 候选结构

```python
class KnowledgeCandidate(TypedDict):
    kind: Literal[
        "table",
        "column",
        "relationship",
        "value_binding",
        "business_term",
        "metric"
    ]
    knowledge_id: str
    score: float
    matched_terms: list[str]
    match_source: Literal[
        "name",
        "alias",
        "description",
        "semantic_tag",
        "value",
        "vector",
        "rule"
    ]
    reason: str
```

示例：

```json
{
  "kind": "column",
  "knowledge_id": "column:hr_emp_base.emp_stat_cd",
  "score": 0.91,
  "matched_terms": ["在职"],
  "match_source": "description",
  "reason": "字段描述中说明 ACTIVE 表示在职。"
}
```

注意：召回结果只是候选，不是最终给 LLM 的内容。

Schema linking 的目标就是从用户问题中找相关表和列，同时排除无关 schema。相关研究也指出，schema linking 的目标是为用户查询检索相关表列，但不完美的 linking 可能漏掉必要列，因此候选召回后还需要谨慎筛选和补全。([arXiv][4])

---

## 4.2 Schema Linking：候选筛选与补全

Knowledge Retrieval 只负责召回候选。

Schema Linking 负责把候选变成“本次问题真正可用的上下文”。

它要做：

```text
候选表筛选
候选字段筛选
字段角色判断
关系补全
value binding 选择
候选去重
上下文预算控制
生成 selection evidence
记录 dropped candidates
记录 warnings
```

CHESS 的 schema pruning 也体现了类似思想：先做列过滤、表选择、最终列选择，目标是提取最小充分 schema，而不是把所有候选都传给生成模型。([arXiv][2])

### 输出结构

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

---

## 4.3 SchemaLinkingResult

SchemaLinkingResult 是“本次问题的 schema 选择结果”。

它比最终给 LLM 的上下文更完整，主要用于：

```text
调试
artifact
复盘
解释为什么选这些表字段
解释为什么丢弃某些候选
记录不确定性
```

### 示例

```json
{
  "selected_tables": [
    {
      "table": "hr_emp_base",
      "role": "primary",
      "reason": "统计员工人数需要员工主表。"
    },
    {
      "table": "hr_dept_dim",
      "role": "join_support",
      "reason": "按部门统计需要部门名称。"
    }
  ],
  "relevant_columns": [
    {
      "table": "hr_emp_base",
      "column": "emp_id",
      "role": "measure",
      "reason": "用于 COUNT 员工。"
    },
    {
      "table": "hr_emp_base",
      "column": "emp_stat_cd",
      "role": "filter",
      "reason": "用于过滤在职员工。"
    },
    {
      "table": "hr_dept_dim",
      "column": "dept_nm",
      "role": "dimension",
      "reason": "作为部门分组字段。"
    }
  ],
  "selected_relationships": [
    {
      "left_table": "hr_emp_base",
      "left_column": "dept_id",
      "right_table": "hr_dept_dim",
      "right_column": "dept_id",
      "reason": "员工表通过 dept_id 关联部门表。"
    }
  ],
  "value_bindings": [
    {
      "business_term": "在职员工",
      "table": "hr_emp_base",
      "column": "emp_stat_cd",
      "operator": "=",
      "value": "ACTIVE",
      "reason": "ACTIVE 表示当前在职员工。"
    }
  ],
  "warnings": []
}
```

---

## 4.4 SqlGenerationContext

SqlGenerationContext 是最终给 SQL LLM 的标准输入。

它应该比 SchemaLinkingResult 更干净。

```text
SchemaLinkingResult：
  包含候选、证据、丢弃项、warning，主要用于 artifact。

SqlGenerationContext：
  只包含 SQL LLM 需要生成 SQL 的信息。
```

### 推荐结构

```python
class SqlGenerationContext(TypedDict):
    question: SqlGenerationQuestion
    schema_context: SqlGenerationSchemaContext
    sql_policy: SqlGenerationPolicy
    output_contract: SqlGenerationOutputContract
```

其中：

```python
class SqlGenerationSchemaContext(TypedDict):
    dialect: str
    tables: list[SqlGenerationTable]
    columns: list[SqlGenerationColumn]
    relationships: list[SqlGenerationRelationship]
    value_bindings: list[SqlGenerationValueBinding]
```

最终 prompt 应该基于 SqlGenerationContext 渲染。

---

## 5. 哪些内容进入 final_prompt，哪些只进入 artifact

这个边界很重要。

### 进入 final_prompt

```text
ProcessedQuestion.text
选中的表
选中的字段
字段含义
字段角色
join 关系
value bindings
SQL policy
output contract
必要 warning
```

### 只进入 artifact

```text
所有候选
候选分数
match_source
selection evidence
dropped_candidates
完整 source trace
retrieval raw chunks
debug 信息
```

原因是：LLM 需要干净、稳定、低噪音的输入；但开发者需要完整可复盘的中间过程。

---

## 6. 当前本地项目应该做什么

当前本地项目只做 KnowledgeLayer 消费设计。

应该做：

```text
1. 定义 KnowledgeLayer 输入契约。
2. 定义 ProcessedQuestion 输入契约。
3. 定义 KnowledgeRetrievalResult / KnowledgeCandidate。
4. 定义 SchemaLinkingResult。
5. 定义 SqlGenerationContext。
6. 定义 SchemaLinkingResult -> SqlGenerationContext 的转换规则。
7. 定义 final_prompt 如何渲染 SqlGenerationContext。
8. 定义 artifact 如何记录候选、证据、最终上下文。
```

不应该做：

```text
1. 不处理真实数据库。
2. 不设计 DB Agent 具体实现。
3. 不接真实向量库。
4. 不接真实 SQL LLM。
5. 不做 QueryPlan。
6. 不做 retry。
7. 不做人工审核流程。
```

---

## 7. 后续与 DB Agent 的关系

未来 DB Agent 的职责是：

```text
Raw Database
  -> KnowledgeLayer
```

当前本地项目的职责是：

```text
ProcessedQuestion + KnowledgeLayer
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> FinalPrompt
```

因此，只要未来 DB Agent 输出的 KnowledgeLayer 满足当前定义的契约，本地项目就不需要重构。

这就是当前先设计 KnowledgeLayer 契约的价值。

---

## 8. 推荐后续项目结构

当前项目后续可以按这个方向增加模块，但不要一次性全实现。

```text
src/nl2sqlagent/
  workflows/
    nl2sql/
      knowledge/
        types.py                # KnowledgeLayer / TableKnowledge / ColumnKnowledge
        retrieval.py            # KnowledgeRetrievalResult / Candidate 结构
        schema_linking.py       # SchemaLinkingResult 结构与转换规则
        sql_context.py          # SqlGenerationContext 结构

      prompt_payload.py         # 组装 prompt_payload
      prompt_builder.py         # 渲染 final_prompt
      nodes.py                  # 后续增加 build_schema_context_node
```

第一阶段甚至可以只增加类型和测试，不实现复杂检索算法。

---

## 9. 推荐分阶段推进

### Step 1：只定义契约

```text
KnowledgeLayer
ProcessedQuestion
KnowledgeCandidate
SchemaLinkingResult
SqlGenerationContext
```

目标：先把“数据长什么样”定下来。

### Step 2：用 fixture 模拟 KnowledgeLayer

```text
不要接真实数据库。
不要接真实向量库。
用接近真实命名风格的 fixture。
```

例如：

```text
hr_emp_base
hr_dept_dim
payroll_salary_mth
biz_order_main
biz_order_item
crm_customer_profile
```

### Step 3：实现最小检索

```text
关键词匹配
别名匹配
描述匹配
value binding 匹配
```

目标不是最强召回，而是验证链路。

### Step 4：实现 SchemaLinkingResult -> SqlGenerationContext

```text
候选结果
  -> 选中表字段关系
  -> 给 LLM 的干净上下文
```

### Step 5：升级 final_prompt

让 prompt 变成：

```text
Processed Question
Selected Tables
Relevant Columns
Relationships
Value Bindings
SQL Policy
Output Contract
```

### Step 6：升级 artifact

增加或扩展：

```text
knowledge_retrieval.json
schema_linking_result.json
sql_generation_context.json
```

或者先放入现有：

```text
prompt_payload.json
graph_updates.jsonl
```

---

## 10. 一句话总结

后续整体结构应该是：

```text
真实数据库
  -> DB Agent
  -> KnowledgeLayer
```

这是未来很后的事情。

当前本地项目只做：

```text
ProcessedQuestion
  + KnowledgeLayer
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> FinalPrompt
```

其中最难的是：

```text
KnowledgeLayer 如何与 ProcessedQuestion 协作。
```

它可能用向量，也可能用关键词、别名、规则、图关系、混合检索。但无论算法是什么，最终都要产出统一的：

```text
SchemaLinkingResult
SqlGenerationContext
```

这就是当前阶段最应该先设计清楚的边界。

[1]: https://arxiv.org/abs/2304.11015?utm_source=chatgpt.com "DIN-SQL: Decomposed In-Context Learning of Text-to- ..."
[2]: https://arxiv.org/html/2405.16755v1?utm_source=chatgpt.com "CHESS: Contextual Harnessing for Efficient SQL Synthesis"
[3]: https://blog.nilenso.com/blog/2025/05/15/exploring-rag-based-approach-for-text-to-sql/?utm_source=chatgpt.com "Exploring RAG based approaches for Text-to-SQL - nilenso blog"
[4]: https://arxiv.org/html/2408.07702v2?utm_source=chatgpt.com "The Death of Schema Linking? Text-to-SQL in the Age of ..."
