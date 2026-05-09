# NL2SQL Run Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 4 NL2SQL run artifacts so every workflow run writes stable local evidence for input, prompt payload, final prompt, graph updates, output, and manifest.

**Architecture:** Keep generic LangGraph execution in `workflows/runtime`, keep NL2SQL-specific artifact writing in `workflows/nl2sql/artifacts.py`, and keep `nodes.py` pure. `Nl2SqlWorkflow` only orchestrates graph execution, artifact writing, metadata merge, and app-log summaries.

**Tech Stack:** Python 3.12, LangGraph, dataclasses, TypedDict, JSON/JSONL/TXT files, existing logging runtime, pytest.

---

## 0. Scope Guard

This plan implements:

```text
docs/temp/Phase4_NL2SQL运行artifact设计.md
```

Before any Python command, follow the repository rule:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
```

Do not use bare `python`.

Allowed to create:

```text
src/nl2sqlagent/workflows/nl2sql/artifacts.py
tests/unit/workflows/nl2sql/test_artifacts.py
```

Allowed to modify:

```text
src/nl2sqlagent/workflows/runtime/graph_runtime.py
src/nl2sqlagent/workflows/runtime/__init__.py
src/nl2sqlagent/workflows/nl2sql/workflow.py
src/nl2sqlagent/workflows/nl2sql/__init__.py
src/nl2sqlagent/bootstrap/container.py
tests/unit/workflows/runtime/test_graph_runtime.py
tests/integration/test_nl2sql_workflow.py
```

Modify only if needed:

```text
src/nl2sqlagent/bootstrap/app.py
tests/unit/workflows/nl2sql/test_contracts.py
```

Forbidden in this phase:

```text
real LLM calls
real token usage files
empty token_usage.json
LangSmith
OpenTelemetry
real database
real schema grounding
SQL execution
retry / feedback loop
domain/services/integrations directories
CLI ask command
artifact file writes inside nodes.py
NL2SQL business-field parsing inside GraphRuntime
json.dump/json.dumps artifact content inside Nl2SqlWorkflow.run
```

Design rules:

```text
1. GraphRuntime returns raw LangGraph update chunks only.
2. Artifact writer is the only code that normalizes graph update chunks into node/update JSONL rows.
3. Artifact writer is the only code that constructs artifact path metadata.
4. Path objects may exist internally, but JSON files and output.metadata must contain strings or null.
5. prompt_payload and final_prompt still come from final_state.
6. No artifact failure should change Nl2SqlOutput.status unless artifact_required=True is used directly in tests.
7. token_usage_path is always null in Phase 4.
8. app.log contains summaries and paths only, not full prompt_payload/final_prompt/rows.
9. Do not redesign state/options/prompt_payload types in this phase.
```

Current dirty-worktree caution:

```text
The user may have unrelated uncommitted docs/temp changes.
Do not stage, restore, or commit docs/temp files unless explicitly instructed.
```

---

## 1. Target File Responsibilities

```text
workflows/runtime/graph_runtime.py
  Owns GraphRunResult and invoke_with_updates(...).
  Owns a public resolve_thread_id(...) helper so workflow logging and graph config use one thread-id rule.
  Runs graph.stream(..., stream_mode="updates") once.
  Calls graph.get_state(config) with the same config object.
  Returns final_state as a plain dict, raw update chunks, and resolved thread_id.
  Does not inspect prompt_payload, final_prompt, sql, rows, or other NL2SQL fields.

workflows/nl2sql/artifacts.py
  Owns Nl2SqlArtifactPaths, Nl2SqlArtifactResult, Nl2SqlArtifactMetadata, NormalizedGraphUpdate.
  Computes artifact_id and paths.
  Writes input.json, prompt_payload.json, final_prompt.txt, graph_updates.jsonl, output.json, manifest.json.
  Converts Path/datetime/other values into JSON-safe values.
  Normalizes raw LangGraph update chunks into {"node": ..., "update": ...} JSONL rows.

workflows/nl2sql/workflow.py
  Injects log_dir/logger.
  Calls GraphRuntime.invoke_with_updates for run(...).
  Builds Nl2SqlOutput from final_state.
  Calls write_nl2sql_artifacts(...).
  Merges artifact_result.metadata into output.metadata.
  Writes started/finished/error app-log summaries.

bootstrap/container.py
  Passes logging_runtime.log_dir and logging_runtime.logger into Nl2SqlWorkflow.

nodes.py
  No changes expected.
  Must stay file-system-free and logger-free.
```

---

## Task 1: Graph Runtime Result And Single-Execution Updates

**Files:**

- Modify: `src/nl2sqlagent/workflows/runtime/graph_runtime.py`
- Modify: `src/nl2sqlagent/workflows/runtime/__init__.py`
- Modify: `tests/unit/workflows/runtime/test_graph_runtime.py`

- [ ] **Step 1: Write failing tests for invoke_with_updates**

Append tests to `tests/unit/workflows/runtime/test_graph_runtime.py`:

```python
from typing import Any


@dataclass
class _FakeStateSnapshot:
    values: dict[str, Any]


@dataclass
class _StatefulFakeGraph:
    stream_config: dict | None = None
    get_state_config: dict | None = None
    stream_call_count: int = 0
    get_state_call_count: int = 0

    def stream(self, input: dict, config: dict, stream_mode: str):
        self.stream_call_count += 1
        self.stream_config = config
        yield {"build_prompt": {"final_prompt": "prompt"}}
        yield {"execute_sql": {"result_rows": [{"value": 1}]}}

    def get_state(self, config: dict) -> _FakeStateSnapshot:
        self.get_state_call_count += 1
        self.get_state_config = config
        return _FakeStateSnapshot(
            values={
                "status": "success",
                "final_prompt": "prompt",
                "result_rows": [{"value": 1}],
            }
        )


def test_graph_runtime_invoke_with_updates_returns_updates_final_state_and_thread_id() -> None:
    graph = _StatefulFakeGraph()
    runtime = GraphRuntime()

    result = runtime.invoke_with_updates(
        graph=graph,
        input={"raw_question": "统计员工数量"},
        run_context=_run_context(),
        thread_id="thread-phase4",
    )

    assert result.thread_id == "thread-phase4"
    assert result.updates == [
        {"build_prompt": {"final_prompt": "prompt"}},
        {"execute_sql": {"result_rows": [{"value": 1}]}},
    ]
    assert result.final_state == {
        "status": "success",
        "final_prompt": "prompt",
        "result_rows": [{"value": 1}],
    }
    assert graph.stream_call_count == 1
    assert graph.get_state_call_count == 1


def test_graph_runtime_invoke_with_updates_uses_same_config_for_stream_and_get_state() -> None:
    graph = _StatefulFakeGraph()
    runtime = GraphRuntime()

    runtime.invoke_with_updates(
        graph=graph,
        input={"raw_question": "统计员工数量"},
        run_context=_run_context(),
        thread_id=None,
    )

    assert graph.stream_config is graph.get_state_config
    assert graph.stream_config == {
        "configurable": {"thread_id": "thread-run-test"},
        "metadata": {"run_id": "run-test", "run_date": "20260508"},
    }


def test_graph_runtime_resolve_thread_id_matches_config_rule() -> None:
    runtime = GraphRuntime()

    assert runtime.resolve_thread_id(
        run_context=_run_context(),
        thread_id=None,
    ) == "thread-run-test"
    assert runtime.resolve_thread_id(
        run_context=_run_context(),
        thread_id="custom-thread",
    ) == "custom-thread"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/runtime/test_graph_runtime.py -v
```

Expected:

```text
FAIL because GraphRuntime.invoke_with_updates does not exist.
```

- [ ] **Step 3: Implement GraphRunResult and invoke_with_updates**

Modify `src/nl2sqlagent/workflows/runtime/graph_runtime.py`:

```python
@dataclass(frozen=True)
class GraphRunResult:
    final_state: dict[str, Any]
    updates: list[dict[str, Any]]
    thread_id: str
```

Add public thread-id resolution:

```python
def resolve_thread_id(
    self,
    *,
    run_context: RunContext,
    thread_id: str | None,
) -> str:
    return resolve_thread_id(
        run_id=run_context.run_id,
        thread_id=thread_id,
    )
```

Then update `_config(...)` to call `self.resolve_thread_id(...)` instead of directly calling the imported helper. This keeps workflow logging and graph config on the same rule.

Add method to `GraphRuntime`:

```python
def invoke_with_updates(
    self,
    *,
    graph,
    input: dict[str, Any],
    run_context: RunContext,
    thread_id: str | None = None,
) -> GraphRunResult:
    config = self._config(
        run_context=run_context,
        thread_id=thread_id,
    )
    updates = list(
        graph.stream(
            input,
            config=config,
            stream_mode="updates",
        )
    )
    state_snapshot = graph.get_state(config)
    return GraphRunResult(
        final_state=dict(state_snapshot.values),
        updates=updates,
        thread_id=str(config["configurable"]["thread_id"]),
    )
```

Update `__all__` in `graph_runtime.py` and `workflows/runtime/__init__.py` to export `GraphRunResult`.

- [ ] **Step 4: Run graph runtime tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/runtime/test_graph_runtime.py -v
```

Expected:

```text
All graph runtime tests pass.
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows/runtime/graph_runtime.py src/nl2sqlagent/workflows/runtime/__init__.py tests/unit/workflows/runtime/test_graph_runtime.py
git commit -m "feat: add graph runtime updates result"
```

---

## Task 2: Artifact Writer Models, Paths, And Update Normalization

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/artifacts.py`
- Test: `tests/unit/workflows/nl2sql/test_artifacts.py`

- [ ] **Step 1: Write failing tests for artifact paths and update normalization**

Create `tests/unit/workflows/nl2sql/test_artifacts.py` with:

```python
from __future__ import annotations

import json
from datetime import datetime

from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql.artifacts import (
    build_nl2sql_artifact_paths,
    normalize_graph_updates,
)
from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput


def _run_context() -> RunContext:
    return RunContext(
        run_id="run-phase4",
        run_date="20260509",
        started_at=datetime(2026, 5, 9, 9, 0, 0),
    )


def test_build_nl2sql_artifact_paths_prefers_request_id(tmp_path) -> None:
    paths = build_nl2sql_artifact_paths(
        log_dir=tmp_path / "logs" / "20260509" / "run-phase4",
        run_context=_run_context(),
        input=Nl2SqlInput(
            question="统计员工数量",
            request_id="request/中文 1",
        ),
        resolved_thread_id="thread-phase4",
    )

    assert paths.artifact_dir == (
        tmp_path
        / "logs"
        / "20260509"
        / "run-phase4"
        / "artifacts"
        / "nl2sql"
        / "request_1"
    )
    assert paths.input_path == paths.artifact_dir / "input.json"
    assert paths.prompt_payload_path == paths.artifact_dir / "prompt_payload.json"
    assert paths.final_prompt_path == paths.artifact_dir / "final_prompt.txt"
    assert paths.graph_updates_path == paths.artifact_dir / "graph_updates.jsonl"
    assert paths.output_path == paths.artifact_dir / "output.json"
    assert paths.manifest_path == paths.artifact_dir / "manifest.json"
    assert paths.token_usage_path is None


def test_build_nl2sql_artifact_paths_falls_back_to_thread_id(tmp_path) -> None:
    paths = build_nl2sql_artifact_paths(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量"),
        resolved_thread_id="thread:phase4",
    )

    assert paths.artifact_dir == tmp_path / "artifacts" / "nl2sql" / "thread_phase4"


def test_build_nl2sql_artifact_paths_falls_back_to_run_id_when_request_id_is_sanitized_empty(tmp_path) -> None:
    paths = build_nl2sql_artifact_paths(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量", request_id="中文"),
        resolved_thread_id="thread-phase4",
    )

    assert paths.artifact_dir == tmp_path / "artifacts" / "nl2sql" / "run-phase4"


def test_normalize_graph_updates_expands_each_node_update() -> None:
    rows = normalize_graph_updates(
        [
            {"build_prompt": {"final_prompt": "prompt"}},
            {
                "check_sql": {"checked_sql": "SELECT 1 AS value"},
                "execute_sql": {"result_rows": [{"value": 1}]},
            },
        ]
    )

    assert rows == [
        {"node": "build_prompt", "update": {"final_prompt": "prompt"}},
        {"node": "check_sql", "update": {"checked_sql": "SELECT 1 AS value"}},
        {"node": "execute_sql", "update": {"result_rows": [{"value": 1}]}},
    ]


def test_normalized_graph_updates_are_json_serializable() -> None:
    rows = normalize_graph_updates([{"build_prompt": {"final_prompt": "prompt"}}])

    assert json.loads(json.dumps(rows[0], ensure_ascii=False)) == rows[0]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_artifacts.py -v
```

Expected:

```text
FAIL because nl2sqlagent.workflows.nl2sql.artifacts does not exist.
```

- [ ] **Step 3: Implement artifact data models and helpers**

Create `src/nl2sqlagent/workflows/nl2sql/artifacts.py` with these public structures:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput


class Nl2SqlArtifactMetadata(TypedDict):
    artifact_manifest_path: str | None
    input_path: str | None
    prompt_payload_path: str | None
    final_prompt_path: str | None
    graph_updates_path: str | None
    output_path: str | None
    token_usage_path: str | None
    artifact_error: str | None


class NormalizedGraphUpdate(TypedDict):
    node: str
    update: dict[str, Any]


@dataclass(frozen=True)
class Nl2SqlArtifactPaths:
    artifact_dir: Path
    input_path: Path
    prompt_payload_path: Path
    final_prompt_path: Path
    graph_updates_path: Path
    output_path: Path
    manifest_path: Path
    token_usage_path: Path | None = None


@dataclass(frozen=True)
class Nl2SqlArtifactResult:
    paths: Nl2SqlArtifactPaths | None
    metadata: Nl2SqlArtifactMetadata
    artifact_error: str | None = None


def _safe_artifact_id(value: str, *, fallback: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_-]+", "_", value).strip("_")
    return safe or fallback


def build_nl2sql_artifact_paths(
    *,
    log_dir: Path,
    run_context: RunContext,
    input: Nl2SqlInput,
    resolved_thread_id: str,
) -> Nl2SqlArtifactPaths:
    raw_artifact_id = input.request_id or resolved_thread_id
    artifact_id = _safe_artifact_id(raw_artifact_id, fallback=run_context.run_id)
    artifact_dir = log_dir / "artifacts" / "nl2sql" / artifact_id
    return Nl2SqlArtifactPaths(
        artifact_dir=artifact_dir,
        input_path=artifact_dir / "input.json",
        prompt_payload_path=artifact_dir / "prompt_payload.json",
        final_prompt_path=artifact_dir / "final_prompt.txt",
        graph_updates_path=artifact_dir / "graph_updates.jsonl",
        output_path=artifact_dir / "output.json",
        manifest_path=artifact_dir / "manifest.json",
        token_usage_path=None,
    )


def normalize_graph_updates(
    graph_updates: list[dict[str, Any]],
) -> list[NormalizedGraphUpdate]:
    rows: list[NormalizedGraphUpdate] = []
    for chunk in graph_updates:
        for node, update in chunk.items():
            rows.append({"node": str(node), "update": dict(update or {})})
    return rows
```

Also export these names from `__all__`.

- [ ] **Step 4: Run artifact helper tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_artifacts.py -v
```

Expected:

```text
All artifact helper tests pass.
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/artifacts.py tests/unit/workflows/nl2sql/test_artifacts.py
git commit -m "feat: add nl2sql artifact boundaries"
```

---

## Task 3: Artifact File Writing

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/artifacts.py`
- Modify: `tests/unit/workflows/nl2sql/test_artifacts.py`

- [ ] **Step 1: Add failing tests for successful artifact writing**

Append to `tests/unit/workflows/nl2sql/test_artifacts.py`:

```python
from nl2sqlagent.workflows.nl2sql.artifacts import write_nl2sql_artifacts
from nl2sqlagent.workflows.nl2sql.output import Nl2SqlOutput


def test_write_nl2sql_artifacts_writes_expected_files(tmp_path) -> None:
    started_at = datetime(2026, 5, 9, 9, 0, 0)
    finished_at = datetime(2026, 5, 9, 9, 0, 1)
    final_state = {
        "prompt_payload": {
            "question": {"raw": "统计员工数量", "normalized": "统计员工数量"},
            "debug": {"prompt_version": "phase3.mock.v1"},
        },
        "final_prompt": "User Question:\n统计员工数量",
    }
    output = Nl2SqlOutput(
        status="success",
        message="NL2SQL workflow succeeded.",
        sql="SELECT 1 AS value",
        columns=["value"],
        rows=[{"value": 1}],
        metadata={
            "prompt_payload": final_state["prompt_payload"],
            "final_prompt": final_state["final_prompt"],
        },
    )

    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量", request_id="request-1"),
        resolved_thread_id="thread-phase4",
        final_state=final_state,
        output=output,
        graph_updates=[{"build_prompt": final_state}],
        started_at=started_at,
        finished_at=finished_at,
        artifact_required=True,
    )

    assert result.artifact_error is None
    assert result.paths is not None
    assert result.paths.input_path.exists()
    assert result.paths.prompt_payload_path.exists()
    assert result.paths.final_prompt_path.exists()
    assert result.paths.graph_updates_path.exists()
    assert result.paths.output_path.exists()
    assert result.paths.manifest_path.exists()
    assert result.paths.token_usage_path is None

    input_data = json.loads(result.paths.input_path.read_text(encoding="utf-8"))
    assert input_data["run_id"] == "run-phase4"
    assert input_data["run_date"] == "20260509"
    assert input_data["thread_id"] == "thread-phase4"
    assert input_data["request_id"] == "request-1"
    assert input_data["raw_question"] == "统计员工数量"
    assert input_data["options"] == {}

    assert json.loads(result.paths.prompt_payload_path.read_text(encoding="utf-8")) == final_state["prompt_payload"]
    assert result.paths.final_prompt_path.read_text(encoding="utf-8") == "User Question:\n统计员工数量"

    graph_update_lines = result.paths.graph_updates_path.read_text(encoding="utf-8").splitlines()
    assert len(graph_update_lines) == 1
    assert json.loads(graph_update_lines[0])["node"] == "build_prompt"

    output_data = json.loads(result.paths.output_path.read_text(encoding="utf-8"))
    assert output_data["status"] == "success"
    assert output_data["sql"] == "SELECT 1 AS value"
    assert output_data["metadata"]["artifact_manifest_path"] == str(result.paths.manifest_path)
    assert output_data["metadata"]["token_usage_path"] is None

    manifest = json.loads(result.paths.manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-phase4"
    assert manifest["thread_id"] == "thread-phase4"
    assert manifest["request_id"] == "request-1"
    assert manifest["artifact_id"] == "request-1"
    assert manifest["workflow"] == "nl2sql"
    assert manifest["write_mode"] == "overwrite"
    assert manifest["status"] == "success"
    assert manifest["artifact_error"] is None
    assert manifest["artifact_files"]["token_usage"] is None
    assert manifest["sizes"]["final_prompt_size_chars"] == len("User Question:\n统计员工数量")


def test_write_nl2sql_artifacts_skips_prompt_files_when_prompt_absent(tmp_path) -> None:
    output = Nl2SqlOutput(
        status="needs_clarification",
        message="Please provide a question.",
        metadata={},
    )

    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="   "),
        resolved_thread_id="thread-blank",
        final_state={"status": "needs_clarification"},
        output=output,
        graph_updates=[{"normalize_question": {"status": "needs_clarification"}}],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
        artifact_required=True,
    )

    assert result.paths is not None
    assert result.metadata["prompt_payload_path"] is None
    assert result.metadata["final_prompt_path"] is None
    assert not result.paths.prompt_payload_path.exists()
    assert not result.paths.final_prompt_path.exists()

    manifest = json.loads(result.paths.manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifact_files"]["prompt_payload"] is None
    assert manifest["artifact_files"]["final_prompt"] is None


def test_write_nl2sql_artifacts_without_request_id_uses_thread_artifact_id_and_keeps_thread_in_manifest(tmp_path) -> None:
    output = Nl2SqlOutput(
        status="success",
        message="NL2SQL workflow succeeded.",
        sql="SELECT 1 AS value",
        columns=["value"],
        rows=[{"value": 1}],
        metadata={},
    )

    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量"),
        resolved_thread_id="thread:phase4",
        final_state={"final_prompt": "User Question:\n统计员工数量"},
        output=output,
        graph_updates=[],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
        artifact_required=True,
    )

    assert result.paths is not None
    manifest = json.loads(result.paths.manifest_path.read_text(encoding="utf-8"))
    assert manifest["request_id"] is None
    assert manifest["thread_id"] == "thread:phase4"
    assert manifest["artifact_id"] == "thread_phase4"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_artifacts.py -v
```

Expected:

```text
FAIL because write_nl2sql_artifacts does not exist.
```

- [ ] **Step 3: Implement JSON-safe writing helpers**

In `artifacts.py`, add helpers:

```python
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _write_json(path: Path, data: Any, *, indent: int | None = 2) -> None:
    path.write_text(
        json.dumps(_json_safe(data), ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(_json_safe(row), ensure_ascii=False, separators=(",", ":")) for row in rows),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Implement write_nl2sql_artifacts**

In `artifacts.py`, implement:

```python
def write_nl2sql_artifacts(
    *,
    log_dir: Path,
    run_context: RunContext,
    input: Nl2SqlInput,
    resolved_thread_id: str,
    final_state: dict[str, Any],
    output: Nl2SqlOutput,
    graph_updates: list[dict[str, Any]],
    started_at: datetime,
    finished_at: datetime,
    artifact_required: bool = False,
) -> Nl2SqlArtifactResult:
    ...
```

Implementation requirements:

```text
1. Build paths with build_nl2sql_artifact_paths(...).
2. Create paths.artifact_dir with parents=True, exist_ok=True.
3. Always write input.json.
4. Write prompt_payload.json only when final_state has a non-empty prompt_payload.
5. Write final_prompt.txt only when final_state has a non-empty final_prompt.
6. Always write graph_updates.jsonl using normalize_graph_updates(...).
7. Merge output.metadata with artifact metadata before writing output.json.
8. Write manifest.json last.
9. token_usage_path and manifest.artifact_files.token_usage stay null.
10. If artifact_required=True, re-raise write failures.
11. If artifact_required=False, return Nl2SqlArtifactResult(paths=paths or None, metadata=metadata, artifact_error=str(exc)).
```

`input.json` fields:

```text
run_id, run_date, thread_id, request_id, user_id, database_key, raw_question, options
```

`metadata` fields:

```text
artifact_manifest_path
input_path
prompt_payload_path
final_prompt_path
graph_updates_path
output_path
token_usage_path
artifact_error
```

`manifest.json` fields:

```text
run_id, run_date, thread_id, request_id, artifact_id, workflow, write_mode,
status, started_at, finished_at, duration_ms, artifact_dir, artifact_files,
sizes, artifact_error
```

- [ ] **Step 5: Run artifact tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_artifacts.py -v
```

Expected:

```text
All artifact tests pass.
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/artifacts.py tests/unit/workflows/nl2sql/test_artifacts.py
git commit -m "feat: write nl2sql run artifacts"
```

---

## Task 4: Artifact Failure Behavior

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/artifacts.py`
- Modify: `tests/unit/workflows/nl2sql/test_artifacts.py`

- [ ] **Step 1: Add failing tests for failure policy**

Append:

```python
def test_write_nl2sql_artifacts_failure_does_not_raise_by_default(tmp_path) -> None:
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("block", encoding="utf-8")

    result = write_nl2sql_artifacts(
        log_dir=blocking_file,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量"),
        resolved_thread_id="thread-phase4",
        final_state={"final_prompt": "prompt"},
        output=Nl2SqlOutput(status="success", metadata={}),
        graph_updates=[],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
    )

    assert result.artifact_error is not None
    assert result.metadata["artifact_error"] is not None
    assert result.metadata["artifact_manifest_path"] is None


def test_write_nl2sql_artifacts_required_mode_reraises_failure(tmp_path) -> None:
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("block", encoding="utf-8")

    try:
        write_nl2sql_artifacts(
            log_dir=blocking_file,
            run_context=_run_context(),
            input=Nl2SqlInput(question="统计员工数量"),
            resolved_thread_id="thread-phase4",
            final_state={"final_prompt": "prompt"},
            output=Nl2SqlOutput(status="success", metadata={}),
            graph_updates=[],
            started_at=datetime(2026, 5, 9, 9, 0, 0),
            finished_at=datetime(2026, 5, 9, 9, 0, 1),
            artifact_required=True,
        )
    except OSError:
        pass
    else:
        raise AssertionError("Expected artifact_required=True to re-raise write failure")
```

- [ ] **Step 2: Run tests and verify they fail if failure policy is incomplete**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_artifacts.py -v
```

Expected:

```text
Failure-policy tests pass only after write_nl2sql_artifacts catches non-required failures and reraises required failures.
```

- [ ] **Step 3: Fix failure policy if needed**

Keep the error metadata JSON-safe:

```python
def _empty_error_metadata(error: str) -> Nl2SqlArtifactMetadata:
    return {
        "artifact_manifest_path": None,
        "input_path": None,
        "prompt_payload_path": None,
        "final_prompt_path": None,
        "graph_updates_path": None,
        "output_path": None,
        "token_usage_path": None,
        "artifact_error": error,
    }
```

If a failure happens after some paths are known, it is acceptable to return available path strings plus `artifact_error`.

- [ ] **Step 4: Run artifact tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_artifacts.py -v
```

Expected:

```text
All artifact tests pass.
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/artifacts.py tests/unit/workflows/nl2sql/test_artifacts.py
git commit -m "test: cover nl2sql artifact failure policy"
```

---

## Task 5: Wire Artifacts Into Nl2SqlWorkflow

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/workflow.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/__init__.py` only if public exports need updating
- Modify: `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Add failing integration tests for artifact output**

In `tests/integration/test_nl2sql_workflow.py`, update `_runtime()` only if needed or add a new helper:

```python
def _workflow_with_log_dir(tmp_path):
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
        log_dir=tmp_path / "logs" / run_context.run_date / run_context.run_id,
    )
    return workflow
```

If `Nl2SqlWorkflow` requires a logger parameter, pass a `logging.getLogger("test-nl2sql")` logger with no special handler.

Add tests:

```python
def test_nl2sql_workflow_run_writes_artifacts(tmp_path) -> None:
    workflow = _workflow_with_log_dir(tmp_path)

    output = workflow.run(
        Nl2SqlInput(question="统计员工数量", request_id="request-1"),
        thread_id="thread-nl2sql-artifact",
    )

    assert output.status == "success"
    manifest_path = output.metadata["artifact_manifest_path"]
    assert isinstance(manifest_path, str)

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-nl2sql"
    assert manifest["thread_id"] == "thread-nl2sql-artifact"
    assert manifest["request_id"] == "request-1"
    assert manifest["artifact_id"] == "request-1"
    assert manifest["artifact_files"]["token_usage"] is None

    final_prompt_path = Path(output.metadata["final_prompt_path"])
    prompt_payload_path = Path(output.metadata["prompt_payload_path"])
    graph_updates_path = Path(output.metadata["graph_updates_path"])
    output_path = Path(output.metadata["output_path"])

    assert "User Question:\n统计员工数量" in final_prompt_path.read_text(encoding="utf-8")
    assert json.loads(prompt_payload_path.read_text(encoding="utf-8"))["question"]["normalized"] == "统计员工数量"
    assert any(
        json.loads(line)["node"] == "build_prompt"
        for line in graph_updates_path.read_text(encoding="utf-8").splitlines()
    )
    output_json = json.loads(output_path.read_text(encoding="utf-8"))
    assert output_json["metadata"]["artifact_manifest_path"] == manifest_path
    assert output_json["metadata"]["token_usage_path"] is None


def test_nl2sql_workflow_clarification_writes_artifact_without_prompt_files(tmp_path) -> None:
    workflow = _workflow_with_log_dir(tmp_path)

    output = workflow.run(
        Nl2SqlInput(question="   "),
        thread_id="thread-nl2sql-blank-artifact",
    )

    assert output.status == "needs_clarification"
    assert output.metadata["prompt_payload_path"] is None
    assert output.metadata["final_prompt_path"] is None
    assert output.metadata["graph_updates_path"] is not None
    assert output.metadata["artifact_manifest_path"] is not None
```

Make sure imports include:

```python
import json
import logging
from pathlib import Path
```

- [ ] **Step 2: Run integration tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py -v
```

Expected:

```text
FAIL because Nl2SqlWorkflow does not yet accept log_dir/logger or write artifacts.
```

- [ ] **Step 3: Update Nl2SqlWorkflow dataclass**

Modify `src/nl2sqlagent/workflows/nl2sql/workflow.py`.

Add fields:

```python
from logging import Logger, getLogger
from pathlib import Path


log_dir: Path | None = None
logger: Logger | None = None
```

Use `None` defaults only to keep existing tests easy to migrate. In `run(...)`, require an effective log directory:

```python
effective_log_dir = self.log_dir or Path("workspace") / "logs" / self.run_context.run_date / self.run_context.run_id
effective_logger = self.logger or getLogger(__name__)
```

Do not write artifacts in `stream(...)`; Phase 4 artifact writing belongs to `run(...)`.

- [ ] **Step 4: Update Nl2SqlWorkflow.run**

Replace `GraphRuntime.invoke(...)` usage in `run(...)` with:

```python
started_at = datetime.now(timezone.utc)
resolved_thread_id = self.graph_runtime.resolve_thread_id(
    run_context=self.run_context,
    thread_id=thread_id,
)
effective_logger.info(
    "NL2SQL workflow started run_id=%s thread_id=%s request_id=%s",
    self.run_context.run_id,
    resolved_thread_id,
    input.request_id,
)
graph_result = self.graph_runtime.invoke_with_updates(...)
finished_at = datetime.now(timezone.utc)
output = build_nl2sql_output(graph_result.final_state)
artifact_result = write_nl2sql_artifacts(
    log_dir=effective_log_dir,
    run_context=self.run_context,
    input=input,
    resolved_thread_id=graph_result.thread_id,
    final_state=graph_result.final_state,
    output=output,
    graph_updates=graph_result.updates,
    started_at=started_at,
    finished_at=finished_at,
)
return replace(output, metadata={**output.metadata, **artifact_result.metadata})
```

Use `dataclasses.replace` because `Nl2SqlOutput` is frozen.

Use `resolved_thread_id` for the started log and `graph_result.thread_id` for finished/error logs. Add a defensive assertion or test expectation that they are equal.

Finished app-log summary:

```python
effective_logger.info(
    "NL2SQL workflow finished run_id=%s thread_id=%s status=%s duration_ms=%s artifact_manifest_path=%s",
    self.run_context.run_id,
    graph_result.thread_id,
    output.status,
    ...,
    artifact_result.metadata.get("artifact_manifest_path"),
)
```

If artifact writer returns `artifact_error`, log:

```python
effective_logger.error(
    "NL2SQL artifact write failed run_id=%s thread_id=%s error=%s",
    self.run_context.run_id,
    graph_result.thread_id,
    artifact_result.artifact_error,
)
```

Important: do not log full prompt payload, final prompt, rows, or graph updates.

- [ ] **Step 5: Run integration tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py -v
```

Expected:

```text
All NL2SQL integration tests pass.
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/workflow.py src/nl2sqlagent/workflows/nl2sql/__init__.py tests/integration/test_nl2sql_workflow.py
git commit -m "feat: write nl2sql artifacts from workflow"
```

---

## Task 6: Inject Logging Runtime From Container

**Files:**

- Modify: `src/nl2sqlagent/bootstrap/container.py`
- Modify: `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Add failing build_app assertion for artifact files**

In `test_build_app_exposes_nl2sql_workflow`, after `output = app.nl2sql_workflow.run(...)`, add:

```python
assert output.metadata["artifact_manifest_path"] is not None
assert Path(output.metadata["artifact_manifest_path"]).exists()
assert str(app.logging.log_dir) in output.metadata["artifact_manifest_path"]
```

Ensure `Path` is imported.

- [ ] **Step 2: Run build_app integration test and verify it fails if container is not wired**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py::test_build_app_exposes_nl2sql_workflow -v
```

Expected:

```text
FAIL if Nl2SqlWorkflow is not receiving logging_runtime.log_dir.
```

- [ ] **Step 3: Pass log_dir and logger into Nl2SqlWorkflow**

Modify `src/nl2sqlagent/bootstrap/container.py`:

```python
nl2sql_workflow = Nl2SqlWorkflow(
    graph=nl2sql_graph,
    graph_runtime=graph_runtime,
    run_context=run_context,
    log_dir=logging_runtime.log_dir,
    logger=logging_runtime.logger,
)
```

- [ ] **Step 4: Run build_app integration test**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/integration/test_nl2sql_workflow.py::test_build_app_exposes_nl2sql_workflow -v
```

Expected:

```text
PASS.
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/bootstrap/container.py tests/integration/test_nl2sql_workflow.py
git commit -m "feat: inject nl2sql artifact logging runtime"
```

---

## Task 7: Boundary Regression Tests

**Files:**

- Modify: `tests/unit/workflows/nl2sql/test_artifacts.py`
- Modify: `tests/unit/workflows/runtime/test_graph_runtime.py`
- Modify only if needed: `tests/unit/workflows/nl2sql/test_contracts.py`

- [ ] **Step 1: Add tests that protect artifact metadata shape**

In `tests/unit/workflows/nl2sql/test_artifacts.py`, add:

```python
def test_artifact_metadata_contains_only_json_safe_values(tmp_path) -> None:
    output = Nl2SqlOutput(status="success", metadata={})

    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量"),
        resolved_thread_id="thread-phase4",
        final_state={"final_prompt": "prompt"},
        output=output,
        graph_updates=[],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
        artifact_required=True,
    )

    json.dumps(result.metadata, ensure_ascii=False)
    assert all(not hasattr(value, "exists") for value in result.metadata.values())
```

- [ ] **Step 2: Add static boundary checks**

Create or append tests in `tests/unit/workflows/nl2sql/test_contracts.py` if the file already holds similar contract tests:

```python
from pathlib import Path


def test_nl2sql_nodes_do_not_write_files_or_log_artifacts() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/nodes.py").read_text(encoding="utf-8")

    forbidden = [
        "open(",
        "write_text(",
        "json.dump",
        "json.dumps",
        "logger.",
        "artifact",
    ]
    assert all(token not in source for token in forbidden)


def test_graph_runtime_does_not_reference_nl2sql_business_fields() -> None:
    source = Path("src/nl2sqlagent/workflows/runtime/graph_runtime.py").read_text(encoding="utf-8")

    forbidden = [
        "prompt_payload",
        "final_prompt",
        "generated_sql",
        "checked_sql",
        "result_rows",
        "Nl2Sql",
    ]
    assert all(token not in source for token in forbidden)
```

If `test_contracts.py` already uses a different style, keep that local style but preserve these assertions.

- [ ] **Step 3: Run boundary tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -m pytest tests/unit/workflows/nl2sql/test_artifacts.py tests/unit/workflows/nl2sql/test_contracts.py tests/unit/workflows/runtime/test_graph_runtime.py -v
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 4: Commit**

```powershell
git add tests/unit/workflows/nl2sql/test_artifacts.py tests/unit/workflows/nl2sql/test_contracts.py tests/unit/workflows/runtime/test_graph_runtime.py
git commit -m "test: protect nl2sql artifact boundaries"
```

---

## Task 8: Final Verification

**Files:**

- All Phase 4 implementation files

- [ ] **Step 1: Run NL2SQL unit and integration tests**

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

- [ ] **Step 4: Smoke run and inspect artifact paths**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $python -c "from pathlib import Path; import json; from nl2sqlagent.bootstrap import build_app; from nl2sqlagent.workflows.nl2sql import Nl2SqlInput; app = build_app(run_id='run-phase4-smoke'); output = app.nl2sql_workflow.run(Nl2SqlInput(question='统计员工数量', request_id='request-phase4-smoke'), thread_id='thread-phase4-smoke'); print(output.status); print(output.sql); print(output.metadata['artifact_manifest_path']); manifest = json.loads(Path(output.metadata['artifact_manifest_path']).read_text(encoding='utf-8')); print(manifest['artifact_id']); print(manifest['artifact_files']['token_usage']); print(Path(output.metadata['final_prompt_path']).exists()); print(Path(output.metadata['graph_updates_path']).exists())"
```

Expected:

```text
success
SELECT 1 AS value
<path ending with manifest.json>
request-phase4-smoke
None
True
True
```

- [ ] **Step 5: Confirm app.log does not contain full prompt payload**

Run:

```powershell
.\.ai\local\tools\rg.exe "prompt_payload|User Question:|Schema Context:|result_rows" workspace\logs --glob app.log
```

Expected:

```text
No matches in app.log for full prompt payload/final prompt/rows.
```

If the command finds app.log lines containing full prompt content, remove that logging.

- [ ] **Step 6: Confirm no forbidden architecture was added**

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

- [ ] **Step 7: Confirm nodes and GraphRuntime boundaries**

Run:

```powershell
.\.ai\local\tools\rg.exe "open\(|write_text|json\.dump|json\.dumps|logger\.|artifact" src\nl2sqlagent\workflows\nl2sql\nodes.py
.\.ai\local\tools\rg.exe "prompt_payload|final_prompt|generated_sql|checked_sql|result_rows|Nl2Sql" src\nl2sqlagent\workflows\runtime\graph_runtime.py
```

Expected:

```text
No matches.
```

- [ ] **Step 8: Confirm token usage files were not created**

Run:

```powershell
.\.ai\local\tools\rg.exe --files workspace\logs | .\.ai\local\tools\rg.exe "token_usage"
```

Expected:

```text
No token_usage.json or token_usage.jsonl files.
```

- [ ] **Step 9: Diff check**

Run:

```powershell
git diff --check
```

Expected:

```text
No trailing whitespace errors.
```

- [ ] **Step 10: Final git status**

Run:

```powershell
git -c core.quotepath=false status --short
```

Expected:

```text
Only intentional Phase 4 implementation files are modified/untracked.
Unrelated docs/temp changes remain untouched.
Generated workspace/logs files should not be staged.
```

- [ ] **Step 11: Commit final fixes if needed**

If final verification required small fixes:

```powershell
git add <fixed Phase 4 implementation files only>
git commit -m "fix: stabilize nl2sql run artifacts"
```

Do not stage `workspace/logs`, `.ai/local`, or unrelated `docs/temp` files.

---

## Final Report Template

When complete, report:

```text
Implemented Phase 4 NL2SQL run artifacts.

What changed:
- Added GraphRunResult and GraphRuntime.invoke_with_updates using one graph stream execution plus get_state(config).
- Added NL2SQL artifact writer for input.json, prompt_payload.json, final_prompt.txt, graph_updates.jsonl, output.json, and manifest.json.
- Added structured artifact boundaries: Nl2SqlArtifactPaths, Nl2SqlArtifactResult, Nl2SqlArtifactMetadata, NormalizedGraphUpdate.
- Wired Nl2SqlWorkflow.run to write artifacts and merge artifact path metadata.
- Injected LoggingRuntime log_dir/logger from build_app.
- Kept nodes pure and kept GraphRuntime NL2SQL-agnostic.
- Kept token usage as null metadata only; no token_usage file is created.

Verification:
- pytest tests/unit/workflows/nl2sql tests/unit/workflows/runtime tests/integration/test_nl2sql_workflow.py -v: passed
- pytest -v: passed
- compileall src/nl2sqlagent: passed
- smoke run created manifest/final_prompt/graph_updates/output artifacts: passed
- app.log full prompt/rows check: passed
- forbidden architecture paths not created: confirmed
- no token_usage files created: confirmed

Remaining:
- Real LLM intentionally deferred.
- Real token usage intentionally deferred.
- Real DB/schema grounding intentionally deferred.
- Redaction policy must be revisited before real sensitive data enters prompt/output artifacts.
```
