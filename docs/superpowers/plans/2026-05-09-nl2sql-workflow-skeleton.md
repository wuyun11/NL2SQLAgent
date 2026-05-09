# NL2SQL Workflow Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure Phase 2 NL2SQL LangGraph skeleton that runs a single linear mock flow and exposes `final_prompt` through output metadata and stream chunks.

**Architecture:** Keep Phase 2 as workflow plumbing only. Add `workflows/nl2sql` with stable input/output contracts, serializable graph state, mock nodes, thin routing edges, a response builder, a graph builder, and a workflow facade wired into bootstrap. Do not add retry, real LLM/database/schema grounding, CLI `ask`, or `domain/services/integrations`.

**Tech Stack:** Python 3.12, dataclasses, TypedDict, LangGraph `StateGraph`, existing `GraphRuntime`, pytest.

---

## 0. Scope Guard

This plan implements:

```text
docs/temp/Phase2_NL2SQL工作流骨架设计.md
```

Before any Python command, follow the repository rule:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
```

Do not use bare `python`.

Allowed to create:

```text
src/nl2sqlagent/workflows/nl2sql/__init__.py
src/nl2sqlagent/workflows/nl2sql/input.py
src/nl2sqlagent/workflows/nl2sql/output.py
src/nl2sqlagent/workflows/nl2sql/state.py
src/nl2sqlagent/workflows/nl2sql/response_builder.py
src/nl2sqlagent/workflows/nl2sql/edges.py
src/nl2sqlagent/workflows/nl2sql/nodes.py
src/nl2sqlagent/workflows/nl2sql/graph.py
src/nl2sqlagent/workflows/nl2sql/workflow.py
tests/unit/workflows/nl2sql/test_contracts.py
tests/unit/workflows/nl2sql/test_response_builder.py
tests/unit/workflows/nl2sql/test_edges.py
tests/unit/workflows/nl2sql/test_nodes.py
tests/integration/test_nl2sql_workflow.py
```

Allowed to modify:

```text
src/nl2sqlagent/bootstrap/app.py
src/nl2sqlagent/bootstrap/container.py
```

Forbidden in this phase:

```text
src/nl2sqlagent/domain/
src/nl2sqlagent/services/
src/nl2sqlagent/integrations/
src/nl2sqlagent/interfaces/cli/commands/ask.py
retry / feedback loop
round_index / max_round_count
real LLM
real database
real SQL execution
real schema grounding
schema-index workflow
QueryPlan
Human Review
evaluation golden set
old SQLAgent code migration
```

Design rules:

```text
1. Workflow graph is linear except clarification / failed / success routing.
2. No route points back to generate_sql.
3. State contains only serializable values.
4. Nodes return partial state updates and do not mutate input state.
5. Mock logic can live directly in nodes for Phase 2; do not create services.
6. final_prompt is debug metadata, not a top-level Nl2SqlOutput field.
7. check / execute failures must still preserve final_prompt in output metadata.
8. build_app exposes nl2sql_workflow but still does not expose hello_graph.
```

Current known dirty-worktree caution:

```text
The user may have unrelated staged/uncommitted changes in docs/temp, such as:
  docs/temp/其他ai的评价.md
  docs/temp/计划评价.md
Do not stage, restore, or commit those files unless explicitly instructed.
```

---

## 1. Target File Responsibilities

```text
input.py
  Defines Nl2SqlInput, the external workflow request contract.

output.py
  Defines Nl2SqlStatus and Nl2SqlOutput, the external workflow response contract.

state.py
  Defines Nl2SqlGraphState, the internal LangGraph state snapshot.

response_builder.py
  Converts final graph state into Nl2SqlOutput.

edges.py
  Contains route_after_normalize / route_after_check / route_after_execute only.

nodes.py
  Contains Phase 2 mock nodes: normalize, build_prompt, generate, check, execute, response nodes.

graph.py
  Builds and compiles the Phase 2 NL2SQL StateGraph with a supplied checkpointer.

workflow.py
  Provides Nl2SqlWorkflow facade with run() and stream().

bootstrap/app.py
  Adds nl2sql_workflow to NL2SQLAgentApp.

bootstrap/container.py
  Builds the NL2SQL graph/facade after checkpointer and GraphRuntime exist.
```

---

## Task 1: NL2SQL Contracts And State

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/__init__.py`
- Create: `src/nl2sqlagent/workflows/nl2sql/input.py`
- Create: `src/nl2sqlagent/workflows/nl2sql/output.py`
- Create: `src/nl2sqlagent/workflows/nl2sql/state.py`
- Test: `tests/unit/workflows/nl2sql/test_contracts.py`

- [ ] **Step 1: Write contract tests**

Create `tests/unit/workflows/nl2sql/test_contracts.py`:

```python
from __future__ import annotations

from nl2sqlagent.workflows.nl2sql import (
    Nl2SqlInput,
    Nl2SqlOutput,
)


def test_nl2sql_input_defaults_to_empty_options() -> None:
    request = Nl2SqlInput(question="统计员工数量")

    assert request.question == "统计员工数量"
    assert request.request_id is None
    assert request.user_id is None
    assert request.database_key is None
    assert request.options == {}


def test_nl2sql_input_options_default_dicts_are_not_shared() -> None:
    first = Nl2SqlInput(question="first")
    second = Nl2SqlInput(question="second")

    first.options["force_check_error"] = True

    assert second.options == {}


def test_nl2sql_output_defaults_to_empty_table_and_metadata() -> None:
    response = Nl2SqlOutput(status="success")

    assert response.status == "success"
    assert response.message is None
    assert response.sql is None
    assert response.columns == []
    assert response.rows == []
    assert response.trace_id is None
    assert response.metadata == {}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_contracts.py -v
```

Expected:

```text
FAIL because nl2sqlagent.workflows.nl2sql does not exist.
```

- [ ] **Step 3: Implement input contract**

Create `src/nl2sqlagent/workflows/nl2sql/input.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Nl2SqlInput:
    question: str
    request_id: str | None = None
    user_id: str | None = None
    database_key: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


__all__ = ["Nl2SqlInput"]
```

Note: `frozen=True` only prevents reassigning fields; the `options` dict remains mutable in place. The test `test_nl2sql_input_options_default_dicts_are_not_shared` asserts per-instance `default_factory` isolation, not deep immutability.

- [ ] **Step 4: Implement output contract**

Create `src/nl2sqlagent/workflows/nl2sql/output.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Nl2SqlStatus = Literal[
    "success",
    "needs_clarification",
    "failed",
    "rejected",
]


@dataclass(frozen=True)
class Nl2SqlOutput:
    status: Nl2SqlStatus
    message: str | None = None
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["Nl2SqlOutput", "Nl2SqlStatus"]
```

- [ ] **Step 5: Implement graph state**

Create `src/nl2sqlagent/workflows/nl2sql/state.py`:

```python
from __future__ import annotations

from typing import Any, Literal, TypedDict


class Nl2SqlGraphState(TypedDict, total=False):
    request_id: str | None
    user_id: str | None
    database_key: str | None

    raw_question: str
    normalized_question: str
    clarification_message: str | None

    options: dict[str, Any]
    prompt_payload: dict[str, Any]
    final_prompt: str | None

    generated_sql: str | None
    checked_sql: str | None
    check_error: str | None
    execute_error: str | None

    result_columns: list[str]
    result_rows: list[dict[str, Any]]

    status: Literal[
        "running",
        "success",
        "needs_clarification",
        "failed",
        "rejected",
    ]
    message: str | None


__all__ = ["Nl2SqlGraphState"]
```

Note: `options` is included in graph state so mock nodes can read `force_check_error` and `force_execute_error`. It remains Phase 2 mock control, not a long-term business model.

- [ ] **Step 6: Export NL2SQL contracts**

Create `src/nl2sqlagent/workflows/nl2sql/__init__.py`:

```python
from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput
from nl2sqlagent.workflows.nl2sql.output import Nl2SqlOutput, Nl2SqlStatus

__all__ = [
    "Nl2SqlInput",
    "Nl2SqlOutput",
    "Nl2SqlStatus",
]
```

- [ ] **Step 7: Run contract tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_contracts.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 8: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql tests/unit/workflows/nl2sql/test_contracts.py
git commit -m "feat: add nl2sql workflow contracts"
```

---

## Task 2: Response Builder

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/response_builder.py`
- Test: `tests/unit/workflows/nl2sql/test_response_builder.py`

- [ ] **Step 1: Write response builder tests**

Create `tests/unit/workflows/nl2sql/test_response_builder.py`:

```python
from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.response_builder import build_nl2sql_output


def test_build_output_for_success_includes_sql_rows_and_prompt_metadata() -> None:
    output = build_nl2sql_output(
        {
            "status": "success",
            "message": "NL2SQL workflow succeeded.",
            "checked_sql": "SELECT 1 AS value",
            "result_columns": ["value"],
            "result_rows": [{"value": 1}],
            "prompt_payload": {"question": "统计员工数量"},
            "final_prompt": "Question: 统计员工数量\nGenerate SQL:",
        }
    )

    assert output.status == "success"
    assert output.message == "NL2SQL workflow succeeded."
    assert output.sql == "SELECT 1 AS value"
    assert output.columns == ["value"]
    assert output.rows == [{"value": 1}]
    assert output.metadata["prompt_payload"] == {"question": "统计员工数量"}
    assert output.metadata["final_prompt"] == "Question: 统计员工数量\nGenerate SQL:"


def test_build_output_for_clarification_does_not_require_prompt_metadata() -> None:
    output = build_nl2sql_output(
        {
            "status": "needs_clarification",
            "clarification_message": "Please provide a question.",
        }
    )

    assert output.status == "needs_clarification"
    assert output.message == "Please provide a question."
    assert output.sql is None
    assert output.columns == []
    assert output.rows == []
    assert output.metadata == {}


def test_build_output_for_failed_prefers_check_error_message() -> None:
    output = build_nl2sql_output(
        {
            "status": "failed",
            "check_error": "mock check error",
            "execute_error": "mock execute error",
            "message": "fallback message",
            "prompt_payload": {"question": "bad"},
            "final_prompt": "Question: bad\nGenerate SQL:",
        }
    )

    assert output.status == "failed"
    assert output.message == "mock check error"
    assert output.metadata["final_prompt"] == "Question: bad\nGenerate SQL:"


def test_build_output_for_failed_uses_execute_error_when_no_check_error() -> None:
    output = build_nl2sql_output(
        {
            "status": "failed",
            "execute_error": "mock execute error",
            "message": "fallback message",
        }
    )

    assert output.status == "failed"
    assert output.message == "mock execute error"


def test_build_output_for_failed_falls_back_to_default_message() -> None:
    output = build_nl2sql_output({"status": "failed"})

    assert output.status == "failed"
    assert output.message == "NL2SQL workflow failed."
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_response_builder.py -v
```

Expected:

```text
FAIL because response_builder does not exist.
```

- [ ] **Step 3: Implement response builder**

Create `src/nl2sqlagent/workflows/nl2sql/response_builder.py`:

```python
from __future__ import annotations

from typing import Any

from nl2sqlagent.workflows.nl2sql.output import Nl2SqlOutput, Nl2SqlStatus
from nl2sqlagent.workflows.nl2sql.state import Nl2SqlGraphState


def _status(state: Nl2SqlGraphState) -> Nl2SqlStatus:
    raw_status = state.get("status") or "failed"
    if raw_status in {"success", "needs_clarification", "failed", "rejected"}:
        return raw_status
    return "failed"


def _message(state: Nl2SqlGraphState, status: Nl2SqlStatus) -> str | None:
    if status == "needs_clarification":
        return state.get("clarification_message") or state.get("message")
    if status == "failed":
        return (
            state.get("check_error")
            or state.get("execute_error")
            or state.get("message")
            or "NL2SQL workflow failed."
        )
    return state.get("message")


def _metadata(state: Nl2SqlGraphState) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if "prompt_payload" in state:
        metadata["prompt_payload"] = state.get("prompt_payload")
    if "final_prompt" in state:
        metadata["final_prompt"] = state.get("final_prompt")
    return metadata


def build_nl2sql_output(state: Nl2SqlGraphState) -> Nl2SqlOutput:
    status = _status(state)
    return Nl2SqlOutput(
        status=status,
        message=_message(state, status),
        sql=state.get("checked_sql") or state.get("generated_sql"),
        columns=list(state.get("result_columns") or []),
        rows=list(state.get("result_rows") or []),
        metadata=_metadata(state),
    )


__all__ = ["build_nl2sql_output"]
```

- [ ] **Step 4: Run response builder tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_response_builder.py -v
```

Expected:

```text
5 passed
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/response_builder.py tests/unit/workflows/nl2sql/test_response_builder.py
git commit -m "feat: add nl2sql response builder"
```

---

## Task 3: Routing Edges

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/edges.py`
- Test: `tests/unit/workflows/nl2sql/test_edges.py`

- [ ] **Step 1: Write edge tests**

Create `tests/unit/workflows/nl2sql/test_edges.py`:

```python
from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.edges import (
    route_after_check,
    route_after_execute,
    route_after_normalize,
)


def test_route_after_normalize_uses_clarification_message_only() -> None:
    assert (
        route_after_normalize(
            {
                "clarification_message": "Please provide a question.",
                "status": "running",
            }
        )
        == "clarification_response"
    )


def test_route_after_normalize_without_clarification_builds_prompt() -> None:
    assert route_after_normalize({"normalized_question": "统计员工数量"}) == "build_prompt"


def test_route_after_check_goes_failed_when_check_error_exists() -> None:
    assert route_after_check({"check_error": "mock check error"}) == "failed_response"


def test_route_after_check_goes_execute_when_no_check_error() -> None:
    assert route_after_check({"checked_sql": "SELECT 1"}) == "execute_sql"


def test_route_after_execute_goes_failed_when_execute_error_exists() -> None:
    assert route_after_execute({"execute_error": "mock execute error"}) == "failed_response"


def test_route_after_execute_goes_success_when_no_execute_error() -> None:
    assert route_after_execute({"result_rows": [{"value": 1}]}) == "success_response"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_edges.py -v
```

Expected:

```text
FAIL because edges does not exist.
```

- [ ] **Step 3: Implement edges**

Create `src/nl2sqlagent/workflows/nl2sql/edges.py`:

```python
from __future__ import annotations

from typing import Literal

from nl2sqlagent.workflows.nl2sql.state import Nl2SqlGraphState


def route_after_normalize(
    state: Nl2SqlGraphState,
) -> Literal["clarification_response", "build_prompt"]:
    if state.get("clarification_message"):
        return "clarification_response"
    return "build_prompt"


def route_after_check(
    state: Nl2SqlGraphState,
) -> Literal["failed_response", "execute_sql"]:
    if state.get("check_error"):
        return "failed_response"
    return "execute_sql"


def route_after_execute(
    state: Nl2SqlGraphState,
) -> Literal["failed_response", "success_response"]:
    if state.get("execute_error"):
        return "failed_response"
    return "success_response"


__all__ = [
    "route_after_check",
    "route_after_execute",
    "route_after_normalize",
]
```

- [ ] **Step 4: Run edge tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_edges.py -v
```

Expected:

```text
6 passed
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/edges.py tests/unit/workflows/nl2sql/test_edges.py
git commit -m "feat: add nl2sql workflow routing"
```

---

## Task 4: Mock NL2SQL Nodes

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/nodes.py`
- Test: `tests/unit/workflows/nl2sql/test_nodes.py`

- [ ] **Step 1: Write node tests**

Create `tests/unit/workflows/nl2sql/test_nodes.py`:

```python
from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.nodes import (
    build_prompt_node,
    check_sql_node,
    clarification_response_node,
    execute_sql_node,
    failed_response_node,
    generate_sql_node,
    normalize_question_node,
    success_response_node,
)


def test_normalize_question_strips_question() -> None:
    result = normalize_question_node({"raw_question": "  统计员工数量  "})

    assert result == {
        "normalized_question": "统计员工数量",
        "status": "running",
    }


def test_normalize_question_sets_clarification_for_blank_question() -> None:
    result = normalize_question_node({"raw_question": "   "})

    assert result["normalized_question"] == ""
    assert result["clarification_message"] == "Please provide a question."
    assert result["status"] == "needs_clarification"


def test_build_prompt_node_creates_payload_and_final_prompt() -> None:
    result = build_prompt_node({"normalized_question": "统计员工数量"})

    assert result["prompt_payload"]["question"] == "统计员工数量"
    assert result["prompt_payload"]["schema"] == "mock_schema"
    assert "Question: 统计员工数量" in result["final_prompt"]
    assert "Schema: mock_schema" in result["final_prompt"]


def test_generate_sql_node_returns_mock_sql() -> None:
    result = generate_sql_node({"final_prompt": "Question: 统计员工数量"})

    assert result == {"generated_sql": "SELECT 1 AS value"}


def test_check_sql_node_can_force_check_error() -> None:
    result = check_sql_node(
        {
            "generated_sql": "SELECT 1 AS value",
            "options": {"force_check_error": True},
        }
    )

    assert result == {
        "check_error": "mock check error",
        "status": "failed",
    }


def test_check_sql_node_accepts_mock_sql() -> None:
    result = check_sql_node({"generated_sql": "SELECT 1 AS value"})

    assert result == {
        "checked_sql": "SELECT 1 AS value",
        "check_error": None,
    }


def test_execute_sql_node_can_force_execute_error() -> None:
    result = execute_sql_node(
        {
            "checked_sql": "SELECT 1 AS value",
            "options": {"force_execute_error": True},
        }
    )

    assert result == {
        "execute_error": "mock execute error",
        "status": "failed",
    }


def test_execute_sql_node_returns_mock_rows() -> None:
    result = execute_sql_node({"checked_sql": "SELECT 1 AS value"})

    assert result == {
        "result_columns": ["value"],
        "result_rows": [{"value": 1}],
        "execute_error": None,
    }


def test_response_nodes_set_final_status() -> None:
    assert clarification_response_node(
        {"clarification_message": "Please provide a question."}
    ) == {
        "status": "needs_clarification",
        "message": "Please provide a question.",
    }
    assert failed_response_node({"check_error": "mock check error"}) == {
        "status": "failed",
        "message": "mock check error",
    }
    assert success_response_node({}) == {
        "status": "success",
        "message": "NL2SQL workflow succeeded.",
    }
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_nodes.py -v
```

Expected:

```text
FAIL because nodes does not exist.
```

- [ ] **Step 3: Implement nodes**

Create `src/nl2sqlagent/workflows/nl2sql/nodes.py`:

```python
from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.state import Nl2SqlGraphState


def normalize_question_node(state: Nl2SqlGraphState) -> dict:
    question = (state.get("raw_question") or "").strip()
    if not question:
        return {
            "normalized_question": "",
            "clarification_message": "Please provide a question.",
            "status": "needs_clarification",
        }
    return {
        "normalized_question": question,
        "status": "running",
    }


def build_prompt_node(state: Nl2SqlGraphState) -> dict:
    question = state.get("normalized_question") or ""
    prompt_payload = {
        "question": question,
        "schema": "mock_schema",
        "semantic_rules": ["mock_semantic_rule"],
        "instruction": "Generate a read-only SQL query.",
    }
    final_prompt = "\n".join(
        [
            "You are an NL2SQL assistant.",
            f"Question: {prompt_payload['question']}",
            f"Schema: {prompt_payload['schema']}",
            "Semantic Rules:",
            "- mock_semantic_rule",
            "Instruction: Generate a read-only SQL query.",
        ]
    )
    return {
        "prompt_payload": prompt_payload,
        "final_prompt": final_prompt,
    }


def generate_sql_node(state: Nl2SqlGraphState) -> dict:
    return {"generated_sql": "SELECT 1 AS value"}


def check_sql_node(state: Nl2SqlGraphState) -> dict:
    options = state.get("options") or {}
    if options.get("force_check_error") is True:
        return {
            "check_error": "mock check error",
            "status": "failed",
        }
    return {
        "checked_sql": state.get("generated_sql") or "",
        "check_error": None,
    }


def execute_sql_node(state: Nl2SqlGraphState) -> dict:
    options = state.get("options") or {}
    if options.get("force_execute_error") is True:
        return {
            "execute_error": "mock execute error",
            "status": "failed",
        }
    return {
        "result_columns": ["value"],
        "result_rows": [{"value": 1}],
        "execute_error": None,
    }


def clarification_response_node(state: Nl2SqlGraphState) -> dict:
    message = state.get("clarification_message") or "Please provide a question."
    return {
        "status": "needs_clarification",
        "message": message,
    }


def failed_response_node(state: Nl2SqlGraphState) -> dict:
    message = (
        state.get("check_error")
        or state.get("execute_error")
        or state.get("message")
        or "NL2SQL workflow failed."
    )
    return {
        "status": "failed",
        "message": message,
    }


def success_response_node(state: Nl2SqlGraphState) -> dict:
    return {
        "status": "success",
        "message": "NL2SQL workflow succeeded.",
    }


__all__ = [
    "build_prompt_node",
    "check_sql_node",
    "clarification_response_node",
    "execute_sql_node",
    "failed_response_node",
    "generate_sql_node",
    "normalize_question_node",
    "success_response_node",
]
```

- [ ] **Step 4: Run node tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_nodes.py -v
```

Expected:

```text
9 passed
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/nodes.py tests/unit/workflows/nl2sql/test_nodes.py
git commit -m "feat: add mock nl2sql workflow nodes"
```

---

## Task 5: Graph Builder

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/graph.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/__init__.py`
- Test: `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Write initial graph integration tests**

Create `tests/integration/test_nl2sql_workflow.py` with graph-level tests first:

```python
from __future__ import annotations

from datetime import datetime

from nl2sqlagent.platform.config import CheckpointerSection, WorkflowSection
from nl2sqlagent.platform.persistence import build_checkpointer
from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql import build_nl2sql_graph
from nl2sqlagent.workflows.runtime import GraphRuntime


def _runtime() -> tuple[GraphRuntime, object, RunContext]:
    return (
        GraphRuntime(),
        build_checkpointer(
            WorkflowSection(checkpointer=CheckpointerSection(provider="memory"))
        ),
        RunContext(
            run_id="run-nl2sql",
            run_date="20260509",
            started_at=datetime(2026, 5, 9, 9, 0, 0),
        ),
    )


def test_nl2sql_graph_success_path_includes_final_prompt() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={"raw_question": "统计员工数量", "options": {}},
        run_context=run_context,
        thread_id="thread-nl2sql-success",
    )

    assert result["status"] == "success"
    assert result["checked_sql"] == "SELECT 1 AS value"
    assert result["result_rows"] == [{"value": 1}]
    assert "Question: 统计员工数量" in result["final_prompt"]


def test_nl2sql_graph_blank_question_goes_to_clarification() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={"raw_question": "   ", "options": {}},
        run_context=run_context,
        thread_id="thread-nl2sql-clarification",
    )

    assert result["status"] == "needs_clarification"
    assert result["message"] == "Please provide a question."
    assert "final_prompt" not in result


def test_nl2sql_graph_check_failure_does_not_retry() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={
            "raw_question": "统计员工数量",
            "options": {"force_check_error": True},
        },
        run_context=run_context,
        thread_id="thread-nl2sql-check-failed",
    )

    assert result["status"] == "failed"
    assert result["message"] == "mock check error"
    assert result["check_error"] == "mock check error"
    assert "Question: 统计员工数量" in result["final_prompt"]
    assert "result_rows" not in result


def test_nl2sql_graph_execute_failure_does_not_retry() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={
            "raw_question": "统计员工数量",
            "options": {"force_execute_error": True},
        },
        run_context=run_context,
        thread_id="thread-nl2sql-execute-failed",
    )

    assert result["status"] == "failed"
    assert result["message"] == "mock execute error"
    assert result["execute_error"] == "mock execute error"
    assert "Question: 统计员工数量" in result["final_prompt"]
```

- [ ] **Step 2: Run graph tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py -v
```

Expected:

```text
FAIL because build_nl2sql_graph does not exist.
```

- [ ] **Step 3: Implement graph builder**

Create `src/nl2sqlagent/workflows/nl2sql/graph.py`:

```python
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from nl2sqlagent.workflows.nl2sql.edges import (
    route_after_check,
    route_after_execute,
    route_after_normalize,
)
from nl2sqlagent.workflows.nl2sql.nodes import (
    build_prompt_node,
    check_sql_node,
    clarification_response_node,
    execute_sql_node,
    failed_response_node,
    generate_sql_node,
    normalize_question_node,
    success_response_node,
)
from nl2sqlagent.workflows.nl2sql.state import Nl2SqlGraphState


def build_nl2sql_graph(*, checkpointer):
    graph = StateGraph(Nl2SqlGraphState)
    graph.add_node("normalize_question", normalize_question_node)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("generate_sql", generate_sql_node)
    graph.add_node("check_sql", check_sql_node)
    graph.add_node("execute_sql", execute_sql_node)
    graph.add_node("clarification_response", clarification_response_node)
    graph.add_node("failed_response", failed_response_node)
    graph.add_node("success_response", success_response_node)

    graph.add_edge(START, "normalize_question")
    graph.add_conditional_edges(
        "normalize_question",
        route_after_normalize,
        {
            "clarification_response": "clarification_response",
            "build_prompt": "build_prompt",
        },
    )
    graph.add_edge("build_prompt", "generate_sql")
    graph.add_edge("generate_sql", "check_sql")
    graph.add_conditional_edges(
        "check_sql",
        route_after_check,
        {
            "failed_response": "failed_response",
            "execute_sql": "execute_sql",
        },
    )
    graph.add_conditional_edges(
        "execute_sql",
        route_after_execute,
        {
            "failed_response": "failed_response",
            "success_response": "success_response",
        },
    )
    graph.add_edge("clarification_response", END)
    graph.add_edge("failed_response", END)
    graph.add_edge("success_response", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["build_nl2sql_graph"]
```

- [ ] **Step 4: Export graph builder**

Modify `src/nl2sqlagent/workflows/nl2sql/__init__.py`:

```python
from nl2sqlagent.workflows.nl2sql.graph import build_nl2sql_graph
from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput
from nl2sqlagent.workflows.nl2sql.output import Nl2SqlOutput, Nl2SqlStatus

__all__ = [
    "Nl2SqlInput",
    "Nl2SqlOutput",
    "Nl2SqlStatus",
    "build_nl2sql_graph",
]
```

- [ ] **Step 5: Run graph integration tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py -v
```

Expected:

```text
4 passed
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql tests/integration/test_nl2sql_workflow.py
git commit -m "feat: add nl2sql workflow graph"
```

---

## Task 6: Workflow Facade

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/workflow.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/__init__.py`
- Test: `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Extend integration tests for facade run and stream**

Append to `tests/integration/test_nl2sql_workflow.py`:

```python
from nl2sqlagent.workflows.nl2sql import Nl2SqlInput, Nl2SqlWorkflow
```

Add:

```python
def test_nl2sql_workflow_run_returns_output_with_prompt_metadata() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
    )

    output = workflow.run(
        Nl2SqlInput(question="统计员工数量"),
        thread_id="thread-nl2sql-workflow-run",
    )

    assert output.status == "success"
    assert output.sql == "SELECT 1 AS value"
    assert output.columns == ["value"]
    assert output.rows == [{"value": 1}]
    assert "Question: 统计员工数量" in output.metadata["final_prompt"]
    assert output.metadata["prompt_payload"]["question"] == "统计员工数量"


def test_nl2sql_workflow_run_preserves_prompt_metadata_on_check_failure() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
    )

    output = workflow.run(
        Nl2SqlInput(
            question="统计员工数量",
            options={"force_check_error": True},
        ),
        thread_id="thread-nl2sql-workflow-check-failed",
    )

    assert output.status == "failed"
    assert output.message == "mock check error"
    assert "Question: 统计员工数量" in output.metadata["final_prompt"]


def test_nl2sql_workflow_stream_updates_exposes_build_prompt_update() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
    )

    chunks = workflow.stream(
        Nl2SqlInput(question="统计员工数量"),
        thread_id="thread-nl2sql-workflow-stream",
        stream_mode="updates",
    )

    assert any(
        isinstance(chunk, dict)
        and "build_prompt" in chunk
        and "Question: 统计员工数量" in chunk["build_prompt"]["final_prompt"]
        for chunk in chunks
    )
```

- [ ] **Step 2: Run extended integration tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py -v
```

Expected:

```text
FAIL because Nl2SqlWorkflow does not exist.
```

- [ ] **Step 3: Implement workflow facade**

Create `src/nl2sqlagent/workflows/nl2sql/workflow.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput
from nl2sqlagent.workflows.nl2sql.output import Nl2SqlOutput
from nl2sqlagent.workflows.nl2sql.response_builder import build_nl2sql_output
from nl2sqlagent.workflows.runtime import GraphRuntime


@dataclass(frozen=True)
class Nl2SqlWorkflow:
    graph: object
    graph_runtime: GraphRuntime
    run_context: RunContext

    @staticmethod
    def _graph_input(input: Nl2SqlInput) -> dict[str, Any]:
        return {
            "request_id": input.request_id,
            "user_id": input.user_id,
            "database_key": input.database_key,
            "raw_question": input.question,
            "options": dict(input.options),
            "status": "running",
        }

    def run(
        self,
        input: Nl2SqlInput,
        *,
        thread_id: str | None = None,
    ) -> Nl2SqlOutput:
        state = self.graph_runtime.invoke(
            graph=self.graph,
            input=self._graph_input(input),
            run_context=self.run_context,
            thread_id=thread_id,
        )
        return build_nl2sql_output(state)

    def stream(
        self,
        input: Nl2SqlInput,
        *,
        thread_id: str | None = None,
        stream_mode: str = "updates",
    ) -> list[Any]:
        return self.graph_runtime.stream(
            graph=self.graph,
            input=self._graph_input(input),
            run_context=self.run_context,
            thread_id=thread_id,
            stream_mode=stream_mode,
        )


__all__ = ["Nl2SqlWorkflow"]
```

- [ ] **Step 4: Export workflow facade**

Modify `src/nl2sqlagent/workflows/nl2sql/__init__.py`:

```python
from nl2sqlagent.workflows.nl2sql.graph import build_nl2sql_graph
from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput
from nl2sqlagent.workflows.nl2sql.output import Nl2SqlOutput, Nl2SqlStatus
from nl2sqlagent.workflows.nl2sql.workflow import Nl2SqlWorkflow

__all__ = [
    "Nl2SqlInput",
    "Nl2SqlOutput",
    "Nl2SqlStatus",
    "Nl2SqlWorkflow",
    "build_nl2sql_graph",
]
```

- [ ] **Step 5: Run integration tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py -v
```

Expected:

```text
7 passed
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql tests/integration/test_nl2sql_workflow.py
git commit -m "feat: add nl2sql workflow facade"
```

---

## Task 7: Bootstrap NL2SQL Workflow

**Files:**

- Modify: `src/nl2sqlagent/bootstrap/app.py`
- Modify: `src/nl2sqlagent/bootstrap/container.py`
- Test: `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Add bootstrap integration tests**

Append to `tests/integration/test_nl2sql_workflow.py`:

```python
from nl2sqlagent.bootstrap import build_app
```

Add:

```python
def test_build_app_exposes_nl2sql_workflow(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yml").write_text(
        "app:\n  name: TestAgent\n  environment: test\n",
        encoding="utf-8",
    )
    (config_dir / "env.yml").write_text(
        "\n".join(
            [
                "paths:",
                "  workspace_dir: workspace",
                "  run_dir: workspace/runs",
                "  log_dir: workspace/logs",
                "",
                "logging:",
                "  level: INFO",
                "  file_enabled: true",
                "  console_enabled: false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (config_dir / "workflow.yml").write_text(
        "workflow:\n  checkpointer:\n    provider: memory\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='test-agent'\n",
        encoding="utf-8",
    )

    app = build_app(project_root=tmp_path, run_id="run-nl2sql-app")

    assert hasattr(app, "nl2sql_workflow")
    assert not hasattr(app, "hello_graph")
    output = app.nl2sql_workflow.run(
        Nl2SqlInput(question="统计员工数量"),
        thread_id="thread-nl2sql-app",
    )
    assert output.status == "success"
    assert "Question: 统计员工数量" in output.metadata["final_prompt"]
```

- [ ] **Step 2: Run bootstrap test and verify it fails**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py::test_build_app_exposes_nl2sql_workflow -v
```

Expected:

```text
FAIL because NL2SQLAgentApp has no nl2sql_workflow.
```

- [ ] **Step 3: Update app dataclass**

Modify `src/nl2sqlagent/bootstrap/app.py`.

Add import:

```python
from nl2sqlagent.workflows.nl2sql import Nl2SqlWorkflow
```

Add field to `NL2SQLAgentApp`:

```python
nl2sql_workflow: Nl2SqlWorkflow
```

Expected final shape:

```python
@dataclass(frozen=True)
class NL2SQLAgentApp:
    config: AppConfig
    paths: ProjectPaths
    logging: LoggingRuntime
    run_context: RunContext
    checkpointer: object
    graph_runtime: GraphRuntime
    nl2sql_workflow: Nl2SqlWorkflow
```

- [ ] **Step 4: Update container**

Modify `src/nl2sqlagent/bootstrap/container.py`.

Add imports:

```python
from nl2sqlagent.workflows.nl2sql import (
    Nl2SqlWorkflow,
    build_nl2sql_graph,
)
```

After `graph_runtime = GraphRuntime()`:

```python
nl2sql_graph = build_nl2sql_graph(checkpointer=checkpointer)
nl2sql_workflow = Nl2SqlWorkflow(
    graph=nl2sql_graph,
    graph_runtime=graph_runtime,
    run_context=run_context,
)
```

Return:

```python
return NL2SQLAgentApp(
    config=config,
    paths=paths,
    logging=logging_runtime,
    run_context=run_context,
    checkpointer=checkpointer,
    graph_runtime=graph_runtime,
    nl2sql_workflow=nl2sql_workflow,
)
```

Do not create or expose `hello_graph`.

- [ ] **Step 5: Run bootstrap integration test**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py::test_build_app_exposes_nl2sql_workflow -v
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run startup CLI regression tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_startup_cli.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Commit**

```powershell
git add src/nl2sqlagent/bootstrap tests/integration/test_nl2sql_workflow.py
git commit -m "feat: expose nl2sql workflow from bootstrap"
```

---

## Task 8: Final Verification

**Files:**

- All Phase 2 files

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

- [ ] **Step 4: Run smoke check for app workflow**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -c "from nl2sqlagent.bootstrap import build_app; from nl2sqlagent.workflows.nl2sql import Nl2SqlInput; app = build_app(run_id='run-phase2-smoke'); output = app.nl2sql_workflow.run(Nl2SqlInput(question='统计员工数量'), thread_id='thread-phase2-smoke'); print(output.status, output.sql, 'final_prompt' in output.metadata, hasattr(app, 'hello_graph'))"
```

Expected:

```text
success SELECT 1 AS value True False
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

- [ ] **Step 6: Confirm no retry fields or routes were introduced**

Run (prefer bundled ripgrep; fallback to `Select-String` if `rg.exe` is missing):

```powershell
$pattern = "round_index|max_round_count|feedback|route.*generate_sql|generate_sql.*route"
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

- [ ] **Step 7: Diff check**

Run:

```powershell
git diff --check
```

Expected:

```text
No trailing whitespace errors.
```

- [ ] **Step 8: Final git status**

Run:

```powershell
git -c core.quotepath=false status --short
```

Expected:

```text
Only intentional Phase 2 files are modified/untracked.
Unrelated docs/temp changes from the user, if present before execution, remain untouched.
```

- [ ] **Step 9: Commit final fixes if needed**

If final verification required small fixes:

```powershell
git add <fixed Phase 2 files only>
git commit -m "fix: stabilize nl2sql workflow skeleton"
```

Do not stage unrelated `docs/temp` files unless the user explicitly asks.

---

## Final Report Template

When complete, report:

```text
Implemented Phase 2 NL2SQL workflow skeleton.

What changed:
- Added Nl2SqlInput / Nl2SqlOutput contracts.
- Added Nl2SqlGraphState.
- Added linear NL2SQL graph without retry.
- Added mock nodes for normalize/build_prompt/generate/check/execute/response.
- Added response builder with prompt metadata.
- Added Nl2SqlWorkflow run/stream facade.
- Wired nl2sql_workflow into build_app.

Verification:
- pytest tests/unit/workflows/nl2sql tests/integration/test_nl2sql_workflow.py -v: passed
- pytest -v: passed
- compileall src/nl2sqlagent: passed
- app workflow smoke: passed
- forbidden paths not created: confirmed
- no retry fields/routes introduced: confirmed

Remaining:
- CLI ask intentionally deferred.
- Real LLM/database/schema grounding intentionally deferred.
- retry/feedback intentionally deferred.
```
