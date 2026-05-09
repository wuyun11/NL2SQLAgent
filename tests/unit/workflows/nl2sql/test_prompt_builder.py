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
    build_mock_prompt_payload,
    build_prompt_payload_from_sql_generation_context,
)


def _payload() -> dict:
    return build_mock_prompt_payload(
        raw_question="  统计员工数量  ",
        normalized_question="统计员工数量",
    )


def test_render_final_prompt_contains_expected_sections() -> None:
    final_prompt = render_final_prompt(_payload())

    assert "You are an NL2SQL assistant." in final_prompt
    assert "Task:" in final_prompt
    assert "User Question:" in final_prompt
    assert "Schema Context:" in final_prompt
    assert "Semantic Context:" in final_prompt
    assert "SQL Policy:" in final_prompt
    assert "Output Contract:" in final_prompt


def test_render_final_prompt_keeps_section_order_stable() -> None:
    final_prompt = render_final_prompt(_payload())

    assert final_prompt.index("Task:") < final_prompt.index("User Question:")
    assert final_prompt.index("User Question:") < final_prompt.index("Schema Context:")
    assert final_prompt.index("Schema Context:") < final_prompt.index("Semantic Context:")
    assert final_prompt.index("Semantic Context:") < final_prompt.index("SQL Policy:")
    assert final_prompt.index("SQL Policy:") < final_prompt.index("Output Contract:")


def test_render_final_prompt_uses_normalized_question_and_allowed_tables() -> None:
    final_prompt = render_final_prompt(_payload())

    assert "统计员工数量" in final_prompt
    assert "Allowed tables:" in final_prompt
    assert "- Table: employee" in final_prompt
    assert "Description: mock employee table" in final_prompt
    assert "- id (INTEGER): employee id" in final_prompt
    assert "- name (TEXT): employee name" in final_prompt


def test_render_final_prompt_separates_semantic_context_and_sql_policy() -> None:
    final_prompt = render_final_prompt(_payload())

    assert "- Term 员工: mock business term for employee" in final_prompt
    assert "- Rule: Use only active records when such flag is available." in final_prompt
    assert "- Assumption: No extra business filter is applied in Phase 3 mock prompt." in final_prompt
    assert "- Readonly only: true" in final_prompt
    assert "- SELECT * allowed: false" in final_prompt
    assert "- LIMIT required: true" in final_prompt
    assert "- Default LIMIT: 100" in final_prompt


def test_render_final_prompt_instructs_no_markdown_fences_without_using_fences() -> None:
    final_prompt = render_final_prompt(_payload())

    assert "- Return only one SQL statement." in final_prompt
    assert "- Do not include markdown fences." in final_prompt
    assert "- Do not explain the SQL." in final_prompt
    assert "```" not in final_prompt


def test_render_final_prompt_does_not_render_debug() -> None:
    final_prompt = render_final_prompt(_payload())

    assert "Debug:" not in final_prompt
    assert "phase3.mock.v1" not in final_prompt
    assert "mock_prompt_payload_builder" not in final_prompt


def test_render_final_prompt_renders_relationships_and_value_bindings_from_sql_context() -> None:
    question = build_initial_processed_question("按部门统计在职员工人数")
    knowledge = build_sample_processed_database_knowledge()
    retrieval = build_knowledge_retrieval_result(question, knowledge)
    linking = build_schema_linking_result(question, knowledge, retrieval)
    context = build_sql_generation_context(question, knowledge, linking)
    final_prompt = render_final_prompt(
        build_prompt_payload_from_sql_generation_context(context)
    )

    assert "Relationships:" in final_prompt
    assert "- emp_stat_cd (filter): required by value binding" in final_prompt
    assert "- emp_id (measure): metric hint employee_count" in final_prompt
    assert "- dept_nm (dimension): dimension hint department" in final_prompt
    assert "hr_emp_base.dept_id = hr_dept_dim.dept_id" in final_prompt
    assert "Value Bindings:" in final_prompt
    assert "在职员工 -> hr_emp_base.emp_stat_cd = ACTIVE" in final_prompt
    assert "dropped_candidates" not in final_prompt
    assert "retrieval_method" not in final_prompt
    assert "vector_score" not in final_prompt
    assert "chunk_id" not in final_prompt
