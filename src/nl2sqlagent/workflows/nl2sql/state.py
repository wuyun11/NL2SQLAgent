from __future__ import annotations

from typing import Any, Literal, TypedDict

from nl2sqlagent.workflows.nl2sql.knowledge_contracts import (
    KnowledgeRetrievalResult,
    ProcessedDatabaseKnowledge,
    ProcessedQuestion,
    SchemaLinkingResult,
    SqlGenerationContext,
)
from nl2sqlagent.workflows.nl2sql.prompt_payload import Nl2SqlPromptPayload
from nl2sqlagent.workflows.nl2sql.runtime_options import Nl2SqlRuntimeOptions


class Nl2SqlGraphState(TypedDict, total=False):
    request_id: str | None
    user_id: str | None
    database_key: str | None

    raw_question: str
    normalized_question: str
    clarification_message: str | None

    options: dict[str, Any]
    runtime_options: Nl2SqlRuntimeOptions
    processed_question: ProcessedQuestion
    processed_database_knowledge: ProcessedDatabaseKnowledge
    knowledge_retrieval_result: KnowledgeRetrievalResult
    schema_linking_result: SchemaLinkingResult
    sql_generation_context: SqlGenerationContext
    prompt_payload: Nl2SqlPromptPayload
    final_prompt: str | None

    llm_result: dict[str, object]
    generate_error: str | None

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
