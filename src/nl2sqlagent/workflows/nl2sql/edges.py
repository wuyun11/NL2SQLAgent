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


def route_after_generate(
    state: Nl2SqlGraphState,
) -> Literal["failed_response", "check_sql"]:
    if state.get("generate_error"):
        return "failed_response"
    return "check_sql"


__all__ = [
    "route_after_check",
    "route_after_execute",
    "route_after_generate",
    "route_after_normalize",
]
