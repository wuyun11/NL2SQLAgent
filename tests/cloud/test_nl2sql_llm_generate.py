from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from nl2sqlagent.platform.config import CheckpointerSection, WorkflowSection
from nl2sqlagent.platform.persistence import build_checkpointer
from nl2sqlagent.platform.paths import find_project_root
from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql import Nl2SqlInput, Nl2SqlWorkflow, build_nl2sql_graph
from nl2sqlagent.workflows.nl2sql.sql_generator import OpenAICompatibleSqlGenerator
from nl2sqlagent.workflows.runtime import GraphRuntime

pytestmark = pytest.mark.cloud


@pytest.mark.skipif(
    not os.environ.get("DASHSCOPE_API_KEY"),
    reason="DASHSCOPE_API_KEY not set",
)
def test_nl2sql_cloud_llm_returns_sql_like_text(tmp_path: Path) -> None:
    project_root = find_project_root(Path(__file__))
    gen = OpenAICompatibleSqlGenerator(
        chat_model_name="glm-5",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        temperature=0.0,
        timeout_seconds=120,
        project_root=project_root,
    )
    checkpointer = build_checkpointer(
        WorkflowSection(checkpointer=CheckpointerSection(provider="memory"))
    )
    graph = build_nl2sql_graph(checkpointer=checkpointer, sql_generator=gen)
    workflow = Nl2SqlWorkflow(
        graph=graph,
        graph_runtime=GraphRuntime(),
        run_context=RunContext(
            run_id="run-cloud-nl2sql",
            run_date="20260511",
            started_at=datetime(2026, 5, 11, 9, 0, 0),
        ),
        log_dir=tmp_path / "logs" / "20260511" / "run-cloud-nl2sql",
    )

    output = workflow.run(
        Nl2SqlInput(question="仅回复 SQL：查询 1 加 1 的和，SQLite，单列别名 value"),
        thread_id="thread-cloud-nl2sql",
    )

    assert output.status == "success"
    assert output.sql
    assert "select" in output.sql.lower()
    assert output.metadata["llm_result"]["model_name"] == "glm-5"
    assert output.metadata["llm_result"]["raw_text"]
