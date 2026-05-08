from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppSection:
    name: str
    environment: str


@dataclass(frozen=True)
class PathsSection:
    workspace_dir: str
    run_dir: str
    log_dir: str


@dataclass(frozen=True)
class LoggingSection:
    level: str
    file_enabled: bool
    console_enabled: bool


@dataclass(frozen=True)
class AppConfig:
    app: AppSection
    paths: PathsSection
    logging: LoggingSection


__all__ = [
    "AppConfig",
    "AppSection",
    "LoggingSection",
    "PathsSection",
]
