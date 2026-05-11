from __future__ import annotations

import json
from pathlib import Path

from nl2sqlagent.interfaces.cli.main import main


def _write_config(project_root: Path, provider: str = "fake") -> None:
    config_dir = project_root / "config"
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
                "  level: INFO",
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
    if provider == "fake":
        model = "model:\n  sql_generator:\n    provider: fake\n"
    else:
        model = (
            "model:\n  sql_generator:\n    provider: openai_compatible\n"
            "    chat_model_name: qwen-max\n"
            "    base_url: https://example.invalid/v1\n"
            "    api_key_env: DASHSCOPE_API_KEY\n"
            "    temperature: 0\n"
            "    timeout_seconds: 30\n"
        )
    (config_dir / "model.yml").write_text(model, encoding="utf-8")
    (project_root / "pyproject.toml").write_text(
        "[project]\nname='test-agent'\n",
        encoding="utf-8",
    )


def test_cli_run_nl2sql_cases_with_fake_generator(tmp_path: Path, capsys) -> None:
    _write_config(tmp_path, provider="fake")
    exit_code = main(
        [
            "run-nl2sql-cases",
            "--project-root",
            str(tmp_path),
            "--run-id",
            "phase8-fake-cases",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out.strip())
    assert payload["run_id"] == "phase8-fake-cases"
    assert payload["real_llm"] is False
    assert len(payload["cases"]) == 6


def test_cli_run_nl2sql_cases_can_filter_case_id(tmp_path: Path, capsys) -> None:
    _write_config(tmp_path, provider="fake")
    exit_code = main(
        [
            "run-nl2sql-cases",
            "--project-root",
            str(tmp_path),
            "--case-id",
            "case_002_active_employee_by_department",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out.strip())
    assert [row["case_id"] for row in payload["cases"]] == [
        "case_002_active_employee_by_department"
    ]


def test_cli_run_nl2sql_cases_requires_real_llm_flag_for_provider_call(
    tmp_path: Path, capsys
) -> None:
    _write_config(tmp_path, provider="openai")
    exit_code = main(
        [
            "run-nl2sql-cases",
            "--project-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out.strip())
    assert payload["real_llm"] is False
