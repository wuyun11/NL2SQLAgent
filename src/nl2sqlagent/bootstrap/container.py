from __future__ import annotations

from pathlib import Path

from nl2sqlagent.bootstrap.app import NL2SQLAgentApp
from nl2sqlagent.platform.config import load_app_config
from nl2sqlagent.platform.config.models import SqlGeneratorSection
from nl2sqlagent.platform.errors import ConfigurationError
from nl2sqlagent.platform.logging import build_logger
from nl2sqlagent.platform.paths import (
    find_project_root,
    resolve_project_paths,
)
from nl2sqlagent.platform.persistence import build_checkpointer
from nl2sqlagent.platform.runtime import create_run_context
from nl2sqlagent.workflows.nl2sql import (
    Nl2SqlWorkflow,
    build_nl2sql_graph,
)
from nl2sqlagent.workflows.nl2sql.sql_generator import (
    FakeSqlGenerator,
    OpenAICompatibleSqlGenerator,
    SqlGenerator,
)
from nl2sqlagent.workflows.runtime import GraphRuntime


def build_sql_generator(
    *,
    sql_generator: SqlGeneratorSection,
    project_root: Path,
) -> SqlGenerator:
    if sql_generator.provider == "fake":
        return FakeSqlGenerator(sql=sql_generator.fixed_sql or "SELECT 1 AS value")
    if sql_generator.provider == "openai_compatible":
        if sql_generator.chat_model_name is None:
            raise ConfigurationError("model.sql_generator.chat_model_name is required")
        if not sql_generator.base_url:
            raise ConfigurationError("model.sql_generator.base_url is required")
        if not sql_generator.api_key_env:
            raise ConfigurationError("model.sql_generator.api_key_env is required")
        if sql_generator.temperature is None:
            raise ConfigurationError("model.sql_generator.temperature is required")
        if sql_generator.timeout_seconds is None:
            raise ConfigurationError("model.sql_generator.timeout_seconds is required")
        return OpenAICompatibleSqlGenerator(
            chat_model_name=sql_generator.chat_model_name,
            base_url=sql_generator.base_url,
            api_key_env=sql_generator.api_key_env,
            temperature=sql_generator.temperature,
            timeout_seconds=sql_generator.timeout_seconds,
            project_root=project_root,
        )
    raise ConfigurationError(
        f"unsupported model.sql_generator.provider: {sql_generator.provider!r}"
    )


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
    sql_generator = build_sql_generator(
        sql_generator=config.model.sql_generator,
        project_root=resolved_project_root,
    )
    nl2sql_graph = build_nl2sql_graph(
        checkpointer=checkpointer,
        sql_generator=sql_generator,
    )
    nl2sql_workflow = Nl2SqlWorkflow(
        graph=nl2sql_graph,
        graph_runtime=graph_runtime,
        run_context=run_context,
        log_dir=logging_runtime.log_dir,
        logger=logging_runtime.logger,
    )
    return NL2SQLAgentApp(
        config=config,
        paths=paths,
        logging=logging_runtime,
        run_context=run_context,
        checkpointer=checkpointer,
        graph_runtime=graph_runtime,
        nl2sql_workflow=nl2sql_workflow,
    )


__all__ = ["build_app", "build_sql_generator"]
