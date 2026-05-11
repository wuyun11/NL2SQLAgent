from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nl2sqlagent.workflows.nl2sql.knowledge_contracts import (
    ProcessedDatabaseKnowledge,
    ProcessedQuestion,
)


@dataclass(frozen=True)
class Nl2SqlInput:
    question: str
    request_id: str | None = None
    user_id: str | None = None
    database_key: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    case_id: str | None = None
    processed_question: ProcessedQuestion | None = None
    processed_database_knowledge: ProcessedDatabaseKnowledge | None = None


__all__ = ["Nl2SqlInput"]
