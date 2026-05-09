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


def test_knowledge_contracts_are_importable_without_heavy_layers() -> None:
    from nl2sqlagent.workflows.nl2sql.knowledge_contracts import (
        KnowledgeRetrievalResult,
        ProcessedDatabaseKnowledge,
        ProcessedQuestion,
        SchemaLinkingResult,
        SqlGenerationContext,
    )

    assert ProcessedQuestion
    assert ProcessedDatabaseKnowledge
    assert KnowledgeRetrievalResult
    assert SchemaLinkingResult
    assert SqlGenerationContext


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


def test_runtime_options_are_normalized_in_workflow_not_nodes() -> None:
    workflow_source = Path("src/nl2sqlagent/workflows/nl2sql/workflow.py").read_text(
        encoding="utf-8"
    )
    nodes_source = Path("src/nl2sqlagent/workflows/nl2sql/nodes.py").read_text(
        encoding="utf-8"
    )

    assert "normalize_runtime_options" in workflow_source
    assert "normalize_runtime_options" not in nodes_source


def test_nl2sql_nodes_do_not_read_raw_options() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/nodes.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        'state.get("options")',
        "state.get('options')",
        'state["options"]',
        "state['options']",
    ]
    assert all(token not in source for token in forbidden)
    assert "runtime_options" in source


def test_response_builder_does_not_construct_artifact_metadata() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/response_builder.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "artifact_manifest_path",
        "input_path",
        "prompt_payload_path",
        "final_prompt_path",
        "graph_updates_path",
        "output_path",
        "token_usage_path",
        "artifact_error",
    ]
    assert all(token not in source for token in forbidden)


def test_workflow_does_not_hand_write_artifact_metadata_keys() -> None:
    import ast

    source = Path("src/nl2sqlagent/workflows/nl2sql/workflow.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "artifact_manifest_path",
        "input_path",
        "prompt_payload_path",
        "final_prompt_path",
        "graph_updates_path",
        "output_path",
        "token_usage_path",
        "artifact_error",
    ]

    tree = ast.parse(source)
    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert all(token not in string_literals for token in forbidden)
    assert "artifact_result.metadata" in source


def test_artifacts_module_owns_artifact_metadata_keys() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/artifacts.py").read_text(
        encoding="utf-8"
    )

    required = [
        "Nl2SqlArtifactMetadata",
        "artifact_manifest_path",
        "prompt_payload_path",
        "final_prompt_path",
        "graph_updates_path",
        "token_usage_path",
        "artifact_error",
    ]
    assert all(token in source for token in required)


def test_phase5_does_not_add_heavy_architecture_layers() -> None:
    forbidden_paths = [
        Path("src/nl2sqlagent/domain"),
        Path("src/nl2sqlagent/services"),
        Path("src/nl2sqlagent/integrations"),
        Path("src/nl2sqlagent/workflows/nl2sql/stages"),
        Path("src/nl2sqlagent/workflows/nl2sql/models"),
    ]

    assert all(not path.exists() for path in forbidden_paths)


def test_phase5_does_not_introduce_stage_protocol_or_context_result_shells() -> None:
    import ast

    root = Path("src/nl2sqlagent/workflows/nl2sql")
    forbidden = {
        "Nl2SqlContext",
        "Nl2SqlStageProtocol",
        "PrepareStage",
        "GenerateStage",
        "CheckStage",
        "ExecuteStage",
        "PrepareResult",
        "GenerateResult",
        "CheckResult",
        "ExecuteResult",
    }

    used_names: set[str] = set()
    for file in root.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                used_names.add(node.attr)
            elif isinstance(node, ast.ClassDef):
                used_names.add(node.name)
            elif isinstance(node, ast.FunctionDef):
                used_names.add(node.name)

    assert forbidden.isdisjoint(used_names)
