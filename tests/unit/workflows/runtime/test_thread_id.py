from __future__ import annotations

import pytest

from nl2sqlagent.workflows.runtime import resolve_thread_id


def test_resolve_thread_id_uses_explicit_value() -> None:
    assert (
        resolve_thread_id(run_id="run-a1b2c3d4", thread_id=" custom-thread ")
        == "custom-thread"
    )


def test_resolve_thread_id_falls_back_for_blank_thread_id() -> None:
    assert (
        resolve_thread_id(run_id="run-a1b2c3d4", thread_id="   ")
        == "thread-run-a1b2c3d4"
    )


def test_resolve_thread_id_falls_back_when_not_provided() -> None:
    assert resolve_thread_id(run_id="run-a1b2c3d4") == "thread-run-a1b2c3d4"


def test_resolve_thread_id_rejects_blank_run_id() -> None:
    with pytest.raises(ValueError, match="run_id"):
        resolve_thread_id(run_id="   ")
