from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.knowledge_pipeline import (
    build_initial_processed_question,
    build_knowledge_retrieval_result,
    build_sample_processed_database_knowledge,
    build_schema_linking_result,
    build_sql_generation_context,
)
from nl2sqlagent.workflows.nl2sql.prompt_builder import render_final_prompt
from nl2sqlagent.workflows.nl2sql.prompt_payload import (
    build_prompt_payload_from_sql_generation_context,
)
from nl2sqlagent.workflows.nl2sql.sql_generator import SqlGenerator
from nl2sqlagent.workflows.nl2sql.state import Nl2SqlGraphState


def normalize_question_node(state: Nl2SqlGraphState) -> dict:
    question = (state.get("raw_question") or "").strip()
    if not question:
        return {
            "normalized_question": "",
            "clarification_message": "Please provide a question.",
            "status": "needs_clarification",
        }
    return {
        "normalized_question": question,
        "status": "running",
    }


def build_prompt_node(state: Nl2SqlGraphState) -> dict:
    raw_question = state.get("raw_question") or state.get("normalized_question") or ""
    normalized_question = state.get("normalized_question") or raw_question.strip()
    processed_question = state.get("processed_question") or build_initial_processed_question(
        normalized_question
    )
    processed_database_knowledge = state.get(
        "processed_database_knowledge"
    ) or build_sample_processed_database_knowledge()
    knowledge_retrieval_result = build_knowledge_retrieval_result(
        processed_question, processed_database_knowledge
    )
    schema_linking_result = build_schema_linking_result(
        processed_question,
        processed_database_knowledge,
        knowledge_retrieval_result,
    )
    sql_generation_context = build_sql_generation_context(
        processed_question,
        processed_database_knowledge,
        schema_linking_result,
    )
    prompt_payload = build_prompt_payload_from_sql_generation_context(
        sql_generation_context
    )
    return {
        "processed_question": processed_question,
        "processed_database_knowledge": processed_database_knowledge,
        "knowledge_retrieval_result": knowledge_retrieval_result,
        "schema_linking_result": schema_linking_result,
        "sql_generation_context": sql_generation_context,
        "prompt_payload": prompt_payload,
        "final_prompt": render_final_prompt(prompt_payload),
    }


def generate_sql_node(
    state: Nl2SqlGraphState,
    *,
    sql_generator: SqlGenerator,
) -> dict:
    final_prompt = state.get("final_prompt") or ""
    if not final_prompt.strip():
        return {
            "generate_error": "final_prompt is required before SQL generation",
            "status": "failed",
        }
    try:
        result = sql_generator.generate(final_prompt)
    except Exception as exc:
        return {
            "generate_error": str(exc),
            "status": "failed",
        }
    return {
        "generated_sql": result.generated_sql,
        "llm_result": {
            "model_name": result.model_name,
            "raw_text": result.raw_text,
        },
        "generate_error": None,
    }


def check_sql_node(state: Nl2SqlGraphState) -> dict:
    runtime_options = state.get("runtime_options") or {}
    if runtime_options.get("force_check_error") is True:
        return {
            "check_error": "mock check error",
            "status": "failed",
        }
    return {
        "checked_sql": state.get("generated_sql") or "",
        "check_error": None,
    }


def execute_sql_node(state: Nl2SqlGraphState) -> dict:
    runtime_options = state.get("runtime_options") or {}
    if runtime_options.get("force_execute_error") is True:
        return {
            "execute_error": "mock execute error",
            "status": "failed",
        }
    return {
        "result_columns": ["value"],
        "result_rows": [{"value": 1}],
        "execute_error": None,
    }


def clarification_response_node(state: Nl2SqlGraphState) -> dict:
    message = state.get("clarification_message") or "Please provide a question."
    return {
        "status": "needs_clarification",
        "message": message,
    }


def failed_response_node(state: Nl2SqlGraphState) -> dict:
    message = (
        state.get("generate_error")
        or state.get("check_error")
        or state.get("execute_error")
        or state.get("message")
        or "NL2SQL workflow failed."
    )
    return {
        "status": "failed",
        "message": message,
    }


def success_response_node(state: Nl2SqlGraphState) -> dict:
    return {
        "status": "success",
        "message": "NL2SQL workflow succeeded.",
    }


__all__ = [
    "build_prompt_node",
    "check_sql_node",
    "clarification_response_node",
    "execute_sql_node",
    "failed_response_node",
    "generate_sql_node",
    "normalize_question_node",
    "success_response_node",
]
