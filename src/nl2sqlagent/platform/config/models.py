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
class CheckpointerSection:
    provider: str


@dataclass(frozen=True)
class WorkflowSection:
    checkpointer: CheckpointerSection


@dataclass(frozen=True)
class SqlGeneratorSection:
    provider: str
    fixed_sql: str | None = None
    chat_model_name: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    temperature: float | None = None
    timeout_seconds: int | None = None


@dataclass(frozen=True)
class ModelSection:
    sql_generator: SqlGeneratorSection


@dataclass(frozen=True)
class AppConfig:
    app: AppSection
    paths: PathsSection
    logging: LoggingSection
    workflow: WorkflowSection
    model: ModelSection


__all__ = [
    "AppConfig",
    "AppSection",
    "CheckpointerSection",
    "LoggingSection",
    "ModelSection",
    "PathsSection",
    "SqlGeneratorSection",
    "WorkflowSection",
]
