from __future__ import annotations

from datetime import datetime

from nl2sqlagent.bootstrap import build_app
from nl2sqlagent.platform.config import CheckpointerSection, WorkflowSection
from nl2sqlagent.platform.persistence import build_checkpointer
from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql import (
    Nl2SqlInput,
    Nl2SqlWorkflow,
    build_nl2sql_graph,
)
from nl2sqlagent.workflows.runtime import GraphRuntime


def _runtime() -> tuple[GraphRuntime, object, RunContext]:
    return (
        GraphRuntime(),
        build_checkpointer(
            WorkflowSection(checkpointer=CheckpointerSection(provider="memory"))
        ),
        RunContext(
            run_id="run-nl2sql",
            run_date="20260509",
            started_at=datetime(2026, 5, 9, 9, 0, 0),
        ),
    )


def test_nl2sql_graph_success_path_includes_final_prompt() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={"raw_question": "统计员工数量", "options": {}},
        run_context=run_context,
        thread_id="thread-nl2sql-success",
    )

    assert result["status"] == "success"
    assert result["checked_sql"] == "SELECT 1 AS value"
    assert result["result_rows"] == [{"value": 1}]
    assert "Question: 统计员工数量" in result["final_prompt"]


def test_nl2sql_graph_blank_question_goes_to_clarification() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={"raw_question": "   ", "options": {}},
        run_context=run_context,
        thread_id="thread-nl2sql-clarification",
    )

    assert result["status"] == "needs_clarification"
    assert result["message"] == "Please provide a question."
    assert "final_prompt" not in result


def test_nl2sql_graph_check_failure_does_not_retry() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={
            "raw_question": "统计员工数量",
            "options": {"force_check_error": True},
        },
        run_context=run_context,
        thread_id="thread-nl2sql-check-failed",
    )

    assert result["status"] == "failed"
    assert result["message"] == "mock check error"
    assert result["check_error"] == "mock check error"
    assert "Question: 统计员工数量" in result["final_prompt"]
    assert "result_rows" not in result


def test_nl2sql_graph_execute_failure_does_not_retry() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={
            "raw_question": "统计员工数量",
            "options": {"force_execute_error": True},
        },
        run_context=run_context,
        thread_id="thread-nl2sql-execute-failed",
    )

    assert result["status"] == "failed"
    assert result["message"] == "mock execute error"
    assert result["execute_error"] == "mock execute error"
    assert "Question: 统计员工数量" in result["final_prompt"]


def test_nl2sql_workflow_run_returns_output_with_prompt_metadata() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
    )

    output = workflow.run(
        Nl2SqlInput(question="统计员工数量"),
        thread_id="thread-nl2sql-workflow-run",
    )

    assert output.status == "success"
    assert output.sql == "SELECT 1 AS value"
    assert output.columns == ["value"]
    assert output.rows == [{"value": 1}]
    assert "Question: 统计员工数量" in output.metadata["final_prompt"]
    assert output.metadata["prompt_payload"]["question"] == "统计员工数量"


def test_nl2sql_workflow_run_preserves_prompt_metadata_on_check_failure() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
    )

    output = workflow.run(
        Nl2SqlInput(
            question="统计员工数量",
            options={"force_check_error": True},
        ),
        thread_id="thread-nl2sql-workflow-check-failed",
    )

    assert output.status == "failed"
    assert output.message == "mock check error"
    assert "Question: 统计员工数量" in output.metadata["final_prompt"]


def test_nl2sql_workflow_stream_updates_exposes_build_prompt_update() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(checkpointer=checkpointer)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
    )

    chunks = workflow.stream(
        Nl2SqlInput(question="统计员工数量"),
        thread_id="thread-nl2sql-workflow-stream",
        stream_mode="updates",
    )

    assert any(
        isinstance(chunk, dict)
        and "build_prompt" in chunk
        and "Question: 统计员工数量" in chunk["build_prompt"]["final_prompt"]
        for chunk in chunks
    )


def test_build_app_exposes_nl2sql_workflow(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yml").write_text(
        "app:\n  name: TestAgent\n  environment: test\n",
        encoding="utf-8",
    )
    (config_dir / "env.yml").write_text(
        "\n".join(
            [
                "paths:",
                "  workspace_dir: workspace",
                "  run_dir: workspace/runs",
                "  log_dir: workspace/logs",
                "",
                "logging:",
                "  level: INFO",
                "  file_enabled: true",
                "  console_enabled: false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (config_dir / "workflow.yml").write_text(
        "workflow:\n  checkpointer:\n    provider: memory\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='test-agent'\n",
        encoding="utf-8",
    )

    app = build_app(project_root=tmp_path, run_id="run-nl2sql-app")

    assert hasattr(app, "nl2sql_workflow")
    assert not hasattr(app, "hello_graph")
    output = app.nl2sql_workflow.run(
        Nl2SqlInput(question="统计员工数量"),
        thread_id="thread-nl2sql-app",
    )
    assert output.status == "success"
    assert "Question: 统计员工数量" in output.metadata["final_prompt"]
