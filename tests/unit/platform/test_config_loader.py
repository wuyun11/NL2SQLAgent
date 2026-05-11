from __future__ import annotations

from pathlib import Path

import pytest

from nl2sqlagent.platform.config import load_app_config
from nl2sqlagent.platform.errors import ConfigurationError


def _write_config(config_dir: Path) -> None:
    config_dir.mkdir()
    (config_dir / "app.yml").write_text(
        "app:\n  name: TestAgent\n  environment: test\n",
        encoding="utf-8",
    )
    (config_dir / "env.yml").write_text(
        "\n".join(
            [
                "paths:",
                "  workspace_dir: workspace",
                "  run_dir: workspace/runs",
                "  log_dir: workspace/logs",
                "",
                "logging:",
                "  level: DEBUG",
                "  file_enabled: true",
                "  console_enabled: false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (config_dir / "workflow.yml").write_text(
        "workflow:\n  checkpointer:\n    provider: memory\n",
        encoding="utf-8",
    )
    (config_dir / "model.yml").write_text(
        "\n".join(
            [
                "model:",
                "  sql_generator:",
                "    provider: fake",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_load_app_config_reads_app_and_env_sections(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    _write_config(config_dir)

    config = load_app_config(config_dir=config_dir)

    assert config.app.name == "TestAgent"
    assert config.app.environment == "test"
    assert config.paths.workspace_dir == "workspace"
    assert config.paths.run_dir == "workspace/runs"
    assert config.paths.log_dir == "workspace/logs"
    assert config.logging.level == "DEBUG"
    assert config.logging.file_enabled is True
    assert config.logging.console_enabled is False
    assert config.workflow.checkpointer.provider == "memory"
    assert config.model.sql_generator.provider == "fake"
    assert config.model.sql_generator.fixed_sql == "SELECT 1 AS value"


def test_load_app_config_raises_for_missing_model_file(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yml").write_text(
        "app:\n  name: TestAgent\n  environment: test\n",
        encoding="utf-8",
    )
    (config_dir / "env.yml").write_text(
        "\n".join(
            [
                "paths:",
                "  workspace_dir: workspace",
                "  run_dir: workspace/runs",
                "  log_dir: workspace/logs",
                "",
                "logging:",
                "  level: DEBUG",
                "  file_enabled: true",
                "  console_enabled: false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (config_dir / "workflow.yml").write_text(
        "workflow:\n  checkpointer:\n    provider: memory\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="model.yml"):
        load_app_config(config_dir=config_dir)


def test_load_app_config_raises_for_missing_file(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yml").write_text(
        "app:\n  name: TestAgent\n  environment: test\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="env.yml"):
        load_app_config(config_dir=config_dir)


def test_load_app_config_raises_for_missing_workflow_file(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yml").write_text(
        "app:\n  name: TestAgent\n  environment: test\n",
        encoding="utf-8",
    )
    (config_dir / "env.yml").write_text(
        "\n".join(
            [
                "paths:",
                "  workspace_dir: workspace",
                "  run_dir: workspace/runs",
                "  log_dir: workspace/logs",
                "",
                "logging:",
                "  level: DEBUG",
                "  file_enabled: true",
                "  console_enabled: false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="workflow.yml"):
        load_app_config(config_dir=config_dir)
