from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from logging import Logger, getLogger
from pathlib import Path
from typing import Any

from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql.artifacts import write_nl2sql_artifacts
from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput
from nl2sqlagent.workflows.nl2sql.output import Nl2SqlOutput
from nl2sqlagent.workflows.nl2sql.response_builder import build_nl2sql_output
from nl2sqlagent.workflows.nl2sql.runtime_options import normalize_runtime_options
from nl2sqlagent.workflows.runtime import GraphRuntime


@dataclass(frozen=True)
class Nl2SqlWorkflow:
    graph: object
    graph_runtime: GraphRuntime
    run_context: RunContext
    log_dir: Path | None = None
    logger: Logger | None = None

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

    def run(
        self,
        input: Nl2SqlInput,
        *,
        thread_id: str | None = None,
    ) -> Nl2SqlOutput:
        effective_log_dir = self.log_dir or (
            Path("workspace") / "logs" / self.run_context.run_date / self.run_context.run_id
        )
        effective_logger = self.logger or getLogger(__name__)
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
        graph_result = self.graph_runtime.invoke_with_updates(
            graph=self.graph,
            input=self._graph_input(input),
            run_context=self.run_context,
            thread_id=thread_id,
        )
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
        if artifact_result.artifact_error:
            effective_logger.error(
                "NL2SQL artifact write failed run_id=%s thread_id=%s error=%s",
                self.run_context.run_id,
                graph_result.thread_id,
                artifact_result.artifact_error,
            )
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        artifact_manifest_path = (
            str(artifact_result.paths.manifest_path)
            if artifact_result.paths is not None
            else None
        )
        effective_logger.info(
            "NL2SQL workflow finished run_id=%s thread_id=%s status=%s duration_ms=%s artifact_manifest=%s",
            self.run_context.run_id,
            graph_result.thread_id,
            output.status,
            duration_ms,
            artifact_manifest_path,
        )
        return replace(output, metadata={**output.metadata, **artifact_result.metadata})

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
