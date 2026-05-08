from __future__ import annotations

from pathlib import Path

from nl2sqlagent.bootstrap.app import NL2SQLAgentApp
from nl2sqlagent.platform.config import load_app_config
from nl2sqlagent.platform.logging import build_logger
from nl2sqlagent.platform.paths import (
    find_project_root,
    resolve_project_paths,
)
from nl2sqlagent.platform.persistence import build_checkpointer
from nl2sqlagent.platform.runtime import create_run_context
from nl2sqlagent.workflows.runtime import GraphRuntime


def build_app(
    *,
    project_root: Path | None = None,
    config_dir: Path | None = None,
    run_id: str | None = None,
) -> NL2SQLAgentApp:
    resolved_project_root = find_project_root(project_root)
    if config_dir is None:
        resolved_config_dir = resolved_project_root / "config"
    elif config_dir.is_absolute():
        resolved_config_dir = config_dir
    else:
        resolved_config_dir = resolved_project_root / config_dir
    config = load_app_config(config_dir=resolved_config_dir)
    run_context = create_run_context(run_id=run_id)
    paths = resolve_project_paths(
        project_root=resolved_project_root,
        workspace_dir=config.paths.workspace_dir,
        run_dir=config.paths.run_dir,
        log_dir=config.paths.log_dir,
    )
    logging_runtime = build_logger(
        app_name=config.app.name,
        level=config.logging.level,
        base_log_dir=paths.log_dir,
        run_date=run_context.run_date,
        run_id=run_context.run_id,
        file_enabled=config.logging.file_enabled,
        console_enabled=config.logging.console_enabled,
    )
    checkpointer = build_checkpointer(config.workflow)
    graph_runtime = GraphRuntime()
    return NL2SQLAgentApp(
        config=config,
        paths=paths,
        logging=logging_runtime,
        run_context=run_context,
        checkpointer=checkpointer,
        graph_runtime=graph_runtime,
    )


__all__ = ["build_app"]
