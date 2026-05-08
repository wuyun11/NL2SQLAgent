from __future__ import annotations


def resolve_thread_id(
    *,
    run_id: str,
    thread_id: str | None = None,
) -> str:
    resolved_run_id = run_id.strip()
    if not resolved_run_id:
        raise ValueError("run_id is required to resolve thread_id")

    if thread_id is not None:
        resolved_thread_id = thread_id.strip()
        if resolved_thread_id:
            return resolved_thread_id

    return f"thread-{resolved_run_id}"


__all__ = ["resolve_thread_id"]
