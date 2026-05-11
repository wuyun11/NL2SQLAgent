# Phase7 NL2SQL 真实运行产物说明

> 本文说明真实运行一次 NL2SQL workflow 后，`workspace/` 下面会产生哪些文件，以及如何通过这些文件判断当前代码执行效果。
>
> 本文不是新的设计方案，而是当前阶段的验收与查看指南。

## 1. 本次真实运行结果

本次使用项目当前配置真实调用 LLM，运行输入为：

```text
question: 按部门统计在职员工人数
request_id: phase7-real-question-001
run_id: phase7-real-run-20260511
thread_id: thread-phase7-real-run
```

运行结果为：

```text
status: success
model: glm-5
sql:
SELECT d.dept_nm, COUNT(e.emp_id) AS employee_count FROM hr_emp_base e JOIN hr_dept_dim d ON e.dept_id = d.dept_id WHERE e.emp_stat_cd = 'ACTIVE' GROUP BY d.dept_nm LIMIT 100
```

这个结果说明：

1. 当前 `build_app -> nl2sql_workflow.run` 可以真实跑通。
2. `build_prompt` 产出的 `final_prompt` 已经被传给真实 LLM。
3. `generate_sql` 已经不只是固定返回 `SELECT 1 AS value`。
4. LLM 能根据当前人工样例中的表、字段、关系、value binding 生成可读 SQL。

但也要注意：

1. 当前 `check_sql` 仍是 mock。
2. 当前 `execute_sql` 仍是 mock。
3. 因此 `output.json` 中的 `columns` / `rows` 只能说明流程走到了执行节点，不能代表真实数据库执行结果。
4. 当前 token usage 还没有接入，所以 `token_usage_path` 为 `null`。

## 2. 本次产物目录

本次真实运行产物目录是：

```text
F:\workspace\workspace_python\NL2SQLAgent\workspace\logs\20260511\phase7-real-run-20260511
```

目录结构如下：

```text
workspace/
  logs/
    20260511/
      phase7-real-run-20260511/
        app.log
        artifacts/
          nl2sql/
            phase7-real-question-001/
              input.json
              prompt_payload.json
              final_prompt.txt
              graph_updates.jsonl
              output.json
              manifest.json
```

其中：

```text
workspace/logs/{run_date}/{run_id}/app.log
```

是一次 run 的总日志。

```text
workspace/logs/{run_date}/{run_id}/artifacts/nl2sql/{request_id}/
```

是一次 NL2SQL 请求的结构化产物目录。

## 3. 每个文件怎么看

### 3.1 app.log

位置：

```text
workspace/logs/20260511/phase7-real-run-20260511/app.log
```

用于看一次 workflow 是否开始、是否结束、最终状态是什么、manifest 写到了哪里。

本次关键日志类似：

```text
NL2SQL workflow started ... request_id=phase7-real-question-001
NL2SQL workflow finished ... status=success ... artifact_manifest=...
```

如果以后运行失败，先看这里可以快速知道：

1. workflow 有没有真正启动。
2. 是否跑到了结束日志。
3. 最终状态是 `success` 还是 `failed`。
4. 对应 artifact 目录在哪里。

### 3.2 manifest.json

位置：

```text
artifacts/nl2sql/phase7-real-question-001/manifest.json
```

用于看一次请求的产物索引。

重点字段：

```text
status:
  当前请求最终状态。

duration_ms:
  当前请求耗时。

artifact_files:
  input / prompt_payload / final_prompt / graph_updates / output / manifest 的绝对路径。

sizes.graph_updates_rows:
  LangGraph stream 写入了多少条节点更新。

sizes.final_prompt_size_chars:
  final_prompt 的字符数。

sizes.result_rows_count:
  当前输出行数。

artifact_error:
  artifact 写入是否失败。
```

本次结果：

```text
status: success
duration_ms: 24537
graph_updates_rows: 6
final_prompt_size_chars: 959
result_rows_count: 1
artifact_error: null
```

### 3.3 input.json

位置：

```text
artifacts/nl2sql/phase7-real-question-001/input.json
```

用于看进入 workflow 的原始请求。

重点看：

```text
request_id
thread_id
question
database
options
```

如果后续同一个问题跑出了不同结果，先确认 `input.json` 是否真的一致。

### 3.4 prompt_payload.json

位置：

```text
artifacts/nl2sql/phase7-real-question-001/prompt_payload.json
```

用于看结构化 prompt payload。

这是当前阶段最重要的调试文件之一。

它回答的是：

```text
最终提示词里的内容是从哪些结构化字段来的？
```

重点看：

```text
question:
  用户问题的 raw / normalized 表达。

schema_context.tables:
  允许 LLM 使用哪些表。

schema_context.relationships:
  允许 LLM 使用哪些 join 关系。

schema_context.value_bindings:
  业务词如何绑定到具体字段和值。

semantic_context.business_terms:
  当前问题涉及哪些业务术语。

sql_policy:
  SQL 约束，例如只读、禁止 SELECT *、要求 LIMIT。

output_contract:
  输出格式约束。
```

对于当前样例，最关键的是：

```text
在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
hr_emp_base.dept_id = hr_dept_dim.dept_id
```

这两个信息进入了 prompt，所以 LLM 生成 SQL 时才能写出：

```text
WHERE e.emp_stat_cd = 'ACTIVE'
JOIN hr_dept_dim d ON e.dept_id = d.dept_id
```

### 3.5 final_prompt.txt

位置：

```text
artifacts/nl2sql/phase7-real-question-001/final_prompt.txt
```

用于看真正发送给 LLM 的最终提示词。

这是判断当前提示词效果的第一入口。

当前样例中的关键内容包括：

```text
User Question:
按部门统计在职员工人数

Allowed tables:
- hr_emp_base
- hr_dept_dim

Relationships:
- hr_emp_base.dept_id = hr_dept_dim.dept_id

Value Bindings:
- 在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE

Output Contract:
- Return only one SQL statement.
- Do not include markdown fences.
- Do not explain the SQL.
```

如果后续 LLM 生成的 SQL 不符合预期，优先检查：

1. 相关表是否进入 `Allowed tables`。
2. 相关字段是否进入表字段列表。
3. join 关系是否进入 `Relationships`。
4. 业务值绑定是否进入 `Value Bindings`。
5. 输出约束是否清晰。

### 3.6 graph_updates.jsonl

位置：

```text
artifacts/nl2sql/phase7-real-question-001/graph_updates.jsonl
```

用于看 LangGraph 每个节点的流式更新。

本次节点顺序为：

```text
normalize_question
build_prompt
generate_sql
check_sql
execute_sql
success_response
```

这个文件适合排查：

1. workflow 是否按预期路径执行。
2. 某个节点到底写入了哪些 state 字段。
3. 失败时是停在 `build_prompt`、`generate_sql`、`check_sql` 还是 `execute_sql`。
4. `generate_sql` 是否写入了 `generated_sql` / `llm_result` / `generate_error`。

当前文件是 JSON Lines 格式，不是一个完整 JSON 数组。查看时可以逐行读，也可以按 node 过滤。

### 3.7 output.json

位置：

```text
artifacts/nl2sql/phase7-real-question-001/output.json
```

用于看最终响应。

重点字段：

```text
status:
  success / failed。

message:
  面向调用方的结果消息。

sql:
  最终生成的 SQL。

columns / rows:
  当前执行节点返回的数据。现阶段仍是 mock。

metadata.prompt_payload:
  本次结构化 prompt payload。

metadata.final_prompt:
  本次最终提示词。

metadata.processed_question:
  当前样例 ProcessedQuestion。

metadata.processed_database_knowledge:
  当前样例 ProcessedDatabaseKnowledge。

metadata.knowledge_retrieval_result:
  知识召回结果。

metadata.schema_linking_result:
  schema linking 结果。

metadata.sql_generation_context:
  进入 prompt payload 前的 SQL 生成上下文。

metadata.llm_result:
  LLM 模型名与原始输出。

metadata.generate_error:
  LLM 生成失败时的错误信息。
```

当前阶段建议重点看：

```text
metadata.processed_question
metadata.processed_database_knowledge
metadata.knowledge_retrieval_result
metadata.schema_linking_result
metadata.sql_generation_context
metadata.final_prompt
metadata.llm_result.raw_text
sql
```

这条链路可以回答当前项目最核心的问题：

```text
人工设计的 ProcessedQuestion + ProcessedDatabaseKnowledge
是否能够通过中间层算法收敛成 LLM 能用的 final_prompt，
并最终让 LLM 生成符合预期的 SQL？
```

## 4. 如何判断当前代码执行效果

建议按下面顺序看。

### 4.1 先看是否跑通

看：

```text
manifest.json.status
output.json.status
app.log
```

如果都是 `success`，说明 workflow 主链路跑通。

### 4.2 再看 prompt 是否符合预期

看：

```text
final_prompt.txt
prompt_payload.json
```

判断：

1. 用户问题是否正确进入 prompt。
2. 允许使用的表是否合理。
3. 字段是否足够生成 SQL。
4. join 关系是否明确。
5. value binding 是否明确。
6. SQL policy 是否明确。

当前样例中，`final_prompt` 已经包含部门维表、员工基础表、部门 join、在职员工状态绑定。

### 4.3 再看 LLM 输出是否符合 prompt

看：

```text
output.json.sql
output.json.metadata.llm_result.raw_text
```

本次 LLM 生成 SQL 使用了：

```text
hr_emp_base
hr_dept_dim
dept_id join
emp_stat_cd = 'ACTIVE'
COUNT(e.emp_id)
GROUP BY d.dept_nm
LIMIT 100
```

这些都能追溯到 `final_prompt` 中的结构化信息，所以本次结果对当前阶段是有效的。

### 4.4 最后看节点链路是否干净

看：

```text
graph_updates.jsonl
```

本次节点顺序符合预期：

```text
normalize_question -> build_prompt -> generate_sql -> check_sql -> execute_sql -> success_response
```

如果后续出现失败，可以用这个文件定位失败发生在哪个节点。

## 5. 当前阶段的边界

当前项目已经适合验证：

```text
ProcessedQuestion + ProcessedDatabaseKnowledge
  -> 中间层召回与 linking
  -> SqlGenerationContext
  -> final_prompt
  -> LLM 生成 SQL
```

当前项目还不适合验证：

```text
真实数据库执行结果是否正确
SQL 语法检查是否严格
SQL 安全策略是否完整
token usage 统计是否完整
任意自然语言问题是否都能自动生成 ProcessedQuestion
任意数据库 schema 是否都能自动生成 ProcessedDatabaseKnowledge
```

所以现阶段验收重点不是“数据库查出来的数据对不对”，而是：

```text
我们设计的中间层对象，能不能稳定地产生可解释、可检查、能影响 LLM 的 final_prompt。
```

## 6. 常用查看命令

查看本次 artifact 文件：

```powershell
$dir = "F:\workspace\workspace_python\NL2SQLAgent\workspace\logs\20260511\phase7-real-run-20260511\artifacts\nl2sql\phase7-real-question-001"
Get-ChildItem $dir
```

查看最终提示词：

```powershell
Get-Content "$dir\final_prompt.txt" -Encoding UTF8
```

查看最终输出：

```powershell
Get-Content "$dir\output.json" -Encoding UTF8
```

查看节点顺序：

```powershell
Get-Content "$dir\graph_updates.jsonl" -Encoding UTF8 | ForEach-Object { ($_ | ConvertFrom-Json).node }
```

查看总日志：

```powershell
Get-Content "F:\workspace\workspace_python\NL2SQLAgent\workspace\logs\20260511\phase7-real-run-20260511\app.log" -Encoding UTF8
```

## 7. 对收尾评审的结论

从本次真实运行看，当前代码主线没有跑偏：

1. LLM 接入在 `SqlGenerator` 依赖中，不在 LangGraph node 里直接初始化 provider。
2. 是否真实调用 LLM 由装配配置决定，没有在业务输入里增加 `use_llm_generate`。
3. LangGraph 仍然负责流程路径，`generate_sql` 失败后会进入失败响应分支。
4. 运行产物已经能看清 `ProcessedQuestion + ProcessedDatabaseKnowledge` 到 `final_prompt` 再到 SQL 的链路。
5. `.pytest_tmp/` 是当前统一测试临时目录，后续不要再引入 `.pytest-temp/` 或 `.pytest-tmp/`。

当前可以进入下一步，但下一步不要急着扩大架构。

更合适的后续工作是继续围绕人工样例验证：

```text
不同 ProcessedQuestion
不同 ProcessedDatabaseKnowledge
不同 value binding / relationship / metric / dimension
```

是否都能稳定产生符合预期的 `final_prompt` 和 SQL。
