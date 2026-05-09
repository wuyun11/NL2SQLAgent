from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.response_builder import build_nl2sql_output


def test_build_output_for_success_includes_sql_rows_and_prompt_metadata() -> None:
    output = build_nl2sql_output(
        {
            "status": "success",
            "message": "NL2SQL workflow succeeded.",
            "checked_sql": "SELECT 1 AS value",
            "result_columns": ["value"],
            "result_rows": [{"value": 1}],
            "prompt_payload": {"question": "统计员工数量"},
            "final_prompt": "Question: 统计员工数量\nGenerate SQL:",
        }
    )

    assert output.status == "success"
    assert output.message == "NL2SQL workflow succeeded."
    assert output.sql == "SELECT 1 AS value"
    assert output.columns == ["value"]
    assert output.rows == [{"value": 1}]
    assert output.metadata["prompt_payload"] == {"question": "统计员工数量"}
    assert output.metadata["final_prompt"] == "Question: 统计员工数量\nGenerate SQL:"


def test_build_output_for_clarification_does_not_require_prompt_metadata() -> None:
    output = build_nl2sql_output(
        {
            "status": "needs_clarification",
            "clarification_message": "Please provide a question.",
        }
    )

    assert output.status == "needs_clarification"
    assert output.message == "Please provide a question."
    assert output.sql is None
    assert output.columns == []
    assert output.rows == []
    assert output.metadata == {}


def test_build_output_for_failed_prefers_check_error_message() -> None:
    output = build_nl2sql_output(
        {
            "status": "failed",
            "check_error": "mock check error",
            "execute_error": "mock execute error",
            "message": "fallback message",
            "prompt_payload": {"question": "bad"},
            "final_prompt": "Question: bad\nGenerate SQL:",
        }
    )

    assert output.status == "failed"
    assert output.message == "mock check error"
    assert output.metadata["final_prompt"] == "Question: bad\nGenerate SQL:"


def test_build_output_for_failed_uses_execute_error_when_no_check_error() -> None:
    output = build_nl2sql_output(
        {
            "status": "failed",
            "execute_error": "mock execute error",
            "message": "fallback message",
        }
    )

    assert output.status == "failed"
    assert output.message == "mock execute error"


def test_build_output_for_failed_falls_back_to_default_message() -> None:
    output = build_nl2sql_output({"status": "failed"})

    assert output.status == "failed"
    assert output.message == "NL2SQL workflow failed."
