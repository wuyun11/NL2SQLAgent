from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.knowledge_pipeline import (
    build_initial_processed_question,
    build_knowledge_retrieval_result,
    build_sample_processed_database_knowledge,
    build_schema_linking_result,
    build_sql_generation_context,
)
from nl2sqlagent.workflows.nl2sql.prompt_payload import (
    build_mock_prompt_payload,
    build_prompt_payload_from_sql_generation_context,
)


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
    assert schema_context["value_bindings"] == []
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


def test_build_mock_prompt_payload_returns_json_like_relationships_boundary() -> None:
    payload = build_mock_prompt_payload(
        raw_question="统计员工数量",
        normalized_question="统计员工数量",
    )

    relationships = payload["schema_context"]["relationships"]
    assert relationships == []
    assert isinstance(relationships, list)


def test_build_prompt_payload_from_sql_generation_context_keeps_clean_boundary() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)
    linking = build_schema_linking_result(question, knowledge, retrieval)
    context = build_sql_generation_context(question, knowledge, linking)

    payload = build_prompt_payload_from_sql_generation_context(context)

    assert list(payload) == [
        "task",
        "question",
        "schema_context",
        "semantic_context",
        "sql_policy",
        "output_contract",
        "debug",
    ]
    assert payload["schema_context"]["value_bindings"] == linking["value_bindings"]
    assert payload["debug"]["source"] == "sql_generation_context"
    serialized = str(payload)
    assert "dropped_candidates" not in serialized
    assert "retrieval_method" not in serialized
    assert "vector_score" not in serialized
    assert "chunk_id" not in serialized


def test_build_prompt_payload_from_sql_generation_context_groups_relevant_columns_by_table() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)
    linking = build_schema_linking_result(question, knowledge, retrieval)
    context = build_sql_generation_context(question, knowledge, linking)

    payload = build_prompt_payload_from_sql_generation_context(context)

    tables = {table["name"]: table for table in payload["schema_context"]["tables"]}
    assert [column["name"] for column in tables["hr_emp_base"]["columns"]] == [
        "emp_stat_cd",
        "emp_id",
        "dept_id",
    ]
    assert [column["name"] for column in tables["hr_dept_dim"]["columns"]] == [
        "dept_nm",
        "dept_id",
    ]
