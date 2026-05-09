# NL2SQL Knowledge Layer Consumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first code path for `ProcessedQuestion + ProcessedDatabaseKnowledge -> KnowledgeRetrievalResult -> SchemaLinkingResult -> SqlGenerationContext -> PromptPayload -> FinalPrompt`.

**Architecture:** Keep the implementation inside the existing `nl2sql` workflow package. Add one central contract file and one small pure-function pipeline file, then wire the result through the existing `build_prompt_node`, prompt payload, prompt renderer, output metadata, and artifact writer. Do not add `domain/`, `services/`, `stages/`, `protocols`, context-shell classes, real LLM calls, real DB calls, vector stores, retry, or SQL templates in this iteration.

**Tech Stack:** Python 3, `TypedDict`, LangGraph existing workflow nodes, existing JSON artifacts, `pytest`.

---

## Source Documents

Read these before editing:

- `.ai/guide/00_协作方式.md`
- `.ai/guide/01_决策偏好.md`
- `.ai/guide/02_风险提醒.md`
- `.ai/guide/03_乱码处理.md`
- `.ai/guide/10_运行方式.md`
- `.ai/guide/04_验证汇报.md`
- `docs/project/Phase6_NL2SQL中间层对象设计.md`

Run Python through the project-local interpreter:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest ...
```

Use UTF-8 in PowerShell when reading/writing Chinese files:

```powershell
[Console]::InputEncoding=[System.Text.Encoding]::UTF8
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$OutputEncoding=[System.Text.Encoding]::UTF8
chcp 65001 > $null
```

## Non-Goals

- Do not implement `RawUserQuestion -> ProcessedQuestion`.
- Do not implement `RawDatabaseSchema -> ProcessedDatabaseKnowledge`.
- Do not connect a real LLM, database, vector store, SQL template route, or history SQL route.
- Do not introduce retry.
- Do not create broad architecture layers such as `domain`, `services`, `integrations`, `stages`, `models`, or protocol abstractions.
- Do not let `KnowledgeCandidate`, `dropped_candidates`, `raw_ref`, `vector_score`, `chunk_id`, or retrieval internals enter `final_prompt`.

## File Structure

Create:

- `src/nl2sqlagent/workflows/nl2sql/knowledge_contracts.py`
  - Owns all TypedDict contracts for processed question, processed knowledge, retrieval, schema linking, and SQL generation context.
  - Keep contracts in one file for the initial implementation so the data shape can be inspected from one place.

- `src/nl2sqlagent/workflows/nl2sql/knowledge_pipeline.py`
  - Owns pure functions:
    - `build_initial_processed_question(...)`
    - `build_sample_processed_database_knowledge()`
    - `build_knowledge_retrieval_result(...)`
    - `build_schema_linking_result(...)`
    - `build_sql_generation_context(...)`
  - No file I/O, no logging, no LangGraph dependency, no artifact writing.
  - The `build_initial_processed_question(...)` and `build_sample_processed_database_knowledge()` functions are temporary fixture-like builders for this first knowledge-layer consumption path. They are not real question understanding, not real knowledge loading, and must not be renamed to production-sounding APIs such as `load_processed_database_knowledge()`.

- `tests/unit/workflows/nl2sql/test_knowledge_pipeline.py`
  - Covers matcher, linker, SQL context, dropped candidates, and pseudo vector candidate behavior.

Modify:

- `src/nl2sqlagent/workflows/nl2sql/state.py`
  - Add graph state fields for `processed_question`, `processed_database_knowledge`, `knowledge_retrieval_result`, `schema_linking_result`, `sql_generation_context`.

- `src/nl2sqlagent/workflows/nl2sql/prompt_payload.py`
  - Add `value_bindings` to schema context.
  - Add `build_prompt_payload_from_sql_generation_context(...)`.
  - Keep `build_mock_prompt_payload(...)` only if tests still need it during migration; by the end, `build_prompt_node` should not call it.

- `src/nl2sqlagent/workflows/nl2sql/prompt_builder.py`
  - Render selected relationships and `schema_context.value_bindings`.
  - Keep debug fields out of `final_prompt`.

- `src/nl2sqlagent/workflows/nl2sql/nodes.py`
  - Replace mock prompt construction with the knowledge pipeline.
  - Return intermediate objects from `build_prompt_node` so LangGraph stream and artifacts expose them.

- `src/nl2sqlagent/workflows/nl2sql/response_builder.py`
  - Add intermediate objects to output metadata for inspectability.
  - Continue to avoid artifact path metadata here.

- `src/nl2sqlagent/workflows/nl2sql/artifacts.py`
  - Inspect only by default. The initial implementation should rely on existing `output.json` metadata and `graph_updates.jsonl` to expose intermediate objects.
  - Do not add standalone files such as `knowledge_retrieval_result.json`, `schema_linking_result.json`, or `sql_generation_context.json` in this plan unless an existing artifact serialization bug makes a tiny centralized fix unavoidable.

- Existing tests under `tests/unit/workflows/nl2sql/` and `tests/integration/test_nl2sql_workflow.py`.

## Data Shape Rules

The implementation must preserve this boundary:

```text
KnowledgeRetrievalResult:
  candidates, retrieval_method, match_source, raw_ref, evidence_text
  artifact/debug only

SchemaLinkingResult:
  selected_tables, relevant_columns, selected_relationships, value_bindings,
  evidence, dropped_candidates, warnings
  artifact/debug source of truth for final selection

SqlGenerationContext:
  clean SQL-generation input
  no full candidates, no dropped candidates, no vector raw_ref

PromptPayload / FinalPrompt:
  built only from SqlGenerationContext
```

`value_bindings` belongs under `schema_context.value_bindings`, not `semantic_context`.

## Task 1: Add Knowledge Contracts

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/knowledge_contracts.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/state.py`
- Test: `tests/unit/workflows/nl2sql/test_contracts.py`

- [ ] **Step 1: Write contract import test**

Add a test that imports the new public contract names and checks the heavy-layer guard still passes.

```python
def test_knowledge_contracts_are_importable_without_heavy_layers() -> None:
    from nl2sqlagent.workflows.nl2sql.knowledge_contracts import (
        KnowledgeRetrievalResult,
        ProcessedDatabaseKnowledge,
        ProcessedQuestion,
        SchemaLinkingResult,
        SqlGenerationContext,
    )

    assert ProcessedQuestion
    assert ProcessedDatabaseKnowledge
    assert KnowledgeRetrievalResult
    assert SchemaLinkingResult
    assert SqlGenerationContext
```

- [ ] **Step 2: Run the focused failing test**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_contracts.py::test_knowledge_contracts_are_importable_without_heavy_layers -q
```

Expected: FAIL because `knowledge_contracts.py` does not exist.

- [ ] **Step 3: Create `knowledge_contracts.py`**

Implement `TypedDict` contracts. Keep them lightweight and JSON-shaped.

Minimum required names:

```python
from __future__ import annotations

from typing import Any, TypedDict


class ProcessedQuestion(TypedDict, total=False):
    raw: str
    text: str
    keywords: list[str]
    business_terms: list[str]
    metric_hints: list[str]
    dimension_hints: list[str]
    filter_hints: list[str]
    time_hints: list[str]
    assumptions: list[str]


class KnowledgeTable(TypedDict, total=False):
    id: str
    name: str
    business_name: str
    description: str
    aliases: list[str]
    table_type: str
    enabled: bool
    source: str
    verified: bool


class KnowledgeColumn(TypedDict, total=False):
    id: str
    table_name: str
    name: str
    business_name: str
    data_type: str
    description: str
    aliases: list[str]
    semantic_tags: list[str]
    source: str
    verified: bool


class KnowledgeRelationship(TypedDict, total=False):
    id: str
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    relationship_type: str
    description: str
    source: str
    verified: bool


class KnowledgeValueBinding(TypedDict, total=False):
    id: str
    business_term: str
    table_name: str
    column_name: str
    operator: str
    value: Any
    description: str
    source: str
    verified: bool


class KnowledgeBusinessTerm(TypedDict, total=False):
    id: str
    term: str
    description: str
    related_tables: list[str]
    related_columns: list[str]
    related_value_bindings: list[str]
    source: str
    verified: bool


class ProcessedDatabaseKnowledge(TypedDict):
    dialect: str
    tables: list[KnowledgeTable]
    columns: list[KnowledgeColumn]
    relationships: list[KnowledgeRelationship]
    value_bindings: list[KnowledgeValueBinding]
    business_terms: list[KnowledgeBusinessTerm]


class KnowledgeCandidate(TypedDict, total=False):
    kind: str
    knowledge_id: str
    score: float
    matched_terms: list[str]
    retrieval_method: str
    match_source: str
    evidence_text: str
    reason: str
    raw_ref: dict[str, Any]


class KnowledgeRetrievalResult(TypedDict, total=False):
    candidates: list[KnowledgeCandidate]
    warnings: list[str]
    metadata: dict[str, Any]
```

Also define:

```python
class SelectedTable(TypedDict, total=False): ...
class RelevantColumn(TypedDict, total=False): ...
class SelectedRelationship(TypedDict, total=False): ...
class SelectedValueBinding(TypedDict, total=False): ...
class SelectionEvidence(TypedDict, total=False): ...
class DroppedCandidate(TypedDict, total=False): ...
class SchemaLinkingResult(TypedDict): ...
class SqlGenerationQuestion(TypedDict, total=False): ...
class SqlGenerationTable(TypedDict, total=False): ...
class SqlGenerationColumn(TypedDict, total=False): ...
class SqlGenerationRelationship(TypedDict, total=False): ...
class SqlGenerationSchemaContext(TypedDict): ...
class SqlGenerationSemanticContext(TypedDict, total=False): ...
class SqlGenerationPolicy(TypedDict): ...
class SqlGenerationOutputContract(TypedDict): ...
class SqlGenerationContext(TypedDict): ...
```

Use the exact field intent from `docs/project/Phase6_NL2SQL中间层对象设计.md`.

- [ ] **Step 4: Update graph state**

In `state.py`, import the new contracts and add optional state fields:

```python
processed_question: ProcessedQuestion
processed_database_knowledge: ProcessedDatabaseKnowledge
knowledge_retrieval_result: KnowledgeRetrievalResult
schema_linking_result: SchemaLinkingResult
sql_generation_context: SqlGenerationContext
```

- [ ] **Step 5: Run contract tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/knowledge_contracts.py src/nl2sqlagent/workflows/nl2sql/state.py tests/unit/workflows/nl2sql/test_contracts.py
git commit -m "feat: add nl2sql knowledge contracts"
```

## Task 2: Add Sample Processed Inputs and Structured Retrieval

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/knowledge_pipeline.py`
- Test: `tests/unit/workflows/nl2sql/test_knowledge_pipeline.py`

- [ ] **Step 1: Write failing tests for processed fixtures**

Add tests:

```python
from nl2sqlagent.workflows.nl2sql.knowledge_pipeline import (
    build_initial_processed_question,
    build_sample_processed_database_knowledge,
)


def test_build_initial_processed_question_for_employee_department_question() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")

    assert question["raw"] == "按部门统计在职员工人数"
    assert question["text"] == "按部门统计在职员工人数"
    assert "在职员工" in question["business_terms"]
    assert "employee_count" in question["metric_hints"]
    assert "department" in question["dimension_hints"]
    assert "active_employee" in question["filter_hints"]


def test_sample_processed_database_knowledge_contains_verified_hr_relationship() -> None:
    knowledge = build_sample_processed_database_knowledge()

    assert knowledge["dialect"] == "sqlite"
    assert any(table["name"] == "hr_emp_base" for table in knowledge["tables"])
    assert any(table["name"] == "hr_dept_dim" for table in knowledge["tables"])
    assert any(
        relationship["left_table"] == "hr_emp_base"
        and relationship["right_table"] == "hr_dept_dim"
        and relationship["verified"] is True
        for relationship in knowledge["relationships"]
    )
```

- [ ] **Step 2: Write failing retrieval test**

```python
from nl2sqlagent.workflows.nl2sql.knowledge_pipeline import (
    build_knowledge_retrieval_result,
)


def test_structured_retrieval_finds_tables_columns_and_value_binding() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()

    result = build_knowledge_retrieval_result(question, knowledge)
    pairs = {(item["kind"], item["knowledge_id"]) for item in result["candidates"]}

    assert ("table", "table:hr_emp_base") in pairs
    assert ("table", "table:hr_dept_dim") in pairs
    assert ("column", "column:hr_emp_base.emp_stat_cd") in pairs
    assert ("value_binding", "value:active_employee") in pairs
    assert all(item["retrieval_method"] == "structured" for item in result["candidates"])
```

- [ ] **Step 3: Run the failing tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_knowledge_pipeline.py -q
```

Expected: FAIL because the module/functions are missing.

- [ ] **Step 4: Implement sample processed inputs**

In `knowledge_pipeline.py`, define:

```python
def build_initial_processed_question(raw_question: str) -> ProcessedQuestion:
    text = raw_question.strip()
    return {
        "raw": raw_question,
        "text": text,
        "keywords": ["部门", "在职", "员工", "人数"],
        "business_terms": ["在职员工"],
        "metric_hints": ["employee_count"],
        "dimension_hints": ["department"],
        "filter_hints": ["active_employee"],
        "time_hints": [],
        "assumptions": [],
    }
```

This is intentionally a hand-written middle-layer object, not question understanding.

Add a short docstring or comment above this function:

```python
"""Temporary fixture-like processed question builder for the first knowledge-layer consumption path.

This is not real question understanding.
"""
```

Also define `build_sample_processed_database_knowledge()` with:

- `hr_emp_base`
- `hr_dept_dim`
- columns:
  - `hr_emp_base.emp_id`
  - `hr_emp_base.dept_id`
  - `hr_emp_base.emp_stat_cd`
  - `hr_dept_dim.dept_id`
  - `hr_dept_dim.dept_nm`
- verified relationship:
  - `hr_emp_base.dept_id = hr_dept_dim.dept_id`
- verified value binding:
  - `在职员工 -> hr_emp_base.emp_stat_cd = "ACTIVE"`
- unrelated enabled tables for boundary tests:
  - `finance_salary_month`
  - `sys_user_log`
- one disabled table for disabled-knowledge behavior tests:
  - `tmp_import_record`

Add a short docstring or comment above this function:

```python
"""Temporary sample knowledge builder for local workflow wiring tests.

This is not a production knowledge loader.
"""
```

- [ ] **Step 5: Implement structured retrieval**

Implement `build_knowledge_retrieval_result(question, knowledge)`.

Rules:

- Match lower-cased `keywords`, `business_terms`, `metric_hints`, `dimension_hints`, `filter_hints`, and `time_hints`.
- Match against table `name`, `business_name`, `aliases`, `description`.
- Match against column `name`, `business_name`, `aliases`, `description`, `semantic_tags`.
- Match value binding `business_term` and `description`.
- Do not emit candidates for `enabled=False` tables or columns belonging to disabled tables.
- Use stable scores such as:
  - `1.0` for direct business term / alias match.
  - `0.85` for keyword / semantic tag match.
  - `0.7` for description match.
- Deduplicate by `(kind, knowledge_id)`.

- [ ] **Step 6: Run retrieval tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_knowledge_pipeline.py -q
```

Expected: PASS for tests added so far.

- [ ] **Step 7: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/knowledge_pipeline.py tests/unit/workflows/nl2sql/test_knowledge_pipeline.py
git commit -m "feat: add structured knowledge retrieval"
```

## Task 3: Build SchemaLinkingResult from Candidates

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/knowledge_pipeline.py`
- Test: `tests/unit/workflows/nl2sql/test_knowledge_pipeline.py`

- [ ] **Step 1: Write failing schema linking test**

```python
from nl2sqlagent.workflows.nl2sql.knowledge_pipeline import (
    build_schema_linking_result,
)


def test_schema_linking_promotes_employee_question_candidates() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)

    result = build_schema_linking_result(question, knowledge, retrieval)

    assert [table["table_name"] for table in result["selected_tables"]] == [
        "hr_emp_base",
        "hr_dept_dim",
    ]
    assert {
        (column["table_name"], column["column_name"], column["role"])
        for column in result["relevant_columns"]
    } >= {
        ("hr_emp_base", "emp_id", "measure"),
        ("hr_emp_base", "dept_id", "join_key"),
        ("hr_emp_base", "emp_stat_cd", "filter"),
        ("hr_dept_dim", "dept_id", "join_key"),
        ("hr_dept_dim", "dept_nm", "dimension"),
    }
    assert result["selected_relationships"] == [
        {
            "left_table": "hr_emp_base",
            "left_column": "dept_id",
            "right_table": "hr_dept_dim",
            "right_column": "dept_id",
            "reason": "verified relationship between selected tables",
        }
    ]
    assert result["value_bindings"][0]["business_term"] == "在职员工"
```

- [ ] **Step 2: Write failing dropped candidate boundary test**

```python
def test_schema_linking_keeps_unselected_candidates_out_of_selected_context() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)
    retrieval["candidates"].append(
        {
            "kind": "table",
            "knowledge_id": "table:finance_salary_month",
            "score": 0.2,
            "matched_terms": ["人数"],
            "retrieval_method": "structured",
            "match_source": "description",
            "reason": "low confidence unrelated candidate for boundary test",
        }
    )

    result = build_schema_linking_result(question, knowledge, retrieval)

    assert "finance_salary_month" not in [
        item["table_name"] for item in result["selected_tables"]
    ]
    assert any(
        item["target_name"] == "finance_salary_month"
        for item in result["dropped_candidates"]
    )
```

- [ ] **Step 3: Run failing schema linking tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_knowledge_pipeline.py -q
```

Expected: FAIL because `build_schema_linking_result` is missing.

- [ ] **Step 4: Implement schema linking**

In `knowledge_pipeline.py`, implement `build_schema_linking_result(question, knowledge, retrieval)`.

Minimum rules:

- Only promote candidates whose target knowledge exists and is enabled.
- Promote table candidates when score is high enough or when table is required by a selected column/value binding.
- Promote column candidates and their parent table.
- Promote value binding candidates:
  - select its table
  - select its column as `role="filter"`
  - add selected value binding
- Add measure/dimension columns from hints:
  - `employee_count` selects `hr_emp_base.emp_id` as `measure`
  - `department` selects `hr_dept_dim.dept_nm` as `dimension`
- When two selected tables have a verified relationship, add it and add both join key columns as `join_key`.
- If a candidate is not promoted, add it to `dropped_candidates`.
- If selected tables have no verified relationship, add a warning and do not invent joins.

Keep helper functions private and small. This file can contain local helpers such as `_knowledge_by_id`, `_add_selected_table`, `_add_relevant_column`, but do not create service classes.

- [ ] **Step 5: Run schema linking tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_knowledge_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/knowledge_pipeline.py tests/unit/workflows/nl2sql/test_knowledge_pipeline.py
git commit -m "feat: link knowledge candidates to schema context"
```

## Task 4: Build SqlGenerationContext

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/knowledge_pipeline.py`
- Test: `tests/unit/workflows/nl2sql/test_knowledge_pipeline.py`

- [ ] **Step 1: Write failing SQL context tests**

```python
from nl2sqlagent.workflows.nl2sql.knowledge_pipeline import (
    build_sql_generation_context,
)


def test_sql_generation_context_is_clean_prompt_input() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)
    linking = build_schema_linking_result(question, knowledge, retrieval)

    context = build_sql_generation_context(question, knowledge, linking)

    assert context["question"]["text"] == "按部门统计在职员工人数"
    assert context["schema_context"]["dialect"] == "sqlite"
    assert context["schema_context"]["value_bindings"] == linking["value_bindings"]
    assert "在职员工" in context["semantic_context"]["business_terms"]
    assert context["sql_policy"]["readonly_only"] is True
    assert context["output_contract"]["format"] == "sql_only"
    serialized = str(context)
    assert "dropped_candidates" not in serialized
    assert "retrieval_method" not in serialized
    assert "vector_score" not in serialized
    assert "chunk_id" not in serialized
```

- [ ] **Step 2: Run failing SQL context test**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_knowledge_pipeline.py::test_sql_generation_context_is_clean_prompt_input -q
```

Expected: FAIL because the function is missing.

- [ ] **Step 3: Implement SQL context builder**

Implement `build_sql_generation_context(...)`.

Mapping:

- `ProcessedQuestion.text -> question.text`
- `ProcessedQuestion.raw -> question.raw`
- `ProcessedQuestion.assumptions -> question.assumptions` and `semantic_context.assumptions`
- `ProcessedDatabaseKnowledge.dialect -> schema_context.dialect`
- `SchemaLinkingResult.selected_tables -> schema_context.tables`
- `SchemaLinkingResult.relevant_columns -> schema_context.columns`
- `SchemaLinkingResult.selected_relationships -> schema_context.relationships`
- `SchemaLinkingResult.value_bindings -> schema_context.value_bindings`
- `ProcessedQuestion.business_terms -> semantic_context.business_terms`
- SQL policy:
  - `readonly_only=True`
  - `allow_select_star=False`
  - `require_limit=True`
  - `default_limit=100`
- output contract same as current prompt payload.

Do not include retrieval candidates, raw refs, evidence details, or dropped candidates.

- [ ] **Step 4: Run SQL context tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_knowledge_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/knowledge_pipeline.py tests/unit/workflows/nl2sql/test_knowledge_pipeline.py
git commit -m "feat: build sql generation context"
```

## Task 5: Build Prompt Payload from SqlGenerationContext

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/prompt_payload.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/prompt_builder.py`
- Test: `tests/unit/workflows/nl2sql/test_prompt_payload.py`
- Test: `tests/unit/workflows/nl2sql/test_prompt_builder.py`

- [ ] **Step 1: Write failing prompt payload tests**

Add tests that build the full pipeline and then call `build_prompt_payload_from_sql_generation_context(context)`.

Required assertions:

- top-level keys remain:
  - `task`
  - `question`
  - `schema_context`
  - `semantic_context`
  - `sql_policy`
  - `output_contract`
  - `debug`
- `schema_context.value_bindings` exists.
- `debug.source` says the source is `sql_generation_context`.
- payload string does not contain `dropped_candidates`, `retrieval_method`, `vector_score`, or `chunk_id`.

- [ ] **Step 2: Write failing prompt renderer tests**

Add assertions:

```python
assert "Value Bindings:" in final_prompt
assert "在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE" in final_prompt
assert "Relationships:" in final_prompt
assert "hr_emp_base.dept_id = hr_dept_dim.dept_id" in final_prompt
assert "dropped_candidates" not in final_prompt
assert "retrieval_method" not in final_prompt
assert "vector_score" not in final_prompt
assert "chunk_id" not in final_prompt
```

- [ ] **Step 3: Run failing prompt tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_prompt_payload.py tests/unit/workflows/nl2sql/test_prompt_builder.py -q
```

Expected: FAIL because payload/context mapping is missing.

- [ ] **Step 4: Implement prompt payload builder**

Add `build_prompt_payload_from_sql_generation_context(sql_generation_context)`.

Keep `Nl2SqlPromptPayload` field names stable so current callers and artifacts stay readable.

Update `PromptSchemaContext` to include:

```python
value_bindings: list[dict[str, object]]
```

Convert `SqlGenerationContext` into prompt payload without reading retrieval/linking objects.

- [ ] **Step 5: Update prompt renderer**

In `_render_schema_context(...)`:

- Render relationships as concise join lines.
- Render value bindings after relationships.
- Keep output deterministic.

Example line:

```text
- 在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
```

Do not render debug.

- [ ] **Step 6: Run prompt tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_prompt_payload.py tests/unit/workflows/nl2sql/test_prompt_builder.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/prompt_payload.py src/nl2sqlagent/workflows/nl2sql/prompt_builder.py tests/unit/workflows/nl2sql/test_prompt_payload.py tests/unit/workflows/nl2sql/test_prompt_builder.py
git commit -m "feat: build prompt payload from sql context"
```

## Task 6: Wire Pipeline into build_prompt_node

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/nodes.py`
- Modify: `tests/unit/workflows/nl2sql/test_nodes.py`
- Modify: `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Update node test expectations**

Change `test_build_prompt_node_creates_structured_payload_and_final_prompt` to assert:

- result includes:
  - `processed_question`
  - `processed_database_knowledge`
  - `knowledge_retrieval_result`
  - `schema_linking_result`
  - `sql_generation_context`
  - `prompt_payload`
  - `final_prompt`
- `prompt_payload["schema_context"]["tables"]` includes `hr_emp_base` and `hr_dept_dim`.
- `final_prompt` includes `在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE`.
- `final_prompt` does not include dropped/debug/retrieval internals.

- [ ] **Step 2: Update integration test expectations**

In `tests/integration/test_nl2sql_workflow.py`, update success-path and artifact-path tests so they expect the HR sample prompt instead of the old `employee` mock table.

Also assert graph stream update exposes `schema_linking_result` and `sql_generation_context` under the `build_prompt` update.

- [ ] **Step 3: Run failing node/integration tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_nodes.py tests/integration/test_nl2sql_workflow.py -q
```

Expected: FAIL because node still calls `build_mock_prompt_payload`.

- [ ] **Step 4: Implement node wiring**

In `nodes.py`, replace mock payload call with:

```python
processed_question = build_initial_processed_question(normalized_question)
processed_database_knowledge = build_sample_processed_database_knowledge()
knowledge_retrieval_result = build_knowledge_retrieval_result(
    processed_question,
    processed_database_knowledge,
)
schema_linking_result = build_schema_linking_result(
    processed_question,
    processed_database_knowledge,
    knowledge_retrieval_result,
)
sql_generation_context = build_sql_generation_context(
    processed_question,
    processed_database_knowledge,
    schema_linking_result,
)
prompt_payload = build_prompt_payload_from_sql_generation_context(
    sql_generation_context
)
```

Return all intermediate objects in the node update.

Do not add artifact writing, logging, or file I/O in `nodes.py`; the contract test forbids this.

- [ ] **Step 5: Run node/integration tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_nodes.py tests/integration/test_nl2sql_workflow.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/nodes.py tests/unit/workflows/nl2sql/test_nodes.py tests/integration/test_nl2sql_workflow.py
git commit -m "feat: wire knowledge pipeline into prompt node"
```

## Task 7: Expose Artifacts and Output Metadata

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/response_builder.py`
- Inspect: `src/nl2sqlagent/workflows/nl2sql/artifacts.py`
- Modify: `tests/unit/workflows/nl2sql/test_response_builder.py`
- Modify: `tests/unit/workflows/nl2sql/test_artifacts.py`
- Modify: `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Write failing response metadata test**

In `test_response_builder.py`, assert `build_nl2sql_output(...)` metadata includes:

- `prompt_payload`
- `final_prompt`
- `processed_question`
- `knowledge_retrieval_result`
- `schema_linking_result`
- `sql_generation_context`

It must not construct artifact path metadata.

- [ ] **Step 2: Write failing artifact test**

Use a `final_state` containing the new intermediate objects.

Minimum required assertions:

- `output.json["metadata"]["schema_linking_result"]` exists.
- `output.json["metadata"]["sql_generation_context"]` exists.
- `graph_updates.jsonl` preserves the `build_prompt` update with retrieval/linking/context.
- `final_prompt.txt` does not contain `dropped_candidates`.

Do not add standalone artifact files in this task. The first implementation should prove observability through the existing artifact surfaces:

- `output.json`
- `graph_updates.jsonl`
- `prompt_payload.json`
- `final_prompt.txt`

- [ ] **Step 3: Run failing artifact/response tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_response_builder.py tests/unit/workflows/nl2sql/test_artifacts.py -q
```

Expected: FAIL until metadata is exposed.

- [ ] **Step 4: Update `response_builder.py`**

Extend `build_prompt_debug_metadata(...)` to include the new intermediate state keys when present.

Keep artifact metadata keys out of this file; `test_response_builder_does_not_construct_artifact_metadata` must continue to pass.

- [ ] **Step 5: Keep `artifacts.py` unchanged unless serialization is broken**

Because `write_nl2sql_artifacts(...)` already writes:

- `prompt_payload.json`
- `final_prompt.txt`
- normalized graph updates
- `output.json` metadata

the expected implementation is to keep `artifacts.py` unchanged. Only make a tiny fix here if the new intermediate objects are not JSON-serializable through the existing `_json_safe(...)` path.

- [ ] **Step 6: Run artifact/response tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_response_builder.py tests/unit/workflows/nl2sql/test_artifacts.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/response_builder.py tests/unit/workflows/nl2sql/test_response_builder.py tests/unit/workflows/nl2sql/test_artifacts.py tests/integration/test_nl2sql_workflow.py
git commit -m "feat: expose knowledge pipeline artifacts"
```

## Task 8: Add Prompt Boundary Regression Tests

**Files:**

- Modify: `tests/unit/workflows/nl2sql/test_knowledge_pipeline.py`
- Modify: `tests/unit/workflows/nl2sql/test_prompt_payload.py`
- Modify: `tests/unit/workflows/nl2sql/test_prompt_builder.py`

- [ ] **Step 1: Test dropped candidates never enter context or prompt**

Build a retrieval result with an unrelated candidate, run linking/context/payload/prompt, and assert:

```python
assert any(item["target_name"] == "finance_salary_month" for item in linking["dropped_candidates"])
assert "finance_salary_month" not in str(context)
assert "finance_salary_month" not in str(payload)
assert "finance_salary_month" not in final_prompt
assert "dropped_candidates" not in final_prompt
```

If this test fails because `finance_salary_month` appears in `SqlGenerationContext`, fix `build_sql_generation_context(...)`. Do not weaken the assertion or hide the failure by renaming the sample table.

- [ ] **Step 2: Test pseudo vector candidate cannot bypass SchemaLinkingResult**

Append a candidate:

```python
{
    "kind": "table",
    "knowledge_id": "table:sys_user_log",
    "score": 0.99,
    "matched_terms": ["员工"],
    "retrieval_method": "vector",
    "match_source": "document",
    "raw_ref": {"vector_score": 0.99, "chunk_id": "chunk-1"},
    "reason": "pseudo vector candidate for boundary test",
}
```

Expected:

- It appears in `KnowledgeRetrievalResult`.
- It appears in `SchemaLinkingResult.dropped_candidates` unless a deterministic linking rule explicitly promotes it.
- It does not appear in `SqlGenerationContext`.
- `vector_score` and `chunk_id` do not appear in `PromptPayload` or `FinalPrompt`.

- [ ] **Step 3: Run boundary tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_knowledge_pipeline.py tests/unit/workflows/nl2sql/test_prompt_payload.py tests/unit/workflows/nl2sql/test_prompt_builder.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add tests/unit/workflows/nl2sql/test_knowledge_pipeline.py tests/unit/workflows/nl2sql/test_prompt_payload.py tests/unit/workflows/nl2sql/test_prompt_builder.py
git commit -m "test: lock prompt boundary for knowledge candidates"
```

## Task 9: Final Verification

**Files:**

- No new files unless tests reveal a necessary small fix.

- [ ] **Step 1: Run all NL2SQL workflow tests**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql tests/integration/test_nl2sql_workflow.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Manually inspect one artifact run**

Use an existing workflow test artifact or run the workflow through the app entrypoint if already documented in `.ai/guide/10_运行方式.md`.

Verify:

- `final_prompt.txt` contains selected HR tables, columns, relationship, and value binding.
- `prompt_payload.json` contains `schema_context.value_bindings`.
- `output.json` or `graph_updates.jsonl` contains:
  - `processed_question`
  - `knowledge_retrieval_result`
  - `schema_linking_result`
  - `sql_generation_context`
- `final_prompt.txt` does not contain:
  - `dropped_candidates`
  - `retrieval_method`
  - `vector_score`
  - `chunk_id`
  - `raw_ref`

- [ ] **Step 4: Check architecture guard**

Run:

```powershell
$py = Get-Content .\.ai\local\python_path.txt -Encoding UTF8
& $py -m pytest tests/unit/workflows/nl2sql/test_contracts.py -q
```

Expected: PASS, especially the no-heavy-layer tests.

- [ ] **Step 5: Review git diff**

Run:

```powershell
git diff --stat
git diff -- src/nl2sqlagent/workflows/nl2sql tests/unit/workflows/nl2sql tests/integration/test_nl2sql_workflow.py
```

Check:

- No unrelated doc rewrites.
- No accidental broad refactor.
- No file I/O in `nodes.py`.
- No artifact metadata path keys in `response_builder.py`.
- No new `domain/services/integrations/stages/models` directories.

- [ ] **Step 6: Final commit**

If all checks pass and there are uncommitted fixes:

```powershell
git add src/nl2sqlagent/workflows/nl2sql tests/unit/workflows/nl2sql tests/integration/test_nl2sql_workflow.py
git commit -m "feat: complete nl2sql knowledge layer consumption"
```

## Acceptance Criteria

The implementation is complete when:

- `build_prompt_node` no longer builds the final prompt directly from `build_mock_prompt_payload`.
- The workflow produces:
  - `processed_question`
  - `processed_database_knowledge`
  - `knowledge_retrieval_result`
  - `schema_linking_result`
  - `sql_generation_context`
  - `prompt_payload`
  - `final_prompt`
- `final_prompt` is derived from `SqlGenerationContext`.
- `schema_context.value_bindings` exists and includes:
  - `在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE`
- `KnowledgeRetrievalResult` can contain noisy candidates.
- `SchemaLinkingResult.dropped_candidates` records candidates that did not make the final context.
- Dropped candidates and pseudo vector internals do not appear in `SqlGenerationContext`, `PromptPayload`, or `FinalPrompt`.
- Artifacts make the intermediate chain visible through `output.json` and/or `graph_updates.jsonl`.
- The implementation stays inside the existing NL2SQL workflow package and does not introduce early heavy architecture layers.
