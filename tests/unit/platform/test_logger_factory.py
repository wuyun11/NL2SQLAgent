from __future__ import annotations

from pathlib import Path

from nl2sqlagent.platform.logging import build_logger


def test_build_logger_creates_run_log_directory_and_file(tmp_path: Path) -> None:
    runtime = build_logger(
        app_name="TestAgent",
        level="INFO",
        base_log_dir=tmp_path / "logs",
        run_date="20260508",
        run_id="run-test",
        file_enabled=True,
        console_enabled=False,
    )

    runtime.logger.info("hello")

    assert runtime.log_dir == tmp_path / "logs" / "20260508" / "run-test"
    assert runtime.app_log_file == runtime.log_dir / "app.log"
    assert runtime.app_log_file.exists()
    assert "hello" in runtime.app_log_file.read_text(encoding="utf-8")


def test_build_logger_clears_existing_handlers(tmp_path: Path) -> None:
    first = build_logger(
        app_name="RepeatAgent",
        level="INFO",
        base_log_dir=tmp_path / "logs",
        run_date="20260508",
        run_id="run-one",
        file_enabled=True,
        console_enabled=False,
    )
    first_handler_count = len(first.logger.handlers)

    second = build_logger(
        app_name="RepeatAgent",
        level="INFO",
        base_log_dir=tmp_path / "logs",
        run_date="20260508",
        run_id="run-two",
        file_enabled=True,
        console_enabled=False,
    )

    assert len(second.logger.handlers) == first_handler_count
    assert second.logger.propagate is False
