# NL2SQL 当前阶段总结与后续路线

> 本文用于阶段性回顾。
>
> 它不是执行计划，也不是下一阶段详细设计；目的是说明当前项目已经完成了什么，以及后续大概要验证什么。

## 1. 当前项目已经做到了什么

当前项目已经从一个基础 LangGraph 骨架，推进到了一条可观察的 NL2SQL 中间层消费链路。

当前最重要的主线是：

```text
ProcessedQuestion
  + ProcessedDatabaseKnowledge
  -> KnowledgeRetrievalResult
  -> SchemaLinkingResult
  -> SqlGenerationContext
  -> PromptPayload
  -> FinalPrompt
```

也就是说，项目现在已经不是只会拼一个 mock prompt。

它已经可以用人工设计的中间层对象，经过候选召回、schema linking、SQL 生成上下文构造，最后生成可查看的 `final_prompt`。

### 1.1 运行底座

当前已经具备：

```text
配置加载
项目路径解析
run_id / run_date
日志目录
app.log
bootstrap/build_app
LangGraph checkpointer
```

这些能力解决的是：

```text
项目怎么启动。
一次运行怎么定位。
日志写到哪里。
后续 workflow 怎么被统一装配。
```

### 1.2 LangGraph 工作流骨架

当前 NL2SQL 主流程是：

```text
normalize_question
  -> build_prompt
  -> generate_sql
  -> check_sql
  -> execute_sql
  -> response
```

其中：

```text
normalize_question:
  仍然只是基础 strip 和空问题判断。

build_prompt:
  已经接入中间层消费链路。

generate_sql:
  当前仍然是 SELECT 1 AS value 的 mock。

check_sql / execute_sql:
  当前仍然是 mock，用于跑通工作流形状。
```

这一步的意义是：

```text
后续接 LLM 时，只需要优先替换 generate_sql_node。
不要在接 LLM 时重新搅动前面的知识层消费链路。
```

### 1.3 中间层对象链路

当前已经新增并落地了核心数据契约：

```text
ProcessedQuestion
ProcessedDatabaseKnowledge
KnowledgeCandidate
KnowledgeRetrievalResult
SchemaLinkingResult
SqlGenerationContext
```

当前本地实现里，`ProcessedQuestion` 和 `ProcessedDatabaseKnowledge` 仍然来自人工样例：

```text
build_initial_processed_question()
build_sample_processed_database_knowledge()
```

这两个函数是临时样例入口，不是真正的问题理解或知识生产。

但它们现在足够用于验证一个更关键的问题：

```text
如果我人工设计好了 ProcessedQuestion 和 ProcessedDatabaseKnowledge，
系统能不能把它们稳定转换成适合 LLM 生成 SQL 的 final_prompt？
```

### 1.4 Knowledge Retrieval

当前已经有 structured matcher，可以产出：

```text
KnowledgeRetrievalResult
  candidates
  warnings
  metadata
```

它的职责是：

```text
只负责召回候选。
不负责最终选表。
不负责组装 prompt。
不直接进入 final_prompt。
```

这层已经验证了一个重要边界：

```text
后续即使引入 vector candidate，
也不能绕过 SchemaLinkingResult 直接进入 SqlGenerationContext / PromptPayload / FinalPrompt。
```

### 1.5 Schema Linking

当前已经能从候选和中间层知识中得到：

```text
selected_tables
relevant_columns
selected_relationships
value_bindings
evidence
dropped_candidates
warnings
```

当前样例问题：

```text
按部门统计在职员工人数
```

可以得到：

```text
hr_emp_base
hr_dept_dim
hr_emp_base.emp_id
hr_emp_base.emp_stat_cd
hr_emp_base.dept_id
hr_dept_dim.dept_id
hr_dept_dim.dept_nm
hr_emp_base.dept_id = hr_dept_dim.dept_id
在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
```

同时已经补过一个关键修复：

```text
如果没有 candidates，也没有 metric_hints / dimension_hints，
schema linking 不应该无条件塞入 HR 样例表字段。
```

### 1.6 SqlGenerationContext / PromptPayload / FinalPrompt

当前 `final_prompt` 已经来自：

```text
SqlGenerationContext -> PromptPayload -> FinalPrompt
```

而不是直接从 retrieval candidates 或 dropped candidates 拼出来。

当前 final prompt 已经能看到：

```text
User Question
Allowed tables
Relevant columns
Relationships
Value Bindings
Semantic Context
SQL Policy
Output Contract
```

示例中已经包含类似内容：

```text
Table: hr_emp_base
  Columns:
  - emp_stat_cd (filter): required by value binding
  - emp_id (measure): metric hint employee_count
  - dept_id (join_key): join key from selected relationship

Table: hr_dept_dim
  Columns:
  - dept_nm (dimension): dimension hint department
  - dept_id (join_key): join key from selected relationship

Relationships:
- hr_emp_base.dept_id = hr_dept_dim.dept_id

Value Bindings:
- 在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
```

这一步很重要。

因为下一阶段要验证的不是“能不能调用 LLM”，而是：

```text
这样设计 ProcessedQuestion 和 ProcessedDatabaseKnowledge，
最终形成的 prompt 是否足够让 LLM 生成符合预期的 SQL。
```

### 1.7 运行 artifact

当前每次 NL2SQL `run()` 都会写出：

```text
input.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
output.json
manifest.json
```

当前 artifact 可以观察：

```text
用户输入
prompt_payload
final_prompt
LangGraph 节点更新
最终 output
processed_question
processed_database_knowledge
knowledge_retrieval_result
schema_linking_result
sql_generation_context
```

这让下一阶段验证 LLM 输出时有足够证据判断：

```text
SQL 生成不好，是 prompt 给少了？
字段设计不够？
value binding 不清楚？
relationship 不清楚？
还是模型本身没按要求输出？
```

## 2. 当前还没有做什么

当前还没有做：

```text
真实 LLM 调用
真实数据库读取
真实 SQL 执行
真实 RawUserQuestion -> ProcessedQuestion
真实 RawDatabaseSchema -> ProcessedDatabaseKnowledge
真实 schema grounding
真实 semantic catalog
真实 SQL policy check
retry / repair
query plan
evaluation dataset
```

这些没有做是刻意的。

其中尤其要注意：

```text
ProcessedQuestion 怎么从用户原始问题得出，是非常复杂的事情。
ProcessedDatabaseKnowledge 怎么从真实数据库和人工治理得出，也是非常复杂的事情。
```

下一步暂时不应该把重点放在这两个对象的生产过程上。

更合理的下一步是：

```text
先假设这两个对象已经由人工设计好。
然后验证它们能不能支撑 LLM 生成正确或接近正确的 SQL。
```

## 3. 当前阶段的核心判断

当前项目最重要的判断是：

```text
先验证中间层对象是否能支撑 SQL 生成，
再讨论中间层对象如何自动生产。
```

原因是：

```text
如果人工设计的 ProcessedQuestion + ProcessedDatabaseKnowledge
都不能让 LLM 生成理想 SQL，
那就说明对象字段、上下文组织或 prompt 结构还不对。

这时候去做自动问题理解、自动知识抽取、向量召回，
只会把不确定性继续放大。
```

所以当前后续路线应该收敛为：

```text
人工样例
  -> final_prompt
  -> LLM generated_sql
  -> artifact 观察
  -> 反推中间层字段和 prompt 是否需要调整
```

而不是马上进入：

```text
真实数据库解析
自动 schema 知识构建
向量库
复杂问题理解
```

## 4. 后续最关键的问题

下一阶段要回答的问题是：

```text
我人工设计的 ProcessedQuestion 和 ProcessedDatabaseKnowledge，
经过当前 pipeline 后形成的 final_prompt，
能不能让 LLM 生成我期望的 SQL？
```

这个问题可以拆成几个子问题。

### 4.1 样例是否足够代表目标场景

下一阶段需要先设计几组人工样例。

每组样例包含：

```text
ProcessedQuestion
ProcessedDatabaseKnowledge
期望观察点
可选：参考 SQL
```

样例不要太多。

第一批更适合覆盖：

```text
单表聚合
两表 join
value binding 过滤
时间过滤
维度分组
无关候选被丢弃
```

### 4.2 final_prompt 是否给够 SQL LLM 材料

需要观察：

```text
表是否明确。
字段是否明确。
字段角色是否明确。
join 关系是否明确。
value binding 是否足够清楚。
SQL policy 是否约束到位。
Output Contract 是否足够避免解释性文本。
```

如果 LLM 生成不好，优先判断：

```text
是不是 final_prompt 材料不足。
是不是字段描述不够。
是不是业务值绑定不够明确。
是不是指标口径缺失。
是不是输出契约不够强。
```

而不是先怀疑：

```text
是不是要上向量。
是不是要上复杂 agent。
是不是要先自动生成 ProcessedQuestion。
```

### 4.3 generated_sql 应该如何进入 artifact

下一阶段接 LLM 后，至少要能在 artifact 里看到：

```text
final_prompt.txt
prompt_payload.json
generated_sql
model 信息
可选 token usage
可选 raw model response
```

当前已经有 `output.json` 和 `graph_updates.jsonl`，初版可以继续复用。

不要一开始就设计复杂评测系统。

先做到：

```text
我能打开 artifact，
看到这次 prompt 是什么，
LLM 返回 SQL 是什么。
```

### 4.4 是否需要执行 SQL

下一阶段可以先不执行真实 SQL。

原因是当前目标不是验证数据库结果，而是验证：

```text
中间层对象 + prompt 是否能让 LLM 生成合理 SQL。
```

初版可以只做轻量检查：

```text
不是空字符串
没有 markdown fence
是单条 SQL
只读倾向
包含预期表名
包含预期字段或条件
```

真实 SQL 执行可以后置。

## 5. 后续大致路线

### 阶段 A：人工中间层样例集

先不要设计 `ProcessedQuestion` 和 `ProcessedDatabaseKnowledge` 的自动来源。

先手写几组样例：

```text
员工部门统计
有效订单金额统计
客户维度聚合
时间范围过滤
无关表候选丢弃
```

每组样例都应该能回答：

```text
这个问题需要哪些表？
哪些字段是 measure / dimension / filter / join_key？
哪些 value binding 必须进入 WHERE？
哪些 relationship 必须进入 JOIN？
最终希望 SQL 大概长什么样？
```

### 阶段 B：最薄 LLM SQL 生成节点

把当前：

```text
generate_sql_node -> SELECT 1 AS value
```

替换或旁路为最薄的 LLM 调用：

```text
final_prompt -> LLM -> generated_sql
```

这一层初版只负责：

```text
读取 final_prompt
调用模型
拿到文本
写入 generated_sql
```

不要让 LLM 在这里重新做 schema linking。

不要让 LLM 直接读取 `KnowledgeRetrievalResult`。

### 阶段 C：SQL 输出观察与轻量检查

先不做复杂 SQL 执行。

初版检查：

```text
SQL 非空
没有 markdown fence
不是解释文本
只包含一条语句
包含 selected_tables
包含 value_bindings 对应条件
包含 selected_relationships 对应 join 条件
```

这些检查更多是为了帮助观察，不是为了替代人工判断。

### 阶段 D：反推中间层字段设计

拿到 LLM 生成 SQL 后，再反过来看：

```text
ProcessedQuestion 字段是否够用？
ProcessedDatabaseKnowledge 字段是否够用？
SchemaLinkingResult 是否保留了必要信息？
SqlGenerationContext 是否过少或过多？
PromptPayload 是否组织清楚？
FinalPrompt 是否把关键内容表达清楚？
```

这一阶段才是当前项目真正有价值的验证。

如果 SQL 生成效果不好，优先调整：

```text
中间层字段
字段描述
value binding 表达
relationship 表达
prompt 组织方式
output contract
```

而不是马上扩大到自动知识生产。

### 阶段 E：再讨论中间层对象来源

只有当人工中间层样例已经能稳定支撑 SQL 生成后，再讨论：

```text
RawUserQuestion -> ProcessedQuestion
RawDatabaseSchema / Manual Metadata -> ProcessedDatabaseKnowledge
```

这两个问题很重要，但应该后置。

因为它们本质上是在回答：

```text
如何生产高质量中间层对象？
```

而当前更基础的问题是：

```text
什么样的中间层对象才算高质量？
它们能不能支撑 SQL 生成？
```

## 6. 下一阶段建议

下一阶段建议命名为：

```text
LLM SQL 生成验证
```

它的目标不是完整 NL2SQL。

它只验证：

```text
人工 ProcessedQuestion
人工 ProcessedDatabaseKnowledge
当前 knowledge pipeline
当前 final_prompt
LLM generated_sql
```

建议验收标准：

```text
1. 至少有 2-3 组人工中间层样例。
2. 每组样例都能生成 final_prompt。
3. final_prompt 能进入 LLM。
4. generated_sql 能写入 output / artifact。
5. artifact 能同时看到 prompt_payload、final_prompt、generated_sql。
6. 至少能人工比较 generated_sql 与参考 SQL 的差异。
7. 不引入真实数据库执行作为硬依赖。
8. 不设计 RawUserQuestion -> ProcessedQuestion 的自动生产。
9. 不设计 RawDatabaseSchema -> ProcessedDatabaseKnowledge 的自动生产。
```

## 7. 当前阶段的一句话总结

当前项目已经完成了：

```text
人工中间层对象
  -> 候选召回
  -> schema linking
  -> SQL 生成上下文
  -> prompt payload
  -> final prompt
```

下一步最重要的是验证：

```text
这些人工设计的 ProcessedQuestion 和 ProcessedDatabaseKnowledge，
能不能通过当前 prompt 让 LLM 生成符合预期的 SQL。
```

只有这个验证成立后，才值得继续讨论：

```text
ProcessedQuestion 如何自动得出。
ProcessedDatabaseKnowledge 如何从真实数据库和人工治理中得出。
是否要引入向量、历史 SQL、辅助 LLM 或更复杂的知识生产流程。
```
