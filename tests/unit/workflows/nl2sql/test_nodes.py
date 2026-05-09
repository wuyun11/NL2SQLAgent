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

    assert result["prompt_payload"]["question"] == {
        "raw": "  统计员工数量  ",
        "normalized": "统计员工数量",
    }
    assert result["prompt_payload"]["schema_context"]["dialect"] == "sqlite"
    assert result["prompt_payload"]["schema_context"]["tables"][0]["name"] == "employee"
    assert result["prompt_payload"]["sql_policy"]["readonly_only"] is True
    assert result["prompt_payload"]["output_contract"]["format"] == "sql_only"
    assert result["prompt_payload"]["debug"]["prompt_version"] == "phase3.mock.v1"
    assert "User Question:\n统计员工数量" in result["final_prompt"]
    assert "Allowed tables:" in result["final_prompt"]
    assert "- Table: employee" in result["final_prompt"]
    assert "SQL Policy:" in result["final_prompt"]
    assert "Output Contract:" in result["final_prompt"]
    assert "phase3.mock.v1" not in result["final_prompt"]


def test_generate_sql_node_returns_sql_only_mock_sql() -> None:
    result = generate_sql_node({"final_prompt": "User Question:\n统计员工数量"})

    assert result == {"generated_sql": "SELECT 1 AS value"}
    assert "```" not in result["generated_sql"]
    assert "\n" not in result["generated_sql"]


def test_check_sql_node_can_force_check_error() -> None:
    result = check_sql_node(
        {
            "generated_sql": "SELECT 1 AS value",
            "options": {"force_check_error": True},
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
            "options": {"force_execute_error": True},
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
    assert success_response_node({}) == {
        "status": "success",
        "message": "NL2SQL workflow succeeded.",
    }
