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
