from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from nl2sqlagent.workflows.nl2sql.edges import (
    route_after_check,
    route_after_execute,
    route_after_generate,
    route_after_normalize,
)
from nl2sqlagent.workflows.nl2sql.nodes import (
    build_prompt_node,
    check_sql_node,
    clarification_response_node,
    execute_sql_node,
    failed_response_node,
    generate_sql_node,
    normalize_question_node,
    success_response_node,
)
from nl2sqlagent.workflows.nl2sql.sql_generator import SqlGenerator
from nl2sqlagent.workflows.nl2sql.state import Nl2SqlGraphState


def build_nl2sql_graph(*, checkpointer, sql_generator: SqlGenerator):
    graph = StateGraph(Nl2SqlGraphState)
    graph.add_node("normalize_question", normalize_question_node)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node(
        "generate_sql",
        partial(generate_sql_node, sql_generator=sql_generator),
    )
    graph.add_node("check_sql", check_sql_node)
    graph.add_node("execute_sql", execute_sql_node)
    graph.add_node("clarification_response", clarification_response_node)
    graph.add_node("failed_response", failed_response_node)
    graph.add_node("success_response", success_response_node)

    graph.add_edge(START, "normalize_question")
    graph.add_conditional_edges(
        "normalize_question",
        route_after_normalize,
        {
            "clarification_response": "clarification_response",
            "build_prompt": "build_prompt",
        },
    )
    graph.add_edge("build_prompt", "generate_sql")
    graph.add_conditional_edges(
        "generate_sql",
        route_after_generate,
        {
            "failed_response": "failed_response",
            "check_sql": "check_sql",
        },
    )
    graph.add_conditional_edges(
        "check_sql",
        route_after_check,
        {
            "failed_response": "failed_response",
            "execute_sql": "execute_sql",
        },
    )
    graph.add_conditional_edges(
        "execute_sql",
        route_after_execute,
        {
            "failed_response": "failed_response",
            "success_response": "success_response",
        },
    )
    graph.add_edge("clarification_response", END)
    graph.add_edge("failed_response", END)
    graph.add_edge("success_response", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["build_nl2sql_graph"]
