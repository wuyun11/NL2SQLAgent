from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

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
