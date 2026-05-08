from __future__ import annotations

from pathlib import Path

from nl2sqlagent.platform.paths import (
    find_project_root,
    resolve_project_paths,
)


def test_find_project_root_prefers_explicit_path(tmp_path: Path) -> None:
    explicit = tmp_path / "project"
    explicit.mkdir()

    assert find_project_root(explicit) == explicit.resolve()


def test_find_project_root_searches_for_pyproject(tmp_path: Path) -> None:
    project = tmp_path / "project"
    child = project / "a" / "b"
    child.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    assert find_project_root(None, cwd=child) == project.resolve()


def test_resolve_project_paths_creates_base_directories(tmp_path: Path) -> None:
    paths = resolve_project_paths(
        project_root=tmp_path,
        workspace_dir="workspace",
        run_dir="workspace/runs",
        log_dir="workspace/logs",
    )

    assert paths.project_root == tmp_path.resolve()
    assert paths.workspace_dir == (tmp_path / "workspace").resolve()
    assert paths.run_dir == (tmp_path / "workspace" / "runs").resolve()
    assert paths.log_dir == (tmp_path / "workspace" / "logs").resolve()
    assert paths.workspace_dir.is_dir()
    assert paths.run_dir.is_dir()
    assert paths.log_dir.is_dir()
