from __future__ import annotations

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
    question = state.get("normalized_question") or ""
    prompt_payload = {
        "question": question,
        "schema": "mock_schema",
        "semantic_rules": ["mock_semantic_rule"],
        "instruction": "Generate a read-only SQL query.",
    }
    final_prompt = "\n".join(
        [
            "You are an NL2SQL assistant.",
            f"Question: {prompt_payload['question']}",
            f"Schema: {prompt_payload['schema']}",
            "Semantic Rules:",
            "- mock_semantic_rule",
            "Instruction: Generate a read-only SQL query.",
        ]
    )
    return {
        "prompt_payload": prompt_payload,
        "final_prompt": final_prompt,
    }


def generate_sql_node(state: Nl2SqlGraphState) -> dict:
    return {"generated_sql": "SELECT 1 AS value"}


def check_sql_node(state: Nl2SqlGraphState) -> dict:
    options = state.get("options") or {}
    if options.get("force_check_error") is True:
        return {
            "check_error": "mock check error",
            "status": "failed",
        }
    return {
        "checked_sql": state.get("generated_sql") or "",
        "check_error": None,
    }


def execute_sql_node(state: Nl2SqlGraphState) -> dict:
    options = state.get("options") or {}
    if options.get("force_execute_error") is True:
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
        state.get("check_error")
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
