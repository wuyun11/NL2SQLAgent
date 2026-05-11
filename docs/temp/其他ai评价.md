我看完这份 `Phase7_NL2SQL_LLM接入设计.md`，结论是：

```text
没有明显绕过 LangGraph 框架的嫌疑。
相反，这份设计是在有意识地防止“第二套流程控制”重新出现。
```

它的核心思路是：**LangGraph 继续负责流程，`generate_sql` 节点继续代表“生成 SQL”这个业务步骤，`SqlGenerator` 只是这个节点内部注入的模型调用适配器。** 这和 LangGraph 的设计方式是吻合的：StateGraph 的节点通过读取/写入共享 state 通信，节点返回 partial state update；条件边用于根据 state 决定下一步去哪里。([reference.langchain.com][1])

---

## 1. 这份设计没有绕过框架，原因很明确

文档里最关键的一句是：

```text
本阶段只替换 final_prompt -> generated_sql。
```

也就是只把当前 mock：

```python
return {"generated_sql": "SELECT 1 AS value"}
```

替换成：

```text
final_prompt -> SqlGenerator -> generated_sql
```

而不是重新引入一套：

```text
Chain
Stage
Orchestration
MainOrchestration
```

文档也明确写了不做 `engine/chains`、`GenerateStage`、`MainOrchestration`，并且强调流程分支必须继续体现在 `graph.py`，不能藏进 `options.use_llm_generate` 或新的 Stage/Chain 里。

这点非常重要。因为你之前重构的根本风险就是“两套流程控制”：

```text
LangGraph 一套流程
Stage/Orchestration 又一套流程
```

而这份文档现在明确拒绝这个方向。

---

## 2. `SqlGenerator` 这个抽象是合适的，不是乱加层

这份设计新增：

```python
@dataclass(frozen=True)
class SqlGenerationResult:
    generated_sql: str
    model_name: str
    raw_text: str

class SqlGenerator(Protocol):
    def generate(self, final_prompt: str) -> SqlGenerationResult: ...
```

这个抽象我认为是合理的。它不是新的 workflow，也不是新的业务阶段；它只是 `generate_sql_node` 的依赖。

它解决的是：

```text
单元测试 / 集成测试用 FakeSqlGenerator。
cloud / 本地人工验证用 OpenAICompatibleSqlGenerator。
generate_sql_node 不直接关心具体 provider。
```

这符合依赖注入的方向。LangChain/LangGraph 的 runtime context 文档也把数据库连接、API client、配置等依赖作为运行时上下文/依赖注入对象，而不是硬编码在节点里。([LangChain 文档][2])

所以这个抽象不是“绕开框架”，而是为了让节点保持薄。

---

## 3. `generate_sql_node` 的职责边界是对的

文档规定 `generate_sql_node` 只做：

```text
1. 从 state 读取 final_prompt。
2. 调用注入的 SqlGenerator。
3. 把 generated_sql / llm_result 写回 state。
4. 捕获异常，写 generate_error。
```

并明确不做：

```text
读取 API key
初始化 ChatOpenAI
判断 provider
写 artifact
记录 token usage
retry / repair
```

这个边界非常干净。

它也符合 LangGraph 节点的基本模式：节点函数接收 state，返回需要更新的 state 片段。([reference.langchain.com][1])

如果后续实现真的按这个写，`nodes.py` 不会变成大泥球。

---

## 4. `route_after_generate` 放进 graph 是正确的

文档里把：

```text
generate_sql -> check_sql
```

改成：

```text
generate_sql -> route_after_generate -> check_sql / failed_response
```

这是正确的。

因为：

```text
生成失败后是否继续 check_sql
```

这是 workflow 分支，不应该藏在 `generate_sql_node` 内部的 if 里，也不应该由外部 orchestration 决定。

这和 LangGraph 条件边的用途一致：通过 `add_conditional_edges` 让路由函数根据 state 决定下一节点。([LangChain 文档][3])

所以这不是绕过框架，而是在更充分地使用 LangGraph。

---

## 5. 我最认可的点：不用 `use_llm_generate`

文档明确不设计：

```text
options.use_llm_generate
```

而是通过装配区分：

```text
单元测试 / 普通集成测试:
  FakeSqlGenerator

本地人工 LLM 验证 / cloud 测试:
  OpenAICompatibleSqlGenerator
```

这个判断非常关键。

如果你用 `options.use_llm_generate`，后面很容易继续出现：

```text
use_vector
use_history_sql
use_template
use_retry
```

最后就变成：

```text
graph.py 看起来是一条流程，
但真实行为都藏在 options 里。
```

而现在的设计是：

```text
环境差异靠装配。
业务流程靠 LangGraph。
```

这条线非常对。

---

## 6. 当前设计有一个小风险：`sql_generator.py` 放在 workflow 包里

文档建议新增：

```text
src/nl2sqlagent/workflows/nl2sql/sql_generator.py
```

并说明暂时不新增：

```text
src/nl2sqlagent/infrastructure/llm/
```

理由是：

```text
当前 LLM 调用只服务 NL2SQL workflow 的 generate_sql 节点。
等多个 workflow 复用 LLM provider 后，再考虑迁移公共基础设施。
```

这个取舍我可以接受。

但要注意一个边界：

```text
sql_generator.py 可以是当前 workflow 的薄 adapter。
不要在里面发展出一整套 chain / prompt / retry / logging 框架。
```

如果以后出现第二个 workflow 也需要 chat model，再迁移到 `platform/llm` 或 `infrastructure/llm`。当前不要提前抽公共层，这个判断是克制的。

---

## 7. 配置设计基本合理，但有一个实现细节要小心

新增：

```yaml
model:
  sql_generator:
    provider: openai_compatible
    chat_model_name: glm-5
    base_url: ...
    api_key_env: DASHSCOPE_API_KEY
    temperature: 0
    timeout_seconds: 60
```

这没问题。文档也强调 `provider` 是部署/装配配置，不是业务输入开关，不进入 `Nl2SqlInput.options` 或 `runtime_options`。

我建议执行时守住一点：

```text
API key 缺失不要写进 artifact / app.log。
generate_error 可以写 “missing API key env: DASHSCOPE_API_KEY”，但不要写真实值。
```

这份文档已经提到真实 key 不进入 graph state、artifact、app.log。这个边界要在测试里保护。

---

## 8. 不做 token usage / LangSmith / retry 是正确的

这份设计明确不做：

```text
token usage
LangSmith
retry / repair
真实数据库执行
向量召回
历史 SQL 模板
```

我认为这非常正确。

尤其是 retry / repair，它不是“加个字段”这么简单，而是 workflow 结构变化：

```text
check_sql failed
  -> repair prompt
  -> generate_sql
  -> check_sql
```

这个应该以后用 LangGraph 分支/循环单独设计，现在混进去会干扰本阶段目标。

当前目标只是验证：

```text
final_prompt -> LLM -> generated_sql
```

所以本阶段保持薄是对的。

---

## 9. 这份文档仍需要补一个执行层面的保护

文档第 12.4 已经建议架构保护测试：

```text
1. src/ 中不出现 use_llm_generate。
2. src/ 中不新增 engine/chains。
3. src/ 中不新增 application/stages。
4. nodes.py 中不出现 ChatOpenAI / DASHSCOPE_API_KEY / base_url / api_key。
```

这个必须保留。

我还建议加一个：

```text
5. artifacts.py / response_builder.py 中不出现 api_key / DASHSCOPE_API_KEY 的真实值。
```

也就是测试 secret 不进入输出。

---

## 10. 是否有“绕过框架”的嫌疑？

我会分成三个判断。

### 没有绕过的部分

```text
1. 继续使用 graph.py 表达流程。
2. 失败分支用 route_after_generate 条件边。
3. generate_sql_node 返回 partial state update。
4. LLM 调用结果进入 state / artifact。
5. 不引入 Stage / Chain / Orchestration。
6. 不用 options 隐藏切换真实 LLM。
```

这些都说明没有绕过 LangGraph。

### 需要小心的部分

```text
1. sql_generator.py 不要演化成 NL2SQLChain。
2. OpenAICompatibleSqlGenerator 不要负责 prompt、artifact、retry、token usage。
3. container 装配不要变成第二套 orchestration。
4. cloud test 不要进入默认 pytest。
```

这些是实现时的风险，不是设计本身的问题。

### 我会要求执行计划中明确的边界

```text
generate_sql_node:
  只能 import SqlGenerator / SqlGenerationError / SqlGenerationResult。
  不能 import ChatOpenAI。
  不能 import os.environ。
  不能读取 model.yml。
  不能写 artifact。
```

这个边界一旦守住，项目就不会乱。

---

## 最终评价

这份 `Phase7_NL2SQL_LLM接入设计.md` **没有明显绕过框架的嫌疑**，而且比“参考旧项目直接搬 Chain/Stage”要稳很多。

它的正确形状是：

```text
LangGraph 继续管流程；
generate_sql 节点继续表示“生成 SQL”；
SqlGenerator 只是节点依赖；
Fake / Real generator 通过装配切换；
生成失败通过 LangGraph 条件边进入 failed_response；
结果继续进入 graph state 和 artifact；
不新建第二套 Chain / Stage / Orchestration。
```

一句话结论：

```text
可以作为 Phase7 LLM 接入的设计稿通过。
下一步应该写 implementation plan，但必须保留架构保护测试，防止实现时把 ChatOpenAI、API key、Stage/Chain 偷偷塞回 nodes.py 或新流程里。
```

[1]: https://reference.langchain.com/python/langgraph/graph/state/StateGraph?utm_source=chatgpt.com "StateGraph | langgraph"
[2]: https://docs.langchain.com/oss/python/langchain/runtime?utm_source=chatgpt.com "Runtime - Docs by LangChain"
[3]: https://docs.langchain.com/oss/python/langgraph/graph-api?utm_source=chatgpt.com "Graph API overview - Docs by LangChain"
