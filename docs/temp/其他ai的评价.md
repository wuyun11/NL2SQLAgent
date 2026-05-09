这份 Phase 3 执行计划**可以执行**。
它已经不是设计稿，而是完整 implementation plan：范围边界明确、文件清单明确、测试先行、每个 Task 有预期失败和验证步骤，最后还有 forbidden path、no retry、debug 不进入 final_prompt 的检查。

## 结论

```text
可以开始执行 Phase 3。
```

我只建议执行前改 1 个小点，另外注意 2 个执行细节。

---

## 做得好的地方

### 1. 范围控制非常清楚

计划明确只允许新增：

```text
prompt_payload.py
prompt_builder.py
test_prompt_payload.py
test_prompt_builder.py
```

只允许修改：

```text
nodes.py
test_nodes.py
test_response_builder.py
test_nl2sql_workflow.py
```

并明确禁止新增 `domain/services/integrations`、真实 LLM、真实数据库、schema grounding、retry、QueryPlan、CLI ask 等。

这个边界非常好，能防止 AI 一边写 prompt，一边顺手开始接 LLM 或 services。

---

### 2. prompt builder / payload builder 分工正确

计划把 Phase 3 拆成两个纯函数：

```text
prompt_payload.py
  build_mock_prompt_payload(...)
  只负责生成结构化材料

prompt_builder.py
  render_final_prompt(prompt_payload)
  只负责渲染最终 prompt
```

并明确它们不读配置、不读 schema 文件、不访问 logger、DB 或外部 client。

这个设计是对的。LangGraph 的 Graph API 本身强调 State / Nodes / Edges：节点接收 state，返回 state update。([LangChain 文档][1]) 你现在让 `build_prompt_node` 只做薄编排：读 state、调用 payload builder、调用 prompt renderer、返回 `prompt_payload/final_prompt`，这非常符合当前阶段。

---

### 3. final_prompt 的测试非常有价值

计划里 `test_prompt_builder.py` 会测：

```text
包含固定 section
section 顺序稳定
schema / semantic / sql_policy / output_contract 文本存在
不包含 markdown fences
不渲染 debug
```

这很好。

Prompt 最怕“看起来只是改了一点字符串”，实际导致模型行为变化。你现在把段落顺序、关键约束、debug 不渲染这些都写成测试，后面改 prompt 时能及时发现变化。

OpenAI 的提示工程建议也强调，要清楚表达任务、给足上下文，并明确输出格式；你的 `Task / User Question / Schema Context / Semantic Context / SQL Policy / Output Contract` 正好是在结构上做这件事。([OpenAI][2])

---

### 4. debug 不进入 final_prompt 的规则很好

计划明确：

```text
debug 留在 prompt_payload metadata
final_prompt 不渲染 debug
```

并在最终验证里检查 `phase3.mock.v1` 和 `mock_prompt_payload_builder` 不应被 renderer 加进 final_prompt。

这个边界很重要。`debug` 是给人和系统看的，不是给模型看的。把它留在 metadata 可以调试，把它排除在 final_prompt 外可以保持提示词干净。

---

### 5. stream / metadata 观察路径没有丢

计划要求继续保持：

```text
output metadata 暴露 prompt_payload / final_prompt
stream updates 暴露 build_prompt 的 prompt_payload / final_prompt
```

这和 Phase 2 的核心目标一致。LangGraph streaming 文档说明，`updates` 可以看到每步 state update，`values` 可以看到每步后的完整 state。([LangChain 文档][3]) 所以你继续用 stream 来观察 `build_prompt` 节点的结果是合理的。

---

## 执行前建议改 1 个小点

### `test_render_final_prompt_renders_output_contract_without_markdown_fences` 的语义稍微有歧义

测试里有：

````python
assert "- Do not include markdown fences." in final_prompt
assert "```" not in final_prompt
````

这个是对的，但容易被误读成“final_prompt 不应该提 markdown fences”。实际上你的意思是：

````text
final_prompt 可以告诉模型不要输出 markdown fences；
final_prompt 自己不能包含 ``` 这种 fence 符号。
````

建议把测试名改成更准确：

```python
def test_render_final_prompt_instructs_no_markdown_fences_without_using_fences() -> None:
```

这不是功能问题，只是避免后续维护者看错。

---

## 执行时注意 2 个细节

### 1. `list(payload)` 断言依赖 dict 插入顺序，可以接受

测试里：

```python
assert list(payload) == [
    "task",
    "question",
    "schema_context",
    ...
]
```

Python 3.7+ 已经保证 dict 保持插入顺序，所以这个测试可以接受；你的项目是 Python 3.12，更没问题。它能防止 payload 顶层字段顺序被无意改乱。

### 2. `prompt_payload` 现在还是 dict，不要急着 dataclass 化

目前计划使用 dict 是合理的。因为 Phase 3 的目标是 prompt 结构验证，不是类型系统完善。现在如果引入一堆 `TaskPayload / SchemaContext / SqlPolicy` dataclass，会扩大范围。等真实 schema / semantic / policy 接入后，再考虑类型化也不迟。

---

## 是否可以直接开始？

可以。

我建议执行口径如下：

```text
可以开始执行 Phase 3。

严格按 2026-05-09-nl2sql-prompt-payload.md 的 Task 1-6 顺序执行。

不允许扩范围：
- 不创建 domain/services/integrations
- 不接真实 LLM/database/schema grounding
- 不新增 retry/feedback/round_index/max_round_count
- 不新增 CLI ask
- 不迁移旧 SQLAgent 代码

执行前可把 prompt_builder 的 markdown fence 测试名改得更准确。
```

## 最终判断

**可以执行。**

这份计划已经具备直接实施条件：它只改变 prompt payload 和 final_prompt 渲染边界，不改 graph 形状，不引入外部依赖，不破坏 Phase 2 线性 workflow，而且测试覆盖了结构、顺序、metadata、stream、debug 隔离和 no retry。

[1]: https://docs.langchain.com/oss/python/langgraph/graph-api?utm_source=chatgpt.com "Graph API overview - Docs by LangChain"
[2]: https://openai.com/?utm_source=chatgpt.com "OpenAI | OpenAI"
[3]: https://docs.langchain.com/oss/python/langgraph/streaming?utm_source=chatgpt.com "Streaming - Docs by LangChain"
