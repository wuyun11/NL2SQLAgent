from __future__ import annotations

from dataclasses import dataclass
import logging
from logging import Logger
from pathlib import Path


@dataclass(frozen=True)
class LoggingRuntime:
    logger: Logger
    log_dir: Path
    app_log_file: Path | None


def _log_level(level: str) -> int:
    normalized = level.strip().upper()
    value = getattr(logging, normalized, None)
    if not isinstance(value, int):
        return logging.INFO
    return value


def build_logger(
    *,
    app_name: str,
    level: str,
    base_log_dir: Path,
    run_date: str,
    run_id: str,
    file_enabled: bool,
    console_enabled: bool,
) -> LoggingRuntime:
    log_dir = base_log_dir / run_date / run_id
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(app_name)
    logger.handlers.clear()
    logger.setLevel(_log_level(level))
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    app_log_file: Path | None = None
    if file_enabled:
        app_log_file = log_dir / "app.log"
        file_handler = logging.FileHandler(app_log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return LoggingRuntime(
        logger=logger,
        log_dir=log_dir,
        app_log_file=app_log_file,
    )


__all__ = ["LoggingRuntime", "build_logger"]
