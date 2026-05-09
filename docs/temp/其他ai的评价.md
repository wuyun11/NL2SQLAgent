可以执行。
这份 `2026-05-09-nl2sql-data-contracts.md` 已经是**可执行 implementation plan**，不是设计稿了。它把 Phase 5 的目标、范围、文件改动、测试先行步骤、最终验证和禁止事项都写清楚了，而且基本完全承接了前一份 Phase 5 设计目标：只做轻量数据契约，不接真实 LLM / DB / schema，不引入重型 stage/service/protocol/context 架构。

## 结论

```text
可以执行。
```

但我建议执行前修 3 个小点，都是为了减少 AI 执行时踩坑，不影响整体方向。

---

## 这份计划做得好的地方

### 1. 范围控制非常清楚

计划明确只新增：

```text
runtime_options.py
test_runtime_options.py
```

主要修改 `workflow.py / nodes.py / prompt_payload.py / prompt_builder.py / response_builder.py / state.py`，并明确禁止真实 LLM、真实数据库、真实 schema grounding、retry、QueryPlan、CLI ask、`domain/services/integrations`、stage/protocol/context/result model、Pydantic 和 artifact 格式重设计。

这个范围非常好。它防止 Phase 5 变成“顺手接真实能力”或者“顺手搭一堆空架构”。

---

### 2. `runtime_options` 这一步非常必要

计划要求：

```text
External input can still expose options: dict[str, Any]
Only normalize_runtime_options may interpret raw options keys
Nodes must read runtime_options, not state["options"]
Unknown options are ignored by runtime_options but preserved in input.options
Only bool True/False values activate mock runtime flags
```

这正好解决了当前 `options` 变成 magic-key 垃圾桶的风险。

尤其是这两个规则很重要：

```text
未知 options 保留在 input artifact 里，用于复现。
节点只能看白名单化后的 runtime_options。
```

这样后续如果有人传：

```python
{"temperature": 0.1, "force_check_error": "true"}
```

不会影响节点执行，但仍然能在 `input.json` 里看到原始输入，这个设计很稳。

---

### 3. 继续使用 `TypedDict` 是正确的

计划没有引入 Pydantic，也没有把 graph state 改成 dataclass，而是继续使用 `TypedDict`。这和 LangGraph 的使用方式一致：LangGraph 的 StateGraph 节点通过读取共享 state 并返回 `Partial<State>` 进行通信，State schema 可以是 `TypedDict` 或 Pydantic model。([LangChain 参考文档][1])

而 Python TypedDict 的 `total=False` 语义也适合 LangGraph state：字段可以非必需，符合节点逐步填充状态的模型。([Typing Python][2])

所以 Phase 5 继续保持：

```python
class Nl2SqlGraphState(TypedDict, total=False):
    ...
```

是正确的。不要为了“更类型化”强行上 dataclass 或 Pydantic。

---

### 4. metadata 边界收敛得很好

计划明确：

```text
response_builder owns prompt debug metadata only
artifacts.py owns artifact metadata only
workflow.py may merge metadata but must not hand-write artifact path keys
GraphRuntime remains NL2SQL-agnostic
```

这个边界非常重要。

它延续了 Phase 4 的 artifact 设计：artifact 路径和 metadata 只应该由 `artifacts.py` 构造，workflow 只合并，不解释 artifact 字段。Phase 4 设计里也明确 artifact writer 放在 `workflows/nl2sql/artifacts.py`，因为这些字段具有明显 NL2SQL 业务含义，不适合放到平台层过早抽象。

---

## 执行前建议修 3 个小点

### 1. Task 2 把 `_graph_input` 测试放在 integration 里不太合适

计划里在 `tests/integration/test_nl2sql_workflow.py` 添加：

```python
Nl2SqlWorkflow._graph_input(...)
```

这其实是一个纯函数/静态方法测试，更像 unit test，不是 integration test。

不阻塞执行，但我建议改到：

```text
tests/unit/workflows/nl2sql/test_workflow.py
```

如果现在没有这个文件，也可以暂时保留在 integration 里。但长期看，`_graph_input` 的契约属于 workflow 单元行为，不应该依赖 integration 测试文件。

更稳的执行方式：

```text
可以先按计划放 integration；
后续如果 workflow 单测增多，再拆 test_workflow.py。
```

---

### 2. `normalize_runtime_options` 的 “False 是否保留” 要确认

计划里测试期望：

```python
normalize_runtime_options({
    "force_check_error": True,
    "force_execute_error": False,
}) == {
    "force_check_error": True,
    "force_execute_error": False,
}
```

这表示 `False` 也会进入 runtime_options。

这个可以接受，因为它保留了用户明确传入的白名单 bool 值。但如果你希望 runtime_options 只保存“激活的开关”，那应该只保留 True。

我建议**保持计划当前写法**：True/False 都保留。理由是：

```text
1. 它表达“用户明确设置过这个开关”。
2. 节点判断用 `is True`，False 不会触发错误。
3. artifact / state 中能看到明确设置。
```

但执行时一定要保持节点判断：

```python
runtime_options.get("force_check_error") is True
```

不要写成：

```python
if runtime_options.get("force_check_error"):
```

虽然当前等价，但 `is True` 更符合设计意图。

---

### 3. `test_phase5_does_not_introduce_stage_protocol_or_context_result_shells` 可能误伤字符串

这个测试会扫描 `workflows/nl2sql` 下所有 `.py`，禁止出现：

```text
PrepareStage
GenerateStage
CheckStage
ExecuteStage
PrepareResult
...
```

方向是对的，但以后如果注释里提到“不要引入 PrepareStage”，也会失败。

当前可以执行，因为它就是为了防止过度抽象。但我建议在实现时避免在源码注释中写这些 forbidden token；把这类解释留在 docs，不要写进 `.py`。

---

## 我认为不需要改的地方

### 1. 不需要新增 `domain/services/integrations`

计划明确禁止这些目录，非常正确。Phase 5 是数据契约收敛，不是业务能力拆分。前置设计也明确 Phase 5 要收敛 options / prompt_payload / output metadata / graph state 的字段边界，但不新增重型结构。

### 2. 不需要改变 artifact 文件格式

计划只做 artifact metadata 来源边界测试，不重写 Phase 4 artifact。这个正确。Phase 4 已经确定了 `input.json / prompt_payload.json / final_prompt.txt / graph_updates.jsonl / output.json / manifest.json`，并且不生成真实 `token_usage.json`。

### 3. 不需要为 `rows` 建类型模型

`rows: list[dict[str, Any]]` 继续保留是合理的。SQL 查询结果列是动态的，当前没有固定业务表格 schema；强行建模会过早。前置设计也明确 rows 只表示最终结果表格，不要把调试信息塞进去。

---

## 是否可以开始执行？

可以。执行口径建议是：

```text
可以开始执行 Phase 5。

严格按 2026-05-09-nl2sql-data-contracts.md 的 Task 1-9 顺序执行。

不要扩大范围：
- 不接真实 LLM / DB / schema grounding
- 不新增 retry / QueryPlan / CLI ask
- 不新增 domain/services/integrations
- 不新增 stage/protocol/context/result model
- 不改 artifact 文件格式
- 不把 metadata key 写散到 workflow.py
```

## 最终判断

这份计划已经具备执行条件。它的关键优点是：

```text
1. 把 options 收敛为 runtime_options。
2. 让 nodes 不再直接读取原始 options。
3. 给 prompt_payload 加 TypedDict 契约。
4. 保持 graph state 适配 LangGraph 的 TypedDict(total=False) 模型。
5. 把 prompt debug metadata 和 artifact metadata 来源分开。
6. 用边界测试防止 GraphRuntime、nodes、workflow.py 重新污染。
7. 用最终验证确认没有新增重型架构。
```

一句话总结：

**可以执行。Phase 5 不会让项目“长壳”，但会把下一步接真实 LLM/schema/DB 前最容易乱的数据边界先收住。**

[1]: https://reference.langchain.com/python/langgraph/graph/state/StateGraph?utm_source=chatgpt.com "StateGraph | langgraph"
[2]: https://typing.python.org/en/latest/spec/typeddict.html?utm_source=chatgpt.com "Typed dictionaries — typing documentation"
