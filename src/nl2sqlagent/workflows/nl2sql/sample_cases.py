from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput
from nl2sqlagent.workflows.nl2sql.knowledge_contracts import (
    ProcessedDatabaseKnowledge,
    ProcessedQuestion,
)


@dataclass(frozen=True)
class SchemaLinkingExpectation:
    selected_tables: list[str]
    relevant_columns: list[str]
    relationships: list[str]
    value_bindings: list[str]
    dropped_tables: list[str]


@dataclass(frozen=True)
class Nl2SqlSampleCase:
    case_id: str
    title: str
    risk_focus: str
    raw_question: str
    processed_question: ProcessedQuestion
    processed_database_knowledge: ProcessedDatabaseKnowledge
    expected_schema_linking: SchemaLinkingExpectation
    expected_prompt_contains: list[str]
    expected_prompt_excludes: list[str]
    expected_sql_shape: list[str]
    reference_sql: str
    review_notes: str = ""

    def to_input(self) -> Nl2SqlInput:
        return Nl2SqlInput(
            question=self.raw_question,
            request_id=self.case_id,
            case_id=self.case_id,
            processed_question=self.processed_question,
            processed_database_knowledge=self.processed_database_knowledge,
        )


def _ensure_non_empty(value: Any, field_name: str, case_id: str | None = None) -> str:
    text = str(value or "").strip()
    if text:
        return text
    prefix = f"case {case_id}: " if case_id else ""
    raise ValueError(f"{prefix}{field_name} must be non-empty")


def _parse_schema_linking_expectation(
    value: dict[str, Any], *, case_id: str
) -> SchemaLinkingExpectation:
    return SchemaLinkingExpectation(
        selected_tables=list(value.get("selected_tables", [])),
        relevant_columns=list(value.get("relevant_columns", [])),
        relationships=list(value.get("relationships", [])),
        value_bindings=list(value.get("value_bindings", [])),
        dropped_tables=list(value.get("dropped_tables", [])),
    )


def load_sample_case_file(path: Path) -> list[Nl2SqlSampleCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    knowledge = data.get("knowledge")
    if not isinstance(knowledge, dict):
        raise ValueError("knowledge must be an object")
    for key in (
        "dialect",
        "tables",
        "columns",
        "relationships",
        "value_bindings",
        "business_terms",
    ):
        if key not in knowledge:
            raise ValueError(f"knowledge.{key} is required")

    seen_case_ids: set[str] = set()
    cases: list[Nl2SqlSampleCase] = []
    for item in data.get("cases", []):
        if not isinstance(item, dict):
            raise ValueError("each case must be an object")
        case_id = _ensure_non_empty(item.get("case_id"), "case_id")
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)
        raw_question = _ensure_non_empty(item.get("raw_question"), "raw_question", case_id)
        processed_question = dict(item.get("processed_question") or {})
        _ensure_non_empty(processed_question.get("text"), "processed_question.text", case_id)
        prompt_contains = list(item.get("expected_prompt_contains", []))
        if not prompt_contains:
            raise ValueError(
                f"case {case_id}: expected_prompt_contains must not be empty"
            )
        sql_shape = list(item.get("expected_sql_shape", []))
        if not sql_shape:
            raise ValueError(f"case {case_id}: expected_sql_shape must not be empty")
        cases.append(
            Nl2SqlSampleCase(
                case_id=case_id,
                title=str(item.get("title", "")),
                risk_focus=str(item.get("risk_focus", "")),
                raw_question=raw_question,
                processed_question=processed_question,
                processed_database_knowledge=knowledge,
                expected_schema_linking=_parse_schema_linking_expectation(
                    dict(item.get("expected_schema_linking") or {}), case_id=case_id
                ),
                expected_prompt_contains=prompt_contains,
                expected_prompt_excludes=list(item.get("expected_prompt_excludes", [])),
                expected_sql_shape=sql_shape,
                reference_sql=str(item.get("reference_sql", "")),
                review_notes=str(item.get("review_notes", "")),
            )
        )
    return cases


def assert_prompt_expectations(case: Nl2SqlSampleCase, final_prompt: str) -> None:
    for expected in case.expected_prompt_contains:
        assert expected in final_prompt, f"[{case.case_id}] prompt should contain: {expected}"
    for unexpected in case.expected_prompt_excludes:
        assert (
            unexpected not in final_prompt
        ), f"[{case.case_id}] prompt should exclude: {unexpected}"


__all__ = [
    "Nl2SqlSampleCase",
    "SchemaLinkingExpectation",
    "assert_prompt_expectations",
    "load_sample_case_file",
]
