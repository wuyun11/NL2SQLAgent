from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_date: str
    started_at: datetime


def create_run_context(
    *,
    run_id: str | None = None,
    now: datetime | None = None,
) -> RunContext:
    started_at = now or datetime.now()
    resolved_run_id = run_id.strip() if run_id is not None else ""
    if not resolved_run_id:
        resolved_run_id = f"run-{uuid4().hex[:8]}"
    return RunContext(
        run_id=resolved_run_id,
        run_date=started_at.strftime("%Y%m%d"),
        started_at=started_at,
    )


__all__ = ["RunContext", "create_run_context"]
