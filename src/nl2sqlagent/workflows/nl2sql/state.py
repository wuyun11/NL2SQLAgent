from __future__ import annotations

from typing import Any, Literal, TypedDict


class Nl2SqlGraphState(TypedDict, total=False):
    request_id: str | None
    user_id: str | None
    database_key: str | None

    raw_question: str
    normalized_question: str
    clarification_message: str | None

    options: dict[str, Any]
    prompt_payload: dict[str, Any]
    final_prompt: str | None

    generated_sql: str | None
    checked_sql: str | None
    check_error: str | None
    execute_error: str | None

    result_columns: list[str]
    result_rows: list[dict[str, Any]]

    status: Literal[
        "running",
        "success",
        "needs_clarification",
        "failed",
        "rejected",
    ]
    message: str | None


__all__ = ["Nl2SqlGraphState"]
