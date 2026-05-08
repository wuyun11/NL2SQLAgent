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
