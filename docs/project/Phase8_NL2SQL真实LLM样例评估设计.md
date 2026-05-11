# Phase8 NL2SQL 真实 LLM 样例评估设计

> 本文设计如何由 AI 助手运行真实 LLM 样例，并基于 artifact 自动整理评估结论。
>
> 这里的“评估”不是 pytest 自动断言，也不是人工肉眼评审。
>
> 目标是让 AI 助手按固定流程读取样例期望和运行产物，判断同一样例多次运行是否稳定、不同样例输出是否符合预期，并输出一份可复查的评价文档。

## 1. 背景

当前 Phase8 已经具备：

```text
人工样例文件:
  examples/nl2sql_cases/phase8_cases.json

样例运行入口:
  python -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases

真实 LLM 显式运行:
  --real-llm

运行产物:
  workspace/logs/{run_date}/{run_id}/artifacts/nl2sql/{case_id}/
```

fake generator 已经验证了：

```text
case -> workflow -> prompt -> artifact
```

真实 LLM 样例评估要验证的是：

```text
当前 final_prompt 能不能稳定约束模型生成 SQL。
```

也就是说，真实 LLM 评估不是验证数据库结果，而是验证：

```text
模型输出是否受 ProcessedQuestion + ProcessedDatabaseKnowledge + SchemaLinkingResult + final_prompt 控制。
```

## 2. 当前不引入人工评估环节

当前不设计“人工逐条打分”的流程。

原因：

```text
1. 当前样例已经写了 expected_prompt_contains / expected_prompt_excludes / expected_sql_shape / reference_sql。
2. artifact 已经记录 prompt_payload / final_prompt / schema_linking_result / llm_result。
3. AI 助手可以基于这些结构化证据做第一轮评估。
4. 人工评估容易变成临时口径，难以复用。
```

但这不代表评估完全自动化。

更准确地说，当前采用：

```text
AI 助手执行评估。
评估依据来自样例期望和 artifact。
评估结果写成文档，供人复查。
```

AI 助手不能只凭“看起来差不多”判断通过。

它必须把结论追溯到：

```text
expected_schema_linking
expected_prompt_contains
expected_prompt_excludes
expected_sql_shape
reference_sql
final_prompt.txt
output.json.metadata.llm_result.raw_text
output.json.metadata.schema_linking_result
```

## 3. 评估要回答的问题

真实 LLM 评估需要回答两类问题。

### 3.1 单个样例是否符合预期

对每个 case，需要判断：

```text
1. workflow 是否 success。
2. final_prompt 是否包含 expected_prompt_contains。
3. final_prompt 是否不包含 expected_prompt_excludes。
4. schema_linking_result 是否满足 expected_schema_linking。
5. LLM raw_text 是否只是一条 SQL。
6. LLM raw_text 是否没有 markdown fence。
7. LLM raw_text 是否没有解释文本。
8. SQL 是否包含 expected_sql_shape 的核心要素。
9. SQL 是否只使用 final_prompt 允许的表。
10. SQL 是否没有使用 expected_prompt_excludes 排除的表。
11. SQL 是否使用了正确 value binding。
12. SQL 是否使用了正确 join。
13. SQL 是否遵守 LIMIT 要求。
```

### 3.2 同一样例多次运行是否稳定

对同一个 case，多次真实 LLM 运行后，需要判断：

```text
1. raw_text 是否每次都是 SQL only。
2. 使用的表是否一致。
3. 使用的 join 是否一致。
4. 使用的 value binding 是否一致。
5. 聚合粒度是否一致。
6. LIMIT 是否一致或等价。
7. alias / 换行 / 表名前缀差异是否只是格式差异。
```

稳定不要求逐字符一致。

例如下面两条可以视为稳定：

```sql
SELECT d.dept_nm, COUNT(e.emp_id)
FROM hr_emp_base e
JOIN hr_dept_dim d ON e.dept_id = d.dept_id
WHERE e.emp_stat_cd = 'ACTIVE'
GROUP BY d.dept_nm
LIMIT 100
```

```sql
SELECT hr_dept_dim.dept_nm, COUNT(hr_emp_base.emp_id)
FROM hr_emp_base
JOIN hr_dept_dim ON hr_emp_base.dept_id = hr_dept_dim.dept_id
WHERE hr_emp_base.emp_stat_cd = 'ACTIVE'
GROUP BY hr_dept_dim.dept_nm
LIMIT 100
```

它们的结构一致，只是 alias 风格不同。

## 4. 运行策略

### 4.1 初次全量运行

首次真实 LLM 评估建议跑全部 6 个样例，每个样例 1 次。

命令：

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --run-id phase8-real-llm-all-v1
```

目的：

```text
确认 6 个样例在真实模型下是否都能产出 SQL。
确认是否存在明显 fail case。
确认 prompt 对不同风险类型是否有效。
```

### 4.2 稳定性运行

如果首次全量运行没有明显失败，再挑选 2-3 个代表性样例多跑几次。

推荐重复样例：

```text
case_002_active_employee_by_department:
  两表 join + value binding。

case_005_drop_import_table:
  干扰候选过滤。

case_006_ambiguous_employee_count:
  歧义问题，不应凭空加 ACTIVE。
```

推荐每个样例跑 3 次。

命令示例：

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()

& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_002_active_employee_by_department --run-id phase8-real-repeat-case002-r1
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_002_active_employee_by_department --run-id phase8-real-repeat-case002-r2
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_002_active_employee_by_department --run-id phase8-real-repeat-case002-r3
```

这种方式会产生多个 run_id，便于逐次比较 artifact。

### 4.3 是否一次跑全部样例多轮

不建议初版直接跑：

```text
6 cases x 3 rounds = 18 次 LLM 调用
```

原因：

```text
1. 成本更高。
2. 输出更多，评估更慢。
3. 如果第一轮就发现 prompt 问题，多轮运行没有意义。
```

所以推荐：

```text
第一步:
  6 cases x 1 round

第二步:
  2-3 key cases x 3 rounds
```

## 5. AI 助手评估流程

AI 助手执行评估时，按固定顺序进行。

### 5.1 收集输入

读取：

```text
examples/nl2sql_cases/phase8_cases.json
```

获取：

```text
case_id
title
risk_focus
raw_question
expected_schema_linking
expected_prompt_contains
expected_prompt_excludes
expected_sql_shape
reference_sql
```

### 5.2 执行真实 LLM 运行

执行：

```powershell
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --run-id {run_id}
```

要求：

```text
1. run_id 必须明确。
2. 不要覆盖不相关 run。
3. 保存命令输出中的 artifact_manifest_path。
4. 如果某个 case status != success，也要继续记录失败信息。
```

### 5.3 读取 artifact

对每个 case，读取：

```text
manifest.json
output.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
```

重点字段：

```text
output.status
output.sql
output.metadata.llm_result.model_name
output.metadata.llm_result.raw_text
output.metadata.schema_linking_result
output.metadata.prompt_payload
```

### 5.4 生成单 case 评估

AI 助手对每个 case 输出：

```text
case_id
title
risk_focus
status
model
artifact_dir
final_prompt_key_points
llm_raw_text
reference_sql
verdict
evidence
issues
```

其中 `verdict` 只能取：

```text
pass:
  SQL 符合样例目标。

minor_diff:
  SQL 与 reference_sql 有格式、alias、COUNT 表达等轻微差异，但语义符合。

fail_prompt_missing:
  final_prompt 没给够信息。

fail_linking:
  schema_linking_result 选错、漏选或错误保留候选。

fail_llm:
  final_prompt 信息足够，但 LLM 没遵守。

fail_output_contract:
  LLM 输出不是 SQL only，包含解释、markdown fence 或多条语句。

fail_case_design:
  样例期望本身不清楚，无法判定。

run_failed:
  workflow 或 provider 调用失败。
```

### 5.5 生成稳定性评估

如果同一个 case 有多次 run，AI 助手要整理：

```text
case_id
runs
sql_outputs
stable_dimensions
unstable_dimensions
stability_verdict
```

`stability_verdict` 只能取：

```text
stable:
  多次输出结构一致，只存在格式或 alias 差异。

acceptable_variation:
  有轻微 SQL 表达差异，但不影响语义。

unstable:
  多次输出在表、join、value binding、聚合粒度、过滤条件上不一致。

not_enough_runs:
  运行次数不足，不能判断稳定性。
```

## 6. AI 助手判断规则

当前不引入 SQL parser。

AI 助手先使用文本级和结构级检查。

### 6.1 输出格式检查

fail 条件：

```text
raw_text 为空。
raw_text 包含 ```。
raw_text 明显包含解释文本，例如 “下面是 SQL”、“这个查询会”。
raw_text 包含多条 SQL 语句。
```

### 6.2 表使用检查

从 `final_prompt.txt` 中读取 allowed tables。

判断 SQL 是否只使用这些表。

如果 SQL 使用了 `expected_prompt_excludes` 排除的表，判定：

```text
fail_llm
```

如果 final_prompt 本身包含了不该出现的表，判定：

```text
fail_linking
```

或：

```text
fail_prompt_missing
```

具体取决于 `schema_linking_result` 是否已经错了。

### 6.3 value binding 检查

对 expected value binding：

```text
hr_emp_base.emp_stat_cd=ACTIVE
hr_emp_base.emp_stat_cd=INACTIVE
hr_emp_base.emp_type_cd=FULL_TIME
```

检查 SQL 中是否出现对应字段和值。

允许：

```text
emp_stat_cd = 'ACTIVE'
hr_emp_base.emp_stat_cd = 'ACTIVE'
e.emp_stat_cd = 'ACTIVE'
```

不允许：

```text
ACTIVE 错成 INACTIVE。
没有过滤条件。
在歧义样例中凭空加入 ACTIVE。
```

### 6.4 join 检查

对 expected relationship：

```text
hr_emp_base.dept_id=hr_dept_dim.dept_id
```

检查 SQL 中是否存在等价 join。

允许 alias：

```text
e.dept_id = d.dept_id
hr_emp_base.dept_id = hr_dept_dim.dept_id
```

当前 AI 助手可以结合 SQL 文本和 reference_sql 进行判断。

如果判断不确定，不能强行 pass，应标记：

```text
minor_diff
```

并说明不确定点。

### 6.5 聚合与粒度检查

对 count 类样例：

```text
必须出现 COUNT。
```

对按部门统计：

```text
必须出现部门名称或部门字段。
必须出现 GROUP BY 部门字段。
```

对非分组总数：

```text
不应出现不必要 GROUP BY。
```

### 6.6 LIMIT 检查

当前 SQL policy 要求：

```text
require_limit = true
default_limit = 100
```

所以真实 LLM 输出应包含：

```text
LIMIT 100
```

没有 LIMIT 时，通常判定：

```text
fail_llm
```

除非 final_prompt 没有包含 LIMIT 要求，那就是：

```text
fail_prompt_missing
```

## 7. 评价文档格式

AI 助手最终输出评价文档到：

```text
docs/temp/Phase8_真实LLM样例运行评估.md
```

建议结构：

```markdown
# Phase8 真实 LLM 样例运行评估

## 1. 运行信息

- run_id
- run_date
- model
- cases_path
- command
- artifact root

## 2. 总体结论

- pass 数量
- minor_diff 数量
- fail 数量
- run_failed 数量
- 当前最主要问题

## 3. 单样例评估

### case_001_xxx

- question
- risk_focus
- verdict
- artifact_dir
- final_prompt 关键证据
- LLM raw output
- reference_sql
- 判断依据
- 问题归因

## 4. 稳定性评估

### case_002_xxx

- runs
- outputs
- stability_verdict
- stable_dimensions
- unstable_dimensions

## 5. 结论与下一步

- 是改 ProcessedQuestion？
- 是改 ProcessedDatabaseKnowledge？
- 是改 schema linking？
- 是改 prompt？
- 还是只是模型输出差异可接受？
```

## 8. 推荐首次执行方案

首次执行建议：

```text
Step 1:
  跑全部 6 个样例，每个 1 次。

Step 2:
  AI 助手读取 artifact，生成单样例评估。

Step 3:
  如果全部 pass/minor_diff，再挑 2-3 个样例做三轮稳定性运行。

Step 4:
  AI 助手补充稳定性评估。
```

具体命令：

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()

& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases `
  --real-llm `
  --run-id phase8-real-llm-all-v1
```

如果需要稳定性运行：

```powershell
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_002_active_employee_by_department --run-id phase8-real-repeat-case002-r1
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_002_active_employee_by_department --run-id phase8-real-repeat-case002-r2
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_002_active_employee_by_department --run-id phase8-real-repeat-case002-r3

& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_005_drop_import_table --run-id phase8-real-repeat-case005-r1
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_005_drop_import_table --run-id phase8-real-repeat-case005-r2
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_005_drop_import_table --run-id phase8-real-repeat-case005-r3

& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_006_ambiguous_employee_count --run-id phase8-real-repeat-case006-r1
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_006_ambiguous_employee_count --run-id phase8-real-repeat-case006-r2
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_006_ambiguous_employee_count --run-id phase8-real-repeat-case006-r3
```

## 9. 当前不做的事情

当前不做：

```text
1. 不把真实 LLM 结果写成 pytest 断言。
2. 不做 SQL AST 等价判断。
3. 不执行真实数据库。
4. 不做自动评分器服务。
5. 不引入 LangSmith。
6. 不根据一次失败就修改 prompt。
7. 不因为 alias 不同判定失败。
```

当前要做的是：

```text
让 AI 助手能够按固定证据链评估真实 LLM 输出，
并把评估结论沉淀成可复查文档。
```
