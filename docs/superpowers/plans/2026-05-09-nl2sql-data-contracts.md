# NL2SQL Data Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 5 lightweight NL2SQL data contracts so runtime options, prompt payload, graph state, and output metadata have clear ownership before real LLM/schema/DB integration.

**Architecture:** Keep LangGraph as the workflow state/update boundary and add only lightweight `TypedDict` contracts plus small constructor/normalizer functions. Do not add `stage`, `service`, `protocol`, `Nl2SqlContext`, domain/services/integrations directories, or any real external system integration.

**Tech Stack:** Python 3.12, LangGraph, dataclasses, `TypedDict`, pytest, existing NL2SQL workflow/artifact modules.

---

## 0. Scope Guard

This plan implements:

```text
docs/project/Phase5_NL2SQL数据契约设计.md
```

It also incorporates the latest `docs/temp/其他ai的评价.md` recommendations:

```text
1. normalize_runtime_options ignores unknown keys.
2. bool normalization accepts only real bool values; no string parsing.
3. runtime_options is built in workflow._graph_input, not in nodes.
4. response_builder gets a small prompt debug metadata boundary.
5. boundary tests avoid brittle broad string checks.
```

Before any Python command, follow the repository rule:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
```

Do not use bare `python`.

Allowed to create:

```text
src/nl2sqlagent/workflows/nl2sql/runtime_options.py
tests/unit/workflows/nl2sql/test_runtime_options.py
```

Allowed to modify:

```text
src/nl2sqlagent/workflows/nl2sql/workflow.py
src/nl2sqlagent/workflows/nl2sql/nodes.py
src/nl2sqlagent/workflows/nl2sql/prompt_payload.py
src/nl2sqlagent/workflows/nl2sql/prompt_builder.py
src/nl2sqlagent/workflows/nl2sql/response_builder.py
src/nl2sqlagent/workflows/nl2sql/state.py
src/nl2sqlagent/workflows/nl2sql/__init__.py
tests/unit/workflows/nl2sql/test_nodes.py
tests/unit/workflows/nl2sql/test_prompt_payload.py
tests/unit/workflows/nl2sql/test_prompt_builder.py
tests/unit/workflows/nl2sql/test_response_builder.py
tests/unit/workflows/nl2sql/test_contracts.py
tests/integration/test_nl2sql_workflow.py
```

Modify only if needed:

```text
src/nl2sqlagent/workflows/nl2sql/output.py
tests/unit/workflows/nl2sql/test_artifacts.py
```

Forbidden in this phase:

```text
real LLM calls
real database access
real schema grounding
retry / feedback loop
QueryPlan
CLI ask
domain/ directory
services/ directory
integrations/ directory
workflows/nl2sql/stages/ directory
stage classes
stage protocols
Nl2SqlContext wrapper
per-node result model classes
Pydantic/runtime validation framework
artifact format redesign
metadata breaking change
```

Design rules:

```text
1. External input can still expose options: dict[str, Any].
2. Only normalize_runtime_options may interpret raw options keys.
3. Nodes must read runtime_options, not state["options"].
4. Unknown options are ignored by runtime_options but preserved in input.options for artifact input.json.
5. Only bool True/False values activate mock runtime flags.
6. prompt_payload remains JSON-like but gains TypedDict contracts.
7. response_builder owns prompt debug metadata only.
8. artifacts.py owns artifact metadata only.
9. workflow.py may merge metadata but must not hand-write artifact path keys.
10. GraphRuntime remains NL2SQL-agnostic.
```

Runtime flag semantics:

```text
normalize_runtime_options keeps explicit bool True/False for allowed keys.
Node forced-error checks must use `is True` (not truthy checks).
```

Current dirty-worktree caution:

```text
The Phase 5 design doc may be uncommitted.
Do not restore, delete, or rewrite unrelated user changes.
Do not stage workspace/logs, .ai/local, or generated artifacts.
```

---

## 1. Target File Responsibilities

```text
workflows/nl2sql/runtime_options.py
  Owns Nl2SqlRuntimeOptions and normalize_runtime_options(...).
  Is the only module that interprets raw input.options keys.
  Ignores unknown keys.
  Accepts only actual bool values for force_check_error and force_execute_error.

workflows/nl2sql/workflow.py
  Builds graph input.
  Preserves raw options for artifact input.json.
  Adds runtime_options from normalize_runtime_options(input.options).
  Does not normalize options inside nodes.

workflows/nl2sql/nodes.py
  Reads state["runtime_options"] for mock check/execute failures.
  Does not directly read state["options"].
  Does not write files or metadata.

workflows/nl2sql/prompt_payload.py
  Owns TypedDict contracts for the current prompt payload shape.
  build_mock_prompt_payload returns Nl2SqlPromptPayload.
  Does not read config or call external systems.

workflows/nl2sql/prompt_builder.py
  Accepts Nl2SqlPromptPayload or equivalent mapping.
  Renders final_prompt exactly as before.
  Does not render debug into final_prompt.

workflows/nl2sql/state.py
  Keeps Nl2SqlGraphState as TypedDict(total=False).
  Adds runtime_options and Nl2SqlPromptPayload type references.
  Keeps rows dynamic.

workflows/nl2sql/response_builder.py
  Owns build_prompt_debug_metadata(...).
  build_nl2sql_output uses that helper.
  Does not construct artifact metadata.

workflows/nl2sql/artifacts.py
  No redesign expected.
  Remains the only source of artifact path metadata.
```

---

## Task 1: Runtime Options Contract

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/runtime_options.py`
- Create: `tests/unit/workflows/nl2sql/test_runtime_options.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/__init__.py`

- [ ] **Step 1: Write failing tests for runtime option normalization**

Create `tests/unit/workflows/nl2sql/test_runtime_options.py`:

```python
from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.runtime_options import normalize_runtime_options


def test_normalize_runtime_options_defaults_to_empty_dict() -> None:
    assert normalize_runtime_options(None) == {}
    assert normalize_runtime_options({}) == {}


def test_normalize_runtime_options_keeps_allowed_bool_flags() -> None:
    assert normalize_runtime_options(
        {
            "force_check_error": True,
            "force_execute_error": False,
        }
    ) == {
        "force_check_error": True,
        "force_execute_error": False,
    }


def test_normalize_runtime_options_ignores_unknown_keys() -> None:
    assert normalize_runtime_options(
        {
            "force_check_error": True,
            "temperature": 0.1,
            "dialect": "sqlite",
            "schema": {"name": "demo"},
        }
    ) == {"force_check_error": True}


def test_normalize_runtime_options_ignores_non_bool_values() -> None:
    assert normalize_runtime_options(
        {
            "force_check_error": "true",
            "force_execute_error": 1,
        }
    ) == {}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_runtime_options.py -v
```

Expected:

```text
FAIL because runtime_options.py does not exist.
```

- [ ] **Step 3: Implement runtime_options.py**

Create `src/nl2sqlagent/workflows/nl2sql/runtime_options.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict


class Nl2SqlRuntimeOptions(TypedDict, total=False):
    force_check_error: bool
    force_execute_error: bool


_ALLOWED_BOOL_KEYS = (
    "force_check_error",
    "force_execute_error",
)


def normalize_runtime_options(
    options: Mapping[str, object] | None,
) -> Nl2SqlRuntimeOptions:
    normalized: Nl2SqlRuntimeOptions = {}
    if not options:
        return normalized

    for key in _ALLOWED_BOOL_KEYS:
        value = options.get(key)
        if isinstance(value, bool):
            normalized[key] = value
    return normalized


__all__ = ["Nl2SqlRuntimeOptions", "normalize_runtime_options"]
```

Important:

```text
Do not parse strings like "true".
Do not coerce 1/0 into bool.
Do not carry unknown keys into runtime_options.
```

- [ ] **Step 4: Export runtime options if local package style expects it**

If `src/nl2sqlagent/workflows/nl2sql/__init__.py` exports workflow-facing types, add:

```python
from nl2sqlagent.workflows.nl2sql.runtime_options import (
    Nl2SqlRuntimeOptions,
    normalize_runtime_options,
)
```

and include them in `__all__`.

If that file only exports public user-facing workflow APIs, skip this export. Keep the local style.

- [ ] **Step 5: Run tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_runtime_options.py -v
```

Expected:

```text
All runtime option tests pass.
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/runtime_options.py tests/unit/workflows/nl2sql/test_runtime_options.py src/nl2sqlagent/workflows/nl2sql/__init__.py
git commit -m "feat: add nl2sql runtime options contract"
```

---

## Task 2: Wire Runtime Options Into Workflow Input

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/workflow.py`
- Modify: `tests/integration/test_nl2sql_workflow.py`
- Modify: `tests/unit/workflows/nl2sql/test_contracts.py`

Note:

```text
The _graph_input contract test is placed in integration temporarily to stay close to workflow graph wiring.
If workflow-focused unit tests expand later, move this case to tests/unit/workflows/nl2sql/test_workflow.py.
```

- [ ] **Step 1: Add failing workflow input test**

Append to `tests/integration/test_nl2sql_workflow.py`:

```python
def test_nl2sql_workflow_graph_input_preserves_options_and_adds_runtime_options() -> None:
    graph_input = Nl2SqlWorkflow._graph_input(
        Nl2SqlInput(
            question="统计员工数量",
            options={
                "force_check_error": True,
                "temperature": 0.1,
                "force_execute_error": "true",
            },
        )
    )

    assert graph_input["options"] == {
        "force_check_error": True,
        "temperature": 0.1,
        "force_execute_error": "true",
    }
    assert graph_input["runtime_options"] == {"force_check_error": True}
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py::test_nl2sql_workflow_graph_input_preserves_options_and_adds_runtime_options -v
```

Expected:

```text
FAIL because _graph_input does not add runtime_options yet.
```

- [ ] **Step 3: Update workflow._graph_input**

Modify `src/nl2sqlagent/workflows/nl2sql/workflow.py`:

```python
from nl2sqlagent.workflows.nl2sql.runtime_options import normalize_runtime_options
```

Update `_graph_input`:

```python
@staticmethod
def _graph_input(input: Nl2SqlInput) -> dict[str, Any]:
    return {
        "request_id": input.request_id,
        "user_id": input.user_id,
        "database_key": input.database_key,
        "raw_question": input.question,
        "options": dict(input.options),
        "runtime_options": normalize_runtime_options(input.options),
        "status": "running",
    }
```

- [ ] **Step 4: Add contract check that normalization is not in nodes**

Append to `tests/unit/workflows/nl2sql/test_contracts.py`:

```python
def test_runtime_options_are_normalized_in_workflow_not_nodes() -> None:
    workflow_source = Path("src/nl2sqlagent/workflows/nl2sql/workflow.py").read_text(
        encoding="utf-8"
    )
    nodes_source = Path("src/nl2sqlagent/workflows/nl2sql/nodes.py").read_text(
        encoding="utf-8"
    )

    assert "normalize_runtime_options" in workflow_source
    assert "normalize_runtime_options" not in nodes_source
```

- [ ] **Step 5: Run selected tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py::test_nl2sql_workflow_graph_input_preserves_options_and_adds_runtime_options tests/unit/workflows/nl2sql/test_contracts.py::test_runtime_options_are_normalized_in_workflow_not_nodes -v
```

Expected:

```text
PASS.
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/workflow.py tests/integration/test_nl2sql_workflow.py tests/unit/workflows/nl2sql/test_contracts.py
git commit -m "feat: normalize nl2sql runtime options in workflow"
```

---

## Task 3: Make Nodes Read Runtime Options

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/nodes.py`
- Modify: `tests/unit/workflows/nl2sql/test_nodes.py`
- Modify: `tests/integration/test_nl2sql_workflow.py`
- Modify: `tests/unit/workflows/nl2sql/test_contracts.py`

- [ ] **Step 1: Update node tests to use runtime_options**

Change the forced-error tests in `tests/unit/workflows/nl2sql/test_nodes.py`:

```python
def test_check_sql_node_can_force_check_error() -> None:
    result = check_sql_node(
        {
            "generated_sql": "SELECT 1 AS value",
            "runtime_options": {"force_check_error": True},
        }
    )

    assert result == {
        "check_error": "mock check error",
        "status": "failed",
    }


def test_execute_sql_node_can_force_execute_error() -> None:
    result = execute_sql_node(
        {
            "checked_sql": "SELECT 1 AS value",
            "runtime_options": {"force_execute_error": True},
        }
    )

    assert result == {
        "execute_error": "mock execute error",
        "status": "failed",
    }
```

Add regression tests:

```python
def test_check_sql_node_ignores_raw_options() -> None:
    result = check_sql_node(
        {
            "generated_sql": "SELECT 1 AS value",
            "options": {"force_check_error": True},
        }
    )

    assert result == {
        "checked_sql": "SELECT 1 AS value",
        "check_error": None,
    }


def test_execute_sql_node_ignores_raw_options() -> None:
    result = execute_sql_node(
        {
            "checked_sql": "SELECT 1 AS value",
            "options": {"force_execute_error": True},
        }
    )

    assert result == {
        "result_columns": ["value"],
        "result_rows": [{"value": 1}],
        "execute_error": None,
    }
```

- [ ] **Step 2: Run tests and verify relevant failures**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_nodes.py -v
```

Expected:

```text
FAIL because nodes still read state["options"].
```

- [ ] **Step 3: Update nodes to read runtime_options**

Modify `src/nl2sqlagent/workflows/nl2sql/nodes.py`.

Change `check_sql_node`:

```python
def check_sql_node(state: Nl2SqlGraphState) -> dict:
    runtime_options = state.get("runtime_options") or {}
    if runtime_options.get("force_check_error") is True:
        return {
            "check_error": "mock check error",
            "status": "failed",
        }
    return {
        "checked_sql": state.get("generated_sql") or "",
        "check_error": None,
    }
```

Change `execute_sql_node`:

```python
def execute_sql_node(state: Nl2SqlGraphState) -> dict:
    runtime_options = state.get("runtime_options") or {}
    if runtime_options.get("force_execute_error") is True:
        return {
            "execute_error": "mock execute error",
            "status": "failed",
        }
    return {
        "result_columns": ["value"],
        "result_rows": [{"value": 1}],
        "execute_error": None,
    }
```

- [ ] **Step 4: Update integration graph tests**

In `tests/integration/test_nl2sql_workflow.py`, direct `runtime.invoke(...)` calls that previously supplied forced errors through `options` must now include `runtime_options`.

For check failure:

```python
input={
    "raw_question": "统计员工数量",
    "options": {"force_check_error": True},
    "runtime_options": {"force_check_error": True},
}
```

For execute failure:

```python
input={
    "raw_question": "统计员工数量",
    "options": {"force_execute_error": True},
    "runtime_options": {"force_execute_error": True},
}
```

Workflow-level tests using `workflow.run(Nl2SqlInput(... options=...))` should not need manual `runtime_options`; workflow handles that.

- [ ] **Step 5: Add precise static boundary check**

Append to `tests/unit/workflows/nl2sql/test_contracts.py`:

```python
def test_nl2sql_nodes_do_not_read_raw_options() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/nodes.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        'state.get("options")',
        "state.get('options')",
        'state["options"]',
        "state['options']",
    ]
    assert all(token not in source for token in forbidden)
    assert "runtime_options" in source
```

Do not use a broad `"options"` forbidden token because `runtime_options` intentionally contains that word.

- [ ] **Step 6: Run selected tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_nodes.py tests/integration/test_nl2sql_workflow.py tests/unit/workflows/nl2sql/test_contracts.py -v
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 7: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/nodes.py tests/unit/workflows/nl2sql/test_nodes.py tests/integration/test_nl2sql_workflow.py tests/unit/workflows/nl2sql/test_contracts.py
git commit -m "refactor: make nl2sql nodes use runtime options"
```

---

## Task 4: Prompt Payload TypedDict Contracts

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/prompt_payload.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/prompt_builder.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/state.py`
- Modify: `tests/unit/workflows/nl2sql/test_prompt_payload.py`
- Modify: `tests/unit/workflows/nl2sql/test_prompt_builder.py`

- [ ] **Step 1: Add contract assertions for prompt payload shape**

Append to `tests/unit/workflows/nl2sql/test_prompt_payload.py`:

```python
def test_build_mock_prompt_payload_returns_json_like_relationships_boundary() -> None:
    payload = build_mock_prompt_payload(
        raw_question="统计员工数量",
        normalized_question="统计员工数量",
    )

    relationships = payload["schema_context"]["relationships"]
    assert relationships == []
    assert isinstance(relationships, list)
```

If this already passes before implementation, keep it as a regression test.

- [ ] **Step 2: Add TypedDict definitions**

Modify `src/nl2sqlagent/workflows/nl2sql/prompt_payload.py`:

```python
from typing import TypedDict


class PromptTask(TypedDict):
    type: str
    goal: str


class PromptQuestion(TypedDict):
    raw: str
    normalized: str


class PromptColumn(TypedDict):
    name: str
    type: str
    description: str


class PromptTable(TypedDict):
    name: str
    description: str
    columns: list[PromptColumn]


class PromptSchemaContext(TypedDict):
    dialect: str
    tables: list[PromptTable]
    relationships: list[dict[str, object]]


class PromptSemanticTerm(TypedDict):
    name: str
    description: str


class PromptSemanticContext(TypedDict):
    business_terms: list[PromptSemanticTerm]
    rules: list[str]
    assumptions: list[str]


class PromptSqlPolicy(TypedDict):
    readonly_only: bool
    allow_select_star: bool
    require_limit: bool
    default_limit: int


class PromptOutputContract(TypedDict):
    format: str
    requirements: list[str]


class PromptDebug(TypedDict):
    prompt_version: str
    source: str


class Nl2SqlPromptPayload(TypedDict):
    task: PromptTask
    question: PromptQuestion
    schema_context: PromptSchemaContext
    semantic_context: PromptSemanticContext
    sql_policy: PromptSqlPolicy
    output_contract: PromptOutputContract
    debug: PromptDebug
```

Change function signature:

```python
def build_mock_prompt_payload(
    *,
    raw_question: str,
    normalized_question: str,
) -> Nl2SqlPromptPayload:
    ...
```

Update `__all__` to export the new public contract types.

- [ ] **Step 3: Type prompt_builder input**

Modify `src/nl2sqlagent/workflows/nl2sql/prompt_builder.py` to import:

```python
from nl2sqlagent.workflows.nl2sql.prompt_payload import Nl2SqlPromptPayload
```

Then update:

```python
def render_final_prompt(prompt_payload: Nl2SqlPromptPayload) -> str:
    ...
```

If existing implementation needs `Mapping[str, object]` to stay convenient, use:

```python
def render_final_prompt(prompt_payload: Nl2SqlPromptPayload) -> str:
```

and keep current dict-style access. Do not add runtime validation.

- [ ] **Step 4: Update graph state typing**

Modify `src/nl2sqlagent/workflows/nl2sql/state.py`:

```python
from nl2sqlagent.workflows.nl2sql.prompt_payload import Nl2SqlPromptPayload
from nl2sqlagent.workflows.nl2sql.runtime_options import Nl2SqlRuntimeOptions
```

Change state fields:

```python
options: dict[str, Any]
runtime_options: Nl2SqlRuntimeOptions
prompt_payload: Nl2SqlPromptPayload
result_rows: list[dict[str, Any]]
```

Keep `TypedDict(total=False)`.

Optional readability cleanup: group fields with short comments:

```python
# Input identity
# Question
# Runtime
# Prompt
# SQL
# Execution result
# Response
```

Do not introduce `Nl2SqlContext`.

- [ ] **Step 5: Run prompt and state-adjacent tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_prompt_payload.py tests/unit/workflows/nl2sql/test_prompt_builder.py tests/unit/workflows/nl2sql/test_nodes.py -v
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/prompt_payload.py src/nl2sqlagent/workflows/nl2sql/prompt_builder.py src/nl2sqlagent/workflows/nl2sql/state.py tests/unit/workflows/nl2sql/test_prompt_payload.py tests/unit/workflows/nl2sql/test_prompt_builder.py
git commit -m "refactor: add nl2sql prompt payload contracts"
```

---

## Task 5: Response Metadata Boundary

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/response_builder.py`
- Modify: `tests/unit/workflows/nl2sql/test_response_builder.py`
- Modify: `tests/unit/workflows/nl2sql/test_contracts.py`

- [ ] **Step 1: Add focused tests for prompt debug metadata helper**

Append to `tests/unit/workflows/nl2sql/test_response_builder.py`:

```python
from nl2sqlagent.workflows.nl2sql.response_builder import build_prompt_debug_metadata


def test_build_prompt_debug_metadata_includes_only_prompt_fields() -> None:
    state = {
        "prompt_payload": {"question": {"normalized": "统计员工数量"}},
        "final_prompt": "User Question:\n统计员工数量",
        "artifact_manifest_path": "should-not-be-copied",
        "result_rows": [{"value": 1}],
    }

    assert build_prompt_debug_metadata(state) == {
        "prompt_payload": {"question": {"normalized": "统计员工数量"}},
        "final_prompt": "User Question:\n统计员工数量",
    }


def test_build_prompt_debug_metadata_returns_empty_for_clarification_state() -> None:
    assert build_prompt_debug_metadata(
        {
            "status": "needs_clarification",
            "message": "Please provide a question.",
        }
    ) == {}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_response_builder.py -v
```

Expected:

```text
FAIL because build_prompt_debug_metadata does not exist.
```

- [ ] **Step 3: Implement build_prompt_debug_metadata**

Modify `src/nl2sqlagent/workflows/nl2sql/response_builder.py`.

Replace `_metadata` with public helper:

```python
def build_prompt_debug_metadata(state: Nl2SqlGraphState) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if "prompt_payload" in state:
        metadata["prompt_payload"] = state.get("prompt_payload")
    if "final_prompt" in state:
        metadata["final_prompt"] = state.get("final_prompt")
    return metadata
```

Then use it:

```python
metadata=build_prompt_debug_metadata(state),
```

Update `__all__`:

```python
__all__ = ["build_nl2sql_output", "build_prompt_debug_metadata"]
```

Do not add artifact path keys here.

- [ ] **Step 4: Add static boundary test for metadata ownership**

Append to `tests/unit/workflows/nl2sql/test_contracts.py`:

```python
def test_response_builder_does_not_construct_artifact_metadata() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/response_builder.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "artifact_manifest_path",
        "input_path",
        "prompt_payload_path",
        "final_prompt_path",
        "graph_updates_path",
        "output_path",
        "token_usage_path",
        "artifact_error",
    ]
    assert all(token not in source for token in forbidden)
```

- [ ] **Step 5: Run response and contract tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_response_builder.py tests/unit/workflows/nl2sql/test_contracts.py -v
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/response_builder.py tests/unit/workflows/nl2sql/test_response_builder.py tests/unit/workflows/nl2sql/test_contracts.py
git commit -m "refactor: isolate nl2sql prompt debug metadata"
```

---

## Task 6: Artifact Metadata Boundary Regression

**Files:**

- Modify: `tests/unit/workflows/nl2sql/test_contracts.py`
- Modify only if needed: `tests/unit/workflows/nl2sql/test_artifacts.py`

- [ ] **Step 1: Add workflow metadata merge boundary test**

Append to `tests/unit/workflows/nl2sql/test_contracts.py`:

```python
def test_workflow_does_not_hand_write_artifact_metadata_keys() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/workflow.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        '"artifact_manifest_path"',
        '"input_path"',
        '"prompt_payload_path"',
        '"final_prompt_path"',
        '"graph_updates_path"',
        '"output_path"',
        '"token_usage_path"',
        '"artifact_error"',
    ]
    assert all(token not in source for token in forbidden)
    assert "artifact_result.metadata" in source
```

This test protects the rule:

```text
workflow.py may merge metadata, but artifacts.py owns artifact key construction.
```

- [ ] **Step 2: Add artifact writer ownership test**

Append:

```python
def test_artifacts_module_owns_artifact_metadata_keys() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/artifacts.py").read_text(
        encoding="utf-8"
    )

    required = [
        "Nl2SqlArtifactMetadata",
        "artifact_manifest_path",
        "prompt_payload_path",
        "final_prompt_path",
        "graph_updates_path",
        "token_usage_path",
        "artifact_error",
    ]
    assert all(token in source for token in required)
```

- [ ] **Step 3: Run contract tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_contracts.py -v
```

Expected:

```text
PASS.
```

- [ ] **Step 4: Commit**

```powershell
git add tests/unit/workflows/nl2sql/test_contracts.py
git commit -m "test: protect nl2sql metadata boundaries"
```

---

## Task 7: Workflow Regression And Artifact Compatibility

**Files:**

- Modify: `tests/integration/test_nl2sql_workflow.py`
- Modify: `tests/unit/workflows/nl2sql/test_artifacts.py` only if artifact assertions need updating because state now includes runtime_options.

- [ ] **Step 1: Add workflow-level unknown options regression**

Append to `tests/integration/test_nl2sql_workflow.py`:

```python
def test_nl2sql_workflow_ignores_unknown_options_but_preserves_input_artifact(
    tmp_path,
) -> None:
    workflow = _workflow_with_log_dir(tmp_path)

    output = workflow.run(
        Nl2SqlInput(
            question="统计员工数量",
            options={
                "temperature": 0.1,
                "force_check_error": "true",
            },
        ),
        thread_id="thread-nl2sql-unknown-options",
    )

    assert output.status == "success"
    input_path = Path(output.metadata["input_path"])
    input_data = json.loads(input_path.read_text(encoding="utf-8"))
    assert input_data["options"] == {
        "temperature": 0.1,
        "force_check_error": "true",
    }
```

This confirms:

```text
Unknown/raw options stay visible in input artifact for reproduction.
They do not affect nodes because runtime_options ignores them.
```

- [ ] **Step 2: Add workflow-level runtime options still force mock errors**

Append:

```python
def test_nl2sql_workflow_runtime_options_still_support_mock_check_failure(
    tmp_path,
) -> None:
    workflow = _workflow_with_log_dir(tmp_path)

    output = workflow.run(
        Nl2SqlInput(
            question="统计员工数量",
            options={"force_check_error": True},
        ),
        thread_id="thread-nl2sql-runtime-check-error",
    )

    assert output.status == "failed"
    assert output.message == "mock check error"
    assert output.metadata["artifact_manifest_path"] is not None
    assert output.metadata["prompt_payload"]["question"]["normalized"] == "统计员工数量"
```

- [ ] **Step 3: Run NL2SQL integration tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py -v
```

Expected:

```text
PASS.
```

- [ ] **Step 4: Run artifact tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_artifacts.py -v
```

Expected:

```text
PASS.
```

- [ ] **Step 5: Commit**

```powershell
git add tests/integration/test_nl2sql_workflow.py tests/unit/workflows/nl2sql/test_artifacts.py
git commit -m "test: preserve nl2sql artifact compatibility"
```

---

## Task 8: Anti-Overengineering Boundary Check

**Files:**

- Modify: `tests/unit/workflows/nl2sql/test_contracts.py`

- [ ] **Step 1: Add test that forbidden architecture directories were not added**

Append:

```python
def test_phase5_does_not_add_heavy_architecture_layers() -> None:
    forbidden_paths = [
        Path("src/nl2sqlagent/domain"),
        Path("src/nl2sqlagent/services"),
        Path("src/nl2sqlagent/integrations"),
        Path("src/nl2sqlagent/workflows/nl2sql/stages"),
        Path("src/nl2sqlagent/workflows/nl2sql/models"),
    ]

    assert all(not path.exists() for path in forbidden_paths)
```

- [ ] **Step 2: Add test that no stage/protocol/context result names were introduced**

Append:

```python
def test_phase5_does_not_introduce_stage_protocol_or_context_result_shells() -> None:
    import ast

    root = Path("src/nl2sqlagent/workflows/nl2sql")
    forbidden = {
        "Nl2SqlContext",
        "Nl2SqlStageProtocol",
        "PrepareStage",
        "GenerateStage",
        "CheckStage",
        "ExecuteStage",
        "PrepareResult",
        "GenerateResult",
        "CheckResult",
        "ExecuteResult",
    }

    used_names: set[str] = set()
    for file in root.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                used_names.add(node.attr)
            elif isinstance(node, ast.ClassDef):
                used_names.add(node.name)
            elif isinstance(node, ast.FunctionDef):
                used_names.add(node.name)

    assert forbidden.isdisjoint(used_names)
```

Why this shape:

```text
AST name scanning checks executable identifiers and avoids false failures caused by comments/docs mentioning forbidden words.
```

- [ ] **Step 3: Run contract tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_contracts.py -v
```

Expected:

```text
PASS.
```

- [ ] **Step 4: Commit**

```powershell
git add tests/unit/workflows/nl2sql/test_contracts.py
git commit -m "test: prevent phase5 overengineering"
```

---

## Task 9: Final Verification

**Files:**

- All Phase 5 implementation files.

- [ ] **Step 1: Run focused NL2SQL tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql tests/unit/workflows/runtime tests/integration/test_nl2sql_workflow.py -v
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

- [ ] **Step 4: Smoke run with raw options and runtime behavior**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -c "from pathlib import Path; import json; from nl2sqlagent.bootstrap import build_app; from nl2sqlagent.workflows.nl2sql import Nl2SqlInput; app = build_app(run_id='run-phase5-smoke'); output = app.nl2sql_workflow.run(Nl2SqlInput(question='统计员工数量', request_id='request-phase5-smoke', options={'temperature': 0.1, 'force_check_error': 'true'}), thread_id='thread-phase5-smoke'); print(output.status); print(output.sql); print(output.metadata['artifact_manifest_path']); input_data = json.loads(Path(output.metadata['input_path']).read_text(encoding='utf-8')); print(input_data['options']); print(Path(output.metadata['final_prompt_path']).exists())"
```

Expected:

```text
success
SELECT 1 AS value
<path ending with manifest.json>
{'temperature': 0.1, 'force_check_error': 'true'}
True
```

The string `"true"` must not force a check failure.

- [ ] **Step 5: Smoke run with real bool runtime error flag**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -c "from nl2sqlagent.bootstrap import build_app; from nl2sqlagent.workflows.nl2sql import Nl2SqlInput; app = build_app(run_id='run-phase5-check-error'); output = app.nl2sql_workflow.run(Nl2SqlInput(question='统计员工数量', options={'force_check_error': True}), thread_id='thread-phase5-check-error'); print(output.status); print(output.message); print(output.metadata['artifact_manifest_path'] is not None)"
```

Expected:

```text
failed
mock check error
True
```

- [ ] **Step 6: Confirm nodes do not read raw options**

Run:

```powershell
.\.ai\local\tools\rg.exe "state\.get\([\"']options[\"']\)|state\[[\"']options[\"']\]" src\nl2sqlagent\workflows\nl2sql\nodes.py
```

Expected:

```text
No matches.
```

- [ ] **Step 7: Confirm forbidden architecture was not added**

Run:

```powershell
Test-Path .\src\nl2sqlagent\domain
Test-Path .\src\nl2sqlagent\services
Test-Path .\src\nl2sqlagent\integrations
Test-Path .\src\nl2sqlagent\workflows\nl2sql\stages
Test-Path .\src\nl2sqlagent\workflows\nl2sql\models
```

Expected:

```text
False
False
False
False
False
```

- [ ] **Step 8: Confirm workflow does not hand-write artifact metadata keys**

Run:

```powershell
.\.ai\local\tools\rg.exe "\"artifact_manifest_path\"|\"prompt_payload_path\"|\"final_prompt_path\"|\"graph_updates_path\"|\"token_usage_path\"|\"artifact_error\"" src\nl2sqlagent\workflows\nl2sql\workflow.py
```

Expected:

```text
No matches.
```

- [ ] **Step 9: Confirm GraphRuntime remains NL2SQL-agnostic**

Run:

```powershell
.\.ai\local\tools\rg.exe "prompt_payload|final_prompt|generated_sql|checked_sql|result_rows|Nl2Sql" src\nl2sqlagent\workflows\runtime\graph_runtime.py
```

Expected:

```text
No matches.
```

- [ ] **Step 10: Diff check**

Run:

```powershell
git diff --check
```

Expected:

```text
No trailing whitespace errors.
```

- [ ] **Step 11: Final git status**

Run:

```powershell
git -c core.quotepath=false status --short
```

Expected:

```text
Only intentional Phase 5 files are modified/untracked.
Generated workspace/logs files are not staged.
Unrelated user changes are untouched.
```

- [ ] **Step 12: Commit final fixes if needed**

If final verification required small fixes:

```powershell
git add <fixed Phase 5 implementation files only>
git commit -m "fix: stabilize nl2sql data contracts"
```

Do not stage `workspace/logs`, `.ai/local`, or unrelated files.

---

## Final Report Template

When complete, report:

```text
Implemented Phase 5 NL2SQL data contracts.

What changed:
- Added Nl2SqlRuntimeOptions and normalize_runtime_options.
- Workflow preserves raw options and adds normalized runtime_options to graph input.
- Nodes read runtime_options and no longer interpret raw options.
- prompt_payload now has TypedDict contracts.
- Nl2SqlGraphState references runtime_options and Nl2SqlPromptPayload while remaining TypedDict(total=False).
- response_builder now owns prompt debug metadata through build_prompt_debug_metadata.
- artifact metadata remains owned by artifacts.py.
- Added regression checks against stage/service/protocol/context-result overengineering.

Verification:
- pytest tests/unit/workflows/nl2sql tests/unit/workflows/runtime tests/integration/test_nl2sql_workflow.py -v: passed
- pytest -v: passed
- compileall src/nl2sqlagent: passed
- smoke run with unknown/string options stayed success: passed
- smoke run with bool force_check_error failed as expected: passed
- nodes raw-options boundary check: passed
- forbidden architecture directories not created: confirmed
- GraphRuntime NL2SQL-agnostic boundary: confirmed

Remaining:
- Real LLM intentionally deferred.
- Real schema grounding intentionally deferred.
- Real DB/SQL execution intentionally deferred.
- relationship contract remains intentionally light until real schema relations are introduced.
```
