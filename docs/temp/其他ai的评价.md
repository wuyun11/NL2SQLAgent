这份 `2026-05-09-nl2sql-run-artifacts.md` **整体可以执行**，而且比上一份设计稿已经前进到 implementation plan 级别了。它把 Phase 4 的核心边界守得很好：`GraphRuntime` 只处理通用 LangGraph 执行，`artifacts.py` 只处理 NL2SQL artifact，`nodes.py` 保持纯净，`Nl2SqlWorkflow` 只做编排、metadata 合并和 app.log 摘要。

## 结论

```text
可以执行。
但执行前建议修 3 个小问题。
```

这 3 个问题不是架构方向问题，而是测试/实现细节问题，修完后更稳。

---

## 这份计划做得好的地方

### 1. 范围控制非常清楚

计划明确允许创建：

```text
src/nl2sqlagent/workflows/nl2sql/artifacts.py
tests/unit/workflows/nl2sql/test_artifacts.py
```

并且明确禁止：

```text
real LLM calls
real token usage files
LangSmith
OpenTelemetry
real database
real schema grounding
retry / feedback loop
domain/services/integrations
CLI ask
artifact file writes inside nodes.py
NL2SQL business-field parsing inside GraphRuntime
```

这个范围非常好。

它能防止 AI 在做 artifact 时顺手创建 `services/`、接真实 LLM、写 token 文件，或者把 artifact 写入逻辑塞进 node。

---

### 2. GraphRuntime 边界是正确的

计划里要求：

```text
GraphRuntime returns raw LangGraph update chunks only.
Artifact writer is the only code that normalizes graph update chunks into node/update JSONL rows.
```

这个非常关键。

也就是说：

```text
GraphRuntime:
  只知道 LangGraph stream / get_state / thread_id

artifacts.py:
  才知道 graph_updates.jsonl 要写成 {"node": ..., "update": ...}

Nl2SqlWorkflow:
  编排 run + artifact + metadata
```

这个边界是对的。

LangGraph 官方文档也说明，`stream_mode="updates"` 用于流式获取每一步后的 state update，`stream_mode="values"` 用于获取每一步后的完整 state。([LangChain 文档][1]) 而 `graph.get_state(config)` 会根据指定 thread 的 config 返回最新 `StateSnapshot`。([LangChain 文档][2]) 所以你现在的 `invoke_with_updates -> stream updates -> get_state(config)` 路线是合理的。

---

### 3. artifact writer 责任清晰

计划把 artifact writer 定位为唯一负责这些事情的地方：

```text
构造 artifact path
写 input.json / prompt_payload.json / final_prompt.txt / graph_updates.jsonl / output.json / manifest.json
把 Path/datetime/dataclass 转成 JSON-safe value
把 raw graph update chunks 标准化成 JSONL rows
```

这很好。

尤其是你明确禁止：

```text
json.dump/json.dumps artifact content inside Nl2SqlWorkflow.run
```

这个规则很重要。否则 `workflow.py` 会越来越胖。

---

### 4. JSONL 设计是合理的

`graph_updates.jsonl` 每行一个节点 update：

```json
{"node":"build_prompt","update":{"final_prompt":"..."}}
```

这非常适合 LangGraph updates。JSON Lines 的基本约定就是 UTF-8 编码、每行一个合法 JSON value、用换行分隔。([JSON Lines][3])

所以 graph updates 用 JSONL，比写一个大 JSON 数组更适合后续追加、筛选、diff 和 agent 读取。

---

## 执行前建议修 3 个小问题

### 问题 1：`_safe_artifact_id` 会把中文 request_id 全部丢掉

计划里的测试：

```python
request_id="request/中文 1"
```

期望目录：

```text
request_1
```

这是因为只保留：

```text
0-9 A-Z a-z _ -
```

这个规则可以接受，但要意识到：如果 request_id 是纯中文，比如：

```text
请求一
```

会被清洗成空字符串，然后回退到 `run_id`。这可能导致多个中文 request_id 都落到同一个目录。

建议改成更安全的规则之一：

**方案 A：保持当前规则，但文档和测试里明确：非 ASCII request_id 会被丢弃，空值回退 run_id。**

**方案 B：更推荐，保留 Unicode 字母数字：**

```python
safe = re.sub(r"[^\w-]+", "_", value, flags=re.UNICODE).strip("_")
```

不过 Windows 路径和跨平台兼容上，方案 A 更保守。

我的建议：**Phase 4 初版可以保留当前 ASCII 规则，但加一个测试：纯非法 request_id 回退 run_id。**

例如：

```python
def test_build_nl2sql_artifact_paths_falls_back_when_request_id_becomes_empty(tmp_path) -> None:
    paths = build_nl2sql_artifact_paths(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量", request_id="中文"),
        resolved_thread_id="thread-phase4",
    )

    assert paths.artifact_dir == tmp_path / "artifacts" / "nl2sql" / "run-phase4"
```

---

### 问题 2：`artifact_id = request_id else thread_id` 但 manifest 测试要确认 thread_id 仍保留

计划已经要求 manifest/input/output.metadata 同时保留 `request_id` 和 `thread_id`，这是对的。

但 Task 3 的主测试只断言了：

```python
manifest["thread_id"] == "thread-phase4"
manifest["request_id"] == "request-1"
manifest["artifact_id"] == "request-1"
```

这个够用。建议再补一个 fallback 场景，验证没有 request_id 时：

```text
artifact_id = thread_id 清洗结果
manifest.request_id = None
manifest.thread_id = 原始 resolved_thread_id
```

这样能防止实现时把 `artifact_id` 误当成 `thread_id`。

---

### 问题 3：`app.log` 检查命令可能误扫 artifact 文件

最终验证里有：

```powershell
.\.ai\local\tools\rg.exe "prompt_payload|User Question:|Schema Context:|result_rows" workspace\logs
```

它下面写了：

```text
It is acceptable if rg finds artifact JSON/TXT files under artifacts/
```

但这个命令本身会扫整个 `workspace/logs`，artifact 里肯定会出现这些内容，于是执行者会看到大量 matches，不好判断哪些来自 `app.log`。

建议改成只扫 `app.log`：

```powershell
Get-ChildItem -Path workspace\logs -Filter app.log -Recurse | ForEach-Object {
  Select-String -Path $_.FullName -Pattern "prompt_payload|User Question:|Schema Context:|result_rows"
}
```

或者如果用 rg：

```powershell
.\.ai\local\tools\rg.exe "prompt_payload|User Question:|Schema Context:|result_rows" workspace\logs --glob app.log
```

这个建议值得执行前改掉。

---

## 还有几个小的实现提醒

### 1. `graph.stream_config is graph.get_state_config` 这个测试很好

这个断言非常有价值：

```python
assert graph.stream_config is graph.get_state_config
```

它强制 `stream` 和 `get_state` 使用同一个 config 对象。

这能避免一个很隐蔽的问题：`stream` 用一个 thread_id，`get_state` 重新生成另一个 thread_id，最终拿不到刚才执行的状态。

---

### 2. `GraphRuntime.resolve_thread_id` 公开出来是对的

因为 `Nl2SqlWorkflow` 要在 started log 里写 resolved thread_id。如果它自己重新拼一遍，就会出现两个 thread_id 规则。

现在计划让 workflow 调用：

```python
self.graph_runtime.resolve_thread_id(...)
```

这很合理。

---

### 3. `Nl2SqlWorkflow` 的 `log_dir/logger` 默认值可以保留，但要注意测试过渡

计划里为了让旧测试容易迁移，给了：

```python
log_dir: Path | None = None
logger: Logger | None = None
```

这个可以接受。

不过长期看，`build_app` 创建出来的正式 workflow 应该一定有 `log_dir/logger`。所以 Task 6 的 container 注入是必须的。

---

### 4. `stream()` 不写 artifact 是正确的

计划明确：

```text
Do not write artifacts in stream(...); Phase 4 artifact writing belongs to run(...).
```

这个判断对。

因为 `stream()` 本来就是给调用方实时消费的。如果它也写 artifact，会引入两套路径和写入时机。Phase 4 初版只让 `run()` 自动产出完整 artifact，更清楚。

---

## 是否可以直接执行？

可以，但我建议先改这 3 处：

```text
1. 补 artifact_id 纯非法字符回退 run_id 的测试。
2. 补 request_id 缺失时 artifact_id 使用 thread_id，但 manifest 仍保留 thread_id 的测试。
3. 最终 app.log 检查命令改成只扫 app.log，不扫整个 artifacts 目录。
```

改完后就可以按 Task 1-8 执行。

---

## 最终判断

这份计划已经具备执行条件。它的关键优点是：

```text
1. 先扩 GraphRuntime，而不是让 workflow 自己处理 LangGraph stream/get_state。
2. artifact writer 独立，workflow 不直接 json.dump。
3. nodes 继续纯净。
4. graph_updates.jsonl 有明确标准化规则。
5. output.metadata 只放字符串路径和 null。
6. artifact 失败默认不影响业务 status。
7. token_usage 只预留 null，不创建假文件。
8. 最终验证覆盖架构边界。
```

一句话总结：

**可以执行。执行前把 artifact_id 边界测试和 app.log 检查命令补一下，会更稳。**

[1]: https://docs.langchain.com/oss/python/langgraph/streaming?utm_source=chatgpt.com "Streaming - Docs by LangChain"
[2]: https://docs.langchain.com/oss/python/langgraph/persistence?utm_source=chatgpt.com "Persistence - Docs by LangChain"
[3]: https://jsonlines.org/?utm_source=chatgpt.com "JSON Lines"
