from __future__ import annotations

from pathlib import Path

from nl2sqlagent.interfaces.cli.main import main


def _write_config(project_root: Path) -> None:
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
    (project_root / "pyproject.toml").write_text(
        "[project]\nname='test-agent'\n",
        encoding="utf-8",
    )


def test_startup_cli_outputs_summary_and_writes_log(
    tmp_path: Path,
    capsys,
) -> None:
    _write_config(tmp_path)

    exit_code = main(
        [
            "startup",
            "--project-root",
            str(tmp_path),
            "--run-id",
            "run-cli",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "TestAgent startup ready" in captured.out
    assert "run_id=run-cli" in captured.out
    log_dir_line = next(
        line for line in captured.out.splitlines() if line.startswith("log_dir=")
    )
    log_dir = Path(log_dir_line.removeprefix("log_dir="))
    assert log_dir.name == "run-cli"
    assert (log_dir / "app.log").exists()


def test_startup_cli_returns_nonzero_for_missing_config(
    tmp_path: Path,
    capsys,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='test-agent'\n",
        encoding="utf-8",
    )

    exit_code = main(["startup", "--project-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error:" in captured.err
