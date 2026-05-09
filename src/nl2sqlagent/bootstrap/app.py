from __future__ import annotations

from dataclasses import dataclass

from nl2sqlagent.platform.config import AppConfig
from nl2sqlagent.platform.logging import LoggingRuntime
from nl2sqlagent.platform.paths import ProjectPaths
from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql import Nl2SqlWorkflow
from nl2sqlagent.workflows.runtime import GraphRuntime


@dataclass(frozen=True)
class NL2SQLAgentApp:
    config: AppConfig
    paths: ProjectPaths
    logging: LoggingRuntime
    run_context: RunContext
    checkpointer: object
    graph_runtime: GraphRuntime
    nl2sql_workflow: Nl2SqlWorkflow


__all__ = ["NL2SQLAgentApp"]
