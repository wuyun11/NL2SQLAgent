from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    workspace_dir: Path
    run_dir: Path
    log_dir: Path


def find_project_root(
    project_root: Path | None = None,
    *,
    cwd: Path | None = None,
) -> Path:
    if project_root is not None:
        return project_root.resolve()

    current = (cwd or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate
    return current


def _resolve_path(project_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def resolve_project_paths(
    *,
    project_root: Path,
    workspace_dir: str,
    run_dir: str,
    log_dir: str,
) -> ProjectPaths:
    resolved_root = project_root.resolve()
    paths = ProjectPaths(
        project_root=resolved_root,
        workspace_dir=_resolve_path(resolved_root, workspace_dir),
        run_dir=_resolve_path(resolved_root, run_dir),
        log_dir=_resolve_path(resolved_root, log_dir),
    )
    paths.workspace_dir.mkdir(parents=True, exist_ok=True)
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    paths.log_dir.mkdir(parents=True, exist_ok=True)
    return paths


__all__ = [
    "ProjectPaths",
    "find_project_root",
    "resolve_project_paths",
]
