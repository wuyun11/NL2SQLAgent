# NL2SQL Manual Case Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small manual NL2SQL case validation harness so 5-8 hand-authored `ProcessedQuestion + ProcessedDatabaseKnowledge` samples can run through the existing LangGraph workflow, write artifacts, and support human review of `final_prompt -> generated_sql`.

**Architecture:** Keep the main workflow unchanged in shape: `normalize_question -> build_prompt -> generate_sql -> check_sql -> execute_sql -> response`. Add explicit manual middle-layer inputs to `Nl2SqlInput`, let `build_prompt_node` use them when provided, and add a thin case loader/runner for Phase8 examples. Do not add a second workflow controller, Chain/Stage layer, vector retrieval, history SQL, real DB execution, retry, token usage, or `use_llm_generate`.

**Tech Stack:** Python 3.12, LangGraph workflow already in the repo, `TypedDict` contracts, JSON case files, existing artifact writer, `pytest`, optional real LLM through existing `SqlGenerator`.

---

## Source Documents

Read these before editing:

- `.ai/guide/00_协作方式.md`
- `.ai/guide/01_决策偏好.md`
- `.ai/guide/02_风险提醒.md`
- `.ai/guide/03_乱码处理.md`
- `.ai/guide/10_运行方式.md`
- `.ai/guide/04_验证汇报.md`
- `docs/project/Phase8_NL2SQL人工样例验证设计.md`
- `docs/project/Phase7_NL2SQL真实运行产物说明.md`
- `docs/project/Phase6_NL2SQL中间层对象设计.md`
- `docs/project/Phase7_NL2SQL_LLM接入设计.md`

Run Python through the project-local interpreter:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest ... --basetemp .pytest_tmp
```

Use UTF-8 in PowerShell when reading/writing Chinese files:

```powershell
[Console]::InputEncoding=[System.Text.Encoding]::UTF8
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$OutputEncoding=[System.Text.Encoding]::UTF8
chcp 65001 > $null
```

## Non-Goals

- Do not add `use_llm_generate`.
- Do not implement token usage, LangSmith, retry, repair, vector retrieval, history SQL templates, real DB execution, automatic `ProcessedQuestion`, or automatic `ProcessedDatabaseKnowledge`.
- Do not create `engine/chains`, `application/stages`, `GenerateStage`, `Nl2SqlChain`, `MainOrchestration`, or a second workflow controller.
- Do not let `nodes.py` import or initialize `ChatOpenAI`, read API keys, read model config, write files, or write artifacts.
- Do not run real LLM by default. Real LLM sample runs must require an explicit CLI flag.
- Do not let dropped candidates enter `final_prompt`.
- Do not create `.pytest-temp/` or `.pytest-tmp/`; use `.pytest_tmp/`.

## File Structure

Create:

- `examples/nl2sql_cases/phase8_cases.json`
  - Owns the Phase8 manual sample matrix.
  - Contains a shared `ProcessedDatabaseKnowledge`, six case definitions, expected prompt checks, expected schema linking checks, and reference SQL.

- `src/nl2sqlagent/workflows/nl2sql/sample_cases.py`
  - Owns `Nl2SqlSampleCase` / expectation typed contracts, JSON loading, case validation, and conversion to `Nl2SqlInput`.
  - No LangGraph imports, no provider imports, no artifact writing.

- `src/nl2sqlagent/interfaces/cli/commands/nl2sql_cases.py`
  - Owns the explicit manual case runner command.
  - Loads cases, builds the app, runs selected cases, prints a compact JSON summary, and writes normal NL2SQL artifacts through the existing workflow.

- `tests/unit/workflows/nl2sql/test_sample_cases.py`
  - Covers JSON loading, validation, conversion to `Nl2SqlInput`, and expectation helpers.

- `tests/integration/test_nl2sql_case_runner.py`
  - Covers running one or more Phase8 cases with a fake SQL generator and verifies artifact files.

Modify:

- `src/nl2sqlagent/workflows/nl2sql/input.py`
  - Add optional manual `processed_question`, `processed_database_knowledge`, and `case_id` fields to `Nl2SqlInput`.

- `src/nl2sqlagent/workflows/nl2sql/workflow.py`
  - Pass the optional manual middle-layer fields into graph state.

- `src/nl2sqlagent/workflows/nl2sql/nodes.py`
  - Let `build_prompt_node` prefer provided `processed_question` / `processed_database_knowledge`; fall back to the current temporary builders when they are absent.

- `src/nl2sqlagent/workflows/nl2sql/artifacts.py`
  - Include `case_id` in `input.json` when present.
  - Keep output artifact shape otherwise unchanged.

- `src/nl2sqlagent/bootstrap/container.py`
  - Add an optional `sql_generator_override` parameter to `build_app` for tests and fake sample runs only.
  - If override is provided, use it instead of config model provider.

- `src/nl2sqlagent/interfaces/cli/main.py`
  - Add explicit `run-nl2sql-cases` command and CLI arguments.

- Existing tests under `tests/unit/workflows/nl2sql/` and `tests/integration/`
  - Update only where needed for new optional fields and new case flow.

## Phase8 Case Data Shape

`examples/nl2sql_cases/phase8_cases.json` should use this shape:

```json
{
  "version": "phase8.manual-cases.v1",
  "knowledge": {
    "dialect": "sqlite",
    "tables": [],
    "columns": [],
    "relationships": [],
    "value_bindings": [],
    "business_terms": []
  },
  "cases": [
    {
      "case_id": "case_001_active_employee_count",
      "title": "统计在职员工人数",
      "risk_focus": "single table + value binding",
      "raw_question": "统计在职员工人数",
      "processed_question": {
        "raw": "统计在职员工人数",
        "text": "统计在职员工人数",
        "keywords": ["在职", "员工", "人数"],
        "business_terms": ["在职员工"],
        "metric_hints": ["employee_count"],
        "dimension_hints": [],
        "filter_hints": ["active_employee"],
        "time_hints": [],
        "assumptions": []
      },
      "expected_schema_linking": {
        "selected_tables": ["hr_emp_base"],
        "relevant_columns": ["hr_emp_base.emp_id", "hr_emp_base.emp_stat_cd"],
        "relationships": [],
        "value_bindings": ["hr_emp_base.emp_stat_cd=ACTIVE"],
        "dropped_tables": []
      },
      "expected_prompt_contains": [
        "Table: hr_emp_base",
        "在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE"
      ],
      "expected_prompt_excludes": [
        "Table: tmp_import_record"
      ],
      "expected_sql_shape": [
        "COUNT",
        "hr_emp_base",
        "emp_stat_cd",
        "ACTIVE"
      ],
      "reference_sql": "SELECT COUNT(emp_id) AS employee_count FROM hr_emp_base WHERE emp_stat_cd = 'ACTIVE' LIMIT 100",
      "review_notes": ""
    }
  ]
}
```

The actual file must contain six cases from `docs/project/Phase8_NL2SQL人工样例验证设计.md`:

- `case_001_active_employee_count`
- `case_002_active_employee_by_department`
- `case_003_inactive_employee_by_department`
- `case_004_full_time_employee_count`
- `case_005_drop_import_table`
- `case_006_ambiguous_employee_count`

The shared knowledge must include:

- `hr_emp_base`
- `hr_dept_dim`
- `tmp_import_record`
- `sys_user_log`
- `finance_salary_month`
- columns:
  - `hr_emp_base.emp_id`
  - `hr_emp_base.dept_id`
  - `hr_emp_base.emp_stat_cd`
  - `hr_emp_base.emp_type_cd`
  - `hr_dept_dim.dept_id`
  - `hr_dept_dim.dept_nm`
- relationship:
  - `hr_emp_base.dept_id = hr_dept_dim.dept_id`
- value bindings:
  - `在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE`
  - `离职员工 -> hr_emp_base.emp_stat_cd = INACTIVE`
  - `正式员工 -> hr_emp_base.emp_type_cd = FULL_TIME`

For `case_005_drop_import_table`, make `tmp_import_record` enabled but unverified or table_type `staging`, so it can be retrieved but must be dropped before `final_prompt`.

---

### Task 1: Add Manual Middle-Layer Inputs

**Files:**
- Modify: `src/nl2sqlagent/workflows/nl2sql/input.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/workflow.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/artifacts.py`
- Test: `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Write failing integration test for input propagation**

Add a test that constructs `Nl2SqlInput` with `case_id`, `processed_question`, and `processed_database_knowledge`, runs the workflow with `FakeSqlGenerator`, and asserts:

```python
assert output.metadata["processed_question"]["text"] == "统计在职员工人数"
assert output.metadata["processed_database_knowledge"]["dialect"] == "sqlite"
assert output.metadata["input_path"]
```

Then read `input.json` and assert:

```python
assert input_json["case_id"] == "case_001_active_employee_count"
```

- [ ] **Step 2: Run test and verify it fails**

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/integration/test_nl2sql_workflow.py::test_nl2sql_workflow_accepts_manual_middle_layer_inputs -q --basetemp .pytest_tmp
```

Expected: FAIL because `Nl2SqlInput` has no fields and `workflow._graph_input` does not propagate them.

- [ ] **Step 3: Add optional fields to `Nl2SqlInput`**

In `src/nl2sqlagent/workflows/nl2sql/input.py`:

```python
from nl2sqlagent.workflows.nl2sql.knowledge_contracts import (
    ProcessedDatabaseKnowledge,
    ProcessedQuestion,
)

@dataclass(frozen=True)
class Nl2SqlInput:
    question: str
    request_id: str | None = None
    user_id: str | None = None
    database_key: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    case_id: str | None = None
    processed_question: ProcessedQuestion | None = None
    processed_database_knowledge: ProcessedDatabaseKnowledge | None = None
```

- [ ] **Step 4: Propagate fields into graph state**

In `Nl2SqlWorkflow._graph_input`, add:

```python
"case_id": input.case_id,
"processed_question": input.processed_question,
"processed_database_knowledge": input.processed_database_knowledge,
```

Do not put these into `runtime_options`.

- [ ] **Step 5: Write `case_id` to `input.json`**

In `write_nl2sql_artifacts`, add:

```python
"case_id": input.case_id,
```

Do not duplicate full `processed_question` / `processed_database_knowledge` into `input.json`; they are already in `output.json.metadata`.

- [ ] **Step 6: Run test and verify it still fails at `build_prompt_node`**

Expected: it may still use temporary builders. That is okay; Task 2 fixes node behavior.

---

### Task 2: Make `build_prompt_node` Use Manual Inputs

**Files:**
- Modify: `src/nl2sqlagent/workflows/nl2sql/nodes.py`
- Test: `tests/unit/workflows/nl2sql/test_nodes.py`
- Test: `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Write failing node test**

Add:

```python
def test_build_prompt_node_uses_manual_processed_question_and_knowledge() -> None:
    manual_question = {
        "raw": "统计员工人数",
        "text": "统计员工人数",
        "keywords": ["员工", "人数"],
        "business_terms": [],
        "metric_hints": ["employee_count"],
        "dimension_hints": [],
        "filter_hints": [],
        "time_hints": [],
        "assumptions": ["未限定员工状态，默认统计全部员工"],
    }
    manual_knowledge = build_sample_processed_database_knowledge()

    result = build_prompt_node({
        "raw_question": "统计员工人数",
        "normalized_question": "统计员工人数",
        "processed_question": manual_question,
        "processed_database_knowledge": manual_knowledge,
    })

    assert result["processed_question"] == manual_question
    assert result["processed_database_knowledge"] == manual_knowledge
    assert "在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE" not in result["final_prompt"]
    assert "未限定员工状态，默认统计全部员工" in result["final_prompt"]
```

Import `build_sample_processed_database_knowledge` from `knowledge_pipeline`.

- [ ] **Step 2: Run test and verify it fails**

```powershell
& $py -m pytest tests/unit/workflows/nl2sql/test_nodes.py::test_build_prompt_node_uses_manual_processed_question_and_knowledge -q --basetemp .pytest_tmp
```

- [ ] **Step 3: Modify `build_prompt_node` minimally**

Change:

```python
processed_question = build_initial_processed_question(normalized_question)
processed_database_knowledge = build_sample_processed_database_knowledge()
```

to:

```python
processed_question = state.get("processed_question") or build_initial_processed_question(normalized_question)
processed_database_knowledge = (
    state.get("processed_database_knowledge")
    or build_sample_processed_database_knowledge()
)
```

- [ ] **Step 4: Run node and integration tests**

```powershell
& $py -m pytest tests/unit/workflows/nl2sql/test_nodes.py tests/integration/test_nl2sql_workflow.py -q --basetemp .pytest_tmp
```

Expected: PASS.

---

### Task 3: Add Case Contracts and Loader

**Files:**
- Create: `src/nl2sqlagent/workflows/nl2sql/sample_cases.py`
- Create: `tests/unit/workflows/nl2sql/test_sample_cases.py`

- [ ] **Step 1: Write failing tests for loader**

Test cases:

```python
def test_load_sample_case_file_returns_cases(tmp_path: Path) -> None: ...
def test_sample_case_to_input_preserves_manual_middle_layer() -> None: ...
def test_sample_case_expectations_can_check_prompt_contains_and_excludes() -> None: ...
def test_load_sample_case_file_rejects_duplicate_case_ids(tmp_path: Path) -> None: ...
```

Use a tiny temporary JSON file in tests. Do not depend on the full Phase8 JSON yet.

- [ ] **Step 2: Run tests and verify they fail**

```powershell
& $py -m pytest tests/unit/workflows/nl2sql/test_sample_cases.py -q --basetemp .pytest_tmp
```

- [ ] **Step 3: Implement `sample_cases.py`**

Use dataclasses, not a deep class hierarchy:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput
from nl2sqlagent.workflows.nl2sql.knowledge_contracts import (
    ProcessedDatabaseKnowledge,
    ProcessedQuestion,
)


@dataclass(frozen=True)
class SchemaLinkingExpectation:
    selected_tables: list[str]
    relevant_columns: list[str]
    relationships: list[str]
    value_bindings: list[str]
    dropped_tables: list[str]


@dataclass(frozen=True)
class Nl2SqlSampleCase:
    case_id: str
    title: str
    risk_focus: str
    raw_question: str
    processed_question: ProcessedQuestion
    processed_database_knowledge: ProcessedDatabaseKnowledge
    expected_schema_linking: SchemaLinkingExpectation
    expected_prompt_contains: list[str]
    expected_prompt_excludes: list[str]
    expected_sql_shape: list[str]
    reference_sql: str
    review_notes: str = ""

    def to_input(self) -> Nl2SqlInput:
        return Nl2SqlInput(
            question=self.raw_question,
            request_id=self.case_id,
            case_id=self.case_id,
            processed_question=self.processed_question,
            processed_database_knowledge=self.processed_database_knowledge,
        )
```

Add:

```python
def load_sample_case_file(path: Path) -> list[Nl2SqlSampleCase]: ...
def assert_prompt_expectations(case: Nl2SqlSampleCase, final_prompt: str) -> None: ...
```

Validation rules:

- `case_id` must be non-empty and unique.
- `raw_question` must be non-empty.
- `processed_question.text` must be non-empty.
- shared `knowledge` must contain `dialect`, `tables`, `columns`, `relationships`, `value_bindings`, `business_terms`.
- `expected_prompt_contains` and `expected_sql_shape` must not be empty.

- [ ] **Step 4: Run loader tests**

```powershell
& $py -m pytest tests/unit/workflows/nl2sql/test_sample_cases.py -q --basetemp .pytest_tmp
```

Expected: PASS.

---

### Task 4: Add Phase8 Case File

**Files:**
- Create: `examples/nl2sql_cases/phase8_cases.json`
- Test: `tests/unit/workflows/nl2sql/test_sample_cases.py`

- [ ] **Step 1: Add test that loads real Phase8 case file**

```python
def test_phase8_case_file_loads_all_expected_cases() -> None:
    path = Path("examples/nl2sql_cases/phase8_cases.json")
    cases = load_sample_case_file(path)

    assert [case.case_id for case in cases] == [
        "case_001_active_employee_count",
        "case_002_active_employee_by_department",
        "case_003_inactive_employee_by_department",
        "case_004_full_time_employee_count",
        "case_005_drop_import_table",
        "case_006_ambiguous_employee_count",
    ]
```

- [ ] **Step 2: Run test and verify it fails**

```powershell
& $py -m pytest tests/unit/workflows/nl2sql/test_sample_cases.py::test_phase8_case_file_loads_all_expected_cases -q --basetemp .pytest_tmp
```

- [ ] **Step 3: Create `phase8_cases.json`**

Use the data shape above.

Important case expectations:

`case_001_active_employee_count`:

```text
contains:
  Table: hr_emp_base
  在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
excludes:
  Table: hr_dept_dim
  Table: tmp_import_record
```

`case_002_active_employee_by_department`:

```text
contains:
  Table: hr_emp_base
  Table: hr_dept_dim
  hr_emp_base.dept_id = hr_dept_dim.dept_id
  在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
```

`case_003_inactive_employee_by_department`:

```text
contains:
  离职员工 -> hr_emp_base.emp_stat_cd = INACTIVE
excludes:
  在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
```

`case_004_full_time_employee_count`:

```text
contains:
  正式员工 -> hr_emp_base.emp_type_cd = FULL_TIME
  emp_type_cd
```

`case_005_drop_import_table`:

```text
contains:
  Table: hr_emp_base
excludes:
  Table: tmp_import_record
expected dropped_tables:
  tmp_import_record
```

`case_006_ambiguous_employee_count`:

```text
contains:
  Table: hr_emp_base
  未限定员工状态，默认统计全部员工
excludes:
  在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE
  离职员工 -> hr_emp_base.emp_stat_cd = INACTIVE
```

- [ ] **Step 4: Run loader tests**

```powershell
& $py -m pytest tests/unit/workflows/nl2sql/test_sample_cases.py -q --basetemp .pytest_tmp
```

Expected: PASS.

---

### Task 5: Adjust Schema Linking for Phase8 Expectations

**Files:**
- Modify: `src/nl2sqlagent/workflows/nl2sql/knowledge_pipeline.py`
- Test: `tests/unit/workflows/nl2sql/test_knowledge_pipeline.py`
- Test: `tests/unit/workflows/nl2sql/test_sample_cases.py`

- [ ] **Step 1: Write tests for unverified/staging table drop**

Add a focused test where retrieval contains a table candidate for `tmp_import_record`, knowledge has that table with `verified=False` or `table_type="staging"`, and `build_schema_linking_result` returns:

```python
assert "tmp_import_record" not in selected_table_names
assert {
    "target_type": "table",
    "target_name": "tmp_import_record",
    ...
} in dropped_candidates
```

Do not rely on the LLM for this test.

- [ ] **Step 2: Run test and verify it fails**

```powershell
& $py -m pytest tests/unit/workflows/nl2sql/test_knowledge_pipeline.py::test_schema_linking_drops_unverified_staging_table_candidate -q --basetemp .pytest_tmp
```

- [ ] **Step 3: Implement minimal drop rule**

In `build_schema_linking_result`, when handling `kind == "table"`:

```python
table_type = str(table.get("table_type", "")).lower()
verified = bool(table.get("verified", False))
if table_type in {"staging", "temporary", "temp"} or not verified:
    dropped_candidates.append({
        "target_type": "table",
        "target_name": str(table.get("name", knowledge_id.split(":")[-1])),
        "reason": "unverified_or_staging_table",
        "score": score,
    })
    continue
```

Keep enabled table filtering intact.

- [ ] **Step 4: Make role assignment less hardcoded only if tests require it**

Current code uses:

```python
role = "primary" if table.get("name") == "hr_emp_base" else "join_support"
```

For Phase8, this is acceptable because the manual cases are HR-focused. Do not generalize unless a test fails for a concrete Phase8 case.

- [ ] **Step 5: Run knowledge pipeline tests**

```powershell
& $py -m pytest tests/unit/workflows/nl2sql/test_knowledge_pipeline.py -q --basetemp .pytest_tmp
```

Expected: PASS.

---

### Task 6: Verify All Phase8 Cases Through Prompt Building

**Files:**
- Test: `tests/integration/test_nl2sql_case_runner.py` or `tests/integration/test_nl2sql_phase8_cases.py`

- [ ] **Step 1: Write fake-generator integration test for all cases**

For each loaded case:

```python
app = build_app(
    project_root=tmp_path_or_repo_root,
    run_id=f"phase8-test-{case.case_id}",
    sql_generator_override=FakeSqlGenerator(sql=case.reference_sql),
)
output = app.nl2sql_workflow.run(case.to_input(), thread_id=f"thread-{case.case_id}")
```

Assert:

```python
assert output.status == "success"
assert output.sql == case.reference_sql
assert output.metadata["artifact_manifest_path"]
assert_prompt_expectations(case, output.metadata["final_prompt"])
```

Also assert selected/dropped expectations from `output.metadata["schema_linking_result"]`:

```python
selected_tables = {item["table_name"] for item in linking["selected_tables"]}
assert set(case.expected_schema_linking.selected_tables) <= selected_tables

dropped_tables = {item["target_name"] for item in linking["dropped_candidates"]}
assert set(case.expected_schema_linking.dropped_tables) <= dropped_tables
```

- [ ] **Step 2: Run test and verify it fails because `build_app` lacks override**

```powershell
& $py -m pytest tests/integration/test_nl2sql_case_runner.py -q --basetemp .pytest_tmp
```

- [ ] **Step 3: Add optional `sql_generator_override` to `build_app`**

In `container.py`:

```python
def build_app(
    *,
    project_root: Path | None = None,
    config_dir: Path | None = None,
    run_id: str | None = None,
    sql_generator_override: SqlGenerator | None = None,
) -> NL2SQLAgentApp:
    ...
    sql_generator = sql_generator_override or build_sql_generator(...)
```

Keep `build_sql_generator` unchanged.

- [ ] **Step 4: Run integration test**

```powershell
& $py -m pytest tests/integration/test_nl2sql_case_runner.py -q --basetemp .pytest_tmp
```

Expected: PASS.

---

### Task 7: Add CLI Case Runner

**Files:**
- Create: `src/nl2sqlagent/interfaces/cli/commands/nl2sql_cases.py`
- Modify: `src/nl2sqlagent/interfaces/cli/main.py`
- Test: `tests/integration/test_startup_cli.py` or create `tests/integration/test_nl2sql_case_cli.py`

- [ ] **Step 1: Write CLI tests**

Add tests:

```python
def test_cli_run_nl2sql_cases_with_fake_generator(tmp_path: Path) -> None: ...
def test_cli_run_nl2sql_cases_can_filter_case_id(tmp_path: Path) -> None: ...
def test_cli_run_nl2sql_cases_requires_real_llm_flag_for_provider_call(tmp_path: Path) -> None: ...
```

The fake CLI test should run without `DASHSCOPE_API_KEY`.

- [ ] **Step 2: Run tests and verify they fail**

```powershell
& $py -m pytest tests/integration/test_nl2sql_case_cli.py -q --basetemp .pytest_tmp
```

- [ ] **Step 3: Implement command module**

In `nl2sql_cases.py`, implement:

```python
def run_nl2sql_cases_summary(
    *,
    cases_path: Path,
    case_id: str | None = None,
    project_root: Path | None = None,
    config_dir: Path | None = None,
    run_id: str | None = None,
    real_llm: bool = False,
) -> str:
    ...
```

Behavior:

- Load all cases from `cases_path`.
- If `case_id` is provided, run only that case.
- If `real_llm` is false, build one app per case with `FakeSqlGenerator(sql=case.reference_sql)`.
- If `real_llm` is true, build app without override so config controls provider.
- Use `run_id` or default `phase8-manual-cases`.
- Run each case through `app.nl2sql_workflow.run(case.to_input(), thread_id=f"thread-{case.case_id}")`.
- Return compact JSON text:

```json
{
  "run_id": "phase8-manual-cases",
  "real_llm": false,
  "cases": [
    {
      "case_id": "case_001_active_employee_count",
      "status": "success",
      "sql": "...",
      "artifact_manifest_path": "..."
    }
  ]
}
```

- [ ] **Step 4: Wire CLI parser**

Add command choice:

```python
choices=("startup", "run-nl2sql-cases")
```

Add args:

```text
--cases-path
--case-id
--real-llm
```

Default cases path:

```text
examples/nl2sql_cases/phase8_cases.json
```

- [ ] **Step 5: Run CLI tests**

```powershell
& $py -m pytest tests/integration/test_nl2sql_case_cli.py tests/integration/test_startup_cli.py -q --basetemp .pytest_tmp
```

Expected: PASS.

---

### Task 8: Add Architecture Guards

**Files:**
- Modify: `tests/unit/workflows/nl2sql/test_contracts.py`

- [ ] **Step 1: Add or extend guards**

Add checks:

```python
def test_phase8_does_not_add_stage_chain_or_use_llm_generate() -> None:
    forbidden = [
        "use_llm_generate",
        "GenerateStage",
        "Nl2SqlChain",
        "MainOrchestration",
    ]
    ...
```

Add guard that sample case loader does not import provider packages:

```python
def test_sample_cases_do_not_import_llm_provider() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/sample_cases.py").read_text(encoding="utf-8")
    assert "ChatOpenAI" not in source
    assert "DASHSCOPE_API_KEY" not in source
    assert "langchain_openai" not in source
```

Add guard that `nodes.py` still does not import provider packages.

- [ ] **Step 2: Run contract tests**

```powershell
& $py -m pytest tests/unit/workflows/nl2sql/test_contracts.py -q --basetemp .pytest_tmp
```

Expected: PASS.

---

### Task 9: Document How to Run and Review Cases

**Files:**
- Modify: `docs/project/Phase8_NL2SQL人工样例验证设计.md`
- Modify: `docs/project/Phase7_NL2SQL真实运行产物说明.md` only if needed

- [ ] **Step 1: Add command examples**

In `Phase8_NL2SQL人工样例验证设计.md`, add a short section:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()

# fake generator, no token cost
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --run-id phase8-fake-cases

# one case with fake generator
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --case-id case_002_active_employee_by_department --run-id phase8-one-case

# explicit real LLM run
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --real-llm --case-id case_002_active_employee_by_department --run-id phase8-real-case
```

Explain:

- fake run proves artifacts and prompt expectations.
- real run consumes LLM tokens and checks actual SQL behavior.
- review order remains `manifest -> output.metadata -> prompt_payload -> final_prompt -> llm_result`.

- [ ] **Step 2: Update current-stage summary if needed**

If implementation changes the next-stage status, update `docs/project/NL2SQL当前阶段总结与后续路线.md` only in a small paragraph. Do not rewrite the whole doc.

---

### Task 10: Final Verification

**Files:**
- No new code unless verification reveals a bug.

- [ ] **Step 1: Run focused test suite**

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest `
  tests/unit/workflows/nl2sql/test_sample_cases.py `
  tests/unit/workflows/nl2sql/test_knowledge_pipeline.py `
  tests/unit/workflows/nl2sql/test_nodes.py `
  tests/unit/workflows/nl2sql/test_contracts.py `
  tests/integration/test_nl2sql_case_runner.py `
  tests/integration/test_nl2sql_case_cli.py `
  -q --basetemp .pytest_tmp
```

Expected: PASS.

- [ ] **Step 2: Run full default tests**

```powershell
& $py -m pytest -q --basetemp .pytest_tmp
```

Expected: PASS with cloud tests deselected.

- [ ] **Step 3: Run fake sample CLI once**

```powershell
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases --run-id phase8-fake-cases
```

Expected:

- exit code 0.
- JSON summary printed.
- each case status is `success`.
- artifacts appear under `workspace/logs/{run_date}/phase8-fake-cases/artifacts/nl2sql/{case_id}/`.

- [ ] **Step 4: Inspect one artifact**

Open:

```text
workspace/logs/{run_date}/phase8-fake-cases/artifacts/nl2sql/case_002_active_employee_by_department/final_prompt.txt
workspace/logs/{run_date}/phase8-fake-cases/artifacts/nl2sql/case_002_active_employee_by_department/output.json
```

Verify:

- `final_prompt.txt` contains `hr_emp_base.dept_id = hr_dept_dim.dept_id`.
- `final_prompt.txt` contains `在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE`.
- `output.json.metadata.schema_linking_result` exists.
- `output.json.metadata.llm_result.model_name` is `fake-sql-generator` for fake run.

- [ ] **Step 5: Optional real LLM smoke test**

Only run if explicitly requested and `DASHSCOPE_API_KEY` is configured:

```powershell
& $py -m nl2sqlagent.interfaces.cli.main run-nl2sql-cases `
  --real-llm `
  --case-id case_002_active_employee_by_department `
  --run-id phase8-real-case
```

Expected:

- exit code 0 if provider is reachable.
- artifact `output.json.metadata.llm_result.model_name` is the configured model.
- generated SQL uses employee table, department table, join, active value binding, group by department.

Do not make the real LLM smoke test part of default pytest.

## Handoff Notes

- Keep edits small and commit after each completed task if the user asks for commits.
- If a Phase8 case fails because current linking logic is too weak, fix the smallest rule needed for that case and add a focused test.
- If a case reveals that `ProcessedQuestion` or `ProcessedDatabaseKnowledge` cannot express the needed semantics, do not invent a large abstraction. Mark that case as `fail_case_design` in notes and report it.
- Do not let fake sample runs hide prompt problems: fake SQL only avoids token cost; prompt and schema-linking expectations still must be asserted.
