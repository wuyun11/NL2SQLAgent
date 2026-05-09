from __future__ import annotations

from typing import Any

from nl2sqlagent.workflows.nl2sql.prompt_payload import Nl2SqlPromptPayload


def _bool_text(value: object) -> str:
    return "true" if value is True else "false"


def _render_schema_context(schema_context: dict[str, Any]) -> list[str]:
    lines = [
        f"Dialect: {schema_context.get('dialect', '')}",
        "Allowed tables:",
    ]
    for table in schema_context.get("tables", []):
        lines.append(f"- Table: {table.get('name', '')}")
        description = table.get("description")
        if description:
            lines.append(f"  Description: {description}")
        lines.append("  Columns:")
        for column in table.get("columns", []):
            lines.append(
                "  - "
                f"{column.get('name', '')} "
                f"({column.get('type', '')}): "
                f"{column.get('description', '')}"
            )

    relationships = schema_context.get("relationships") or []
    if relationships:
        lines.append("Relationships:")
        for relationship in relationships:
            if isinstance(relationship, dict):
                lines.append(
                    "- "
                    f"{relationship.get('left_table', '')}.{relationship.get('left_column', '')} = "
                    f"{relationship.get('right_table', '')}.{relationship.get('right_column', '')}"
                )
            else:
                lines.append(f"- {relationship}")
    else:
        lines.append("Relationships: none")

    value_bindings = schema_context.get("value_bindings") or []
    if value_bindings:
        lines.append("Value Bindings:")
        for value_binding in value_bindings:
            lines.append(
                "- "
                f"{value_binding.get('business_term', '')} -> "
                f"{value_binding.get('table_name', '')}.{value_binding.get('column_name', '')} "
                f"{value_binding.get('operator', '=')} {value_binding.get('value', '')}"
            )
    else:
        lines.append("Value Bindings: none")
    return lines


def _render_semantic_context(semantic_context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for term in semantic_context.get("business_terms", []):
        lines.append(f"- Term {term.get('name', '')}: {term.get('description', '')}")
    for rule in semantic_context.get("rules", []):
        lines.append(f"- Rule: {rule}")
    for assumption in semantic_context.get("assumptions", []):
        lines.append(f"- Assumption: {assumption}")
    return lines or ["- none"]


def _render_sql_policy(sql_policy: dict[str, Any]) -> list[str]:
    return [
        f"- Readonly only: {_bool_text(sql_policy.get('readonly_only'))}",
        f"- SELECT * allowed: {_bool_text(sql_policy.get('allow_select_star'))}",
        f"- LIMIT required: {_bool_text(sql_policy.get('require_limit'))}",
        f"- Default LIMIT: {sql_policy.get('default_limit')}",
    ]


def _render_output_contract(output_contract: dict[str, Any]) -> list[str]:
    return [f"- {requirement}" for requirement in output_contract.get("requirements", [])]


def render_final_prompt(prompt_payload: Nl2SqlPromptPayload) -> str:
    task = prompt_payload["task"]
    question = prompt_payload["question"]
    schema_context = prompt_payload["schema_context"]
    semantic_context = prompt_payload["semantic_context"]
    sql_policy = prompt_payload["sql_policy"]
    output_contract = prompt_payload["output_contract"]

    sections: list[str] = [
        "You are an NL2SQL assistant.",
        "",
        "Task:",
        str(task["goal"]),
        "",
        "User Question:",
        str(question["normalized"]),
        "",
        "Schema Context:",
        *_render_schema_context(schema_context),
        "",
        "Semantic Context:",
        *_render_semantic_context(semantic_context),
        "",
        "SQL Policy:",
        *_render_sql_policy(sql_policy),
        "",
        "Output Contract:",
        *_render_output_contract(output_contract),
    ]
    return "\n".join(sections)


__all__ = ["render_final_prompt"]
