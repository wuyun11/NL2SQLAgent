可以执行。
这份 `2026-05-09-nl2sql-knowledge-layer-consumption.md` 已经是**可执行 implementation plan**，不是单纯设计稿了。它的目标、边界、文件结构、任务顺序、测试先行、验收标准都比较完整，适合交给 AI/开发者按 Task 逐步实现。

## 结论

```text
可以执行。
但建议执行前修 4 个小问题。
```

整体方向是对的：先跑通这条链路：

```text
ProcessedQuestion
  + ProcessedDatabaseKnowledge
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> PromptPayload
  -> FinalPrompt
```

并且明确不接真实 LLM、真实 DB、真实向量库、retry、QueryPlan、domain/services/stages 等重型结构。这个边界非常适合你当前阶段。

LangGraph 的 StateGraph 本身就是节点读取共享 state、返回 partial state update 的模型；官方 reference 也说明节点签名是 `State -> Partial<State>`。所以计划里让 `build_prompt_node` 返回 `processed_question / retrieval / linking / sql_generation_context / prompt_payload / final_prompt`，是符合 LangGraph 使用方式的。([LangChain 参考文档][1])

---

## 做得好的地方

### 1. 范围控制很好

计划明确禁止：

```text
RawUserQuestion -> ProcessedQuestion
RawDatabaseSchema -> ProcessedDatabaseKnowledge
真实 LLM
真实数据库
真实向量库
retry
QueryPlan
domain/services/integrations/stages/models
```

这非常重要。

你这次不是在做完整 NL2SQL，而是在做**知识层消费链路**。这个切分很合理。

---

### 2. 增加 `KnowledgeRetrievalResult` 是正确的

计划明确区分：

```text
KnowledgeRetrievalResult:
  候选召回，可以有噪声。

SchemaLinkingResult:
  最终选择，需要证据、丢弃项、warning。

SqlGenerationContext:
  给 SQL LLM 的干净输入。
```

这个分层是整个方案最核心的地方。

这也符合 Text-to-SQL 里常见的拆分思路。DIN-SQL 就是把 Text-to-SQL 分解为 schema linking、query classification/decomposition、SQL generation、self-correction 等子任务，而不是让一个 LLM 直接承担所有判断。([arXiv][2])

---

### 3. 文件结构克制

计划只新增：

```text
knowledge_contracts.py
knowledge_pipeline.py
test_knowledge_pipeline.py
```

这很好。

你没有一上来创建：

```text
domain/
services/
stages/
models/
protocols/
```

这是正确的。当前阶段先把数据契约和纯函数 pipeline 跑通，比搭抽象层更重要。

---

### 4. 测试设计很扎实

计划覆盖了：

```text
contracts import
sample processed question
sample knowledge layer
structured retrieval
schema linking
SQL generation context
prompt payload
prompt renderer
node integration
artifact metadata
dropped candidates
pseudo vector candidate
final verification
```

尤其是这个测试非常有价值：

```text
伪 vector candidate 不能绕过 SchemaLinkingResult 直接进入 SqlGenerationContext / FinalPrompt。
```

它可以提前锁住架构边界，避免以后接向量时把 top-k chunk 直接塞进 prompt。

---

## 执行前建议修 4 个小问题

### 问题 1：`test_schema_linking_keeps_unselected_candidates_out_of_selected_context` 里 `finance_salary_month` 可能会污染 `str(context)` 测试

后面 Task 8 计划里有：

```python
assert "finance_salary_month" not in str(context)
assert "finance_salary_month" not in str(payload)
assert "finance_salary_month" not in final_prompt
```

这个方向是对的。

但要注意：如果 `SchemaLinkingResult.dropped_candidates` 被错误带入 context，就会失败；这是你想测的。但如果实现里 `semantic_context` 或 debug 字段不小心保留了 dropped 信息，也会失败。

所以这条测试很好，执行时要坚持：**`SqlGenerationContext` 不能包含 dropped_candidates，也不能包含 dropped table name。**

---

### 问题 2：`build_initial_processed_question(...)` 现在只适配“员工部门统计”

计划里：

```python
def build_initial_processed_question(raw_question: str) -> ProcessedQuestion:
    text = raw_question.strip()
    return {
        ...
        "keywords": ["部门", "在职", "员工", "人数"],
        ...
    }
```

这可以接受，因为计划明确说这是**手写中间层对象，不是问题理解**。

但建议在函数注释里写清楚：

```text
This is a temporary fixture-like processed question builder for the first knowledge-layer consumption path. It is not a real question understanding implementation.
```

否则后续别人可能误以为这是正式的 question understanding。

---

### 问题 3：`build_sample_processed_database_knowledge()` 放在 production module 里，要明确是 sample

这次计划把 sample knowledge 放到：

```text
knowledge_pipeline.py
```

这可以接受，因为当前阶段就是为了跑通本地链路。

但它毕竟是样例数据，不是真正业务数据。建议函数名继续保留 `sample`，并避免让其他模块把它误用成正式知识来源。

也就是说，当前可以：

```python
build_sample_processed_database_knowledge()
```

但不要命名成：

```python
load_processed_database_knowledge()
get_processed_database_knowledge()
```

你计划里的命名是好的。

---

### 问题 4：Task 7 artifact 可选独立文件要克制

计划里说可选新增：

```text
knowledge_retrieval_result.json
schema_linking_result.json
sql_generation_context.json
```

但也说如果会让 `artifacts.py` 变大，就先依赖 `output.json` 和 `graph_updates.jsonl`。

我建议初版**不要新增独立 artifact 文件**，除非实现非常简单。

当前最小目标应该是：

```text
output.json metadata 能看到
graph_updates.jsonl 能看到 build_prompt update
final_prompt.txt 干净
prompt_payload.json 有 value_bindings
```

等这条链路稳定后，再拆独立 artifact 文件。

---

## 我认为可以直接按 Task 执行的原因

这份计划符合几个关键原则：

```text
1. 测试先行。
2. 每个 Task 有明确文件范围。
3. 每个 Task 有预期失败和预期通过。
4. 不扩展架构层。
5. 不接真实外部依赖。
6. 不让 retrieval internals 进入 final_prompt。
7. 不让 nodes.py 写文件。
8. 不让 response_builder.py 构造 artifact path metadata。
```

这正好符合你前面一直在收敛的方向。

---

## 执行时最需要守住的边界

### 1. `knowledge_pipeline.py` 必须是纯函数

它只能做：

```text
ProcessedQuestion
ProcessedDatabaseKnowledge
KnowledgeRetrievalResult
SchemaLinkingResult
SqlGenerationContext
```

不能做：

```text
文件 I/O
日志
LangGraph
artifact 写入
真实 LLM
真实 DB
向量库
```

计划已经写了这一点，执行时不要放松。

---

### 2. `build_prompt_node` 只编排，不做业务细节

`nodes.py` 里可以顺序调用：

```python
build_initial_processed_question
build_sample_processed_database_knowledge
build_knowledge_retrieval_result
build_schema_linking_result
build_sql_generation_context
build_prompt_payload_from_sql_generation_context
```

但不要在 `nodes.py` 里写匹配规则、过滤规则、artifact 逻辑。

---

### 3. `PromptPayload / FinalPrompt` 只能来自 `SqlGenerationContext`

这是最重要的验收标准。

不能这样：

```text
KnowledgeRetrievalResult -> PromptPayload
SchemaLinkingResult.dropped_candidates -> PromptPayload
vector raw_ref -> PromptPayload
```

必须是：

```text
SqlGenerationContext -> PromptPayload -> FinalPrompt
```

计划已经把这个作为边界写清楚了。

---

## 最终执行口径

可以这样交给执行者：

```text
可以开始执行 2026-05-09-nl2sql-knowledge-layer-consumption.md。

严格按 Task 1-9 顺序执行。

当前只实现：
- 手写 ProcessedQuestion
- 手写 ProcessedDatabaseKnowledge
- structured matcher
- Candidate -> SchemaLinkingResult
- SchemaLinkingResult -> SqlGenerationContext
- PromptPayload / FinalPrompt 升级
- artifact / metadata 可观察

禁止扩范围：
- 不接真实 LLM / DB / VectorStore
- 不实现 RawUserQuestion -> ProcessedQuestion
- 不实现 RawDatabaseSchema -> ProcessedDatabaseKnowledge
- 不做 retry / QueryPlan
- 不新增 domain/services/integrations/stages/models/protocols
- 不让 dropped_candidates / retrieval_method / vector_score / chunk_id / raw_ref 进入 final_prompt
```

## 最终判断

**可以执行。**

这份计划已经具备实施条件。它不是“继续讨论设计”，而是把设计压成了一个可测试、可分步提交的最小实现路径。唯一要注意的是：执行过程中必须克制，不要顺手把 sample builder 做成正式问题理解，不要顺手加真实向量或 LLM，也不要为了 artifact 一次性新增太多文件。

[1]: https://reference.langchain.com/python/langgraph/graph/state/StateGraph?utm_source=chatgpt.com "StateGraph | langgraph"
[2]: https://arxiv.org/abs/2304.11015?utm_source=chatgpt.com "DIN-SQL: Decomposed In-Context Learning of Text-to- ..."
