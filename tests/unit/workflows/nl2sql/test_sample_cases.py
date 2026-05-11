from __future__ import annotations

import json
from pathlib import Path

import pytest

from nl2sqlagent.workflows.nl2sql.sample_cases import (
    assert_prompt_expectations,
    load_sample_case_file,
)


def _write_case_file(tmp_path: Path, *, duplicate_case_id: bool = False) -> Path:
    payload = {
        "version": "phase8.manual-cases.v1",
        "knowledge": {
            "dialect": "sqlite",
            "tables": [],
            "columns": [],
            "relationships": [],
            "value_bindings": [],
            "business_terms": [],
        },
        "cases": [
            {
                "case_id": "case_001",
                "title": "x",
                "risk_focus": "x",
                "raw_question": "统计在职员工人数",
                "processed_question": {"text": "统计在职员工人数"},
                "expected_schema_linking": {},
                "expected_prompt_contains": ["Table: hr_emp_base"],
                "expected_prompt_excludes": ["Table: tmp_import_record"],
                "expected_sql_shape": ["COUNT"],
                "reference_sql": "SELECT 1",
            },
            {
                "case_id": "case_001" if duplicate_case_id else "case_002",
                "title": "y",
                "risk_focus": "y",
                "raw_question": "统计员工人数",
                "processed_question": {"text": "统计员工人数"},
                "expected_schema_linking": {},
                "expected_prompt_contains": ["Table: hr_emp_base"],
                "expected_prompt_excludes": [],
                "expected_sql_shape": ["COUNT"],
                "reference_sql": "SELECT 2",
            },
        ],
    }
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_sample_case_file_returns_cases(tmp_path: Path) -> None:
    cases = load_sample_case_file(_write_case_file(tmp_path))
    assert [item.case_id for item in cases] == ["case_001", "case_002"]


def test_sample_case_to_input_preserves_manual_middle_layer(tmp_path: Path) -> None:
    case = load_sample_case_file(_write_case_file(tmp_path))[0]
    input_data = case.to_input()
    assert input_data.case_id == "case_001"
    assert input_data.processed_question["text"] == "统计在职员工人数"
    assert input_data.processed_database_knowledge["dialect"] == "sqlite"


def test_sample_case_expectations_can_check_prompt_contains_and_excludes(
    tmp_path: Path,
) -> None:
    case = load_sample_case_file(_write_case_file(tmp_path))[0]
    assert_prompt_expectations(case, "Table: hr_emp_base\nfoo")
    with pytest.raises(AssertionError):
        assert_prompt_expectations(case, "Table: tmp_import_record")


def test_load_sample_case_file_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicate case_id"):
        load_sample_case_file(_write_case_file(tmp_path, duplicate_case_id=True))


def test_phase8_case_file_loads_all_expected_cases() -> None:
    path = Path("examples/nl2sql_cases/phase8_cases.json")
    cases = load_sample_case_file(path)
    assert [case.case_id for case in cases] == [
        "case_001_active_employee_count",
        "case_002_active_employee_by_department",
        "case_003_inactive_employee_by_department",
        "case_004_full_time_employee_count",
        "case_005_drop_import_table",
        "case_006_ambiguous_employee_count",
    ]
