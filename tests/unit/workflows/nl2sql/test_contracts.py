from __future__ import annotations

from pathlib import Path

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


def test_nl2sql_nodes_do_not_write_files_or_log_artifacts() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/nodes.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "open(",
        "write_text(",
        "json.dump",
        "json.dumps",
        "logger.",
        "artifact",
    ]
    assert all(token not in source for token in forbidden)


def test_graph_runtime_does_not_reference_nl2sql_business_fields() -> None:
    source = Path("src/nl2sqlagent/workflows/runtime/graph_runtime.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "prompt_payload",
        "final_prompt",
        "generated_sql",
        "checked_sql",
        "result_rows",
        "Nl2Sql",
    ]
    assert all(token not in source for token in forbidden)
