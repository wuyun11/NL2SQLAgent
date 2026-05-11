from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from nl2sqlagent.platform.config.models import (
    AppConfig,
    AppSection,
    CheckpointerSection,
    LoggingSection,
    ModelSection,
    PathsSection,
    SqlGeneratorSection,
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


def _positive_int(data: dict[str, Any], key: str, *, section: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"config field '{section}.{key}' must be an integer")
    if value <= 0:
        raise ConfigurationError(f"config field '{section}.{key}' must be positive")
    return value


def _finite_float(data: dict[str, Any], key: str, *, section: str) -> float:
    value = data.get(key)
    if isinstance(value, bool):
        raise ConfigurationError(f"config field '{section}.{key}' must be a number")
    if isinstance(value, int | float):
        return float(value)
    raise ConfigurationError(f"config field '{section}.{key}' must be a number")


def _load_sql_generator_section(data: dict[str, Any]) -> SqlGeneratorSection:
    section = "model.sql_generator"
    provider = _string(data, "provider", section=section)
    if provider == "fake":
        fixed = data.get("fixed_sql")
        if fixed is None:
            fixed_sql = "SELECT 1 AS value"
        elif isinstance(fixed, str) and fixed.strip():
            fixed_sql = fixed.strip()
        else:
            raise ConfigurationError(
                f"config field '{section}.fixed_sql' must be a non-empty string when set"
            )
        return SqlGeneratorSection(provider=provider, fixed_sql=fixed_sql)
    if provider == "openai_compatible":
        return SqlGeneratorSection(
            provider=provider,
            chat_model_name=_string(data, "chat_model_name", section=section),
            base_url=_string(data, "base_url", section=section),
            api_key_env=_string(data, "api_key_env", section=section),
            temperature=_finite_float(data, "temperature", section=section),
            timeout_seconds=_positive_int(data, "timeout_seconds", section=section),
        )
    raise ConfigurationError(f"unsupported {section}.provider: {provider!r}")


def load_app_config(config_dir: Path | None = None) -> AppConfig:
    resolved_config_dir = Path("config") if config_dir is None else config_dir
    app_data = _load_yaml_file(resolved_config_dir / "app.yml")
    env_data = _load_yaml_file(resolved_config_dir / "env.yml")
    workflow_data = _load_yaml_file(resolved_config_dir / "workflow.yml")
    model_data = _load_yaml_file(resolved_config_dir / "model.yml")

    app_section = _mapping(app_data, "app", file_name="app.yml")
    paths_section = _mapping(env_data, "paths", file_name="env.yml")
    logging_section = _mapping(env_data, "logging", file_name="env.yml")
    workflow_section = _mapping(workflow_data, "workflow", file_name="workflow.yml")
    checkpointer_section = _mapping(
        workflow_section,
        "checkpointer",
        file_name="workflow.yml",
    )
    model_section = _mapping(model_data, "model", file_name="model.yml")
    sql_generator_section = _mapping(
        model_section,
        "sql_generator",
        file_name="model.yml",
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
        model=ModelSection(
            sql_generator=_load_sql_generator_section(sql_generator_section),
        ),
    )


__all__ = ["load_app_config"]
