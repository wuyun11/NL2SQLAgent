from __future__ import annotations

from nl2sqlagent.workflows.hello.state import HelloGraphState


def greet_node(state: HelloGraphState) -> dict:
    name = state.get("name") or "world"
    return {
        "message": f"hello, {name}",
        "step_count": state.get("step_count", 0) + 1,
    }


__all__ = ["greet_node"]
