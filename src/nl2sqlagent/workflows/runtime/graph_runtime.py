from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.runtime.thread_id import resolve_thread_id


@dataclass(frozen=True)
class GraphRunResult:
    final_state: dict[str, Any]
    updates: list[dict[str, Any]]
    thread_id: str


@dataclass(frozen=True)
class GraphRuntime:
    """Runs compiled LangGraph graphs with project-standard config."""

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

    def _config(
        self,
        *,
        run_context: RunContext,
        thread_id: str | None,
    ) -> dict[str, Any]:
        return {
            "configurable": {
                "thread_id": self.resolve_thread_id(
                    run_context=run_context,
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


__all__ = ["GraphRunResult", "GraphRuntime"]
