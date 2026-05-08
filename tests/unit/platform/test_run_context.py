from __future__ import annotations

from datetime import datetime
import re

from nl2sqlagent.platform.runtime import create_run_context


def test_create_run_context_uses_explicit_run_id() -> None:
    now = datetime(2026, 5, 8, 16, 30, 0)

    context = create_run_context(run_id="manual-run", now=now)

    assert context.run_id == "manual-run"
    assert context.run_date == "20260508"
    assert context.started_at == now


def test_create_run_context_generates_short_prefixed_run_id() -> None:
    now = datetime(2026, 5, 8, 16, 30, 0)

    context = create_run_context(now=now)

    assert re.fullmatch(r"run-[0-9a-f]{8}", context.run_id)
    assert context.run_date == "20260508"
