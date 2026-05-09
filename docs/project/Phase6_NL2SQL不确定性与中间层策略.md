# Phase 6 NL2SQL 不确定性与中间层策略

> 本文是 Phase 6 前的讨论文档。
>
> 它不直接设计代码，也不直接决定是否接入 LLM / 数据库；它先讨论一个更上层的问题：
>
> ```text
> 当输入本身不可靠时，我们是直接处理，还是增加中间层先消化不确定性？
> ```

## 1. 问题背景

NL2SQL 项目里有两个最明显的不确定性来源：

```text
1. 用户问题不确定。
2. 数据库结构不确定。
```

用户问题可能存在：

```text
口语化
省略上下文
业务词不标准
指标口径不明确
时间范围模糊
筛选条件隐含
```

数据库结构也可能存在：

```text
没有外键
没有详细注释
字段名不表达业务含义
表名不表达业务含义
一张表有太多字段
历史表/临时表/冗余表很多
字段值编码不透明
```

这两个问题本质上很像：

```text
系统收到的不是干净、结构化、可信的输入。
```

因此核心问题不是：

```text
怎么把问题丢给 LLM？
```

而是：

```text
哪些不确定性应该在进入最终 SQL LLM 之前被消化？
哪些不确定性可以留给最终 SQL LLM？
哪些不确定性必须由人工或离线流程处理？
```

## 2. 直接处理 vs 增加中间层

面对不确定性，大致有两种路线。

### 2.1 直接处理

直接路线是：

```text
用户问题 + 数据库原始 schema
  -> SQL LLM
  -> SQL
```

优点：

```text
实现最快。
流程最短。
早期 demo 容易做。
```

缺点：

```text
所有不确定性都压到最后一个 LLM。
数据库没有外键时，LLM 要猜 join。
数据库没有注释时，LLM 要猜字段含义。
用户问题模糊时，LLM 要猜业务意图。
生成错了以后，很难判断是哪里错。
```

这种方式适合：

```text
小库
表字段命名非常规范
问题非常标准
只做演示
```

不适合：

```text
真实业务数据库
外键缺失
注释缺失
字段编码复杂
需要可解释和可维护的场景
```

### 2.2 增加中间层

中间层路线是：

```text
用户问题
  -> 问题理解层
  -> schema knowledge layer
  -> schema linking / context building
  -> final prompt
  -> SQL LLM
```

它不要求数据库本身完美。

它的目标是：

```text
把原始输入中的不确定性，提前转成更稳定、更可解释的结构化上下文。
```

优点：

```text
最终 LLM 看到的是经过筛选和解释的上下文。
表、字段、关系、业务规则可以追踪来源。
prompt 出错时能定位是表选错、字段缺失、关系缺失，还是模型没遵守约束。
可以逐步引入人工维护、LLM 辅助、规则和历史 SQL。
```

缺点：

```text
系统复杂度增加。
需要设计中间层的数据结构。
需要维护 schema knowledge。
需要处理知识来源冲突。
需要额外 artifact 观察中间结果。
```

所以中间层不是免费午餐。

它的价值取决于：

```text
它是否真的减少了最终 LLM 需要猜的东西。
它增加的复杂度是否可控。
它的产物是否可观察、可维护、可复用。
```

## 3. 原理：不要把所有不确定性押注到一个 LLM

NL2SQL 失败时，常见问题不是模型完全不会写 SQL。

更常见的是：

```text
模型不知道该用哪张表。
模型不知道字段是什么意思。
模型不知道字段值编码。
模型不知道表之间怎么 join。
模型不知道业务词对应什么过滤条件。
模型拿到了太多无关表，被干扰了。
```

如果我们把这些都交给最后一个 SQL LLM，它就同时承担：

```text
理解用户问题
理解数据库
猜关系
猜字段值
判断业务规则
生成 SQL
遵守安全策略
遵守输出格式
```

这相当于把所有不确定性押注到一个模型调用中。

这会带来几个问题：

```text
1. 不稳定：同一个问题可能多次生成不同选择。
2. 不可解释：不知道为什么选了某张表。
3. 不可维护：业务规则变了，只能改 prompt。
4. 不可测试：很难单独测试“表定位是否正确”。
5. 难复盘：SQL 错了以后，不知道是哪个中间判断错。
```

因此更好的方向是：

```text
让 LLM 参与，但不要让最终 SQL LLM 独自承担所有不确定性。
```

LLM 可以用于：

```text
辅助生成表注释
辅助生成字段注释
辅助发现可能的表关系
辅助提取用户问题中的指标/维度/过滤条件
辅助扩展业务词
```

但这些结果最好先进入中间层，并标记来源和可信度。

最终 SQL LLM 应该消费的是：

```text
经过确认或筛选的上下文。
```

而不是直接面对原始混乱。

## 4. 数据库侧的中间层：Schema Knowledge Layer

对于数据库不确定性，建议引入：

```text
Schema Knowledge Layer
```

它不是数据库本身，也不是 prompt 字符串。

它是数据库原始结构经过补充、治理、确认后的知识层。

### 4.1 它要解决什么

真实数据库经常没有：

```text
外键
注释
清晰命名
字段值含义
业务口径
```

Schema Knowledge Layer 就是为了解决这些缺口。

它应该回答：

```text
这张表代表什么业务对象？
这个字段是什么意思？
这个字段有哪些重要取值？
哪些表之间可以关联？
关联字段是什么？
哪些表是事实表？
哪些表是维表？
哪些表不应该进入 NL2SQL？
```

### 4.2 它的数据来源

Schema Knowledge Layer 可以由多种来源组成：

```text
数据库自动提取：
  表名、字段名、类型、索引、已有外键、样例值。

人工维护：
  表注释、字段注释、业务别名、确认过的外键、禁用表、推荐 join。

LLM 辅助：
  根据表名字段名和样例值生成注释候选。
  根据字段命名推测可能的关系候选。
  根据业务文档生成术语候选。

历史 SQL：
  常见 join 关系。
  常用过滤条件。
  常见指标和维度。

业务配置：
  semantic.yml。
  value hints。
  指标口径。
```

### 4.3 来源优先级

建议明确可信度顺序：

```text
人工确认 > 数据库原始约束 > 历史 SQL 统计 > LLM 生成候选 > 临场推断
```

LLM 生成的内容可以很有用，但不应该默认等同于事实。

每条知识最好有：

```text
source
confidence
verified
updated_at
```

例如：

```json
{
  "from_table": "hr_emp_base",
  "from_column": "dept_id",
  "to_table": "hr_dept_dim",
  "to_column": "dept_id",
  "source": "manual",
  "verified": true
}
```

这样后续出错时能判断：

```text
是数据库原始信息错？
是人工配置错？
是 LLM 候选没确认就用了？
还是在线表定位选错了？
```

## 5. 用户问题侧的中间层：Processed Question

数据库需要中间层，用户问题也一样。

原始用户问题不一定适合直接进入 schema linking。

例如：

```text
看看这个月每个部门的人数
最近订单怎么样
哪些客户比较重要
```

这些问题里有很多隐含信息。

因此可以引入：

```text
Processed Question
```

它负责把原始问题转成更适合检索 schema 的结构。

### 5.1 它要解决什么

Processed Question 应该回答：

```text
用户问的核心对象是什么？
用户要的指标是什么？
用户要按什么维度分组？
用户有哪些过滤条件？
有没有时间范围？
有没有排序、topN、比较、趋势？
是否需要澄清？
```

第一版不需要全部自动化。

可以先只做：

```text
raw
normalized
keywords
business_terms
```

后续再逐步扩展。

### 5.2 它和 LLM 的关系

问题理解可以用规则，也可以用 LLM。

但同样不应该把 LLM 输出直接当最终事实。

更合理的是：

```text
LLM / 规则 / 用户显式输入
  -> Processed Question
  -> artifact 中可见
  -> 后续 schema linking 使用
```

这样即使问题理解错了，也能在 artifact 中发现。

## 6. 在线链路应该收敛成什么

后续在线 NL2SQL 不应是：

```text
Raw Question + Raw DB Schema
  -> SQL LLM
```

而应是：

```text
Raw Question
  -> Processed Question
  -> Schema Knowledge Layer
  -> Schema Linking
  -> Schema Context
  -> Prompt Payload
  -> Final Prompt
  -> SQL LLM
```

其中：

```text
Processed Question:
  消化用户问题的不确定性。

Schema Knowledge Layer:
  消化数据库结构的不确定性。

Schema Linking:
  根据问题从知识层中选择相关表、字段、关系、业务值。

Schema Context:
  给 prompt 使用的本次上下文快照。

Prompt Payload:
  最终提示词的结构化材料。

Final Prompt:
  真正给 SQL LLM 的文本。
```

这条链路的设计目标是：

```text
每一步都有结构化产物。
每一步都能写入 artifact。
每一步都能单独检查。
最终 prompt 不是凭空拼出来的。
```

## 7. 中间层是否真的解决问题

中间层能解决的问题：

```text
1. 缺外键：
   用 relationship catalog 补充。

2. 缺注释：
   用人工维护或 LLM 辅助生成注释候选，再确认。

3. 字段值不透明：
   用 value hints / sample values / 业务规则补充。

4. 用户问题业务词不标准：
   用 business glossary 映射到表字段。

5. 表太多：
   用 schema linking 筛选候选表，避免全量 schema 干扰 LLM。

6. prompt 不可解释：
   用 selection evidence 说明为什么这些表字段进入 prompt。
```

中间层不能自动解决的问题：

```text
1. 如果没人维护业务含义，它不能凭空保证正确。
2. 如果 LLM 生成的关系候选没人确认，它仍可能污染知识库。
3. 如果 schema knowledge 过期，prompt 也会过期。
4. 如果用户问题本身需要澄清，中间层不能强行猜。
```

因此中间层的价值不在于“消灭不确定性”，而在于：

```text
把不确定性显式化、结构化、可观察、可维护。
```

## 8. 中间层会增加什么复杂度

引入中间层会增加复杂度。

主要包括：

```text
1. 数据结构复杂度：
   SchemaCatalog、RelationshipCatalog、BusinessGlossary、ValueHints。

2. 维护复杂度：
   人工维护注释、关系、业务词。

3. 质量控制复杂度：
   LLM 生成候选需要确认。
   人工维护内容需要版本和来源。

4. 流程复杂度：
   在线链路多了 question processing、schema linking、context building。

5. artifact 复杂度：
   需要记录 processed_question、candidate_tables、selection_evidence。
```

但这些复杂度是有边界的。

如果不引入中间层，复杂度不会消失，只会转移到：

```text
最终 SQL LLM 的 prompt 猜测。
生成失败后的排查。
不可解释的错误。
反复手调 prompt。
```

也就是说：

```text
中间层不是增加复杂度，而是把原本隐藏在 LLM 黑盒里的复杂度显式化。
```

显式复杂度更容易测试和维护。

隐式复杂度更难定位和改进。

## 9. 当前项目应该选择的假设

建议当前项目采用这个假设：

```text
系统不直接面对完全未知数据库。
系统面对的是经过 Schema Knowledge Layer 治理后的数据库知识。
```

但这个治理层不一定一开始很重。

第一版可以很轻：

```text
固定的 demo schema catalog
手工维护的表字段注释
手工维护的 relationship
少量 value hints
简单 business glossary
```

后续再逐步增强：

```text
从真实数据库自动提取 physical schema
用 LLM 辅助生成注释候选
人工确认关键关系
引入历史 SQL
引入向量召回
引入 schema index
```

这样项目不会一开始就变重，但方向是正确的。

## 10. 对后续设计的影响

下一阶段不应该直接设计：

```text
LLM 调用
真实数据库执行
向量库
retry
```

更应该设计：

```text
Schema Knowledge Layer
Processed Question
Schema Linking
Schema Context
Prompt Payload 升级
Artifact 观察点
```

具体要回答：

```text
1. 我们如何表达一个“被治理过的数据库知识”？
2. 一个表/字段/关系/业务词需要哪些字段？
3. 哪些知识来自人工，哪些来自数据库，哪些来自 LLM 候选？
4. 用户问题处理后的结构是什么？
5. 表定位结果需要哪些 evidence？
6. 哪些信息进入 final prompt？
7. 哪些信息只进入 artifact，不进入 final prompt？
```

## 11. 推荐的 Phase 6 主题

建议 Phase 6 改成：

```text
Phase 6：NL2SQL 数据库知识层与问题到表定位设计
```

而不是单纯：

```text
Phase 6：接入 LLM
```

Phase 6 的目标应该是：

```text
设计从用户问题到 schema_context 的中间层。
```

它要产出：

```text
ProcessedQuestion 结构
SchemaKnowledge 结构
SelectedTable / RelevantColumn / Relationship / ValueBinding
SelectionEvidence
SchemaContext
Prompt Payload 升级方案
Artifact 新增观察内容
```

它暂时不需要做：

```text
真实 LLM
真实数据库
真实 SQL execution
复杂向量检索
retry
QueryPlan
```

## 12. 一句话总结

面对用户问题和数据库结构这两类不确定输入时，核心选择是：

```text
把不确定性直接押注给最后一个 SQL LLM，
还是先用中间层把不确定性结构化、解释化、可维护化。
```

当前项目应该选择后者。

因为我们真正要解决的不是：

```text
怎么调一个 LLM。
```

而是：

```text
用户问题进来后，
系统凭什么知道该给 LLM 哪些表、字段、关系和业务规则。
```
