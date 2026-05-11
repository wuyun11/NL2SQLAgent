from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.nodes import (
    build_prompt_node,
    check_sql_node,
    clarification_response_node,
    execute_sql_node,
    failed_response_node,
    generate_sql_node,
    normalize_question_node,
    success_response_node,
)
from nl2sqlagent.workflows.nl2sql.knowledge_pipeline import (
    build_sample_processed_database_knowledge,
)
from nl2sqlagent.workflows.nl2sql.sql_generator import FakeSqlGenerator


def test_normalize_question_strips_question() -> None:
    result = normalize_question_node({"raw_question": "  统计员工数量  "})

    assert result == {
        "normalized_question": "统计员工数量",
        "status": "running",
    }


def test_normalize_question_sets_clarification_for_blank_question() -> None:
    result = normalize_question_node({"raw_question": "   "})

    assert result["normalized_question"] == ""
    assert result["clarification_message"] == "Please provide a question."
    assert result["status"] == "needs_clarification"


def test_build_prompt_node_creates_structured_payload_and_final_prompt() -> None:
    result = build_prompt_node(
        {
            "raw_question": "  统计员工数量  ",
            "normalized_question": "统计员工数量",
        }
    )

    assert "processed_question" in result
    assert "processed_database_knowledge" in result
    assert "knowledge_retrieval_result" in result
    assert "schema_linking_result" in result
    assert "sql_generation_context" in result
    assert result["prompt_payload"]["question"]["normalized"] == "统计员工数量"
    assert result["prompt_payload"]["schema_context"]["dialect"] == "sqlite"
    table_names = {
        table["name"] for table in result["prompt_payload"]["schema_context"]["tables"]
    }
    assert {"hr_emp_base", "hr_dept_dim"} <= table_names
    assert result["prompt_payload"]["sql_policy"]["readonly_only"] is True
    assert result["prompt_payload"]["output_contract"]["format"] == "sql_only"
    assert result["prompt_payload"]["debug"]["source"] == "sql_generation_context"
    assert "User Question:\n统计员工数量" in result["final_prompt"]
    assert "Allowed tables:" in result["final_prompt"]
    assert "在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE" in result["final_prompt"]
    assert "SQL Policy:" in result["final_prompt"]
    assert "Output Contract:" in result["final_prompt"]
    assert "dropped_candidates" not in result["final_prompt"]
    assert "retrieval_method" not in result["final_prompt"]


def test_build_prompt_node_uses_manual_processed_question_and_knowledge() -> None:
    manual_question = {
        "raw": "统计员工人数",
        "text": "统计员工人数",
        "keywords": ["员工", "人数"],
        "business_terms": [],
        "metric_hints": ["employee_count"],
        "dimension_hints": [],
        "filter_hints": [],
        "time_hints": [],
        "assumptions": ["未限定员工状态，默认统计全部员工"],
    }
    manual_knowledge = build_sample_processed_database_knowledge()
    result = build_prompt_node(
        {
            "raw_question": "统计员工人数",
            "normalized_question": "统计员工人数",
            "processed_question": manual_question,
            "processed_database_knowledge": manual_knowledge,
        }
    )
    assert result["processed_question"] == manual_question
    assert result["processed_database_knowledge"] == manual_knowledge
    assert "在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE" not in result["final_prompt"]
    assert "未限定员工状态，默认统计全部员工" in result["final_prompt"]


def test_generate_sql_node_returns_sql_from_generator() -> None:
    gen = FakeSqlGenerator(sql="SELECT 1 AS value")
    result = generate_sql_node(
        {"final_prompt": "User Question:\n统计员工数量"},
        sql_generator=gen,
    )

    assert result == {
        "generated_sql": "SELECT 1 AS value",
        "llm_result": {
            "model_name": "fake-sql-generator",
            "raw_text": "SELECT 1 AS value",
        },
        "generate_error": None,
    }
    assert "```" not in result["generated_sql"]
    assert "\n" not in result["generated_sql"]


def test_generate_sql_node_requires_final_prompt() -> None:
    gen = FakeSqlGenerator()
    result = generate_sql_node({"final_prompt": ""}, sql_generator=gen)

    assert result["status"] == "failed"
    assert result["generate_error"] == "final_prompt is required before SQL generation"


def test_generate_sql_node_catches_generator_errors() -> None:
    class _Boom:
        def generate(self, final_prompt: str) -> object:
            raise ValueError("boom")

    result = generate_sql_node(
        {"final_prompt": "User Question:\nx"},
        sql_generator=_Boom(),
    )

    assert result["status"] == "failed"
    assert result["generate_error"] == "boom"


def test_check_sql_node_can_force_check_error() -> None:
    result = check_sql_node(
        {
            "generated_sql": "SELECT 1 AS value",
            "runtime_options": {"force_check_error": True},
        }
    )

    assert result == {
        "check_error": "mock check error",
        "status": "failed",
    }


def test_check_sql_node_accepts_mock_sql() -> None:
    result = check_sql_node({"generated_sql": "SELECT 1 AS value"})

    assert result == {
        "checked_sql": "SELECT 1 AS value",
        "check_error": None,
    }


def test_execute_sql_node_can_force_execute_error() -> None:
    result = execute_sql_node(
        {
            "checked_sql": "SELECT 1 AS value",
            "runtime_options": {"force_execute_error": True},
        }
    )

    assert result == {
        "execute_error": "mock execute error",
        "status": "failed",
    }


def test_execute_sql_node_returns_mock_rows() -> None:
    result = execute_sql_node({"checked_sql": "SELECT 1 AS value"})

    assert result == {
        "result_columns": ["value"],
        "result_rows": [{"value": 1}],
        "execute_error": None,
    }


def test_check_sql_node_ignores_raw_options() -> None:
    result = check_sql_node(
        {
            "generated_sql": "SELECT 1 AS value",
            "options": {"force_check_error": True},
        }
    )

    assert result == {
        "checked_sql": "SELECT 1 AS value",
        "check_error": None,
    }


def test_execute_sql_node_ignores_raw_options() -> None:
    result = execute_sql_node(
        {
            "checked_sql": "SELECT 1 AS value",
            "options": {"force_execute_error": True},
        }
    )

    assert result == {
        "result_columns": ["value"],
        "result_rows": [{"value": 1}],
        "execute_error": None,
    }


def test_response_nodes_set_final_status() -> None:
    assert clarification_response_node(
        {"clarification_message": "Please provide a question."}
    ) == {
        "status": "needs_clarification",
        "message": "Please provide a question.",
    }
    assert failed_response_node({"check_error": "mock check error"}) == {
        "status": "failed",
        "message": "mock check error",
    }
    assert failed_response_node(
        {
            "generate_error": "generator failed",
            "check_error": "mock check error",
        }
    ) == {
        "status": "failed",
        "message": "generator failed",
    }
    assert success_response_node({}) == {
        "status": "success",
        "message": "NL2SQL workflow succeeded.",
    }
