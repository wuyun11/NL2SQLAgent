from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Nl2SqlInput:
    question: str
    request_id: str | None = None
    user_id: str | None = None
    database_key: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


__all__ = ["Nl2SqlInput"]
