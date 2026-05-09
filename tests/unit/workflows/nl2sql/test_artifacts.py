from __future__ import annotations

import json
from datetime import datetime

from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql.artifacts import (
    build_nl2sql_artifact_paths,
    normalize_graph_updates,
    write_nl2sql_artifacts,
)
from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput
from nl2sqlagent.workflows.nl2sql.output import Nl2SqlOutput


def _run_context() -> RunContext:
    return RunContext(
        run_id="run-phase4",
        run_date="20260509",
        started_at=datetime(2026, 5, 9, 9, 0, 0),
    )


def test_build_nl2sql_artifact_paths_prefers_request_id(tmp_path) -> None:
    paths = build_nl2sql_artifact_paths(
        log_dir=tmp_path / "logs" / "20260509" / "run-phase4",
        run_context=_run_context(),
        input=Nl2SqlInput(
            question="统计员工数量",
            request_id="request/中文 1",
        ),
        resolved_thread_id="thread-phase4",
    )

    assert paths.artifact_dir == (
        tmp_path
        / "logs"
        / "20260509"
        / "run-phase4"
        / "artifacts"
        / "nl2sql"
        / "request_1"
    )
    assert paths.input_path == paths.artifact_dir / "input.json"
    assert paths.prompt_payload_path == paths.artifact_dir / "prompt_payload.json"
    assert paths.final_prompt_path == paths.artifact_dir / "final_prompt.txt"
    assert paths.graph_updates_path == paths.artifact_dir / "graph_updates.jsonl"
    assert paths.output_path == paths.artifact_dir / "output.json"
    assert paths.manifest_path == paths.artifact_dir / "manifest.json"
    assert paths.token_usage_path is None


def test_build_nl2sql_artifact_paths_falls_back_to_thread_id(tmp_path) -> None:
    paths = build_nl2sql_artifact_paths(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量"),
        resolved_thread_id="thread:phase4",
    )

    assert paths.artifact_dir == tmp_path / "artifacts" / "nl2sql" / "thread_phase4"


def test_build_nl2sql_artifact_paths_falls_back_to_run_id_when_request_id_is_sanitized_empty(
    tmp_path,
) -> None:
    paths = build_nl2sql_artifact_paths(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量", request_id="中文"),
        resolved_thread_id="thread-phase4",
    )

    assert paths.artifact_dir == tmp_path / "artifacts" / "nl2sql" / "run-phase4"


def test_normalize_graph_updates_expands_each_node_update() -> None:
    rows = normalize_graph_updates(
        [
            {"build_prompt": {"final_prompt": "prompt"}},
            {
                "check_sql": {"checked_sql": "SELECT 1 AS value"},
                "execute_sql": {"result_rows": [{"value": 1}]},
            },
        ]
    )

    assert rows == [
        {"node": "build_prompt", "update": {"final_prompt": "prompt"}},
        {"node": "check_sql", "update": {"checked_sql": "SELECT 1 AS value"}},
        {"node": "execute_sql", "update": {"result_rows": [{"value": 1}]}},
    ]


def test_normalized_graph_updates_are_json_serializable() -> None:
    rows = normalize_graph_updates([{"build_prompt": {"final_prompt": "prompt"}}])

    assert json.loads(json.dumps(rows[0], ensure_ascii=False)) == rows[0]


def test_write_nl2sql_artifacts_writes_expected_files(tmp_path) -> None:
    started_at = datetime(2026, 5, 9, 9, 0, 0)
    finished_at = datetime(2026, 5, 9, 9, 0, 1)
    final_state = {
        "processed_question": {"text": "按部门统计在职员工人数"},
        "knowledge_retrieval_result": {"candidates": []},
        "schema_linking_result": {"selected_tables": [{"table_name": "hr_emp_base"}]},
        "sql_generation_context": {"question": {"text": "按部门统计在职员工人数"}},
        "prompt_payload": {
            "question": {"raw": "按部门统计在职员工人数", "normalized": "按部门统计在职员工人数"},
            "debug": {"prompt_version": "phase6.sql-context.v1"},
        },
        "final_prompt": "User Question:\n按部门统计在职员工人数",
    }
    output = Nl2SqlOutput(
        status="success",
        message="NL2SQL workflow succeeded.",
        sql="SELECT 1 AS value",
        columns=["value"],
        rows=[{"value": 1}],
        metadata={
            "processed_question": final_state["processed_question"],
            "knowledge_retrieval_result": final_state["knowledge_retrieval_result"],
            "schema_linking_result": final_state["schema_linking_result"],
            "sql_generation_context": final_state["sql_generation_context"],
            "prompt_payload": final_state["prompt_payload"],
            "final_prompt": final_state["final_prompt"],
        },
    )

    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量", request_id="request-1"),
        resolved_thread_id="thread-phase4",
        final_state=final_state,
        output=output,
        graph_updates=[{"build_prompt": final_state}],
        started_at=started_at,
        finished_at=finished_at,
        artifact_required=True,
    )

    assert result.artifact_error is None
    assert result.paths is not None
    assert result.paths.input_path.exists()
    assert result.paths.prompt_payload_path.exists()
    assert result.paths.final_prompt_path.exists()
    assert result.paths.graph_updates_path.exists()
    assert result.paths.output_path.exists()
    assert result.paths.manifest_path.exists()
    assert result.paths.token_usage_path is None

    input_data = json.loads(result.paths.input_path.read_text(encoding="utf-8"))
    assert input_data["run_id"] == "run-phase4"
    assert input_data["run_date"] == "20260509"
    assert input_data["thread_id"] == "thread-phase4"
    assert input_data["request_id"] == "request-1"
    assert input_data["raw_question"] == "统计员工数量"
    assert input_data["options"] == {}

    assert (
        json.loads(result.paths.prompt_payload_path.read_text(encoding="utf-8"))
        == final_state["prompt_payload"]
    )
    assert (
        result.paths.final_prompt_path.read_text(encoding="utf-8")
        == "User Question:\n按部门统计在职员工人数"
    )

    graph_update_lines = result.paths.graph_updates_path.read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(graph_update_lines) == 1
    assert json.loads(graph_update_lines[0])["node"] == "build_prompt"

    output_data = json.loads(result.paths.output_path.read_text(encoding="utf-8"))
    assert output_data["status"] == "success"
    assert output_data["sql"] == "SELECT 1 AS value"
    assert (
        output_data["metadata"]["artifact_manifest_path"] == str(result.paths.manifest_path)
    )
    assert output_data["metadata"]["schema_linking_result"]["selected_tables"][0]["table_name"] == "hr_emp_base"
    assert output_data["metadata"]["sql_generation_context"]["question"]["text"] == "按部门统计在职员工人数"
    assert output_data["metadata"]["token_usage_path"] is None

    manifest = json.loads(result.paths.manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-phase4"
    assert manifest["thread_id"] == "thread-phase4"
    assert manifest["request_id"] == "request-1"
    assert manifest["artifact_id"] == "request-1"
    assert manifest["workflow"] == "nl2sql"
    assert manifest["write_mode"] == "overwrite"
    assert manifest["status"] == "success"
    assert manifest["artifact_error"] is None
    assert manifest["artifact_files"]["token_usage"] is None
    assert manifest["sizes"]["final_prompt_size_chars"] == len(final_state["final_prompt"])


def test_write_nl2sql_artifacts_preserves_final_prompt_verbatim(tmp_path) -> None:
    final_prompt = "\n  User Question:\n统计员工数量\n  "

    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量"),
        resolved_thread_id="thread-phase4",
        final_state={"final_prompt": final_prompt},
        output=Nl2SqlOutput(status="success", metadata={}),
        graph_updates=[],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
        artifact_required=True,
    )

    assert result.paths is not None
    assert result.paths.final_prompt_path.read_text(encoding="utf-8") == final_prompt


def test_write_nl2sql_artifacts_skips_prompt_files_when_prompt_absent(tmp_path) -> None:
    output = Nl2SqlOutput(
        status="needs_clarification",
        message="Please provide a question.",
        metadata={},
    )

    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="   "),
        resolved_thread_id="thread-blank",
        final_state={"status": "needs_clarification"},
        output=output,
        graph_updates=[{"normalize_question": {"status": "needs_clarification"}}],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
        artifact_required=True,
    )

    assert result.paths is not None
    assert result.metadata["prompt_payload_path"] is None
    assert result.metadata["final_prompt_path"] is None
    assert not result.paths.prompt_payload_path.exists()
    assert not result.paths.final_prompt_path.exists()

    manifest = json.loads(result.paths.manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifact_files"]["prompt_payload"] is None
    assert manifest["artifact_files"]["final_prompt"] is None


def test_write_nl2sql_artifacts_without_request_id_uses_thread_artifact_id_and_keeps_thread_in_manifest(
    tmp_path,
) -> None:
    output = Nl2SqlOutput(
        status="success",
        message="NL2SQL workflow succeeded.",
        sql="SELECT 1 AS value",
        columns=["value"],
        rows=[{"value": 1}],
        metadata={},
    )

    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量"),
        resolved_thread_id="thread:phase4",
        final_state={"final_prompt": "User Question:\n统计员工数量"},
        output=output,
        graph_updates=[],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
        artifact_required=True,
    )

    assert result.paths is not None
    manifest = json.loads(result.paths.manifest_path.read_text(encoding="utf-8"))
    assert manifest["request_id"] is None
    assert manifest["thread_id"] == "thread:phase4"
    assert manifest["artifact_id"] == "thread_phase4"


def test_write_nl2sql_artifacts_failure_does_not_raise_by_default(tmp_path) -> None:
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("block", encoding="utf-8")

    result = write_nl2sql_artifacts(
        log_dir=blocking_file,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量"),
        resolved_thread_id="thread-phase4",
        final_state={"final_prompt": "prompt"},
        output=Nl2SqlOutput(status="success", metadata={}),
        graph_updates=[],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
    )

    assert result.artifact_error is not None
    assert result.metadata["artifact_error"] is not None
    assert result.metadata["artifact_manifest_path"] is None


def test_write_nl2sql_artifacts_non_io_failure_does_not_raise_by_default(
    tmp_path,
) -> None:
    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量"),
        resolved_thread_id="thread-phase4",
        final_state={"final_prompt": "prompt"},
        output=Nl2SqlOutput(status="success", metadata={}),
        graph_updates=[{"bad_node": 1}],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
    )

    assert result.artifact_error is not None
    assert result.metadata["artifact_error"] is not None
    assert result.metadata["artifact_manifest_path"] is None


def test_write_nl2sql_artifacts_does_not_leave_output_with_missing_manifest_path(
    tmp_path,
) -> None:
    artifact_dir = tmp_path / "artifacts" / "nl2sql" / "request-1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "manifest.json").mkdir()

    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量", request_id="request-1"),
        resolved_thread_id="thread-phase4",
        final_state={"final_prompt": "prompt"},
        output=Nl2SqlOutput(status="success", metadata={}),
        graph_updates=[],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
    )

    assert result.artifact_error is not None
    assert result.metadata["artifact_manifest_path"] is None
    assert not (artifact_dir / "output.json").exists()


def test_write_nl2sql_artifacts_required_mode_reraises_failure(tmp_path) -> None:
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("block", encoding="utf-8")

    try:
        write_nl2sql_artifacts(
            log_dir=blocking_file,
            run_context=_run_context(),
            input=Nl2SqlInput(question="统计员工数量"),
            resolved_thread_id="thread-phase4",
            final_state={"final_prompt": "prompt"},
            output=Nl2SqlOutput(status="success", metadata={}),
            graph_updates=[],
            started_at=datetime(2026, 5, 9, 9, 0, 0),
            finished_at=datetime(2026, 5, 9, 9, 0, 1),
            artifact_required=True,
        )
    except OSError:
        pass
    else:
        raise AssertionError("Expected artifact_required=True to re-raise write failure")


def test_artifact_metadata_contains_only_json_safe_values(tmp_path) -> None:
    output = Nl2SqlOutput(status="success", metadata={})

    result = write_nl2sql_artifacts(
        log_dir=tmp_path,
        run_context=_run_context(),
        input=Nl2SqlInput(question="统计员工数量"),
        resolved_thread_id="thread-phase4",
        final_state={"final_prompt": "prompt"},
        output=output,
        graph_updates=[],
        started_at=datetime(2026, 5, 9, 9, 0, 0),
        finished_at=datetime(2026, 5, 9, 9, 0, 1),
        artifact_required=True,
    )

    json.dumps(result.metadata, ensure_ascii=False)
    assert all(not hasattr(value, "exists") for value in result.metadata.values())
