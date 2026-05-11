from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from nl2sqlagent.bootstrap import build_app
from nl2sqlagent.platform.config import CheckpointerSection, WorkflowSection
from nl2sqlagent.platform.persistence import build_checkpointer
from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql import (
    Nl2SqlInput,
    Nl2SqlWorkflow,
    build_nl2sql_graph,
)
from nl2sqlagent.workflows.nl2sql.sql_generator import FakeSqlGenerator
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


def _nl2sql_graph(checkpointer: object):
    return build_nl2sql_graph(
        checkpointer=checkpointer,
        sql_generator=FakeSqlGenerator(),
    )


def _workflow_with_log_dir(tmp_path) -> Nl2SqlWorkflow:
    runtime, checkpointer, run_context = _runtime()
    graph = _nl2sql_graph(checkpointer)
    return Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
        log_dir=tmp_path / "logs" / run_context.run_date / run_context.run_id,
        logger=logging.getLogger("test-nl2sql"),
    )


def test_nl2sql_graph_success_path_includes_final_prompt() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = _nl2sql_graph(checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={"raw_question": "按部门统计在职员工人数", "options": {}},
        run_context=run_context,
        thread_id="thread-nl2sql-success",
    )

    assert result["status"] == "success"
    assert result["checked_sql"] == "SELECT 1 AS value"
    assert result["result_rows"] == [{"value": 1}]
    assert result["llm_result"]["model_name"] == "fake-sql-generator"
    assert result["llm_result"]["raw_text"] == "SELECT 1 AS value"
    assert "User Question:\n按部门统计在职员工人数" in result["final_prompt"]
    assert "Schema Context:" in result["final_prompt"]
    assert "SQL Policy:" in result["final_prompt"]
    assert "Output Contract:" in result["final_prompt"]
    assert "phase6.sql-context.v1" not in result["final_prompt"]
    assert result["prompt_payload"]["question"]["normalized"] == "按部门统计在职员工人数"
    assert {t["name"] for t in result["prompt_payload"]["schema_context"]["tables"]} >= {
        "hr_emp_base",
        "hr_dept_dim",
    }


def test_nl2sql_graph_blank_question_goes_to_clarification() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = _nl2sql_graph(checkpointer)

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
    graph = _nl2sql_graph(checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={
            "raw_question": "按部门统计在职员工人数",
            "options": {"force_check_error": True},
            "runtime_options": {"force_check_error": True},
        },
        run_context=run_context,
        thread_id="thread-nl2sql-check-failed",
    )

    assert result["status"] == "failed"
    assert result["message"] == "mock check error"
    assert result["check_error"] == "mock check error"
    assert "User Question:\n按部门统计在职员工人数" in result["final_prompt"]
    assert "phase6.sql-context.v1" not in result["final_prompt"]
    assert result["prompt_payload"]["question"]["normalized"] == "按部门统计在职员工人数"
    assert "result_rows" not in result


def test_nl2sql_graph_sql_generation_failure_skips_check_sql() -> None:
    class _RaisingSqlGenerator:
        def generate(self, final_prompt: str) -> object:
            raise RuntimeError("generator failed")

    runtime, checkpointer, run_context = _runtime()
    graph = build_nl2sql_graph(
        checkpointer=checkpointer,
        sql_generator=_RaisingSqlGenerator(),
    )

    result = runtime.invoke(
        graph=graph,
        input={"raw_question": "按部门统计在职员工人数", "options": {}},
        run_context=run_context,
        thread_id="thread-nl2sql-generate-failed",
    )

    assert result["status"] == "failed"
    assert result["generate_error"] == "generator failed"
    assert result["message"] == "generator failed"
    assert not result.get("check_error")
    assert not result.get("checked_sql")


def test_nl2sql_graph_execute_failure_does_not_retry() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = _nl2sql_graph(checkpointer)

    result = runtime.invoke(
        graph=graph,
        input={
            "raw_question": "按部门统计在职员工人数",
            "options": {"force_execute_error": True},
            "runtime_options": {"force_execute_error": True},
        },
        run_context=run_context,
        thread_id="thread-nl2sql-execute-failed",
    )

    assert result["status"] == "failed"
    assert result["message"] == "mock execute error"
    assert result["execute_error"] == "mock execute error"
    assert "User Question:\n按部门统计在职员工人数" in result["final_prompt"]
    assert "phase6.sql-context.v1" not in result["final_prompt"]


def test_nl2sql_workflow_graph_input_preserves_options_and_adds_runtime_options() -> None:
    graph_input = Nl2SqlWorkflow._graph_input(
        Nl2SqlInput(
            question="统计员工数量",
            options={
                "force_check_error": True,
                "temperature": 0.1,
                "force_execute_error": "true",
            },
        )
    )

    assert graph_input["options"] == {
        "force_check_error": True,
        "temperature": 0.1,
        "force_execute_error": "true",
    }
    assert graph_input["runtime_options"] == {"force_check_error": True}


def test_nl2sql_workflow_run_returns_output_with_prompt_metadata() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = _nl2sql_graph(checkpointer)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
    )

    output = workflow.run(
        Nl2SqlInput(question="按部门统计在职员工人数"),
        thread_id="thread-nl2sql-workflow-run",
    )

    assert output.status == "success"
    assert output.sql == "SELECT 1 AS value"
    assert output.columns == ["value"]
    assert output.rows == [{"value": 1}]
    assert "User Question:\n按部门统计在职员工人数" in output.metadata["final_prompt"]
    assert output.metadata["prompt_payload"]["question"]["normalized"] == "按部门统计在职员工人数"
    assert output.metadata["prompt_payload"]["debug"]["prompt_version"] == "phase6.sql-context.v1"
    assert output.metadata["llm_result"]["model_name"] == "fake-sql-generator"
    assert "phase6.sql-context.v1" not in output.metadata["final_prompt"]


def test_nl2sql_workflow_run_preserves_prompt_metadata_on_check_failure() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = _nl2sql_graph(checkpointer)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
    )

    output = workflow.run(
        Nl2SqlInput(
            question="按部门统计在职员工人数",
            options={"force_check_error": True},
        ),
        thread_id="thread-nl2sql-workflow-check-failed",
    )

    assert output.status == "failed"
    assert output.message == "mock check error"
    assert "User Question:\n按部门统计在职员工人数" in output.metadata["final_prompt"]
    assert output.metadata["prompt_payload"]["debug"]["prompt_version"] == "phase6.sql-context.v1"
    assert "phase6.sql-context.v1" not in output.metadata["final_prompt"]


def test_nl2sql_workflow_stream_updates_exposes_build_prompt_update() -> None:
    runtime, checkpointer, run_context = _runtime()
    graph = _nl2sql_graph(checkpointer)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=runtime,
        run_context=run_context,
    )

    chunks = workflow.stream(
        Nl2SqlInput(question="按部门统计在职员工人数"),
        thread_id="thread-nl2sql-workflow-stream",
        stream_mode="updates",
    )

    assert any(
        isinstance(chunk, dict)
        and "build_prompt" in chunk
        and chunk["build_prompt"]["prompt_payload"]["question"]["normalized"] == "按部门统计在职员工人数"
        and "User Question:\n按部门统计在职员工人数" in chunk["build_prompt"]["final_prompt"]
        and "phase6.sql-context.v1" not in chunk["build_prompt"]["final_prompt"]
        and "schema_linking_result" in chunk["build_prompt"]
        and "sql_generation_context" in chunk["build_prompt"]
        for chunk in chunks
    )
    assert any(
        isinstance(chunk, dict)
        and "generate_sql" in chunk
        and chunk["generate_sql"]["llm_result"]["model_name"] == "fake-sql-generator"
        for chunk in chunks
    )


def test_nl2sql_workflow_run_writes_artifacts(tmp_path) -> None:
    workflow = _workflow_with_log_dir(tmp_path)

    output = workflow.run(
        Nl2SqlInput(question="按部门统计在职员工人数", request_id="request-1"),
        thread_id="thread-nl2sql-artifact",
    )

    assert output.status == "success"
    manifest_path = output.metadata["artifact_manifest_path"]
    assert isinstance(manifest_path, str)

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-nl2sql"
    assert manifest["thread_id"] == "thread-nl2sql-artifact"
    assert manifest["request_id"] == "request-1"
    assert manifest["artifact_id"] == "request-1"
    assert manifest["artifact_files"]["token_usage"] is None

    final_prompt_path = Path(output.metadata["final_prompt_path"])
    prompt_payload_path = Path(output.metadata["prompt_payload_path"])
    graph_updates_path = Path(output.metadata["graph_updates_path"])
    output_path = Path(output.metadata["output_path"])

    assert "User Question:\n按部门统计在职员工人数" in final_prompt_path.read_text(encoding="utf-8")
    assert (
        json.loads(prompt_payload_path.read_text(encoding="utf-8"))["question"]["normalized"]
        == "按部门统计在职员工人数"
    )
    assert any(
        json.loads(line)["node"] == "build_prompt"
        for line in graph_updates_path.read_text(encoding="utf-8").splitlines()
    )
    output_json = json.loads(output_path.read_text(encoding="utf-8"))
    assert output_json["metadata"]["artifact_manifest_path"] == manifest_path
    assert output_json["metadata"]["token_usage_path"] is None
    assert output_json["metadata"]["llm_result"]["model_name"] == "fake-sql-generator"
    assert any(
        json.loads(line)["node"] == "generate_sql"
        for line in graph_updates_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def test_nl2sql_workflow_run_does_not_leak_api_key_into_artifacts(
    tmp_path,
    monkeypatch,
) -> None:
    secret = "sk-test-secret-should-not-leak"
    monkeypatch.setenv("DASHSCOPE_API_KEY", secret)
    workflow = _workflow_with_log_dir(tmp_path)

    output = workflow.run(
        Nl2SqlInput(question="按部门统计在职员工人数"),
        thread_id="thread-nl2sql-secret-guard",
    )

    assert output.status == "success"
    bundle = "\n".join(
        [
            Path(output.metadata["final_prompt_path"]).read_text(encoding="utf-8"),
            Path(output.metadata["prompt_payload_path"]).read_text(encoding="utf-8"),
            Path(output.metadata["graph_updates_path"]).read_text(encoding="utf-8"),
            Path(output.metadata["output_path"]).read_text(encoding="utf-8"),
            Path(output.metadata["input_path"]).read_text(encoding="utf-8"),
        ]
    )
    assert secret not in bundle


def test_nl2sql_workflow_clarification_writes_artifact_without_prompt_files(
    tmp_path,
) -> None:
    workflow = _workflow_with_log_dir(tmp_path)

    output = workflow.run(
        Nl2SqlInput(question="   "),
        thread_id="thread-nl2sql-blank-artifact",
    )

    assert output.status == "needs_clarification"
    assert output.metadata["prompt_payload_path"] is None
    assert output.metadata["final_prompt_path"] is None
    assert output.metadata["graph_updates_path"] is not None
    assert output.metadata["artifact_manifest_path"] is not None


def test_nl2sql_workflow_ignores_unknown_options_but_preserves_input_artifact(
    tmp_path,
) -> None:
    workflow = _workflow_with_log_dir(tmp_path)

    output = workflow.run(
        Nl2SqlInput(
            question="按部门统计在职员工人数",
            options={
                "temperature": 0.1,
                "force_check_error": "true",
            },
        ),
        thread_id="thread-nl2sql-unknown-options",
    )

    assert output.status == "success"
    input_path = Path(output.metadata["input_path"])
    input_data = json.loads(input_path.read_text(encoding="utf-8"))
    assert input_data["options"] == {
        "temperature": 0.1,
        "force_check_error": "true",
    }


def test_nl2sql_workflow_runtime_options_still_support_mock_check_failure(
    tmp_path,
) -> None:
    workflow = _workflow_with_log_dir(tmp_path)

    output = workflow.run(
        Nl2SqlInput(
            question="按部门统计在职员工人数",
            options={"force_check_error": True},
        ),
        thread_id="thread-nl2sql-runtime-check-error",
    )

    assert output.status == "failed"
    assert output.message == "mock check error"
    assert output.metadata["artifact_manifest_path"] is not None
    assert output.metadata["prompt_payload"]["question"]["normalized"] == "按部门统计在职员工人数"


def test_nl2sql_workflow_accepts_manual_middle_layer_inputs(tmp_path) -> None:
    workflow = _workflow_with_log_dir(tmp_path)
    output = workflow.run(
        Nl2SqlInput(
            question="统计在职员工人数",
            case_id="case_001_active_employee_count",
            processed_question={
                "raw": "统计在职员工人数",
                "text": "统计在职员工人数",
                "keywords": ["在职", "员工", "人数"],
                "business_terms": ["在职员工"],
                "metric_hints": ["employee_count"],
                "dimension_hints": [],
                "filter_hints": ["active_employee"],
                "time_hints": [],
                "assumptions": [],
            },
            processed_database_knowledge={
                "dialect": "sqlite",
                "tables": [],
                "columns": [],
                "relationships": [],
                "value_bindings": [],
                "business_terms": [],
            },
        ),
        thread_id="thread-manual-inputs",
    )
    assert output.metadata["processed_question"]["text"] == "统计在职员工人数"
    assert output.metadata["processed_database_knowledge"]["dialect"] == "sqlite"
    assert output.metadata["input_path"]
    input_json = json.loads(Path(output.metadata["input_path"]).read_text(encoding="utf-8"))
    assert input_json["case_id"] == "case_001_active_employee_count"


def test_build_app_exposes_nl2sql_workflow(tmp_path, monkeypatch) -> None:
    secret = "sk-test-secret-should-not-leak"
    monkeypatch.setenv("DASHSCOPE_API_KEY", secret)
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
    (config_dir / "model.yml").write_text(
        "model:\n  sql_generator:\n    provider: fake\n",
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
        Nl2SqlInput(question="按部门统计在职员工人数"),
        thread_id="thread-nl2sql-app",
    )
    assert output.status == "success"
    assert "User Question:\n按部门统计在职员工人数" in output.metadata["final_prompt"]
    assert output.metadata["prompt_payload"]["question"]["normalized"] == "按部门统计在职员工人数"
    assert output.metadata["artifact_manifest_path"] is not None
    assert Path(output.metadata["artifact_manifest_path"]).exists()
    assert str(app.logging.log_dir) in output.metadata["artifact_manifest_path"]
    app_log = app.logging.log_dir / "app.log"
    assert app_log.exists()
    assert secret not in app_log.read_text(encoding="utf-8")


def test_build_app_allows_sql_generator_override(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yml").write_text(
        "app:\n  name: TestAgent\n  environment: test\n",
        encoding="utf-8",
    )
    (config_dir / "env.yml").write_text(
        "paths:\n  workspace_dir: workspace\n  run_dir: workspace/runs\n  log_dir: workspace/logs\n\nlogging:\n  level: INFO\n  file_enabled: true\n  console_enabled: false\n",
        encoding="utf-8",
    )
    (config_dir / "workflow.yml").write_text(
        "workflow:\n  checkpointer:\n    provider: memory\n",
        encoding="utf-8",
    )
    (config_dir / "model.yml").write_text(
        "model:\n  sql_generator:\n    provider: openai_compatible\n    chat_model_name: qwen-max\n    base_url: https://example.invalid/v1\n    api_key_env: DASHSCOPE_API_KEY\n    temperature: 0\n    timeout_seconds: 30\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='test-agent'\n",
        encoding="utf-8",
    )
    app = build_app(
        project_root=tmp_path,
        run_id="run-with-override",
        sql_generator_override=FakeSqlGenerator(sql="SELECT 42 AS value"),
    )
    output = app.nl2sql_workflow.run(
        Nl2SqlInput(question="统计员工数量"),
        thread_id="thread-override",
    )
    assert output.sql == "SELECT 42 AS value"
