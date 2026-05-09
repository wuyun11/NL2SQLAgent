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
