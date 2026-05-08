from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from nl2sqlagent.platform.config.models import (
    AppConfig,
    AppSection,
    CheckpointerSection,
    LoggingSection,
    PathsSection,
    WorkflowSection,
)
from nl2sqlagent.platform.errors import ConfigurationError


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"config file not found: {path.name}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"failed to read config file: {path}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigurationError(f"config file must contain a mapping: {path.name}")
    return data


def _mapping(data: dict[str, Any], key: str, *, file_name: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigurationError(f"config section '{key}' is required in {file_name}")
    return value


def _string(data: dict[str, Any], key: str, *, section: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"config field '{section}.{key}' must be a string")
    return value.strip()


def _boolean(data: dict[str, Any], key: str, *, section: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ConfigurationError(f"config field '{section}.{key}' must be a boolean")
    return value


def load_app_config(config_dir: Path | None = None) -> AppConfig:
    resolved_config_dir = Path("config") if config_dir is None else config_dir
    app_data = _load_yaml_file(resolved_config_dir / "app.yml")
    env_data = _load_yaml_file(resolved_config_dir / "env.yml")
    workflow_data = _load_yaml_file(resolved_config_dir / "workflow.yml")

    app_section = _mapping(app_data, "app", file_name="app.yml")
    paths_section = _mapping(env_data, "paths", file_name="env.yml")
    logging_section = _mapping(env_data, "logging", file_name="env.yml")
    workflow_section = _mapping(workflow_data, "workflow", file_name="workflow.yml")
    checkpointer_section = _mapping(
        workflow_section,
        "checkpointer",
        file_name="workflow.yml",
    )

    return AppConfig(
        app=AppSection(
            name=_string(app_section, "name", section="app"),
            environment=_string(app_section, "environment", section="app"),
        ),
        paths=PathsSection(
            workspace_dir=_string(paths_section, "workspace_dir", section="paths"),
            run_dir=_string(paths_section, "run_dir", section="paths"),
            log_dir=_string(paths_section, "log_dir", section="paths"),
        ),
        logging=LoggingSection(
            level=_string(logging_section, "level", section="logging"),
            file_enabled=_boolean(logging_section, "file_enabled", section="logging"),
            console_enabled=_boolean(
                logging_section,
                "console_enabled",
                section="logging",
            ),
        ),
        workflow=WorkflowSection(
            checkpointer=CheckpointerSection(
                provider=_string(
                    checkpointer_section,
                    "provider",
                    section="workflow.checkpointer",
                ),
            ),
        ),
    )


__all__ = ["load_app_config"]
