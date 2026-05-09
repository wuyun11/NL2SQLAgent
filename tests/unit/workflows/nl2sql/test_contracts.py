from __future__ import annotations

from nl2sqlagent.workflows.nl2sql import (
    Nl2SqlInput,
    Nl2SqlOutput,
)


def test_nl2sql_input_defaults_to_empty_options() -> None:
    request = Nl2SqlInput(question="统计员工数量")

    assert request.question == "统计员工数量"
    assert request.request_id is None
    assert request.user_id is None
    assert request.database_key is None
    assert request.options == {}


def test_nl2sql_input_options_default_dicts_are_not_shared() -> None:
    first = Nl2SqlInput(question="first")
    second = Nl2SqlInput(question="second")

    first.options["force_check_error"] = True

    assert second.options == {}


def test_nl2sql_output_defaults_to_empty_table_and_metadata() -> None:
    response = Nl2SqlOutput(status="success")

    assert response.status == "success"
    assert response.message is None
    assert response.sql is None
    assert response.columns == []
    assert response.rows == []
    assert response.trace_id is None
    assert response.metadata == {}
