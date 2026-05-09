from __future__ import annotations

from nl2sqlagent.workflows.nl2sql.edges import (
    route_after_check,
    route_after_execute,
    route_after_normalize,
)


def test_route_after_normalize_uses_clarification_message_only() -> None:
    assert (
        route_after_normalize(
            {
                "clarification_message": "Please provide a question.",
                "status": "running",
            }
        )
        == "clarification_response"
    )


def test_route_after_normalize_without_clarification_builds_prompt() -> None:
    assert route_after_normalize({"normalized_question": "统计员工数量"}) == "build_prompt"


def test_route_after_check_goes_failed_when_check_error_exists() -> None:
    assert route_after_check({"check_error": "mock check error"}) == "failed_response"


def test_route_after_check_goes_execute_when_no_check_error() -> None:
    assert route_after_check({"checked_sql": "SELECT 1"}) == "execute_sql"


def test_route_after_execute_goes_failed_when_execute_error_exists() -> None:
    assert route_after_execute({"execute_error": "mock execute error"}) == "failed_response"


def test_route_after_execute_goes_success_when_no_execute_error() -> None:
    assert route_after_execute({"result_rows": [{"value": 1}]}) == "success_response"
