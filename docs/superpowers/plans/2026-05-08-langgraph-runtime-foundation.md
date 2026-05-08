# LangGraph Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Phase 1 LangGraph runtime foundation: workflow config, memory checkpointer, thread ID resolution, GraphRuntime invoke/stream wrapper, and a tiny hello graph used only by tests.

**Architecture:** Keep Phase 1 limited to LangGraph runtime plumbing. `platform/persistence` creates checkpointers; `bootstrap` exposes the checkpointer and `GraphRuntime`; `workflows/hello` compiles a test graph with a passed checkpointer; `GraphRuntime` only builds RunnableConfig and calls compiled graph `invoke` / `stream`. Do not create domain, services, integrations, LLM, database, vectorstore, token, or business NL2SQL code.

**Tech Stack:** Python 3.12, dataclasses, TypedDict, LangGraph `StateGraph`, LangGraph `InMemorySaver`, pytest.

---

## 0. Scope Guard

This plan implements `docs/temp/Phase1_LangGraph运行底座设计.md`.

Allowed to create or modify:

```text
pyproject.toml
config/workflow.yml
src/nl2sqlagent/platform/config/**
src/nl2sqlagent/platform/persistence/**
src/nl2sqlagent/bootstrap/**
src/nl2sqlagent/workflows/**
tests/unit/platform/test_checkpointer_factory.py
tests/unit/workflows/runtime/**
tests/integration/test_hello_graph_runtime.py
existing Phase 0 tests that need workflow.yml in temp config
```

Forbidden in this phase:

```text
domain/
services/
integrations/
LLM
database
vectorstore
embedding
token usage
LangSmith
NL2SQL business flow
schema grounding
SQL generation
SQL execution
CLI hello-graph command
```

Design rules:

```text
1. GraphRuntime does not hold checkpointer.
2. GraphRuntime does not compile graphs.
3. build_app creates and exposes checkpointer.
4. build_app does not create hello graph or NL2SQL graph.
5. hello graph is only built inside tests.
6. GraphRuntime.stream returns raw list(graph.stream(...)) chunks.
```

Before any Python command:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
```

---

## 1. Target File Changes

Create:

```text
config/workflow.yml

src/nl2sqlagent/platform/persistence/__init__.py
src/nl2sqlagent/platform/persistence/checkpointer_factory.py

src/nl2sqlagent/workflows/__init__.py
src/nl2sqlagent/workflows/runtime/__init__.py
src/nl2sqlagent/workflows/runtime/thread_id.py
src/nl2sqlagent/workflows/runtime/graph_runtime.py

src/nl2sqlagent/workflows/hello/__init__.py
src/nl2sqlagent/workflows/hello/state.py
src/nl2sqlagent/workflows/hello/nodes.py
src/nl2sqlagent/workflows/hello/graph.py

tests/unit/platform/test_checkpointer_factory.py
tests/unit/workflows/runtime/test_thread_id.py
tests/unit/workflows/runtime/test_graph_runtime.py
tests/integration/test_hello_graph_runtime.py
```

Modify:

```text
pyproject.toml
src/nl2sqlagent/platform/config/models.py
src/nl2sqlagent/platform/config/loader.py
src/nl2sqlagent/platform/config/__init__.py
src/nl2sqlagent/bootstrap/app.py
src/nl2sqlagent/bootstrap/container.py
tests/unit/platform/test_config_loader.py
tests/integration/test_startup_cli.py
```

---

## Task 1: Add LangGraph Dependency And Workflow Config

**Files:**

- Modify: `pyproject.toml`
- Create: `config/workflow.yml`
- Modify: `src/nl2sqlagent/platform/config/models.py`
- Modify: `src/nl2sqlagent/platform/config/loader.py`
- Modify: `src/nl2sqlagent/platform/config/__init__.py`
- Modify tests that write temp configs

- [ ] **Step 1: Add LangGraph dependency**

Modify `pyproject.toml`:

```toml
dependencies = [
    "PyYAML>=6.0",
    "langgraph>=1.0",
]
```

- [ ] **Step 2: Add import smoke before deeper work**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -c "from langgraph.checkpoint.memory import InMemorySaver; from langgraph.graph import END, START, StateGraph; print('ok')"
```

Expected:

```text
ok
```

If this fails because `langgraph` is not installed, install project dependencies in the local environment before continuing:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pip install -e ".[dev]"
```

- [ ] **Step 3: Add default workflow config**

Create `config/workflow.yml`:

```yaml
workflow:
  checkpointer:
    provider: memory
```

- [ ] **Step 4: Write config test updates first**

Update `tests/unit/platform/test_config_loader.py` helper `_write_config()` so it also writes:

```python
(config_dir / "workflow.yml").write_text(
    "workflow:\n  checkpointer:\n    provider: memory\n",
    encoding="utf-8",
)
```

Add assertion in `test_load_app_config_reads_app_and_env_sections`:

```python
assert config.workflow.checkpointer.provider == "memory"
```

Add a missing workflow file test:

```python
def test_load_app_config_raises_for_missing_workflow_file(tmp_path: Path) -> None:
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
                "  level: DEBUG",
                "  file_enabled: true",
                "  console_enabled: false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="workflow.yml"):
        load_app_config(config_dir=config_dir)
```

Update `tests/integration/test_startup_cli.py` helper `_write_config()` so it writes `workflow.yml` as above.

- [ ] **Step 5: Run config/startup tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_config_loader.py tests/integration/test_startup_cli.py -v
```

Expected:

```text
FAIL because AppConfig has no workflow field and loader does not read workflow.yml yet.
```

- [ ] **Step 6: Add workflow config models**

Modify `src/nl2sqlagent/platform/config/models.py`:

```python
@dataclass(frozen=True)
class CheckpointerSection:
    provider: str


@dataclass(frozen=True)
class WorkflowSection:
    checkpointer: CheckpointerSection
```

Add field to `AppConfig`:

```python
workflow: WorkflowSection
```

Update `__all__`:

```python
"CheckpointerSection",
"WorkflowSection",
```

- [ ] **Step 7: Update config loader**

Modify `src/nl2sqlagent/platform/config/loader.py`:

Import:

```python
CheckpointerSection,
WorkflowSection,
```

Load:

```python
workflow_data = _load_yaml_file(resolved_config_dir / "workflow.yml")
workflow_section = _mapping(workflow_data, "workflow", file_name="workflow.yml")
checkpointer_section = _mapping(
    workflow_section,
    "checkpointer",
    file_name="workflow.yml",
)
```

Return:

```python
workflow=WorkflowSection(
    checkpointer=CheckpointerSection(
        provider=_string(
            checkpointer_section,
            "provider",
            section="workflow.checkpointer",
        ),
    ),
),
```

Do not provide a silent default if `workflow.yml` is missing.

- [ ] **Step 8: Export workflow config models**

Modify `src/nl2sqlagent/platform/config/__init__.py` to export:

```python
CheckpointerSection
WorkflowSection
```

- [ ] **Step 9: Run updated tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_config_loader.py tests/integration/test_startup_cli.py -v
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 10: Commit**

```powershell
git add pyproject.toml config/workflow.yml src/nl2sqlagent/platform/config tests/unit/platform/test_config_loader.py tests/integration/test_startup_cli.py
git commit -m "feat: add workflow runtime config"
```

---

## Task 2: Thread ID Runtime Helper

**Files:**

- Create: `src/nl2sqlagent/workflows/__init__.py`
- Create: `src/nl2sqlagent/workflows/runtime/__init__.py`
- Create: `src/nl2sqlagent/workflows/runtime/thread_id.py`
- Test: `tests/unit/workflows/runtime/test_thread_id.py`

- [ ] **Step 1: Write thread ID tests**

Create `tests/unit/workflows/runtime/test_thread_id.py`:

```python
from __future__ import annotations

import pytest

from nl2sqlagent.workflows.runtime import resolve_thread_id


def test_resolve_thread_id_uses_explicit_value() -> None:
    assert (
        resolve_thread_id(run_id="run-a1b2c3d4", thread_id=" custom-thread ")
        == "custom-thread"
    )


def test_resolve_thread_id_falls_back_for_blank_thread_id() -> None:
    assert (
        resolve_thread_id(run_id="run-a1b2c3d4", thread_id="   ")
        == "thread-run-a1b2c3d4"
    )


def test_resolve_thread_id_falls_back_when_not_provided() -> None:
    assert resolve_thread_id(run_id="run-a1b2c3d4") == "thread-run-a1b2c3d4"


def test_resolve_thread_id_rejects_blank_run_id() -> None:
    with pytest.raises(ValueError, match="run_id"):
        resolve_thread_id(run_id="   ")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/workflows/runtime/test_thread_id.py -v
```

Expected:

```text
FAIL because workflows.runtime does not exist.
```

- [ ] **Step 3: Implement thread ID helper**

Create `src/nl2sqlagent/workflows/__init__.py`:

```python
__all__: list[str] = []
```

Create `src/nl2sqlagent/workflows/runtime/thread_id.py`:

```python
from __future__ import annotations


def resolve_thread_id(
    *,
    run_id: str,
    thread_id: str | None = None,
) -> str:
    resolved_run_id = run_id.strip()
    if not resolved_run_id:
        raise ValueError("run_id is required to resolve thread_id")

    if thread_id is not None:
        resolved_thread_id = thread_id.strip()
        if resolved_thread_id:
            return resolved_thread_id

    return f"thread-{resolved_run_id}"


__all__ = ["resolve_thread_id"]
```

Create `src/nl2sqlagent/workflows/runtime/__init__.py`:

```python
from nl2sqlagent.workflows.runtime.thread_id import resolve_thread_id

__all__ = ["resolve_thread_id"]
```

- [ ] **Step 4: Run thread ID tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/workflows/runtime/test_thread_id.py -v
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows tests/unit/workflows/runtime/test_thread_id.py
git commit -m "feat: add workflow thread id helper"
```

---

## Task 3: Memory Checkpointer Factory

**Files:**

- Create: `src/nl2sqlagent/platform/persistence/__init__.py`
- Create: `src/nl2sqlagent/platform/persistence/checkpointer_factory.py`
- Test: `tests/unit/platform/test_checkpointer_factory.py`

- [ ] **Step 1: Write checkpointer tests**

Create `tests/unit/platform/test_checkpointer_factory.py`:

```python
from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from nl2sqlagent.platform.config import CheckpointerSection, WorkflowSection
from nl2sqlagent.platform.errors import ConfigurationError
from nl2sqlagent.platform.persistence import build_checkpointer


def test_build_checkpointer_returns_memory_saver() -> None:
    checkpointer = build_checkpointer(
        WorkflowSection(checkpointer=CheckpointerSection(provider="memory"))
    )

    assert isinstance(checkpointer, InMemorySaver)


def test_build_checkpointer_rejects_unknown_provider() -> None:
    with pytest.raises(ConfigurationError, match="checkpointer"):
        build_checkpointer(
            WorkflowSection(checkpointer=CheckpointerSection(provider="sqlite"))
        )
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_checkpointer_factory.py -v
```

Expected:

```text
FAIL because platform.persistence does not exist.
```

- [ ] **Step 3: Implement checkpointer factory**

Create `src/nl2sqlagent/platform/persistence/checkpointer_factory.py`:

```python
from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from nl2sqlagent.platform.config import WorkflowSection
from nl2sqlagent.platform.errors import ConfigurationError


def build_checkpointer(config: WorkflowSection) -> InMemorySaver:
    provider = config.checkpointer.provider.strip().lower()
    if provider == "memory":
        return InMemorySaver()
    raise ConfigurationError(
        f"unsupported workflow.checkpointer.provider: {config.checkpointer.provider}"
    )


__all__ = ["build_checkpointer"]
```

Create `src/nl2sqlagent/platform/persistence/__init__.py`:

```python
from nl2sqlagent.platform.persistence.checkpointer_factory import build_checkpointer

__all__ = ["build_checkpointer"]
```

- [ ] **Step 4: Run checkpointer tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_checkpointer_factory.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/platform/persistence tests/unit/platform/test_checkpointer_factory.py
git commit -m "feat: add memory checkpointer factory"
```

---

## Task 4: GraphRuntime Invoke And Stream

**Files:**

- Create: `src/nl2sqlagent/workflows/runtime/graph_runtime.py`
- Modify: `src/nl2sqlagent/workflows/runtime/__init__.py`
- Test: `tests/unit/workflows/runtime/test_graph_runtime.py`

- [ ] **Step 1: Write GraphRuntime unit tests with fake graph**

Create `tests/unit/workflows/runtime/test_graph_runtime.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.runtime import GraphRuntime


@dataclass
class _FakeGraph:
    last_config: dict | None = None

    def invoke(self, input: dict, config: dict) -> dict:
        self.last_config = config
        return {"received": input["value"]}

    def stream(self, input: dict, config: dict, stream_mode: str):
        self.last_config = config
        yield {"mode": stream_mode, "received": input["value"]}


def _run_context() -> RunContext:
    return RunContext(
        run_id="run-test",
        run_date="20260508",
        started_at=datetime(2026, 5, 8, 17, 0, 0),
    )


def test_graph_runtime_invoke_injects_thread_id_and_metadata() -> None:
    graph = _FakeGraph()
    runtime = GraphRuntime()

    result = runtime.invoke(
        graph=graph,
        input={"value": "hello"},
        run_context=_run_context(),
    )

    assert result == {"received": "hello"}
    assert graph.last_config == {
        "configurable": {"thread_id": "thread-run-test"},
        "metadata": {"run_id": "run-test", "run_date": "20260508"},
    }


def test_graph_runtime_stream_returns_raw_chunks() -> None:
    graph = _FakeGraph()
    runtime = GraphRuntime()

    chunks = runtime.stream(
        graph=graph,
        input={"value": "hello"},
        run_context=_run_context(),
        thread_id="custom-thread",
        stream_mode="updates",
    )

    assert chunks == [{"mode": "updates", "received": "hello"}]
    assert graph.last_config == {
        "configurable": {"thread_id": "custom-thread"},
        "metadata": {"run_id": "run-test", "run_date": "20260508"},
    }
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/workflows/runtime/test_graph_runtime.py -v
```

Expected:

```text
FAIL because GraphRuntime does not exist.
```

- [ ] **Step 3: Implement GraphRuntime**

Create `src/nl2sqlagent/workflows/runtime/graph_runtime.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.runtime.thread_id import resolve_thread_id


@dataclass(frozen=True)
class GraphRuntime:
    """Runs compiled LangGraph graphs with project-standard config."""

    def _config(
        self,
        *,
        run_context: RunContext,
        thread_id: str | None,
    ) -> dict[str, Any]:
        return {
            "configurable": {
                "thread_id": resolve_thread_id(
                    run_id=run_context.run_id,
                    thread_id=thread_id,
                ),
            },
            "metadata": {
                "run_id": run_context.run_id,
                "run_date": run_context.run_date,
            },
        }

    def invoke(
        self,
        *,
        graph,
        input: dict[str, Any],
        run_context: RunContext,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        return dict(
            graph.invoke(
                input,
                config=self._config(
                    run_context=run_context,
                    thread_id=thread_id,
                ),
            )
        )

    def stream(
        self,
        *,
        graph,
        input: dict[str, Any],
        run_context: RunContext,
        thread_id: str | None = None,
        stream_mode: str = "updates",
    ) -> list[Any]:
        return list(
            graph.stream(
                input,
                config=self._config(
                    run_context=run_context,
                    thread_id=thread_id,
                ),
                stream_mode=stream_mode,
            )
        )


__all__ = ["GraphRuntime"]
```

- [ ] **Step 4: Export GraphRuntime**

Modify `src/nl2sqlagent/workflows/runtime/__init__.py`:

```python
from nl2sqlagent.workflows.runtime.graph_runtime import GraphRuntime
from nl2sqlagent.workflows.runtime.thread_id import resolve_thread_id

__all__ = ["GraphRuntime", "resolve_thread_id"]
```

- [ ] **Step 5: Run GraphRuntime tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/workflows/runtime/test_graph_runtime.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/runtime tests/unit/workflows/runtime/test_graph_runtime.py
git commit -m "feat: add graph runtime wrapper"
```

---

## Task 5: Hello Graph For Runtime Verification

**Files:**

- Create: `src/nl2sqlagent/workflows/hello/__init__.py`
- Create: `src/nl2sqlagent/workflows/hello/state.py`
- Create: `src/nl2sqlagent/workflows/hello/nodes.py`
- Create: `src/nl2sqlagent/workflows/hello/graph.py`
- Test: `tests/integration/test_hello_graph_runtime.py`

- [ ] **Step 1: Write hello graph integration tests**

Create `tests/integration/test_hello_graph_runtime.py`:

```python
from __future__ import annotations

from datetime import datetime

from nl2sqlagent.platform.config import CheckpointerSection, WorkflowSection
from nl2sqlagent.platform.persistence import build_checkpointer
from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.hello import build_hello_graph
from nl2sqlagent.workflows.runtime import GraphRuntime


def _runtime() -> tuple[GraphRuntime, object, RunContext]:
    return (
        GraphRuntime(),
        build_checkpointer(
            WorkflowSection(checkpointer=CheckpointerSection(provider="memory"))
        ),
        RunContext(
            run_id="run-hello",
            run_date="20260508",
            started_at=datetime(2026, 5, 8, 17, 30, 0),
        ),
    )


def test_hello_graph_invoke_returns_state() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_hello_graph(checkpointer=checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={"name": "Alice"},
        run_context=run_context,
        thread_id="thread-hello-invoke",
    )

    assert result["message"] == "hello, Alice"
    assert result["step_count"] == 1


def test_hello_graph_stream_updates_returns_raw_chunks() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_hello_graph(checkpointer=checkpointer)

    chunks = runtime.stream(
        graph=graph,
        input={"name": "Bob"},
        run_context=run_context,
        thread_id="thread-hello-stream-updates",
        stream_mode="updates",
    )

    assert chunks
    assert any(
        isinstance(chunk, dict)
        and "greet" in chunk
        and chunk["greet"].get("message") == "hello, Bob"
        for chunk in chunks
    )


def test_hello_graph_stream_values_returns_state_chunks() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_hello_graph(checkpointer=checkpointer)

    chunks = runtime.stream(
        graph=graph,
        input={"name": "Carol"},
        run_context=run_context,
        thread_id="thread-hello-stream-values",
        stream_mode="values",
    )

    assert chunks
    assert any(
        isinstance(chunk, dict) and chunk.get("message") == "hello, Carol"
        for chunk in chunks
    )
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/integration/test_hello_graph_runtime.py -v
```

Expected:

```text
FAIL because workflows.hello does not exist.
```

- [ ] **Step 3: Implement hello state**

Create `src/nl2sqlagent/workflows/hello/state.py`:

```python
from __future__ import annotations

from typing import TypedDict


class HelloGraphState(TypedDict, total=False):
    name: str
    message: str
    step_count: int


__all__ = ["HelloGraphState"]
```

- [ ] **Step 4: Implement hello node**

Create `src/nl2sqlagent/workflows/hello/nodes.py`:

```python
from __future__ import annotations

from nl2sqlagent.workflows.hello.state import HelloGraphState


def greet_node(state: HelloGraphState) -> dict:
    name = state.get("name") or "world"
    return {
        "message": f"hello, {name}",
        "step_count": state.get("step_count", 0) + 1,
    }


__all__ = ["greet_node"]
```

- [ ] **Step 5: Implement hello graph**

Create `src/nl2sqlagent/workflows/hello/graph.py`:

```python
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from nl2sqlagent.workflows.hello.nodes import greet_node
from nl2sqlagent.workflows.hello.state import HelloGraphState


def build_hello_graph(*, checkpointer):
    graph = StateGraph(HelloGraphState)
    graph.add_node("greet", greet_node)
    graph.add_edge(START, "greet")
    graph.add_edge("greet", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["build_hello_graph"]
```

- [ ] **Step 6: Export hello graph**

Create `src/nl2sqlagent/workflows/hello/__init__.py`:

```python
from nl2sqlagent.workflows.hello.graph import build_hello_graph

__all__ = ["build_hello_graph"]
```

- [ ] **Step 7: Run hello integration tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/integration/test_hello_graph_runtime.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 8: Commit**

```powershell
git add src/nl2sqlagent/workflows/hello tests/integration/test_hello_graph_runtime.py
git commit -m "feat: add hello graph runtime verification"
```

---

## Task 6: Bootstrap GraphRuntime And Checkpointer

**Files:**

- Modify: `src/nl2sqlagent/bootstrap/app.py`
- Modify: `src/nl2sqlagent/bootstrap/container.py`
- Test: existing startup tests

- [ ] **Step 1: Update app dataclass**

Modify `src/nl2sqlagent/bootstrap/app.py`.

Import:

```python
from nl2sqlagent.workflows.runtime import GraphRuntime
```

Add fields to `NL2SQLAgentApp`:

```python
checkpointer: object
graph_runtime: GraphRuntime
```

- [ ] **Step 2: Update container**

Modify `src/nl2sqlagent/bootstrap/container.py`.

Import:

```python
from nl2sqlagent.platform.persistence import build_checkpointer
from nl2sqlagent.workflows.runtime import GraphRuntime
```

After logger creation:

```python
checkpointer = build_checkpointer(config.workflow)
graph_runtime = GraphRuntime()
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
)
```

Do not build hello graph in `build_app()`.

- [ ] **Step 3: Run startup tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/integration/test_startup_cli.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 4: Run app smoke**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -c "from nl2sqlagent.bootstrap import build_app; app = build_app(run_id='run-phase1-smoke'); print(type(app.graph_runtime).__name__, type(app.checkpointer).__name__)"
```

Expected:

```text
GraphRuntime InMemorySaver
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/bootstrap
git commit -m "feat: wire graph runtime foundation"
```

---

## Task 7: Final Verification

**Files:**

- All Phase 1 files

- [ ] **Step 1: Run all tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest -v
```

Expected:

```text
All tests pass.
```

- [ ] **Step 2: Compile source**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m compileall src/nl2sqlagent
```

Expected:

```text
No SyntaxError.
```

- [ ] **Step 3: Run startup command**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m nl2sqlagent.interfaces.cli.main startup --project-root . --run-id run-phase1-final
```

Expected:

```text
Startup summary is printed.
workspace/logs/<run_date>/run-phase1-final/app.log exists.
```

- [ ] **Step 4: Confirm allowed and forbidden directories**

Run:

```powershell
Test-Path .\src\nl2sqlagent\workflows
Test-Path .\src\nl2sqlagent\platform\persistence
Test-Path .\src\nl2sqlagent\domain
Test-Path .\src\nl2sqlagent\services
Test-Path .\src\nl2sqlagent\integrations
```

Expected:

```text
True
True
False
False
False
```

- [ ] **Step 5: Verify build_app does not expose hello graph**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -c "from nl2sqlagent.bootstrap import build_app; app = build_app(run_id='run-no-hello'); print(hasattr(app, 'hello_graph'))"
```

Expected:

```text
False
```

- [ ] **Step 6: Diff check**

Run:

```powershell
git diff --check
```

Expected:

```text
No trailing whitespace errors.
```

- [ ] **Step 7: Final status**

Run:

```powershell
git -c core.quotepath=false status --short
```

Expected:

```text
Only intentional files are modified or untracked.
```

- [ ] **Step 8: Commit final fixes if needed**

No extra commit is required if all earlier task commits are clean. If small fixes were needed during final verification:

```powershell
git add <fixed files>
git commit -m "fix: stabilize langgraph runtime foundation"
```

---

## Final Report Template

When complete, report:

```text
Implemented Phase 1 LangGraph runtime foundation.

What changed:
- Added langgraph dependency.
- Added workflow.yml and workflow config models.
- Added memory checkpointer factory.
- Added thread_id resolver.
- Added GraphRuntime invoke/stream wrapper.
- Added hello graph used by tests only.
- Wired checkpointer and GraphRuntime into app bootstrap.

Verification:
- pytest -v: passed
- compileall src/nl2sqlagent: passed
- startup CLI manual check: passed
- workflows and platform/persistence exist: confirmed
- domain/services/integrations not created: confirmed
- app does not expose hello_graph: confirmed

Remaining:
- NL2SQL business graph intentionally deferred to Phase 2.
- LLM/database/vectorstore/token/LangSmith intentionally deferred.
```

