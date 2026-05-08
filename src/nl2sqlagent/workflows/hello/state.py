from __future__ import annotations

from typing import TypedDict


class HelloGraphState(TypedDict, total=False):
    name: str
    message: str
    step_count: int


__all__ = ["HelloGraphState"]
