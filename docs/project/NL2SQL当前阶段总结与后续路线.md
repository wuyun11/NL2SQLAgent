# NL2SQL 当前阶段总结与后续路线

> 本文用于阶段性回顾。
>
> 它不是执行计划，也不是下一阶段详细设计；目的是说明当前项目已经完成了什么，以及后续大概要解决哪些问题。

## 1. 当前项目已经做到了什么

目前项目已经完成了从 Phase 0 到 Phase 5 的基础建设。

这几阶段的核心价值不是“已经能生成真实 SQL”，而是：

```text
把 NL2SQL 项目从随手脚本，推进到一个可运行、可观察、可验证、边界相对清楚的工作流骨架。
```

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

当前 NL2SQL 主流程已经固定为：

```text
normalize_question
  -> build_prompt
  -> generate_sql
  -> check_sql
  -> execute_sql
  -> response
```

现在这些节点大部分仍然是 mock，但 workflow 的形状已经跑通。

这一步的意义是：

```text
后续真实能力应该替换节点内部能力，而不是重新发明流程入口。
```

### 1.3 prompt_payload 与 final_prompt

当前已经把 prompt 从一段简单字符串推进为结构化材料：

```text
task
question
schema_context
semantic_context
sql_policy
output_contract
debug
```

并且由 `prompt_builder` 统一渲染成最终提示词。

这一步解决的是：

```text
最终喂给 LLM 的内容可以被稳定检查。
prompt 的材料来源可以被拆开看。
后续 schema / semantic / policy 都有明确落点。
```

### 1.4 运行 artifact

当前每次 NL2SQL `run()` 都会写出：

```text
input.json
prompt_payload.json
final_prompt.txt
graph_updates.jsonl
output.json
manifest.json
```

这一步非常关键。

它让我们不再依赖：

```text
控制台输出
AI 转述
临时 print
手动翻 checkpoint
```

只要打开 artifact 目录，就能看到：

```text
用户输入是什么。
prompt_payload 是什么。
最终提示词是什么。
LangGraph 哪些节点产生了更新。
最终输出是什么。
```

这也是后续调试表定位、schema grounding、prompt 质量的基础。

### 1.5 数据契约

Phase 5 已经完成了几个重要收敛：

```text
options -> runtime_options
prompt_payload TypedDict
state 中 prompt_payload/runtime_options 类型明确
response metadata 与 artifact metadata 来源分开
nodes 不直接读 raw options
workflow 不手写 artifact metadata
```

这一步解决的是：

```text
不要让 dict[str, Any] 在项目里四处流转。
不要让 nodes、workflow、artifacts、metadata 互相污染。
不要太早引入 stage/service/protocol/context result 的重型壳。
```

当前项目的状态可以概括为：

```text
一个轻量、可观察、数据边界清楚的 NL2SQL LangGraph 骨架。
```

## 2. 当前还没有做什么

当前还没有做：

```text
真实 LLM 调用
真实数据库读取
真实 SQL 执行
真实 schema grounding
真实 semantic catalog
真实 SQL policy check
retry / repair
query plan
evaluation dataset
```

这些没有做是刻意的。

原因是：

```text
接 LLM 和接数据库本身不是当前项目最难的地方。
真正容易卡住的是：
用户问题进来后，系统如何理解问题、如何找到相关表、如何组织最终给 LLM 的上下文。
```

如果这个问题没想清楚，直接接 LLM 只会更快暴露混乱：

```text
模型生成错了，到底是 prompt 问题？
schema 给错了？
表没召回？
业务规则没给？
SQL policy 没约束？
还是模型本身不行？
```

所以当前阶段先不急着接 LLM 是合理的。

## 3. 参考项目给出的核心启发

参考项目的主线不是“自由 agent”，而是工程化 NL2SQL 流水线。

它真正有价值的部分包括：

```text
离线 schema 知识构建
在线 schema grounding
question/schema/semantic/feedback 分块
SQL 生成
SQL 校验
SQL 执行
失败反馈
```

其中最值得当前项目吸收的是：

```text
用户问题不能直接丢给 LLM。
必须先把问题映射到有限、可信、可解释的 schema_context。
```

也就是说，后续关键不是：

```text
怎么调用 LLM。
```

而是：

```text
LLM 应该看到哪些表？
为什么是这些表？
这些表的哪些字段和用户问题有关？
表之间有什么关系？
有哪些业务术语和默认规则？
哪些内容应该进入最终 prompt？
哪些内容只用于调试和解释？
```

参考项目也提醒我们不要照搬它的问题：

```text
不要太早引入过多 stage/service/protocol/result model。
不要让业务主线被壳淹没。
不要让 container 过早变成总配电箱。
不要让 mock 占位长期伪装成正式架构。
```

当前项目后续应该吸收参考项目的能力，而不是复制参考项目的结构重量。

## 4. 后续最关键的问题

后续真正要解决的是：

```text
用户问题进来之后，如何一步步形成最终传给 LLM 的提示词。
```

可以拆成几个子问题。

### 4.1 问题理解

首先要处理用户问题本身：

```text
原始问题是什么？
规整后的问题是什么？
是否为空？
是否明显需要澄清？
是否包含时间、指标、分组、排序、筛选等意图？
```

当前只有最简单的 `strip()`。

后续可以逐步设计：

```text
question.normalized
question.intent_summary
question.key_terms
question.filters
question.metrics
question.group_by
question.order_by
question.time_range
```

但第一版不一定要全部实现。

关键是：

```text
问题理解的产物应该能解释“为什么后面会找这些表”。
```

### 4.2 表定位

这是后续最重要的设计点。

用户问题进来后，系统需要找相关表。

第一版可以先不接向量库，也不接复杂 embedding。

可以先设计一个可观察的表定位流程：

```text
用户问题
  -> 提取关键词 / 业务词
  -> 匹配 schema table 描述 / 字段名 / 字段描述 / 业务别名
  -> 得到 candidate_tables
  -> 给出命中原因
  -> 写入 prompt_payload.schema_context
```

表定位结果不应该只是：

```text
["employee", "department"]
```

更应该包含：

```text
表名
命中原因
命中的字段或术语
置信度或排序依据
是否为主表
是否为辅助表
```

原因是：

```text
我们现在最关心的是最终 prompt 长什么样。
如果表定位不可解释，就很难判断 prompt 里的 schema_context 是否可信。
```

### 4.3 字段定位

找到表之后，还要决定给 LLM 哪些字段。

不要把全表所有字段无脑塞进 prompt。

字段定位需要回答：

```text
哪些字段和用户问题直接相关？
哪些字段是 join/filter/group/order 可能需要的？
哪些字段只是展示字段？
哪些字段虽然没被用户说出来，但业务规则需要？
```

第一版可以简单一些：

```text
相关表的全部字段进入 prompt。
同时在 artifact 中记录命中字段。
```

后续再优化为：

```text
直接相关字段优先展示。
辅助字段折叠或降级。
```

### 4.4 表关系补全

NL2SQL 里很多错误不是单表问题，而是 join 问题。

所以表定位后还要补：

```text
表与表之间如何关联？
外键是什么？
join path 是什么？
是否存在多条可能路径？
```

第一版可以先支持：

```text
从 schema catalog 中读取已有 relationship。
只把 candidate_tables 之间相关的关系放进 prompt。
```

暂时不做复杂 join path 搜索也可以。

### 4.5 业务语义补充

用户说的通常不是数据库字段名。

例如：

```text
活跃用户
有效订单
新客户
销售额
部门人数
```

这些需要 semantic_context。

后续要逐步明确：

```text
业务词对应哪些表字段？
默认过滤条件是什么？
指标口径是什么？
哪些规则应该进入 prompt？
哪些规则只是候选解释？
```

第一版可以先从配置或固定 mock catalog 开始，不急着做复杂语义系统。

### 4.6 最终 prompt 组装

最终目标仍然是看清楚：

```text
传给 LLM 的提示词到底是什么。
```

后续 prompt 应该从现在的结构继续演进为：

```text
Task
User Question
Question Understanding
Candidate Tables
Relevant Columns
Relationships
Semantic Rules
SQL Policy
Output Contract
```

其中每一块都应该能在 artifact 中看到结构化来源。

也就是说：

```text
final_prompt.txt 给人看最终效果。
prompt_payload.json 给人看材料来源。
graph_updates.jsonl 给人看每一步怎么产生。
```

## 5. 后续大致路线

我建议后续路线按下面顺序走。

### 阶段 A：问题理解与表定位设计

这是下一步最值得先做的设计。

目标不是写复杂代码，而是先明确：

```text
用户问题进入系统后，如何生成 candidate_tables。
candidate_tables 应该包含哪些字段。
表定位的 evidence 怎么表达。
这些内容如何进入 prompt_payload。
最终 prompt 应该长什么样。
artifact 里应该能看到哪些中间结果。
```

这一阶段可以只写设计文档，不急着实现。

### 阶段 B：最小 schema catalog

设计清楚后，再实现一个最小 schema catalog。

第一版可以先用本地固定数据或简单配置，不急着接真实数据库。

目标是让：

```text
schema_context 不再是随手 mock。
而是来自一个稳定的 schema catalog 结构。
```

这一步比接数据库重要。

因为真实数据库读取只是 schema catalog 的一个来源。

### 阶段 C：最小表定位流程

有了 schema catalog 后，实现最小 candidate table selection。

第一版可以先基于：

```text
表名
表描述
字段名
字段描述
业务别名
关键词匹配
```

暂时不需要向量库。

重点是：

```text
结果可解释。
artifact 可查看。
prompt 可验证。
```

### 阶段 D：prompt 结构升级

当 candidate_tables 出来后，升级 prompt_payload：

```text
question_understanding
candidate_tables
relevant_columns
relationships
selection_evidence
```

然后检查最终 prompt 是否符合预期。

这一阶段的验收重点不是 SQL 对不对，而是：

```text
给 LLM 的材料是否正确。
是否能解释为什么给这些表。
是否能排除明显无关表。
```

### 阶段 E：SQL policy check

在 LLM 之前或之后都可以推进 SQL policy。

这一步不是为了生成 SQL，而是为了确保未来生成结果有边界：

```text
只读
单语句
禁止 SELECT *
表字段白名单
LIMIT
```

如果没有 SQL policy，接 LLM 后很难判断生成结果是否可接受。

### 阶段 F：再接入 LLM

等前面的 prompt 材料稳定后，再接 LLM。

这时 LLM 接入会变得很薄：

```text
final_prompt -> model -> generated_sql
```

如果生成错了，也能从 artifact 里判断：

```text
是表定位错了？
字段没给够？
关系没给？
业务规则缺失？
还是模型没遵守输出契约？
```

## 6. 下一阶段建议

下一阶段建议先做：

```text
Phase 6：问题理解与表定位设计
```

它应该回答下面几个问题：

```text
1. 用户问题进入后，我们要提取哪些结构化信息？
2. schema catalog 最小需要包含哪些内容？
3. candidate table 的数据结构是什么？
4. table selection evidence 怎么表达？
5. 相关字段和关系怎么进入 prompt_payload？
6. artifact 中要新增哪些文件或字段来观察表定位过程？
7. 最终 prompt 应该升级成什么样？
```

Phase 6 仍然可以不做：

```text
真实 LLM
真实数据库
向量库
复杂 embedding
retry
真实 SQL execution
```

这样做的好处是：

```text
我们先把最容易卡住的“问题到表”的链路设计清楚。
再决定数据库、向量库、LLM 怎么接。
```

## 7. 当前阶段的一句话总结

当前项目已经完成了：

```text
可运行的工作流骨架
可检查的 prompt 结构
可落盘的运行 artifact
可控的数据契约边界
```

后续最重要的不是先接 LLM，而是设计：

```text
用户问题如何被理解，
相关表如何被找到，
这些结果如何变成最终提示词。
```

只要这条链路设计清楚，接数据库、接向量库、接 LLM 都会变成相对局部的实现问题。
