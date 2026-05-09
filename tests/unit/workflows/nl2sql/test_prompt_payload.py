from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.prompt_payload import build_mock_prompt_payload


def test_build_mock_prompt_payload_has_phase3_top_level_fields() -> None:
    payload = build_mock_prompt_payload(
        raw_question="  统计员工数量  ",
        normalized_question="统计员工数量",
    )

    assert list(payload) == [
        "task",
        "question",
        "schema_context",
        "semantic_context",
        "sql_policy",
        "output_contract",
        "debug",
    ]


def test_build_mock_prompt_payload_preserves_raw_and_normalized_question() -> None:
    payload = build_mock_prompt_payload(
        raw_question="  统计员工数量  ",
        normalized_question="统计员工数量",
    )

    assert payload["question"] == {
        "raw": "  统计员工数量  ",
        "normalized": "统计员工数量",
    }


def test_build_mock_prompt_payload_defines_allowed_schema_scope() -> None:
    payload = build_mock_prompt_payload(
        raw_question="统计员工数量",
        normalized_question="统计员工数量",
    )

    schema_context = payload["schema_context"]
    assert schema_context["dialect"] == "sqlite"
    assert schema_context["relationships"] == []
    assert schema_context["tables"] == [
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
    ]


def test_build_mock_prompt_payload_separates_semantic_rules_from_sql_policy() -> None:
    payload = build_mock_prompt_payload(
        raw_question="统计员工数量",
        normalized_question="统计员工数量",
    )

    assert payload["semantic_context"] == {
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
    }
    assert payload["sql_policy"] == {
        "readonly_only": True,
        "allow_select_star": False,
        "require_limit": True,
        "default_limit": 100,
    }


def test_build_mock_prompt_payload_defines_output_contract_and_debug() -> None:
    payload = build_mock_prompt_payload(
        raw_question="统计员工数量",
        normalized_question="统计员工数量",
    )

    assert payload["output_contract"] == {
        "format": "sql_only",
        "requirements": [
            "Return only one SQL statement.",
            "Do not include markdown fences.",
            "Do not explain the SQL.",
        ],
    }
    assert payload["debug"] == {
        "prompt_version": "phase3.mock.v1",
        "source": "mock_prompt_payload_builder",
    }
