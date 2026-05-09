from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.runtime_options import normalize_runtime_options


def test_normalize_runtime_options_defaults_to_empty_dict() -> None:
    assert normalize_runtime_options(None) == {}
    assert normalize_runtime_options({}) == {}


def test_normalize_runtime_options_keeps_allowed_bool_flags() -> None:
    assert normalize_runtime_options(
        {
            "force_check_error": True,
            "force_execute_error": False,
        }
    ) == {
        "force_check_error": True,
        "force_execute_error": False,
    }


def test_normalize_runtime_options_ignores_unknown_keys() -> None:
    assert normalize_runtime_options(
        {
            "force_check_error": True,
            "temperature": 0.1,
            "dialect": "sqlite",
            "schema": {"name": "demo"},
        }
    ) == {"force_check_error": True}


def test_normalize_runtime_options_ignores_non_bool_values() -> None:
    assert normalize_runtime_options(
        {
            "force_check_error": "true",
            "force_execute_error": 1,
        }
    ) == {}
