# Phase7 LLM 接入实现修复建议

> 本文基于当前未提交代码和 `docs/superpowers/plans/2026-05-11-nl2sql-llm-sql-generation.md` 对照检查。
>
> 目标不是重新设计 Phase7，而是判断当前实现是否需要修复、哪些可以接受、哪些先不动。

## 1. 当前实施状态

当前 Phase7 实现已经基本落地。

已完成的主要内容：

```text
1. config/model.yml 已新增。
2. pyproject.toml 已增加 langchain-core / langchain-openai。
3. SqlGenerator / FakeSqlGenerator / OpenAICompatibleSqlGenerator 已新增。
4. generate_sql_node 已改为调用注入的 sql_generator。
5. route_after_generate 已新增。
6. llm_result / generate_error 已进入 state 和 response metadata。
7. tests/cloud 已新增。
8. 架构保护测试已开始覆盖 use_llm_generate / heavy path / nodes.py provider 依赖。
```

已验证：

```text
python -m compileall src tests
  通过

python -m pytest -q
  135 passed

python -m pytest tests/cloud -q
  1 skipped
```

说明：

```text
当前代码不是半成品状态，而是进入“实现完成后修边界和评审”的状态。
```

## 2. 建议必须修复

### 2.1 cloud 测试默认隔离方式需要和计划口径对齐

当前实现：

```toml
[tool.pytest.ini_options]
testpaths = ["tests/unit", "tests/integration"]
markers = [
    "cloud: tests that call remote LLM services and consume token",
]
```

这个能保证：

```text
pytest -q
```

不跑 cloud。

但它不能保证：

```text
pytest tests/cloud -q
```

默认 deselect cloud。当前行为是进入 cloud 测试，然后因为没有 `DASHSCOPE_API_KEY` 而 skip。

建议修成：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-m not cloud"
markers = [
    "cloud: tests that call remote LLM services and consume token",
]
```

然后显式 cloud 运行仍然使用：

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/cloud -q -m cloud
```

为什么必须修：

```text
1. 计划中明确要求 cloud 测试默认不运行。
2. 只靠 testpaths 排除默认集合，容易让直接运行 tests/cloud 的人误触远端调用。
3. addopts = "-m not cloud" 更符合 pytest marker 隔离语义。
```

验收命令：

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest -q
& $py -m pytest tests/cloud -q
& $py -m pytest tests/cloud -q -m cloud
```

期望：

```text
pytest -q:
  非 cloud 测试通过。

pytest tests/cloud -q:
  cloud 测试 deselected。

pytest tests/cloud -q -m cloud:
  有 key 则运行；无 key 则 skip。
```

### 2.2 OpenAI provider 依赖建议懒加载

当前实现：

```python
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
```

这两个 import 在 `sql_generator.py` 模块加载时发生。

建议修成：

```text
FakeSqlGenerator / SqlGenerator / cleanup helper 的导入不触发 langchain_openai import。
OpenAICompatibleSqlGenerator 真正调用远端模型时，再导入 ChatOpenAI。
```

可接受写法：

```python
def _ensure_chat(self):
    from langchain_openai import ChatOpenAI
    ...
```

`HumanMessage` 也可以一起懒加载，或直接让 chat model 接收字符串输入，具体以当前依赖实际可用方式为准。

为什么建议修：

```text
1. 当前普通测试和 fake generator 也会 import langchain_openai。
2. Phase7 设计强调 provider 细节只属于 OpenAICompatibleSqlGenerator。
3. 懒加载能减少非 cloud 路径对 provider 包的耦合。
4. 这是一处低成本边界修复。
```

验收：

```text
tests/unit/workflows/nl2sql/test_sql_generator.py 通过。
普通 pytest -q 通过。
```

### 2.3 架构保护测试需要补全 provider 相关禁词

当前测试：

```python
for token in ("ChatOpenAI", "DASHSCOPE_API_KEY"):
    assert token not in source
```

建议补成：

```python
for token in (
    "ChatOpenAI",
    "DASHSCOPE_API_KEY",
    "api_key",
    "base_url",
    "langchain_openai",
    "os.environ",
):
    assert token not in source
```

为什么建议修：

```text
1. 设计文档要求 nodes.py 不接触 provider 细节。
2. 当前 nodes.py 本身是干净的，补测试不会推动代码复杂化。
3. 能防止后续 agent 把模型初始化塞回 nodes.py。
```

### 2.4 secret 保护测试建议覆盖 app.log

当前已有：

```text
test_nl2sql_workflow_run_does_not_leak_api_key_into_artifacts
```

它覆盖了：

```text
final_prompt.txt
prompt_payload.json
graph_updates.jsonl
output.json
input.json
```

但设计文档验收标准是：

```text
真实 API key 不进入 graph state / artifact / app.log。
```

建议补充：

```text
如果当前测试 run 产生 app.log，则读取 app.log 并断言 fake secret 不存在。
```

为什么建议修：

```text
1. 设计文档明确提到了 app.log。
2. 当前实现看起来没有泄漏，但测试没有锁住这个边界。
3. 后续有人加日志时容易无意输出 provider 配置或异常上下文。
```

## 3. 建议暂不修复

### 3.1 暂不强制给 build_app 增加 sql_generator override

计划里建议：

```python
build_app(..., sql_generator=FakeSqlGenerator(...))
```

当前实现选择了另一种方式：

```text
config/model.yml:
  model.sql_generator.provider = fake / openai_compatible
```

这和原计划不完全一致，但可以接受。

原因：

```text
1. fake / real 仍然是装配差异，不是业务输入。
2. 没有引入 use_llm_generate。
3. graph.py 仍然通过注入的 sql_generator 工作。
4. 测试可以通过临时 model.yml 选择 fake provider。
```

暂不修的理由：

```text
1. 现在为了严格对齐 plan 增加 build_app 参数，收益不大。
2. build_app 是外部入口，少一个测试专用参数反而更稳。
3. 如果后续测试或 app 构建确实需要更直接的依赖注入，再加也不迟。
```

需要保留的边界：

```text
fake provider 只能是部署/测试配置。
不能把 fake / real 切换放进 Nl2SqlInput.options 或 runtime_options。
```

### 3.2 暂不移动 sql_generator.py 到 platform/infrastructure

当前：

```text
src/nl2sqlagent/workflows/nl2sql/sql_generator.py
```

这和设计文档一致。

暂不移动的理由：

```text
1. 当前只有 NL2SQL generate_sql 节点使用它。
2. 提前抽到 platform/llm 或 infrastructure/llm 会增加抽象层。
3. 参考项目的问题之一就是抽象偏早、装配中心过重。
```

后续触发条件：

```text
如果第二个 workflow 也需要 chat model，再考虑迁移为公共 provider。
```

### 3.3 暂不引入 token usage

当前没有实现 token usage，这是正确的。

不要为了 LLM 接入顺手加：

```text
token_usage
token_usage.json
token_usage.log
```

后续应单独结合：

```text
LangGraph callback
LangSmith
stream event
模型响应 metadata
```

统一设计。

## 4. 其他需要清理的点

### 4.1 清理错误命名的临时产物，并统一使用 `.pytest_tmp/`

当前 git status 中出现：

```text
?? .pytest-temp/
```

这个目录名不符合当前项目约定。

当前项目规则见：

```text
.ai/guide/10_运行方式.md
.gitignore
```

约定的 pytest 临时目录是：

```text
.pytest_tmp/
```

不是：

```text
.pytest-temp/
.pytest-tmp/
```

如果出现 `.pytest-temp/`，应视为执行过程中的错误临时产物。

建议：

```text
删除 .pytest-temp/
后续测试命令统一使用 --basetemp .pytest_tmp
```

原因：

```text
1. .pytest-temp/ 不是项目约定目录。
2. .pytest_tmp/ 已列入 .gitignore。
3. 统一 basetemp 能避免 Windows 环境下系统临时目录权限问题。
```

### 4.2 提交前需要确认未跟踪文档归属

当前还有以下未跟踪/修改文档：

```text
docs/project/Phase7_NL2SQL_LLM接入设计.md
docs/temp/Phase7_LLM接入前置口径统计.md
docs/superpowers/plans/2026-05-11-nl2sql-llm-sql-generation.md
docs/architecture/ProcessedQuestion与ProcessedDatabaseKnowledge当前协作说明.md
docs/project/NL2SQL当前阶段总结与后续路线.md
docs/temp/其他ai评价.md
docs/temp/问题.md deleted
```

这些不一定都属于 Phase7 代码提交。

建议在提交前分清：

```text
1. Phase7 LLM 接入设计和 plan 是否一起提交。
2. docs/temp/其他ai评价.md 是否只是外部评价记录。
3. docs/temp/问题.md 删除是否是用户确认过的状态。
4. architecture 当前协作文档是否属于另一阶段。
```

不要在 Phase7 代码提交里混入无关文档，除非用户明确要一起提交。

## 5. 建议修复任务清单

建议交给执行 agent 的修复顺序：

```text
Task 1:
  修改 pyproject.toml：
    testpaths = ["tests"]
    addopts = "-m not cloud"
  验证 pytest -q / pytest tests/cloud -q / pytest tests/cloud -q -m cloud。

Task 2:
  将 langchain_openai.ChatOpenAI 和 langchain_core.messages.HumanMessage 改为懒加载。
  保持 FakeSqlGenerator 不触发 provider import。

Task 3:
  加强 nodes.py provider 边界测试：
    ChatOpenAI
    DASHSCOPE_API_KEY
    api_key
    base_url
    langchain_openai
    os.environ

Task 4:
  secret non-leak 测试增加 app.log 覆盖。

Task 5:
  清理错误命名的 .pytest-temp/。
  后续测试命令统一带 --basetemp .pytest_tmp。

Task 6:
  重新运行：
    python -m compileall src tests
    python -m pytest -q --basetemp .pytest_tmp
    python -m pytest tests/cloud -q --basetemp .pytest_tmp
    python -m pytest tests/cloud -q -m cloud --basetemp .pytest_tmp
```

## 6. 最终判断

当前 Phase7 实现方向是对的，不需要大改。

我建议修复：

```text
1. cloud marker 默认隔离。
2. provider lazy import。
3. 架构保护测试补全。
4. app.log secret 保护。
5. 清理错误命名的临时目录，并统一使用 .pytest_tmp/。
```

我不建议现在修：

```text
1. 强行增加 build_app(sql_generator=...) override。
2. 移动 sql_generator.py 到公共基础设施目录。
3. 引入 token usage。
4. 引入 Chain / Stage / Orchestration。
```

一句话：

```text
这次不是架构路线错了，而是实现已经完成后，需要把“默认不碰 cloud、provider 不污染普通路径、secret 不外泄、测试护栏更完整”这几个边界补牢。
```
