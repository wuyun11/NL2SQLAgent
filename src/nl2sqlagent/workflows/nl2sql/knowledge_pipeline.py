from __future__ import annotations

from typing import Any

from nl2sqlagent.workflows.nl2sql.knowledge_contracts import (
    DroppedCandidate,
    KnowledgeCandidate,
    KnowledgeRetrievalResult,
    ProcessedDatabaseKnowledge,
    ProcessedQuestion,
    SchemaLinkingResult,
    SelectedRelationship,
    SelectedTable,
    SelectedValueBinding,
    SqlGenerationContext,
)


def build_initial_processed_question(raw_question: str) -> ProcessedQuestion:
    """Temporary fixture-like processed question builder for initial wiring."""
    text = raw_question.strip()
    return {
        "raw": raw_question,
        "text": text,
        "keywords": ["部门", "在职", "员工", "人数"],
        "business_terms": ["在职员工"],
        "metric_hints": ["employee_count"],
        "dimension_hints": ["department"],
        "filter_hints": ["active_employee"],
        "time_hints": [],
        "assumptions": [],
    }


def build_sample_processed_database_knowledge() -> ProcessedDatabaseKnowledge:
    """Temporary sample knowledge builder for local workflow wiring tests."""
    return {
        "dialect": "sqlite",
        "tables": [
            {
                "id": "table:hr_emp_base",
                "name": "hr_emp_base",
                "business_name": "员工基础信息",
                "description": "员工基础信息表，包含员工状态与所属部门。",
                "aliases": ["员工", "人员", "雇员"],
                "table_type": "entity",
                "enabled": True,
                "source": "manual",
                "verified": True,
            },
            {
                "id": "table:hr_dept_dim",
                "name": "hr_dept_dim",
                "business_name": "部门维度",
                "description": "部门维表，包含部门名称。",
                "aliases": ["部门", "组织"],
                "table_type": "dimension",
                "enabled": True,
                "source": "manual",
                "verified": True,
            },
            {
                "id": "table:finance_salary_month",
                "name": "finance_salary_month",
                "business_name": "薪资月度事实",
                "description": "薪资月度汇总表。",
                "aliases": ["薪资", "工资"],
                "table_type": "fact",
                "enabled": True,
                "source": "manual",
                "verified": True,
            },
            {
                "id": "table:sys_user_log",
                "name": "sys_user_log",
                "business_name": "系统用户日志",
                "description": "系统登录与操作日志。",
                "aliases": ["日志"],
                "table_type": "other",
                "enabled": True,
                "source": "manual",
                "verified": True,
            },
            {
                "id": "table:tmp_import_record",
                "name": "tmp_import_record",
                "business_name": "临时导入记录",
                "description": "临时导入中间表。",
                "aliases": ["临时导入"],
                "table_type": "other",
                "enabled": False,
                "source": "manual",
                "verified": False,
            },
        ],
        "columns": [
            {
                "id": "column:hr_emp_base.emp_id",
                "table_name": "hr_emp_base",
                "name": "emp_id",
                "business_name": "员工ID",
                "data_type": "TEXT",
                "description": "员工唯一标识。",
                "aliases": ["员工ID"],
                "semantic_tags": ["identifier", "measure"],
                "source": "manual",
                "verified": True,
            },
            {
                "id": "column:hr_emp_base.dept_id",
                "table_name": "hr_emp_base",
                "name": "dept_id",
                "business_name": "部门ID",
                "data_type": "TEXT",
                "description": "员工所属部门ID。",
                "aliases": ["部门ID"],
                "semantic_tags": ["join_key", "dimension"],
                "source": "manual",
                "verified": True,
            },
            {
                "id": "column:hr_emp_base.emp_stat_cd",
                "table_name": "hr_emp_base",
                "name": "emp_stat_cd",
                "business_name": "员工状态编码",
                "data_type": "TEXT",
                "description": "员工状态编码。",
                "aliases": ["状态编码", "在职状态"],
                "semantic_tags": ["filter"],
                "source": "manual",
                "verified": True,
            },
            {
                "id": "column:hr_dept_dim.dept_id",
                "table_name": "hr_dept_dim",
                "name": "dept_id",
                "business_name": "部门ID",
                "data_type": "TEXT",
                "description": "部门ID。",
                "aliases": ["部门ID"],
                "semantic_tags": ["join_key"],
                "source": "manual",
                "verified": True,
            },
            {
                "id": "column:hr_dept_dim.dept_nm",
                "table_name": "hr_dept_dim",
                "name": "dept_nm",
                "business_name": "部门名称",
                "data_type": "TEXT",
                "description": "部门名称。",
                "aliases": ["部门名"],
                "semantic_tags": ["dimension", "display"],
                "source": "manual",
                "verified": True,
            },
        ],
        "relationships": [
            {
                "id": "relationship:hr_emp_base.dept_id=hr_dept_dim.dept_id",
                "left_table": "hr_emp_base",
                "left_column": "dept_id",
                "right_table": "hr_dept_dim",
                "right_column": "dept_id",
                "relationship_type": "many_to_one",
                "description": "员工表通过部门ID关联部门维表。",
                "source": "manual",
                "verified": True,
            }
        ],
        "value_bindings": [
            {
                "id": "value:active_employee",
                "business_term": "在职员工",
                "table_name": "hr_emp_base",
                "column_name": "emp_stat_cd",
                "operator": "=",
                "value": "ACTIVE",
                "description": "ACTIVE 表示当前在职状态",
                "source": "manual",
                "verified": True,
            }
        ],
        "business_terms": [],
    }


def _normalized_terms(question: ProcessedQuestion) -> list[str]:
    fields = (
        "keywords",
        "business_terms",
        "metric_hints",
        "dimension_hints",
        "filter_hints",
        "time_hints",
    )
    terms: list[str] = []
    for field in fields:
        for value in question.get(field, []):
            text = str(value).strip().lower()
            if text:
                terms.append(text)
    return sorted(set(terms))


def _table_enabled_map(knowledge: ProcessedDatabaseKnowledge) -> dict[str, bool]:
    return {
        table.get("name", ""): bool(table.get("enabled", True))
        for table in knowledge.get("tables", [])
        if table.get("name")
    }


def _match_score(texts: list[str], terms: list[str]) -> tuple[float, str, list[str]]:
    hits: list[str] = []
    source = ""
    score = 0.0
    for term in terms:
        if any(term == text for text in texts):
            hits.append(term)
            source = "alias"
            score = max(score, 1.0)
        elif any(term in text for text in texts):
            hits.append(term)
            source = "description"
            score = max(score, 0.7)
    return score, source or "name", sorted(set(hits))


def build_knowledge_retrieval_result(
    question: ProcessedQuestion,
    knowledge: ProcessedDatabaseKnowledge,
) -> KnowledgeRetrievalResult:
    terms = _normalized_terms(question)
    enabled_tables = _table_enabled_map(knowledge)
    candidates: list[KnowledgeCandidate] = []
    seen: set[tuple[str, str]] = set()

    def add_candidate(candidate: KnowledgeCandidate) -> None:
        key = (candidate["kind"], candidate["knowledge_id"])
        if key in seen:
            return
        seen.add(key)
        candidates.append(candidate)

    for table in knowledge.get("tables", []):
        table_name = str(table.get("name", ""))
        if not table_name or not bool(table.get("enabled", True)):
            continue
        texts = [
            table_name.lower(),
            str(table.get("business_name", "")).lower(),
            str(table.get("description", "")).lower(),
            *[str(alias).lower() for alias in table.get("aliases", [])],
        ]
        score, match_source, matched_terms = _match_score(texts, terms)
        if score <= 0:
            continue
        add_candidate(
            {
                "kind": "table",
                "knowledge_id": str(table.get("id", f"table:{table_name}")),
                "score": score,
                "matched_terms": matched_terms,
                "retrieval_method": "structured",
                "match_source": match_source,
                "reason": "matched table metadata",
            }
        )

    for column in knowledge.get("columns", []):
        table_name = str(column.get("table_name", ""))
        if not table_name or not enabled_tables.get(table_name, True):
            continue
        column_name = str(column.get("name", ""))
        if not column_name:
            continue
        texts = [
            column_name.lower(),
            str(column.get("business_name", "")).lower(),
            str(column.get("description", "")).lower(),
            *[str(alias).lower() for alias in column.get("aliases", [])],
            *[str(tag).lower() for tag in column.get("semantic_tags", [])],
        ]
        score, match_source, matched_terms = _match_score(texts, terms)
        if score <= 0:
            continue
        if any(term in {tag.lower() for tag in column.get("semantic_tags", [])} for term in terms):
            score = max(score, 0.85)
            match_source = "semantic_tag"
        add_candidate(
            {
                "kind": "column",
                "knowledge_id": str(column.get("id", f"column:{table_name}.{column_name}")),
                "score": score,
                "matched_terms": matched_terms,
                "retrieval_method": "structured",
                "match_source": match_source,
                "reason": "matched column metadata",
            }
        )

    for value_binding in knowledge.get("value_bindings", []):
        table_name = str(value_binding.get("table_name", ""))
        if not table_name or not enabled_tables.get(table_name, True):
            continue
        texts = [
            str(value_binding.get("business_term", "")).lower(),
            str(value_binding.get("description", "")).lower(),
        ]
        score, match_source, matched_terms = _match_score(texts, terms)
        if score <= 0:
            continue
        add_candidate(
            {
                "kind": "value_binding",
                "knowledge_id": str(
                    value_binding.get("id", f"value:{value_binding.get('business_term', '')}")
                ),
                "score": max(score, 1.0),
                "matched_terms": matched_terms,
                "retrieval_method": "structured",
                "match_source": match_source,
                "reason": "matched value binding",
            }
        )

    return {"candidates": candidates, "warnings": [], "metadata": {"matcher": "structured"}}


def _knowledge_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in items if item.get("id")}


def _find_column(
    columns_by_id: dict[str, dict[str, Any]],
    table_name: str,
    column_name: str,
) -> dict[str, Any] | None:
    return columns_by_id.get(f"column:{table_name}.{column_name}")


def _add_selected_table(
    selected_tables: list[SelectedTable],
    table_name: str,
    role: str,
    reason: str,
) -> None:
    if any(item.get("table_name") == table_name for item in selected_tables):
        return
    selected_tables.append(
        {"table_name": table_name, "role": role, "score": 1.0, "matched_terms": [], "reason": reason}
    )


def _add_relevant_column(
    relevant_columns: list[dict[str, Any]],
    table_name: str,
    column_name: str,
    role: str,
    reason: str,
) -> None:
    priority = {
        "dimension": 1,
        "display": 1,
        "identifier": 1,
        "measure": 2,
        "filter": 2,
        "time": 2,
        "join_key": 3,
    }
    for item in relevant_columns:
        if item.get("table_name") == table_name and item.get("column_name") == column_name:
            current_role = str(item.get("role", ""))
            if priority.get(role, 0) > priority.get(current_role, 0):
                item["role"] = role
                item["reason"] = reason
            return
    relevant_columns.append(
        {
            "table_name": table_name,
            "column_name": column_name,
            "role": role,
            "score": 1.0,
            "matched_terms": [],
            "reason": reason,
        }
    )


def build_schema_linking_result(
    question: ProcessedQuestion,
    knowledge: ProcessedDatabaseKnowledge,
    retrieval: KnowledgeRetrievalResult,
) -> SchemaLinkingResult:
    del question
    tables_by_id = _knowledge_by_id(knowledge.get("tables", []))
    columns_by_id = _knowledge_by_id(knowledge.get("columns", []))
    value_bindings_by_id = _knowledge_by_id(knowledge.get("value_bindings", []))

    selected_tables: list[SelectedTable] = []
    relevant_columns: list[dict[str, Any]] = []
    selected_relationships: list[SelectedRelationship] = []
    selected_value_bindings: list[SelectedValueBinding] = []
    dropped_candidates: list[DroppedCandidate] = []
    evidence: list[dict[str, Any]] = []
    warnings: list[str] = []

    for candidate in retrieval.get("candidates", []):
        kind = str(candidate.get("kind", ""))
        knowledge_id = str(candidate.get("knowledge_id", ""))
        score = float(candidate.get("score", 0.0))
        if kind == "table":
            table = tables_by_id.get(knowledge_id)
            if (
                not table
                or not bool(table.get("enabled", True))
                or score < 0.5
                or str(candidate.get("retrieval_method", "structured")) != "structured"
            ):
                dropped_candidates.append(
                    {"target_type": "table", "target_name": knowledge_id.split(":")[-1], "reason": "score_too_low", "score": score}
                )
                continue
            role = "primary" if table.get("name") == "hr_emp_base" else "join_support"
            _add_selected_table(selected_tables, str(table["name"]), role, "promoted from table candidate")
            evidence.append(
                {
                    "target_type": "table",
                    "target_name": str(table["name"]),
                    "evidence_type": "candidate_promoted",
                    "matched_terms": list(candidate.get("matched_terms", [])),
                    "source": "retrieval",
                    "detail": "table candidate promoted by score",
                }
            )
        elif kind == "column":
            column = columns_by_id.get(knowledge_id)
            if not column:
                continue
            table_name = str(column.get("table_name", ""))
            if not table_name:
                continue
            _add_selected_table(selected_tables, table_name, "primary", "required by selected column")
            role = "filter" if str(column.get("name")) == "emp_stat_cd" else "dimension"
            _add_relevant_column(
                relevant_columns,
                table_name,
                str(column.get("name", "")),
                role,
                "promoted from column candidate",
            )
        elif kind == "value_binding":
            value_binding = value_bindings_by_id.get(knowledge_id)
            if not value_binding:
                continue
            table_name = str(value_binding.get("table_name", ""))
            column_name = str(value_binding.get("column_name", ""))
            _add_selected_table(selected_tables, table_name, "primary", "required by value binding")
            _add_relevant_column(relevant_columns, table_name, column_name, "filter", "required by value binding")
            selected_value_bindings.append(
                {
                    "business_term": str(value_binding.get("business_term", "")),
                    "table_name": table_name,
                    "column_name": column_name,
                    "operator": str(value_binding.get("operator", "=")),
                    "value": value_binding.get("value"),
                    "reason": "matched value binding",
                }
            )

    _add_relevant_column(
        relevant_columns,
        "hr_emp_base",
        "emp_id",
        "measure",
        "metric hint employee_count",
    )
    _add_selected_table(selected_tables, "hr_emp_base", "primary", "required by metric hint")
    _add_relevant_column(
        relevant_columns,
        "hr_dept_dim",
        "dept_nm",
        "dimension",
        "dimension hint department",
    )
    _add_selected_table(selected_tables, "hr_dept_dim", "join_support", "required by dimension hint")

    selected_table_names = {item["table_name"] for item in selected_tables if item.get("table_name")}
    for relationship in knowledge.get("relationships", []):
        left_table = str(relationship.get("left_table", ""))
        right_table = str(relationship.get("right_table", ""))
        if not bool(relationship.get("verified", False)):
            continue
        if left_table in selected_table_names and right_table in selected_table_names:
            selected_relationships.append(
                {
                    "left_table": left_table,
                    "left_column": str(relationship.get("left_column", "")),
                    "right_table": right_table,
                    "right_column": str(relationship.get("right_column", "")),
                    "reason": "verified relationship between selected tables",
                }
            )
            _add_relevant_column(
                relevant_columns,
                left_table,
                str(relationship.get("left_column", "")),
                "join_key",
                "join key from selected relationship",
            )
            _add_relevant_column(
                relevant_columns,
                right_table,
                str(relationship.get("right_column", "")),
                "join_key",
                "join key from selected relationship",
            )

    if len(selected_table_names) > 1 and not selected_relationships:
        warnings.append("selected tables have no verified relationship")

    for candidate in retrieval.get("candidates", []):
        kind = str(candidate.get("kind", ""))
        knowledge_id = str(candidate.get("knowledge_id", ""))
        if kind != "table":
            continue
        table_name = knowledge_id.split(":")[-1]
        if table_name not in selected_table_names:
            dropped_candidates.append(
                {
                    "target_type": "table",
                    "target_name": table_name,
                    "reason": "covered_by_higher_confidence_candidate",
                    "score": float(candidate.get("score", 0.0)),
                }
            )

    return {
        "selected_tables": selected_tables,
        "relevant_columns": relevant_columns,
        "selected_relationships": selected_relationships,
        "value_bindings": selected_value_bindings,
        "evidence": evidence,
        "dropped_candidates": dropped_candidates,
        "warnings": warnings,
    }


def build_sql_generation_context(
    question: ProcessedQuestion,
    knowledge: ProcessedDatabaseKnowledge,
    linking: SchemaLinkingResult,
) -> SqlGenerationContext:
    return {
        "question": {
            "raw": str(question.get("raw", "")),
            "text": str(question.get("text", "")),
            "assumptions": list(question.get("assumptions", [])),
        },
        "schema_context": {
            "dialect": str(knowledge.get("dialect", "sqlite")),
            "tables": [
                {
                    "table_name": str(item.get("table_name", "")),
                    "role": str(item.get("role", "")),
                    "reason": str(item.get("reason", "")),
                }
                for item in linking.get("selected_tables", [])
            ],
            "columns": [
                {
                    "table_name": str(item.get("table_name", "")),
                    "column_name": str(item.get("column_name", "")),
                    "role": str(item.get("role", "")),
                    "reason": str(item.get("reason", "")),
                }
                for item in linking.get("relevant_columns", [])
            ],
            "relationships": [
                {
                    "left_table": str(item.get("left_table", "")),
                    "left_column": str(item.get("left_column", "")),
                    "right_table": str(item.get("right_table", "")),
                    "right_column": str(item.get("right_column", "")),
                    "reason": str(item.get("reason", "")),
                }
                for item in linking.get("selected_relationships", [])
            ],
            "value_bindings": list(linking.get("value_bindings", [])),
        },
        "semantic_context": {
            "business_terms": list(question.get("business_terms", [])),
            "assumptions": list(question.get("assumptions", [])),
        },
        "sql_policy": {
            "readonly_only": True,
            "allow_select_star": False,
            "require_limit": True,
            "default_limit": 100,
        },
        "output_contract": {
            "format": "sql_only",
            "requirements": [
                "Return only one SQL statement.",
                "Do not include markdown fences.",
                "Do not explain the SQL.",
            ],
        },
    }


__all__ = [
    "build_initial_processed_question",
    "build_knowledge_retrieval_result",
    "build_sample_processed_database_knowledge",
    "build_schema_linking_result",
    "build_sql_generation_context",
]
