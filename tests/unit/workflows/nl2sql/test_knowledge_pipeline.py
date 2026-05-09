from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.knowledge_pipeline import (
    build_initial_processed_question,
    build_knowledge_retrieval_result,
    build_sample_processed_database_knowledge,
    build_schema_linking_result,
    build_sql_generation_context,
)
from nl2sqlagent.workflows.nl2sql.prompt_builder import render_final_prompt
from nl2sqlagent.workflows.nl2sql.prompt_payload import (
    build_prompt_payload_from_sql_generation_context,
)


def test_build_initial_processed_question_for_employee_department_question() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")

    assert question["raw"] == "按部门统计在职员工人数"
    assert question["text"] == "按部门统计在职员工人数"
    assert "在职员工" in question["business_terms"]
    assert "employee_count" in question["metric_hints"]
    assert "department" in question["dimension_hints"]
    assert "active_employee" in question["filter_hints"]


def test_sample_processed_database_knowledge_contains_verified_hr_relationship() -> None:
    knowledge = build_sample_processed_database_knowledge()

    assert knowledge["dialect"] == "sqlite"
    assert any(table["name"] == "hr_emp_base" for table in knowledge["tables"])
    assert any(table["name"] == "hr_dept_dim" for table in knowledge["tables"])
    assert any(
        relationship["left_table"] == "hr_emp_base"
        and relationship["right_table"] == "hr_dept_dim"
        and relationship["verified"] is True
        for relationship in knowledge["relationships"]
    )


def test_structured_retrieval_finds_tables_columns_and_value_binding() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()

    result = build_knowledge_retrieval_result(question, knowledge)
    pairs = {(item["kind"], item["knowledge_id"]) for item in result["candidates"]}

    assert ("table", "table:hr_emp_base") in pairs
    assert ("table", "table:hr_dept_dim") in pairs
    assert ("column", "column:hr_emp_base.emp_stat_cd") in pairs
    assert ("value_binding", "value:active_employee") in pairs
    assert all(item["retrieval_method"] == "structured" for item in result["candidates"])


def test_schema_linking_promotes_employee_question_candidates() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)

    result = build_schema_linking_result(question, knowledge, retrieval)

    assert [table["table_name"] for table in result["selected_tables"]] == [
        "hr_emp_base",
        "hr_dept_dim",
    ]
    assert {
        (column["table_name"], column["column_name"], column["role"])
        for column in result["relevant_columns"]
    } >= {
        ("hr_emp_base", "emp_id", "measure"),
        ("hr_emp_base", "dept_id", "join_key"),
        ("hr_emp_base", "emp_stat_cd", "filter"),
        ("hr_dept_dim", "dept_id", "join_key"),
        ("hr_dept_dim", "dept_nm", "dimension"),
    }
    assert result["selected_relationships"] == [
        {
            "left_table": "hr_emp_base",
            "left_column": "dept_id",
            "right_table": "hr_dept_dim",
            "right_column": "dept_id",
            "reason": "verified relationship between selected tables",
        }
    ]
    assert result["value_bindings"][0]["business_term"] == "在职员工"


def test_schema_linking_keeps_unselected_candidates_out_of_selected_context() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)
    retrieval["candidates"].append(
        {
            "kind": "table",
            "knowledge_id": "table:finance_salary_month",
            "score": 0.2,
            "matched_terms": ["人数"],
            "retrieval_method": "structured",
            "match_source": "description",
            "reason": "low confidence unrelated candidate for boundary test",
        }
    )

    result = build_schema_linking_result(question, knowledge, retrieval)

    assert "finance_salary_month" not in [item["table_name"] for item in result["selected_tables"]]
    assert any(item["target_name"] == "finance_salary_month" for item in result["dropped_candidates"])


def test_schema_linking_does_not_add_sample_hr_context_without_candidates_or_hints() -> None:
    question = {
        "raw": "无关问题",
        "text": "无关问题",
        "keywords": [],
        "business_terms": [],
        "metric_hints": [],
        "dimension_hints": [],
        "filter_hints": [],
        "time_hints": [],
        "assumptions": [],
    }
    knowledge = build_sample_processed_database_knowledge()

    result = build_schema_linking_result(
        question,
        knowledge,
        {"candidates": [], "warnings": [], "metadata": {}},
    )

    assert result["selected_tables"] == []
    assert result["relevant_columns"] == []
    assert result["selected_relationships"] == []


def test_sql_generation_context_is_clean_prompt_input() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)
    linking = build_schema_linking_result(question, knowledge, retrieval)

    context = build_sql_generation_context(question, knowledge, linking)

    assert context["question"]["text"] == "按部门统计在职员工人数"
    assert context["schema_context"]["dialect"] == "sqlite"
    assert context["schema_context"]["value_bindings"] == linking["value_bindings"]
    assert "在职员工" in context["semantic_context"]["business_terms"]
    assert context["sql_policy"]["readonly_only"] is True
    assert context["output_contract"]["format"] == "sql_only"
    serialized = str(context)
    assert "dropped_candidates" not in serialized
    assert "retrieval_method" not in serialized
    assert "vector_score" not in serialized
    assert "chunk_id" not in serialized


def test_prompt_boundary_dropped_candidate_never_enters_context_or_prompt() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)
    retrieval["candidates"].append(
        {
            "kind": "table",
            "knowledge_id": "table:finance_salary_month",
            "score": 0.2,
            "matched_terms": ["人数"],
            "retrieval_method": "structured",
            "match_source": "description",
            "reason": "low confidence unrelated candidate for boundary test",
        }
    )
    linking = build_schema_linking_result(question, knowledge, retrieval)
    context = build_sql_generation_context(question, knowledge, linking)
    payload = build_prompt_payload_from_sql_generation_context(context)
    final_prompt = render_final_prompt(payload)

    assert any(item["target_name"] == "finance_salary_month" for item in linking["dropped_candidates"])
    assert "finance_salary_month" not in str(context)
    assert "finance_salary_month" not in str(payload)
    assert "finance_salary_month" not in final_prompt
    assert "dropped_candidates" not in final_prompt


def test_pseudo_vector_candidate_cannot_bypass_schema_linking_result() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)
    retrieval["candidates"].append(
        {
            "kind": "table",
            "knowledge_id": "table:sys_user_log",
            "score": 0.99,
            "matched_terms": ["员工"],
            "retrieval_method": "vector",
            "match_source": "document",
            "raw_ref": {"vector_score": 0.99, "chunk_id": "chunk-1"},
            "reason": "pseudo vector candidate for boundary test",
        }
    )
    linking = build_schema_linking_result(question, knowledge, retrieval)
    context = build_sql_generation_context(question, knowledge, linking)
    payload = build_prompt_payload_from_sql_generation_context(context)
    final_prompt = render_final_prompt(payload)

    assert any(item["knowledge_id"] == "table:sys_user_log" for item in retrieval["candidates"])
    assert any(item["target_name"] == "sys_user_log" for item in linking["dropped_candidates"])
    assert "sys_user_log" not in str(context)
    assert "vector_score" not in str(payload)
    assert "chunk_id" not in str(payload)
    assert "vector_score" not in final_prompt
    assert "chunk_id" not in final_prompt
