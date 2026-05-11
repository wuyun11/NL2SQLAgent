# Phase8 NL2SQL 人工样例验证设计

> 本文设计下一阶段如何用多组人工样例验证当前 NL2SQL 链路。
>
> 当前阶段不追求完整 NL2SQL，也不追求自动生产 `ProcessedQuestion` / `ProcessedDatabaseKnowledge`。
>
> 当前阶段只验证：人工中间层对象能否稳定影响 `final_prompt`，并让 LLM 生成符合预期的 SQL。

## 1. 为什么下一步不是直接写更复杂样例

当前已经跑通一条真实 LLM 调用链路：

```text
ProcessedQuestion
  + ProcessedDatabaseKnowledge
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> PromptPayload
  -> FinalPrompt
  -> LLM
  -> generated_sql
```

第一条真实样例是：

```text
按部门统计在职员工人数
```

它验证了：

```text
2 表 join
value binding: 在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
dimension: 部门
metric: 员工人数
```

但这条样例比较理想，不能说明当前中间层设计已经稳定。

下一步如果直接写复杂样例，例如 4-5 表 join、时间窗口、同比环比、嵌套聚合，会把很多风险混在一起：

```text
ProcessedQuestion 字段是否够用？
ProcessedDatabaseKnowledge 字段是否够用？
structured matcher 是否召回正确？
SchemaLinkingResult 是否收敛正确？
SqlGenerationContext 是否组织正确？
final_prompt 是否表达清楚？
LLM 是否遵守提示词？
```

一旦 SQL 生成不好，很难判断是哪一层的问题。

所以下一步不应该追求复杂度，而应该追求：

```text
有目的地覆盖关键风险。
每个样例只验证少量明确能力。
每个失败都能定位到具体层。
```

## 2. 当前阶段目标

当前阶段目标是构造一组人工样例，用来回答：

```text
我们设计的 ProcessedQuestion + ProcessedDatabaseKnowledge，
能不能通过当前中间层算法，
稳定产生可解释、可检查、能影响 LLM 的 final_prompt？
```

进一步说，当前阶段要验证：

```text
1. 该进入 final_prompt 的表、字段、关系、value binding 能进去。
2. 不该进入 final_prompt 的候选不会进去。
3. final_prompt 能给 LLM 足够信息。
4. LLM 生成的 SQL 能追溯到 final_prompt 中的结构化信息。
5. SQL 生成失败时，能通过 artifact 判断问题在哪一层。
```

当前阶段不验证：

```text
真实数据库执行结果。
复杂 SQL repair。
SQL 性能。
自动从自然语言生成 ProcessedQuestion。
自动从未知数据库生成 ProcessedDatabaseKnowledge。
向量召回。
历史 SQL 模板。
多轮对话。
```

## 3. 样例设计原则

### 3.1 样例不是越多越好

样例数量建议控制在 5-8 个。

原因是当前需要人工观察：

```text
prompt_payload
final_prompt
schema_linking_result
generated_sql
expected_sql
```

样例太多会降低评审质量。

当前更重要的是每个样例都能说明一个明确问题。

### 3.2 先横向覆盖风险，再纵向增加复杂度

样例优先覆盖不同风险类型，而不是不断加表、加字段、加 SQL 技巧。

推荐顺序：

```text
单表基础
两表 join
业务值绑定
业务指标口径
干扰候选过滤
弱信息或歧义问题
```

等这些基础风险跑稳，再考虑：

```text
三表 join
时间条件
多指标
排序 TopN
同比环比
```

### 3.3 每个样例必须能定位失败原因

每个样例都要提前写清楚：

```text
期望召回哪些 candidate。
期望选择哪些 table / column / relationship / value binding。
期望哪些候选被 dropped。
期望 final_prompt 中出现哪些关键内容。
期望 SQL 大致长什么样。
```

否则 LLM 生成不理想时，只能靠感觉判断。

## 4. 样例分层

### 4.1 L1 单表基础样例

目的：

```text
验证不需要 join 时，系统不会过度引入无关表。
```

示例问题：

```text
统计在职员工人数
```

期望：

```text
selected_tables:
  hr_emp_base

relevant_columns:
  hr_emp_base.emp_id
  hr_emp_base.emp_stat_cd

value_bindings:
  在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE

relationships:
  none

final_prompt:
  不应该出现 hr_dept_dim 作为必须 join 的表。
```

参考 SQL：

```sql
SELECT COUNT(emp_id) AS employee_count
FROM hr_emp_base
WHERE emp_stat_cd = 'ACTIVE'
LIMIT 100
```

这个样例可以验证：

```text
value binding 能不能独立生效。
没有部门维度时是否还会错误 join 部门表。
```

### 4.2 L2 两表 join 样例

目的：

```text
验证人工 relationship 能否稳定进入 final_prompt，并影响 SQL join。
```

示例问题：

```text
按部门统计在职员工人数
```

期望：

```text
selected_tables:
  hr_emp_base
  hr_dept_dim

relationships:
  hr_emp_base.dept_id = hr_dept_dim.dept_id

value_bindings:
  在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE

final_prompt:
  必须出现部门名称字段、员工表、部门表、join 关系、在职状态绑定。
```

参考 SQL：

```sql
SELECT d.dept_nm, COUNT(e.emp_id) AS employee_count
FROM hr_emp_base e
JOIN hr_dept_dim d ON e.dept_id = d.dept_id
WHERE e.emp_stat_cd = 'ACTIVE'
GROUP BY d.dept_nm
LIMIT 100
```

这个样例已经真实跑通过，但仍应保留为回归样例。

### 4.3 L3 业务值绑定样例

目的：

```text
验证不同业务词能绑定到不同字段值。
```

示例问题：

```text
按部门统计离职员工人数
```

为了支持这个样例，需要人工知识层包含：

```text
离职员工 -> hr_emp_base.emp_stat_cd = INACTIVE
```

期望：

```text
value_bindings:
  离职员工 -> hr_emp_base.emp_stat_cd = INACTIVE

final_prompt:
  不应该仍然使用 ACTIVE。

generated_sql:
  WHERE e.emp_stat_cd = 'INACTIVE'
```

这个样例可以验证：

```text
value binding 不是写死在“在职员工”上。
同一字段不同业务值能否正确影响 SQL。
```

### 4.4 L4 业务指标口径样例

目的：

```text
验证 metric hint / business term 是否足够表达业务口径。
```

示例问题：

```text
统计正式员工人数
```

这个样例需要先人工定义口径。

例如：

```text
正式员工:
  hr_emp_base.emp_type_cd = FULL_TIME
```

或者：

```text
正式员工:
  hr_emp_base.emp_type_cd = FULL_TIME
  hr_emp_base.emp_stat_cd = ACTIVE
```

这里的关键不是立刻决定最终业务规则，而是验证当前对象设计能否表达：

```text
一个业务词可能对应多个字段约束。
一个指标可能依赖业务口径，而不只是 COUNT(id)。
```

如果当前字段设计表达困难，就说明后续需要增强 `value_bindings` 或 `semantic_context`。

### 4.5 L5 干扰候选样例

目的：

```text
验证 dropped_candidates 不会绕过 SchemaLinkingResult 进入 final_prompt。
```

示例问题：

```text
统计员工导入记录中的在职员工人数
```

这个问题可能召回：

```text
hr_emp_base
tmp_import_record
```

如果当前业务目标仍然是统计员工主数据，而不是临时导入表，则期望：

```text
selected_tables:
  hr_emp_base

dropped_candidates:
  tmp_import_record

final_prompt:
  不出现 tmp_import_record 作为 allowed table。
```

这个样例用于验证：

```text
candidate 被召回不等于可以进入 final_prompt。
final_prompt 只消费 SchemaLinkingResult 选中的内容。
```

### 4.6 L6 歧义问题样例

目的：

```text
验证信息不足时，系统如何暴露假设，而不是让 LLM 自由猜。
```

示例问题：

```text
统计员工人数
```

可能存在歧义：

```text
统计全部员工？
统计在职员工？
是否按当前有效状态过滤？
```

当前阶段可以选择一个保守策略：

```text
如果 ProcessedQuestion 没有业务词“在职员工”，就不要自动加 ACTIVE。
```

期望：

```text
value_bindings:
  none

semantic_context.assumptions:
  可以记录“未限定员工状态，默认统计全部员工”。

final_prompt:
  不应该凭空出现 emp_stat_cd = ACTIVE。
```

这个样例用于验证：

```text
中间层对象没有给的信息，LLM 不应该被 prompt 暗示成确定事实。
```

## 5. 每个样例的数据契约

建议每个样例都包含下面字段。

```text
case_id:
  样例 ID。

title:
  样例名称。

risk_focus:
  这个样例主要验证什么风险。

raw_question:
  用户原始问题。

processed_question:
  人工构造的 ProcessedQuestion。

knowledge_scope:
  本样例使用的 ProcessedDatabaseKnowledge。
  初版可以复用一份共享知识层，也可以在样例里声明增量知识。

expected_retrieval:
  期望召回的 KnowledgeCandidate。

expected_schema_linking:
  期望 selected_tables / relevant_columns / relationships / value_bindings / dropped_candidates。

expected_prompt_contains:
  final_prompt 必须包含的关键文本。

expected_prompt_excludes:
  final_prompt 不应该包含的关键文本。

expected_sql_shape:
  期望 SQL 的结构，不要求逐字符一致。

reference_sql:
  人工参考 SQL。

review_notes:
  人工评审备注。
```

其中最重要的是：

```text
expected_schema_linking
expected_prompt_contains
expected_prompt_excludes
expected_sql_shape
```

因为这四项能把失败定位到不同层：

```text
schema linking 错了:
  看 expected_schema_linking。

schema linking 对，但 prompt 少了:
  看 expected_prompt_contains / excludes。

prompt 对，但 SQL 不对:
  看 expected_sql_shape 和 LLM 输出。
```

## 6. SQL 评审方式

当前不要做自动 SQL 等价判断。

原因是：

```text
SQL 等价判断很复杂。
当前也没有真实数据库执行。
不同模型生成的 alias、COUNT 字段、换行格式可能不同。
```

当前使用人工评审即可。

评审维度：

```text
1. 是否只使用 final_prompt 允许的表。
2. 是否使用正确 join。
3. 是否使用正确 value binding。
4. 是否使用正确聚合。
5. 是否使用正确 group by。
6. 是否遵守 readonly。
7. 是否遵守 LIMIT。
8. 是否没有 markdown fence 和解释文本。
```

可以把评审结果分成：

```text
pass:
  SQL 符合样例目标。

minor_diff:
  SQL 可接受，但和 reference_sql 有轻微差异。

fail_prompt_missing:
  prompt 没给够信息。

fail_linking:
  schema linking 选错或漏选。

fail_llm:
  prompt 信息足够，但模型没有遵守。

fail_case_design:
  样例本身定义不清。
```

## 7. Artifact 查看要求

每个样例运行后，至少要能看到：

```text
input.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
output.json
manifest.json
```

人工评审时建议按顺序看：

```text
1. manifest.json
   确认运行成功、artifact 路径正确。

2. output.json.metadata.processed_question
   确认人工问题对象符合样例设计。

3. output.json.metadata.processed_database_knowledge
   确认知识层包含样例需要的事实。

4. output.json.metadata.knowledge_retrieval_result
   看候选是否被召回。

5. output.json.metadata.schema_linking_result
   看候选是否被正确选择或丢弃。

6. prompt_payload.json
   看进入 prompt 的结构化数据是否正确。

7. final_prompt.txt
   看 LLM 真正看到什么。

8. output.json.metadata.llm_result.raw_text / output.json.sql
   看模型实际生成什么。
```

这套顺序可以避免只盯着 SQL 结果，而忽略中间层到底有没有给对信息。

## 8. 初版样例矩阵

建议初版先做 6 个样例。

| case_id | 问题 | 风险焦点 | 复杂度 |
| --- | --- | --- | --- |
| `case_001_active_employee_count` | 统计在职员工人数 | 单表 + value binding | 低 |
| `case_002_active_employee_by_department` | 按部门统计在职员工人数 | 两表 join + value binding | 低 |
| `case_003_inactive_employee_by_department` | 按部门统计离职员工人数 | 同字段不同业务值 | 中 |
| `case_004_full_time_employee_count` | 统计正式员工人数 | 业务口径表达 | 中 |
| `case_005_drop_import_table` | 统计员工导入记录中的在职员工人数 | 干扰候选过滤 | 中 |
| `case_006_ambiguous_employee_count` | 统计员工人数 | 歧义与默认假设 | 中 |

其中：

```text
case_001 / case_002:
  应作为基础回归样例。

case_003:
  验证 value binding 的可扩展性。

case_004:
  验证字段设计能否表达业务口径。

case_005:
  验证 dropped candidate 不进入 final_prompt。

case_006:
  验证系统不会替用户补充没有给出的业务约束。
```

暂时不建议加入：

```text
同比环比
复杂时间窗口
三表以上 join
子查询
窗口函数
历史 SQL 模板
向量召回
```

这些可以等 6 个基础样例稳定后再加。

## 9. 对代码实现的要求

后续执行时，不建议大改当前架构。

更合适的是最小增加：

```text
人工样例定义
样例加载器
样例运行入口
样例评审记录
必要的测试
```

仍然要保持：

```text
LangGraph 负责流程。
build_prompt 负责中间层消费。
generate_sql 只负责 final_prompt -> SQL。
SqlGenerator 负责 provider 调用。
artifact 负责记录可观察产物。
```

不要引入：

```text
新的 Stage / Chain / Orchestration 层。
use_llm_generate。
自动 schema grounding。
向量库。
历史 SQL 模板。
真实数据库执行强依赖。
```

## 10. 验收标准

当前阶段完成时，应该能做到：

```text
1. 至少 6 个样例可以被单独运行。
2. 每个样例都能生成 artifact。
3. 每个样例都能看到 prompt_payload 和 final_prompt。
4. 每个样例都能看到 generated_sql 和 llm_result。
5. 每个样例都有 expected prompt / SQL shape。
6. 至少能人工标注 pass / minor_diff / fail_*。
7. 失败能定位到 retrieval / schema linking / prompt / LLM / case design。
8. 默认测试不调用真实 LLM。
9. 真实 LLM 样例运行必须是显式命令。
10. `.pytest_tmp/` 仍然是统一测试临时目录。
```

## 11. 下一步建议

下一步应该写一份执行计划，交给 agent 实现。

计划应优先做：

```text
1. 定义样例文件结构。
2. 写 2 个最小样例，先不接真实 LLM。
3. 让样例能复用现有 workflow 生成 artifact。
4. 加默认测试，验证 prompt contains / excludes。
5. 再补足 6 个样例。
6. 最后提供显式真实 LLM 运行命令。
```

这样可以保证：

```text
先验证样例机制。
再验证样例覆盖。
最后才消耗真实 LLM token 看生成效果。
```
