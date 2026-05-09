from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Nl2SqlStatus = Literal[
    "success",
    "needs_clarification",
    "failed",
    "rejected",
]


@dataclass(frozen=True)
class Nl2SqlOutput:
    status: Nl2SqlStatus
    message: str | None = None
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["Nl2SqlOutput", "Nl2SqlStatus"]
