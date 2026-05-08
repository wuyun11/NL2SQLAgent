from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from nl2sqlagent.platform.config import CheckpointerSection, WorkflowSection
from nl2sqlagent.platform.errors import ConfigurationError
from nl2sqlagent.platform.persistence import build_checkpointer


def test_build_checkpointer_returns_memory_saver() -> None:
    checkpointer = build_checkpointer(
        WorkflowSection(checkpointer=CheckpointerSection(provider="memory"))
    )

    assert isinstance(checkpointer, InMemorySaver)


def test_build_checkpointer_rejects_unknown_provider() -> None:
    with pytest.raises(ConfigurationError, match="checkpointer"):
        build_checkpointer(
            WorkflowSection(checkpointer=CheckpointerSection(provider="sqlite"))
        )
