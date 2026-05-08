from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from nl2sqlagent.workflows.hello.nodes import greet_node
from nl2sqlagent.workflows.hello.state import HelloGraphState


def build_hello_graph(*, checkpointer):
    graph = StateGraph(HelloGraphState)
    graph.add_node("greet", greet_node)
    graph.add_edge(START, "greet")
    graph.add_edge("greet", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["build_hello_graph"]
