from __future__ import annotations

from typing import Any


def build_mock_prompt_payload(
    *,
    raw_question: str,
    normalized_question: str,
) -> dict[str, Any]:
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


__all__ = ["build_mock_prompt_payload"]
