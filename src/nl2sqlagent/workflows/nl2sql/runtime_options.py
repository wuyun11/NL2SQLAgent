from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict


class Nl2SqlRuntimeOptions(TypedDict, total=False):
    force_check_error: bool
    force_execute_error: bool


_ALLOWED_BOOL_KEYS = (
    "force_check_error",
    "force_execute_error",
)


def normalize_runtime_options(
    options: Mapping[str, object] | None,
) -> Nl2SqlRuntimeOptions:
    normalized: Nl2SqlRuntimeOptions = {}
    if not options:
        return normalized

    for key in _ALLOWED_BOOL_KEYS:
        value = options.get(key)
        if isinstance(value, bool):
            normalized[key] = value
    return normalized


__all__ = ["Nl2SqlRuntimeOptions", "normalize_runtime_options"]
