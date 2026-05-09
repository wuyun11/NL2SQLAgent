from __future__ import annotations

from typing import TypedDict


class PromptTask(TypedDict):
    type: str
    goal: str


class PromptQuestion(TypedDict):
    raw: str
    normalized: str


class PromptColumn(TypedDict):
    name: str
    type: str
    description: str


class PromptTable(TypedDict):
    name: str
    description: str
    columns: list[PromptColumn]


class PromptSchemaContext(TypedDict):
    dialect: str
    tables: list[PromptTable]
    relationships: list[dict[str, object]]


class PromptSemanticTerm(TypedDict):
    name: str
    description: str


class PromptSemanticContext(TypedDict):
    business_terms: list[PromptSemanticTerm]
    rules: list[str]
    assumptions: list[str]


class PromptSqlPolicy(TypedDict):
    readonly_only: bool
    allow_select_star: bool
    require_limit: bool
    default_limit: int


class PromptOutputContract(TypedDict):
    format: str
    requirements: list[str]


class PromptDebug(TypedDict):
    prompt_version: str
    source: str


class Nl2SqlPromptPayload(TypedDict):
    task: PromptTask
    question: PromptQuestion
    schema_context: PromptSchemaContext
    semantic_context: PromptSemanticContext
    sql_policy: PromptSqlPolicy
    output_contract: PromptOutputContract
    debug: PromptDebug


def build_mock_prompt_payload(
    *,
    raw_question: str,
    normalized_question: str,
) -> Nl2SqlPromptPayload:
    return {
        "task": {
            "type": "nl2sql",
            "goal": "Generate a read-only SQL query for the user question.",
        },
        "question": {
            "raw": raw_question,
            "normalized": normalized_question,
        },
        "schema_context": {
            "dialect": "sqlite",
            "tables": [
                {
                    "name": "employee",
                    "description": "mock employee table",
                    "columns": [
                        {
                            "name": "id",
                            "type": "INTEGER",
                            "description": "employee id",
                        },
                        {
                            "name": "name",
                            "type": "TEXT",
                            "description": "employee name",
                        },
                    ],
                }
            ],
            "relationships": [],
        },
        "semantic_context": {
            "business_terms": [
                {
                    "name": "员工",
                    "description": "mock business term for employee",
                }
            ],
            "rules": [
                "Use only active records when such flag is available.",
            ],
            "assumptions": [
                "No extra business filter is applied in Phase 3 mock prompt.",
            ],
        },
        "sql_policy": {
            "readonly_only": True,
            "allow_select_star": False,
            "require_limit": True,
            "default_limit": 100,
        },
        "output_contract": {
            "format": "sql_only",
            "requirements": [
                "Return only one SQL statement.",
                "Do not include markdown fences.",
                "Do not explain the SQL.",
            ],
        },
        "debug": {
            "prompt_version": "phase3.mock.v1",
            "source": "mock_prompt_payload_builder",
        },
    }


__all__ = [
    "Nl2SqlPromptPayload",
    "PromptColumn",
    "PromptDebug",
    "PromptOutputContract",
    "PromptQuestion",
    "PromptSchemaContext",
    "PromptSemanticContext",
    "PromptSemanticTerm",
    "PromptSqlPolicy",
    "PromptTable",
    "PromptTask",
    "build_mock_prompt_payload",
]
