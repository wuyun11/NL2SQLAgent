# NL2SQL Prompt Payload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Phase 2's mock NL2SQL prompt into a structured Phase 3 `prompt_payload` and deterministic `final_prompt`, while keeping the workflow linear and mock-only.

**Architecture:** Keep all Phase 3 prompt work inside `src/nl2sqlagent/workflows/nl2sql/`. Add one pure payload builder and one pure prompt renderer, then make `build_prompt_node` call them. Do not add real LLM/database/schema grounding, retry, CLI `ask`, or `services/`.

**Tech Stack:** Python 3.12, TypedDict-compatible dictionaries, pure functions, existing LangGraph workflow, pytest.

---

## 0. Scope Guard

This plan implements:

```text
docs/temp/Phase3_NL2SQL提示词结构设计.md
```

Before any Python command, follow the repository rule:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
```

Do not use bare `python`.

Allowed to create:

```text
src/nl2sqlagent/workflows/nl2sql/prompt_payload.py
src/nl2sqlagent/workflows/nl2sql/prompt_builder.py
tests/unit/workflows/nl2sql/test_prompt_payload.py
tests/unit/workflows/nl2sql/test_prompt_builder.py
```

Allowed to modify:

```text
src/nl2sqlagent/workflows/nl2sql/nodes.py
tests/unit/workflows/nl2sql/test_nodes.py
tests/unit/workflows/nl2sql/test_response_builder.py
tests/integration/test_nl2sql_workflow.py
```

Modify only if needed:

```text
src/nl2sqlagent/workflows/nl2sql/__init__.py
```

Forbidden in this phase:

```text
src/nl2sqlagent/domain/
src/nl2sqlagent/services/
src/nl2sqlagent/integrations/
src/nl2sqlagent/interfaces/cli/commands/ask.py
real LLM
real database
real SQL execution
real schema reading
real schema grounding
semantic.yml loading
sql_policy.yml loading
retry / feedback loop
round_index / max_round_count
QueryPlan
Human Review
old SQLAgent code migration
```

Design rules:

```text
1. Keep the graph shape unchanged:
   normalize_question -> build_prompt -> generate_sql -> check_sql -> execute_sql -> response.
2. build_prompt_node must delegate payload construction and prompt rendering to pure functions.
3. prompt_payload must contain:
   task / question / schema_context / semantic_context / sql_policy / output_contract / debug.
4. schema_context.tables is the allowed table scope.
5. semantic_context.rules is for business rules only.
6. sql_policy is for SQL safety and formatting rules only.
7. final_prompt must render:
   Task / User Question / Schema Context / Semantic Context / SQL Policy / Output Contract.
8. final_prompt must not render debug.
9. generate_sql_node remains mock and returns only:
   SELECT 1 AS value
10. output metadata and stream updates must keep exposing prompt_payload and final_prompt.
```

Current dirty-worktree caution:

```text
The user may have unrelated uncommitted files under docs/temp, including:
  docs/temp/其他ai的评价.md
  docs/temp/Phase3_NL2SQL提示词结构设计.md

Do not stage, restore, or commit those files unless explicitly instructed.
```

---

## 1. Target File Responsibilities

```text
prompt_payload.py
  Defines build_mock_prompt_payload(...).
  Returns structured Phase 3 prompt materials.
  Does not render final prompt text.
  Does not read config, schema files, semantic files, logger, graph state, DB, or external clients.

prompt_builder.py
  Defines render_final_prompt(prompt_payload).
  Converts structured prompt_payload into stable final_prompt text.
  Does not mutate prompt_payload.
  Does not render debug.

nodes.py
  Keeps workflow nodes.
  build_prompt_node becomes thin orchestration:
    read raw/normalized question from state,
    call build_mock_prompt_payload(...),
    call render_final_prompt(...),
    return prompt_payload and final_prompt.

test_prompt_payload.py
  Verifies structured payload fields and field meanings.

test_prompt_builder.py
  Verifies final_prompt sections, order, policy text, no debug, and output-contract wording (instruct model not to use markdown fences) without the renderer embedding ``` fences.

test_nodes.py
  Verifies build_prompt_node uses the structured payload and renderer output.

test_nl2sql_workflow.py
  Verifies run metadata and stream updates expose structured payload and final_prompt.
```

---

## Task 1: Prompt Payload Builder

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/prompt_payload.py`
- Test: `tests/unit/workflows/nl2sql/test_prompt_payload.py`

- [ ] **Step 1: Write failing payload tests**

Create `tests/unit/workflows/nl2sql/test_prompt_payload.py`:

```python
from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.prompt_payload import build_mock_prompt_payload


def test_build_mock_prompt_payload_has_phase3_top_level_fields() -> None:
    payload = build_mock_prompt_payload(
        raw_question="  统计员工数量  ",
        normalized_question="统计员工数量",
    )

    assert list(payload) == [
        "task",
        "question",
        "schema_context",
        "semantic_context",
        "sql_policy",
        "output_contract",
        "debug",
    ]


def test_build_mock_prompt_payload_preserves_raw_and_normalized_question() -> None:
    payload = build_mock_prompt_payload(
        raw_question="  统计员工数量  ",
        normalized_question="统计员工数量",
    )

    assert payload["question"] == {
        "raw": "  统计员工数量  ",
        "normalized": "统计员工数量",
    }


def test_build_mock_prompt_payload_defines_allowed_schema_scope() -> None:
    payload = build_mock_prompt_payload(
        raw_question="统计员工数量",
        normalized_question="统计员工数量",
    )

    schema_context = payload["schema_context"]
    assert schema_context["dialect"] == "sqlite"
    assert schema_context["relationships"] == []
    assert schema_context["tables"] == [
        {
            "name": "employee",
            "description": "mock employee table",
            "columns": [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "description": "employee id",
                },
                {
                    "name": "name",
                    "type": "TEXT",
                    "description": "employee name",
                },
            ],
        }
    ]


def test_build_mock_prompt_payload_separates_semantic_rules_from_sql_policy() -> None:
    payload = build_mock_prompt_payload(
        raw_question="统计员工数量",
        normalized_question="统计员工数量",
    )

    assert payload["semantic_context"] == {
        "business_terms": [
            {
                "name": "员工",
                "description": "mock business term for employee",
            }
        ],
        "rules": [
            "Use only active records when such flag is available.",
        ],
        "assumptions": [
            "No extra business filter is applied in Phase 3 mock prompt.",
        ],
    }
    assert payload["sql_policy"] == {
        "readonly_only": True,
        "allow_select_star": False,
        "require_limit": True,
        "default_limit": 100,
    }


def test_build_mock_prompt_payload_defines_output_contract_and_debug() -> None:
    payload = build_mock_prompt_payload(
        raw_question="统计员工数量",
        normalized_question="统计员工数量",
    )

    assert payload["output_contract"] == {
        "format": "sql_only",
        "requirements": [
            "Return only one SQL statement.",
            "Do not include markdown fences.",
            "Do not explain the SQL.",
        ],
    }
    assert payload["debug"] == {
        "prompt_version": "phase3.mock.v1",
        "source": "mock_prompt_payload_builder",
    }
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_prompt_payload.py -v
```

Expected:

```text
FAIL because nl2sqlagent.workflows.nl2sql.prompt_payload does not exist.
```

- [ ] **Step 3: Implement prompt payload builder**

Create `src/nl2sqlagent/workflows/nl2sql/prompt_payload.py`:

```python
from __future__ import annotations

from typing import Any


def build_mock_prompt_payload(
    *,
    raw_question: str,
    normalized_question: str,
) -> dict[str, Any]:
    return {
        "task": {
            "type": "nl2sql",
            "goal": "Generate a read-only SQL query for the user question.",
        },
        "question": {
            "raw": raw_question,
            "normalized": normalized_question,
        },
        "schema_context": {
            "dialect": "sqlite",
            "tables": [
                {
                    "name": "employee",
                    "description": "mock employee table",
                    "columns": [
                        {
                            "name": "id",
                            "type": "INTEGER",
                            "description": "employee id",
                        },
                        {
                            "name": "name",
                            "type": "TEXT",
                            "description": "employee name",
                        },
                    ],
                }
            ],
            "relationships": [],
        },
        "semantic_context": {
            "business_terms": [
                {
                    "name": "员工",
                    "description": "mock business term for employee",
                }
            ],
            "rules": [
                "Use only active records when such flag is available.",
            ],
            "assumptions": [
                "No extra business filter is applied in Phase 3 mock prompt.",
            ],
        },
        "sql_policy": {
            "readonly_only": True,
            "allow_select_star": False,
            "require_limit": True,
            "default_limit": 100,
        },
        "output_contract": {
            "format": "sql_only",
            "requirements": [
                "Return only one SQL statement.",
                "Do not include markdown fences.",
                "Do not explain the SQL.",
            ],
        },
        "debug": {
            "prompt_version": "phase3.mock.v1",
            "source": "mock_prompt_payload_builder",
        },
    }


__all__ = ["build_mock_prompt_payload"]
```

- [ ] **Step 4: Run payload tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_prompt_payload.py -v
```

Expected:

```text
5 passed
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/prompt_payload.py tests/unit/workflows/nl2sql/test_prompt_payload.py
git commit -m "feat: add nl2sql prompt payload builder"
```

---

## Task 2: Final Prompt Renderer

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/prompt_builder.py`
- Test: `tests/unit/workflows/nl2sql/test_prompt_builder.py`

- [ ] **Step 1: Write failing prompt builder tests**

Create `tests/unit/workflows/nl2sql/test_prompt_builder.py`:

```python
from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.prompt_builder import render_final_prompt
from nl2sqlagent.workflows.nl2sql.prompt_payload import build_mock_prompt_payload


def _payload() -> dict:
    return build_mock_prompt_payload(
        raw_question="  统计员工数量  ",
        normalized_question="统计员工数量",
    )


def test_render_final_prompt_contains_expected_sections() -> None:
    final_prompt = render_final_prompt(_payload())

    assert "You are an NL2SQL assistant." in final_prompt
    assert "Task:" in final_prompt
    assert "User Question:" in final_prompt
    assert "Schema Context:" in final_prompt
    assert "Semantic Context:" in final_prompt
    assert "SQL Policy:" in final_prompt
    assert "Output Contract:" in final_prompt


def test_render_final_prompt_keeps_section_order_stable() -> None:
    final_prompt = render_final_prompt(_payload())

    assert final_prompt.index("Task:") < final_prompt.index("User Question:")
    assert final_prompt.index("User Question:") < final_prompt.index("Schema Context:")
    assert final_prompt.index("Schema Context:") < final_prompt.index("Semantic Context:")
    assert final_prompt.index("Semantic Context:") < final_prompt.index("SQL Policy:")
    assert final_prompt.index("SQL Policy:") < final_prompt.index("Output Contract:")


def test_render_final_prompt_uses_normalized_question_and_allowed_tables() -> None:
    final_prompt = render_final_prompt(_payload())

    assert "统计员工数量" in final_prompt
    assert "Allowed tables:" in final_prompt
    assert "- Table: employee" in final_prompt
    assert "Description: mock employee table" in final_prompt
    assert "- id (INTEGER): employee id" in final_prompt
    assert "- name (TEXT): employee name" in final_prompt


def test_render_final_prompt_separates_semantic_context_and_sql_policy() -> None:
    final_prompt = render_final_prompt(_payload())

    assert "- Term 员工: mock business term for employee" in final_prompt
    assert "- Rule: Use only active records when such flag is available." in final_prompt
    assert "- Assumption: No extra business filter is applied in Phase 3 mock prompt." in final_prompt
    assert "- Readonly only: true" in final_prompt
    assert "- SELECT * allowed: false" in final_prompt
    assert "- LIMIT required: true" in final_prompt
    assert "- Default LIMIT: 100" in final_prompt


def test_render_final_prompt_instructs_no_markdown_fences_without_using_fences() -> None:
    final_prompt = render_final_prompt(_payload())

    assert "- Return only one SQL statement." in final_prompt
    assert "- Do not include markdown fences." in final_prompt
    assert "- Do not explain the SQL." in final_prompt
    assert "```" not in final_prompt


def test_render_final_prompt_does_not_render_debug() -> None:
    final_prompt = render_final_prompt(_payload())

    assert "Debug:" not in final_prompt
    assert "phase3.mock.v1" not in final_prompt
    assert "mock_prompt_payload_builder" not in final_prompt
```

Note: `test_render_final_prompt_instructs_no_markdown_fences_without_using_fences` checks two things: `final_prompt` may **tell the model** not to use markdown fences (the requirement line in Output Contract), and the **renderer** must not embed markdown code-fence delimiters in `final_prompt`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_prompt_builder.py -v
```

Expected:

```text
FAIL because nl2sqlagent.workflows.nl2sql.prompt_builder does not exist.
```

- [ ] **Step 3: Implement prompt renderer**

Create `src/nl2sqlagent/workflows/nl2sql/prompt_builder.py`:

```python
from __future__ import annotations

from typing import Any


def _bool_text(value: object) -> str:
    return "true" if value is True else "false"


def _render_schema_context(schema_context: dict[str, Any]) -> list[str]:
    lines = [
        f"Dialect: {schema_context.get('dialect', '')}",
        "Allowed tables:",
    ]
    for table in schema_context.get("tables", []):
        lines.append(f"- Table: {table.get('name', '')}")
        description = table.get("description")
        if description:
            lines.append(f"  Description: {description}")
        lines.append("  Columns:")
        for column in table.get("columns", []):
            lines.append(
                "  - "
                f"{column.get('name', '')} "
                f"({column.get('type', '')}): "
                f"{column.get('description', '')}"
            )

    relationships = schema_context.get("relationships") or []
    if relationships:
        lines.append("Relationships:")
        for relationship in relationships:
            lines.append(f"- {relationship}")
    else:
        lines.append("Relationships: none")
    return lines


def _render_semantic_context(semantic_context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for term in semantic_context.get("business_terms", []):
        lines.append(f"- Term {term.get('name', '')}: {term.get('description', '')}")
    for rule in semantic_context.get("rules", []):
        lines.append(f"- Rule: {rule}")
    for assumption in semantic_context.get("assumptions", []):
        lines.append(f"- Assumption: {assumption}")
    return lines or ["- none"]


def _render_sql_policy(sql_policy: dict[str, Any]) -> list[str]:
    return [
        f"- Readonly only: {_bool_text(sql_policy.get('readonly_only'))}",
        f"- SELECT * allowed: {_bool_text(sql_policy.get('allow_select_star'))}",
        f"- LIMIT required: {_bool_text(sql_policy.get('require_limit'))}",
        f"- Default LIMIT: {sql_policy.get('default_limit')}",
    ]


def _render_output_contract(output_contract: dict[str, Any]) -> list[str]:
    return [f"- {requirement}" for requirement in output_contract.get("requirements", [])]


def render_final_prompt(prompt_payload: dict[str, Any]) -> str:
    task = prompt_payload["task"]
    question = prompt_payload["question"]
    schema_context = prompt_payload["schema_context"]
    semantic_context = prompt_payload["semantic_context"]
    sql_policy = prompt_payload["sql_policy"]
    output_contract = prompt_payload["output_contract"]

    sections: list[str] = [
        "You are an NL2SQL assistant.",
        "",
        "Task:",
        str(task["goal"]),
        "",
        "User Question:",
        str(question["normalized"]),
        "",
        "Schema Context:",
        *_render_schema_context(schema_context),
        "",
        "Semantic Context:",
        *_render_semantic_context(semantic_context),
        "",
        "SQL Policy:",
        *_render_sql_policy(sql_policy),
        "",
        "Output Contract:",
        *_render_output_contract(output_contract),
    ]
    return "\n".join(sections)


__all__ = ["render_final_prompt"]
```

- [ ] **Step 4: Run prompt builder tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_prompt_builder.py -v
```

Expected:

```text
6 passed
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/prompt_builder.py tests/unit/workflows/nl2sql/test_prompt_builder.py
git commit -m "feat: render nl2sql final prompt"
```

---

## Task 3: Wire Structured Prompt Into build_prompt_node

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/nodes.py`
- Modify: `tests/unit/workflows/nl2sql/test_nodes.py`

- [ ] **Step 1: Update node tests for structured payload**

In `tests/unit/workflows/nl2sql/test_nodes.py`, replace `test_build_prompt_node_creates_payload_and_final_prompt` with:

```python
def test_build_prompt_node_creates_structured_payload_and_final_prompt() -> None:
    result = build_prompt_node(
        {
            "raw_question": "  统计员工数量  ",
            "normalized_question": "统计员工数量",
        }
    )

    assert result["prompt_payload"]["question"] == {
        "raw": "  统计员工数量  ",
        "normalized": "统计员工数量",
    }
    assert result["prompt_payload"]["schema_context"]["dialect"] == "sqlite"
    assert result["prompt_payload"]["schema_context"]["tables"][0]["name"] == "employee"
    assert result["prompt_payload"]["sql_policy"]["readonly_only"] is True
    assert result["prompt_payload"]["output_contract"]["format"] == "sql_only"
    assert result["prompt_payload"]["debug"]["prompt_version"] == "phase3.mock.v1"
    assert "User Question:\n统计员工数量" in result["final_prompt"]
    assert "Allowed tables:" in result["final_prompt"]
    assert "- Table: employee" in result["final_prompt"]
    assert "SQL Policy:" in result["final_prompt"]
    assert "Output Contract:" in result["final_prompt"]
    assert "phase3.mock.v1" not in result["final_prompt"]
```

Add this test near `test_generate_sql_node_returns_mock_sql`:

```python
def test_generate_sql_node_returns_sql_only_mock_sql() -> None:
    result = generate_sql_node({"final_prompt": "User Question:\n统计员工数量"})

    assert result == {"generated_sql": "SELECT 1 AS value"}
    assert "```" not in result["generated_sql"]
    assert "\n" not in result["generated_sql"]
```

If the old `test_generate_sql_node_returns_mock_sql` duplicates the same behavior, either replace it with this version or keep only one of them.

- [ ] **Step 2: Run node tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_nodes.py -v
```

Expected:

```text
FAIL because build_prompt_node still returns the Phase 2 flat mock payload.
```

- [ ] **Step 3: Update build_prompt_node**

Modify `src/nl2sqlagent/workflows/nl2sql/nodes.py`.

Add imports:

```python
from nl2sqlagent.workflows.nl2sql.prompt_builder import render_final_prompt
from nl2sqlagent.workflows.nl2sql.prompt_payload import build_mock_prompt_payload
```

Replace `build_prompt_node` with:

```python
def build_prompt_node(state: Nl2SqlGraphState) -> dict:
    raw_question = state.get("raw_question") or state.get("normalized_question") or ""
    normalized_question = state.get("normalized_question") or raw_question.strip()
    prompt_payload = build_mock_prompt_payload(
        raw_question=raw_question,
        normalized_question=normalized_question,
    )
    return {
        "prompt_payload": prompt_payload,
        "final_prompt": render_final_prompt(prompt_payload),
    }
```

Keep all other nodes mock-only. Do not alter graph edges.

- [ ] **Step 4: Run node tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_nodes.py -v
```

Expected:

```text
All node tests pass.
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/nodes.py tests/unit/workflows/nl2sql/test_nodes.py
git commit -m "feat: use structured nl2sql prompt payload"
```

---

## Task 4: Update Output Metadata And Workflow Expectations

**Files:**

- Modify: `tests/unit/workflows/nl2sql/test_response_builder.py`
- Modify: `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Update response builder tests to use structured prompt metadata**

In `tests/unit/workflows/nl2sql/test_response_builder.py`, update tests that hard-code flat prompt payloads.

Use structured examples like:

```python
prompt_payload = {
    "question": {
        "raw": "统计员工数量",
        "normalized": "统计员工数量",
    },
    "debug": {
        "prompt_version": "phase3.mock.v1",
        "source": "mock_prompt_payload_builder",
    },
}
```

For assertions, prefer:

```python
assert output.metadata["prompt_payload"]["question"]["normalized"] == "统计员工数量"
assert output.metadata["prompt_payload"]["debug"]["prompt_version"] == "phase3.mock.v1"
assert "User Question:\n统计员工数量" in output.metadata["final_prompt"]
```

Do not change `response_builder.py` unless tests reveal an actual bug. It should already pass through `prompt_payload` and `final_prompt`.

- [ ] **Step 2: Update integration tests for new final_prompt text**

In `tests/integration/test_nl2sql_workflow.py`, replace old assertions like:

```python
assert "Question: 统计员工数量" in result["final_prompt"]
assert output.metadata["prompt_payload"]["question"] == "统计员工数量"
```

with:

```python
assert "User Question:\n统计员工数量" in result["final_prompt"]
assert "Schema Context:" in result["final_prompt"]
assert "SQL Policy:" in result["final_prompt"]
assert "Output Contract:" in result["final_prompt"]
assert "phase3.mock.v1" not in result["final_prompt"]
assert result["prompt_payload"]["question"]["normalized"] == "统计员工数量"
assert result["prompt_payload"]["schema_context"]["tables"][0]["name"] == "employee"
```

For workflow output assertions, use:

```python
assert "User Question:\n统计员工数量" in output.metadata["final_prompt"]
assert output.metadata["prompt_payload"]["question"]["normalized"] == "统计员工数量"
assert output.metadata["prompt_payload"]["debug"]["prompt_version"] == "phase3.mock.v1"
assert "phase3.mock.v1" not in output.metadata["final_prompt"]
```

For stream assertions, use:

```python
assert any(
    isinstance(chunk, dict)
    and "build_prompt" in chunk
    and chunk["build_prompt"]["prompt_payload"]["question"]["normalized"] == "统计员工数量"
    and "User Question:\n统计员工数量" in chunk["build_prompt"]["final_prompt"]
    and "phase3.mock.v1" not in chunk["build_prompt"]["final_prompt"]
    for chunk in chunks
)
```

- [ ] **Step 3: Run response builder and workflow tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_response_builder.py tests/integration/test_nl2sql_workflow.py -v
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 4: Commit**

```powershell
git add tests/unit/workflows/nl2sql/test_response_builder.py tests/integration/test_nl2sql_workflow.py
git commit -m "test: update nl2sql prompt metadata expectations"
```

---

## Task 5: Package Boundary And Regression Sweep

**Files:**

- Modify only if needed: `src/nl2sqlagent/workflows/nl2sql/__init__.py`

- [ ] **Step 1: Decide whether to export prompt helpers**

Default decision:

```text
Do not export build_mock_prompt_payload or render_final_prompt from __init__.py.
```

Reason:

```text
They are Phase 3 workflow-internal helpers.
Tests can import them from their concrete modules.
The public workflow package surface can remain Nl2SqlInput / Nl2SqlOutput / Nl2SqlWorkflow / build_nl2sql_graph.
```

Only modify `__init__.py` if an existing package-level import pattern forces it.

- [ ] **Step 2: Run all NL2SQL unit and integration tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql tests/integration/test_nl2sql_workflow.py -v
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 3: Commit package-boundary fixes if any**

If `__init__.py` or other small boundary files needed changes:

```powershell
git add src/nl2sqlagent/workflows/nl2sql/__init__.py
git commit -m "chore: keep nl2sql prompt helper boundary"
```

Skip this commit if no files changed.

---

## Task 6: Final Verification

**Files:**

- All Phase 3 files

- [ ] **Step 1: Run NL2SQL workflow tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql tests/integration/test_nl2sql_workflow.py -v
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 2: Run all tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest -v
```

Expected:

```text
All tests pass.
```

- [ ] **Step 3: Compile source**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m compileall src\nl2sqlagent
```

Expected:

```text
No SyntaxError.
```

- [ ] **Step 4: Run smoke check for final prompt visibility**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -c "from nl2sqlagent.bootstrap import build_app; from nl2sqlagent.workflows.nl2sql import Nl2SqlInput; app = build_app(run_id='run-phase3-smoke'); output = app.nl2sql_workflow.run(Nl2SqlInput(question='统计员工数量'), thread_id='thread-phase3-smoke'); print(output.status); print(output.sql); print(output.metadata['prompt_payload']['question']['normalized']); print('User Question:' in output.metadata['final_prompt']); print('phase3.mock.v1' in output.metadata['final_prompt']); print(output.metadata['prompt_payload']['debug']['prompt_version'])"
```

Expected:

```text
success
SELECT 1 AS value
统计员工数量
True
False
phase3.mock.v1
```

- [ ] **Step 5: Confirm forbidden paths were not created**

Run:

```powershell
Test-Path .\src\nl2sqlagent\domain
Test-Path .\src\nl2sqlagent\services
Test-Path .\src\nl2sqlagent\integrations
Test-Path .\src\nl2sqlagent\interfaces\cli\commands\ask.py
```

Expected:

```text
False
False
False
False
```

- [ ] **Step 6: Confirm no retry fields or feedback loop were introduced**

Run:

```powershell
$pattern = "round_index|max_round_count|feedback|feedback_section|route.*generate_sql|generate_sql.*route"
$rg = ".\.ai\local\tools\rg.exe"
if (Test-Path $rg) {
  & $rg $pattern src\nl2sqlagent\workflows\nl2sql
} else {
  Get-ChildItem -Path src\nl2sqlagent\workflows\nl2sql -Filter *.py -Recurse | ForEach-Object {
    Select-String -Path $_.FullName -Pattern $pattern
  }
}
```

Expected:

```text
No matches.
```

- [ ] **Step 7: Confirm final_prompt does not render debug**

Run:

```powershell
$rg = ".\.ai\local\tools\rg.exe"
if (Test-Path $rg) {
  & $rg "phase3\.mock\.v1|mock_prompt_payload_builder" tests src\nl2sqlagent\workflows\nl2sql
} else {
  Get-ChildItem -Path tests,src\nl2sqlagent\workflows\nl2sql -Filter *.py -Recurse | ForEach-Object {
    Select-String -Path $_.FullName -Pattern "phase3\.mock\.v1|mock_prompt_payload_builder"
  }
}
```

Expected:

```text
Matches exist only in payload construction and tests that assert debug is absent from final_prompt or present in metadata.
No renderer code should add debug to final_prompt.
```

- [ ] **Step 8: Diff check**

Run:

```powershell
git diff --check
```

Expected:

```text
No trailing whitespace errors.
```

- [ ] **Step 9: Final git status**

Run:

```powershell
git -c core.quotepath=false status --short
```

Expected:

```text
Only intentional Phase 3 implementation files are modified/untracked.
Unrelated docs/temp changes from the user remain untouched.
```

- [ ] **Step 10: Commit final fixes if needed**

If final verification required small fixes:

```powershell
git add <fixed Phase 3 implementation files only>
git commit -m "fix: stabilize nl2sql prompt payload"
```

Do not stage unrelated `docs/temp` files unless the user explicitly asks.

---

## Final Report Template

When complete, report:

```text
Implemented Phase 3 NL2SQL prompt payload.

What changed:
- Added structured build_mock_prompt_payload with task/question/schema_context/semantic_context/sql_policy/output_contract/debug.
- Added render_final_prompt with stable Task/User Question/Schema Context/Semantic Context/SQL Policy/Output Contract sections.
- Updated build_prompt_node to use the payload builder and prompt renderer.
- Kept generate/check/execute mock-only.
- Kept debug in prompt_payload metadata and out of final_prompt.
- Preserved workflow output metadata and stream visibility.

Verification:
- pytest tests/unit/workflows/nl2sql tests/integration/test_nl2sql_workflow.py -v: passed
- pytest -v: passed
- compileall src/nl2sqlagent: passed
- app workflow smoke: passed
- forbidden paths not created: confirmed
- no retry fields/routes introduced: confirmed

Remaining:
- Real LLM intentionally deferred.
- Real database/schema grounding intentionally deferred.
- retry/feedback intentionally deferred.
- CLI ask intentionally deferred.
```
