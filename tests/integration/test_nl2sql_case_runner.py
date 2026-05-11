from __future__ import annotations

from pathlib import Path

from nl2sqlagent.bootstrap import build_app
from nl2sqlagent.workflows.nl2sql.sample_cases import (
    assert_prompt_expectations,
    load_sample_case_file,
)
from nl2sqlagent.workflows.nl2sql.sql_generator import FakeSqlGenerator


def test_phase8_cases_run_with_fake_generator(tmp_path: Path) -> None:
    cases = load_sample_case_file(Path("examples/nl2sql_cases/phase8_cases.json"))
    for case in cases:
        app = build_app(
            project_root=Path.cwd(),
            run_id=f"phase8-test-{case.case_id}",
            sql_generator_override=FakeSqlGenerator(sql=case.reference_sql),
        )
        output = app.nl2sql_workflow.run(case.to_input(), thread_id=f"thread-{case.case_id}")
        assert output.status == "success"
        assert output.sql == case.reference_sql
        assert output.metadata["artifact_manifest_path"]
        assert_prompt_expectations(case, output.metadata["final_prompt"])
        linking = output.metadata["schema_linking_result"]
        selected_tables = {item["table_name"] for item in linking["selected_tables"]}
        assert set(case.expected_schema_linking.selected_tables) <= selected_tables
        dropped_tables = {item["target_name"] for item in linking["dropped_candidates"]}
        assert set(case.expected_schema_linking.dropped_tables) <= dropped_tables
