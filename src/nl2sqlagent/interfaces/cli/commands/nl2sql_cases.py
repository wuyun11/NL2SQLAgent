from __future__ import annotations

import json
from pathlib import Path

from nl2sqlagent.bootstrap import build_app
from nl2sqlagent.workflows.nl2sql.sample_cases import load_sample_case_file
from nl2sqlagent.workflows.nl2sql.sql_generator import FakeSqlGenerator


def run_nl2sql_cases_summary(
    *,
    cases_path: Path,
    case_id: str | None = None,
    project_root: Path | None = None,
    config_dir: Path | None = None,
    run_id: str | None = None,
    real_llm: bool = False,
) -> str:
    cases = load_sample_case_file(cases_path)
    selected_cases = cases
    if case_id is not None:
        selected_cases = [item for item in cases if item.case_id == case_id]
        if not selected_cases:
            raise ValueError(f"case_id not found: {case_id}")

    effective_run_id = run_id or "phase8-manual-cases"
    rows: list[dict[str, str | None]] = []
    for case in selected_cases:
        app = build_app(
            project_root=project_root,
            config_dir=config_dir,
            run_id=effective_run_id,
            sql_generator_override=None
            if real_llm
            else FakeSqlGenerator(sql=case.reference_sql),
        )
        output = app.nl2sql_workflow.run(
            case.to_input(), thread_id=f"thread-{case.case_id}"
        )
        rows.append(
            {
                "case_id": case.case_id,
                "status": output.status,
                "sql": output.sql,
                "artifact_manifest_path": output.metadata.get("artifact_manifest_path"),
            }
        )
    return json.dumps(
        {"run_id": effective_run_id, "real_llm": real_llm, "cases": rows},
        ensure_ascii=False,
        separators=(",", ":"),
    )


__all__ = ["run_nl2sql_cases_summary"]
