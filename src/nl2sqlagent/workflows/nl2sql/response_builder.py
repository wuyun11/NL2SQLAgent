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


def build_prompt_debug_metadata(state: Nl2SqlGraphState) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in (
        "prompt_payload",
        "final_prompt",
        "processed_question",
        "processed_database_knowledge",
        "knowledge_retrieval_result",
        "schema_linking_result",
        "sql_generation_context",
    ):
        if key in state:
            metadata[key] = state.get(key)
    return metadata


def build_nl2sql_output(state: Nl2SqlGraphState) -> Nl2SqlOutput:
    status = _status(state)
    return Nl2SqlOutput(
        status=status,
        message=_message(state, status),
        sql=state.get("checked_sql") or state.get("generated_sql"),
        columns=list(state.get("result_columns") or []),
        rows=list(state.get("result_rows") or []),
        metadata=build_prompt_debug_metadata(state),
    )


__all__ = ["build_nl2sql_output", "build_prompt_debug_metadata"]
