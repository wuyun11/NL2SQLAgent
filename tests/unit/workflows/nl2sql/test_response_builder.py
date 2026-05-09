from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.knowledge_pipeline import (
    build_initial_processed_question,
    build_knowledge_retrieval_result,
    build_sample_processed_database_knowledge,
    build_schema_linking_result,
    build_sql_generation_context,
)
from nl2sqlagent.workflows.nl2sql.response_builder import (
    build_nl2sql_output,
    build_prompt_debug_metadata,
)


def test_build_output_for_success_includes_sql_rows_and_prompt_metadata() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)
    linking = build_schema_linking_result(question, knowledge, retrieval)
    context = build_sql_generation_context(question, knowledge, linking)
    prompt_payload = {
        "question": {
            "raw": "按部门统计在职员工人数",
            "normalized": "按部门统计在职员工人数",
        },
        "debug": {
            "prompt_version": "phase6.sql-context.v1",
            "source": "sql_generation_context",
        },
    }
    final_prompt = "User Question:\n按部门统计在职员工人数\nSchema Context:\nDialect: sqlite"
    output = build_nl2sql_output(
        {
            "status": "success",
            "message": "NL2SQL workflow succeeded.",
            "checked_sql": "SELECT 1 AS value",
            "result_columns": ["value"],
            "result_rows": [{"value": 1}],
            "processed_question": question,
            "knowledge_retrieval_result": retrieval,
            "schema_linking_result": linking,
            "sql_generation_context": context,
            "prompt_payload": prompt_payload,
            "final_prompt": final_prompt,
        }
    )

    assert output.status == "success"
    assert output.message == "NL2SQL workflow succeeded."
    assert output.sql == "SELECT 1 AS value"
    assert output.columns == ["value"]
    assert output.rows == [{"value": 1}]
    assert output.metadata["prompt_payload"]["question"]["normalized"] == "按部门统计在职员工人数"
    assert output.metadata["prompt_payload"]["debug"]["prompt_version"] == "phase6.sql-context.v1"
    assert "User Question:\n按部门统计在职员工人数" in output.metadata["final_prompt"]
    assert output.metadata["processed_question"]["text"] == "按部门统计在职员工人数"
    assert "schema_linking_result" in output.metadata
    assert "sql_generation_context" in output.metadata


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
    prompt_payload = {
        "question": {
            "raw": "bad",
            "normalized": "bad",
        },
        "debug": {
            "prompt_version": "phase3.mock.v1",
            "source": "mock_prompt_payload_builder",
        },
    }
    final_prompt = "User Question:\nbad\nSchema Context:\nDialect: sqlite"
    output = build_nl2sql_output(
        {
            "status": "failed",
            "check_error": "mock check error",
            "execute_error": "mock execute error",
            "message": "fallback message",
            "prompt_payload": prompt_payload,
            "final_prompt": final_prompt,
        }
    )

    assert output.status == "failed"
    assert output.message == "mock check error"
    assert "User Question:\nbad" in output.metadata["final_prompt"]


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


def test_build_prompt_debug_metadata_includes_intermediate_fields() -> None:
    state = {
        "prompt_payload": {"question": {"normalized": "统计员工数量"}},
        "final_prompt": "User Question:\n统计员工数量",
        "processed_question": {"text": "统计员工数量"},
        "knowledge_retrieval_result": {"candidates": []},
        "schema_linking_result": {"selected_tables": []},
        "sql_generation_context": {"question": {"text": "统计员工数量"}},
        "artifact_manifest_path": "should-not-be-copied",
        "result_rows": [{"value": 1}],
    }

    metadata = build_prompt_debug_metadata(state)
    assert metadata["prompt_payload"] == {"question": {"normalized": "统计员工数量"}}
    assert metadata["final_prompt"] == "User Question:\n统计员工数量"
    assert metadata["processed_question"] == {"text": "统计员工数量"}
    assert metadata["knowledge_retrieval_result"] == {"candidates": []}
    assert metadata["schema_linking_result"] == {"selected_tables": []}
    assert metadata["sql_generation_context"] == {"question": {"text": "统计员工数量"}}
    assert "artifact_manifest_path" not in metadata


def test_build_prompt_debug_metadata_returns_empty_for_clarification_state() -> None:
    assert build_prompt_debug_metadata(
        {
            "status": "needs_clarification",
            "message": "Please provide a question.",
        }
    ) == {}
