from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from nl2sqlagent.platform.config import WorkflowSection
from nl2sqlagent.platform.errors import ConfigurationError


def build_checkpointer(config: WorkflowSection) -> InMemorySaver:
    provider = config.checkpointer.provider.strip().lower()
    if provider == "memory":
        return InMemorySaver()
    raise ConfigurationError(
        f"unsupported workflow.checkpointer.provider: {config.checkpointer.provider}"
    )


__all__ = ["build_checkpointer"]
