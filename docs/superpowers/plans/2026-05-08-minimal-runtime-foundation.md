# Minimal Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest NL2SQLAgent runtime foundation: config loading, path resolution, run context, logger, bootstrap app, and CLI `startup`.

**Architecture:** Keep Phase 0 deliberately tiny. Create only the package metadata and files listed here. Do not create workflows, domain, services, integrations, LangGraph, LLM, database, vectorstore, token usage, or business code. `bootstrap` wires `config -> run_context -> paths -> logger -> app`; CLI only calls `build_app()` and prints startup summary.

**Tech Stack:** Python 3.12, dataclasses, pathlib, argparse, logging, PyYAML, pytest, src-layout package.

---

## 0. Scope Guard

This plan implements `docs/temp/最小运行底座设计.md`.

Allowed to create:

```text
pyproject.toml
config/app.yml
config/env.yml
src/nl2sqlagent/platform/**
src/nl2sqlagent/bootstrap/**
src/nl2sqlagent/interfaces/cli/**
tests/unit/platform/**
tests/integration/test_startup_cli.py
```

Forbidden in this phase:

```text
workflows/
domain/
services/
integrations/
LangGraph
LLM
database
vectorstore
embedding
token usage
LangSmith
request_id
thread_id
trace_id
business NL2SQL logic
```

Before any Python command, follow repository rule:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
```

If `.ai/local/python_path.txt` is missing, stop and ask the user to create it with the local project Python path.

---

## 1. Target File Structure

Create:

```text
pyproject.toml
config/app.yml
config/env.yml

src/nl2sqlagent/__init__.py

src/nl2sqlagent/platform/__init__.py
src/nl2sqlagent/platform/errors.py
src/nl2sqlagent/platform/paths.py
src/nl2sqlagent/platform/config/__init__.py
src/nl2sqlagent/platform/config/models.py
src/nl2sqlagent/platform/config/loader.py
src/nl2sqlagent/platform/runtime/__init__.py
src/nl2sqlagent/platform/runtime/run_context.py
src/nl2sqlagent/platform/logging/__init__.py
src/nl2sqlagent/platform/logging/logger_factory.py

src/nl2sqlagent/bootstrap/__init__.py
src/nl2sqlagent/bootstrap/app.py
src/nl2sqlagent/bootstrap/container.py

src/nl2sqlagent/interfaces/__init__.py
src/nl2sqlagent/interfaces/cli/__init__.py
src/nl2sqlagent/interfaces/cli/main.py
src/nl2sqlagent/interfaces/cli/commands/__init__.py
src/nl2sqlagent/interfaces/cli/commands/startup.py

tests/unit/platform/test_config_loader.py
tests/unit/platform/test_paths.py
tests/unit/platform/test_run_context.py
tests/unit/platform/test_logger_factory.py
tests/integration/test_startup_cli.py
```

Responsibilities:

```text
platform/errors.py
  Project-level exception classes only.

platform/config/models.py
  Frozen dataclass config models.

platform/config/loader.py
  Read config/app.yml and config/env.yml into AppConfig.

platform/paths.py
  Resolve project_root and base workspace/run/log directories.

platform/runtime/run_context.py
  Generate run_id, run_date, started_at.

platform/logging/logger_factory.py
  Build console/file logger for the current run.

bootstrap/app.py
  Define NL2SQLAgentApp dataclass.

bootstrap/container.py
  Build config, run_context, paths, logger, app.

interfaces/cli/main.py
  argparse entrypoint and error handling.

interfaces/cli/commands/startup.py
  Startup command implementation.
```

---

## Task 1: Project Metadata And Minimal Config Files

**Files:**

- Create: `pyproject.toml`
- Create: `config/app.yml`
- Create: `config/env.yml`
- Create: `src/nl2sqlagent/__init__.py`

- [ ] **Step 1: Create package metadata**

Create `pyproject.toml`:

```toml
[project]
name = "nl2sqlagent"
version = "0.1.0"
description = "NL2SQLAgent runtime foundation"
requires-python = ">=3.12"
dependencies = [
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create default config files**

Create `config/app.yml`:

```yaml
app:
  name: NL2SQLAgent
  environment: local
```

Create `config/env.yml`:

```yaml
paths:
  workspace_dir: workspace
  run_dir: workspace/runs
  log_dir: workspace/logs

logging:
  level: INFO
  file_enabled: true
  console_enabled: true
```

- [ ] **Step 3: Create root package marker**

Create `src/nl2sqlagent/__init__.py`:

```python
__all__: list[str] = []
```

- [ ] **Step 4: Verify package can be discovered**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -c "import nl2sqlagent; print('ok')"
```

Expected:

```text
ok
```

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml config src/nl2sqlagent/__init__.py
git commit -m "chore: scaffold minimal runtime package"
```

---

## Task 2: Platform Errors

**Files:**

- Create: `src/nl2sqlagent/platform/__init__.py`
- Create: `src/nl2sqlagent/platform/errors.py`

- [ ] **Step 1: Create platform package marker**

Create `src/nl2sqlagent/platform/__init__.py`:

```python
__all__: list[str] = []
```

- [ ] **Step 2: Implement minimal project errors**

Create `src/nl2sqlagent/platform/errors.py`:

```python
from __future__ import annotations


class NL2SQLAgentError(Exception):
    """Base project error."""


class ConfigurationError(NL2SQLAgentError):
    """Raised when config is missing or invalid."""


class StartupError(NL2SQLAgentError):
    """Raised when application startup fails."""


__all__ = [
    "ConfigurationError",
    "NL2SQLAgentError",
    "StartupError",
]
```

- [ ] **Step 3: Run import smoke**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -c "from nl2sqlagent.platform.errors import ConfigurationError, StartupError; print(ConfigurationError.__name__, StartupError.__name__)"
```

Expected:

```text
ConfigurationError StartupError
```

- [ ] **Step 4: Commit**

```powershell
git add src/nl2sqlagent/platform
git commit -m "chore: add platform error types"
```

---

## Task 3: Config Models And Loader

**Files:**

- Create: `src/nl2sqlagent/platform/config/__init__.py`
- Create: `src/nl2sqlagent/platform/config/models.py`
- Create: `src/nl2sqlagent/platform/config/loader.py`
- Test: `tests/unit/platform/test_config_loader.py`

- [ ] **Step 1: Write config loader tests**

Create `tests/unit/platform/test_config_loader.py`:

```python
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


def test_load_app_config_raises_for_missing_file(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yml").write_text(
        "app:\n  name: TestAgent\n  environment: test\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="env.yml"):
        load_app_config(config_dir=config_dir)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_config_loader.py -v
```

Expected:

```text
FAIL because platform.config does not exist.
```

- [ ] **Step 3: Implement config models**

Create `src/nl2sqlagent/platform/config/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppSection:
    name: str
    environment: str


@dataclass(frozen=True)
class PathsSection:
    workspace_dir: str
    run_dir: str
    log_dir: str


@dataclass(frozen=True)
class LoggingSection:
    level: str
    file_enabled: bool
    console_enabled: bool


@dataclass(frozen=True)
class AppConfig:
    app: AppSection
    paths: PathsSection
    logging: LoggingSection


__all__ = [
    "AppConfig",
    "AppSection",
    "LoggingSection",
    "PathsSection",
]
```

- [ ] **Step 4: Implement config loader**

Create `src/nl2sqlagent/platform/config/loader.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from nl2sqlagent.platform.config.models import (
    AppConfig,
    AppSection,
    LoggingSection,
    PathsSection,
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


def load_app_config(config_dir: Path | None = None) -> AppConfig:
    resolved_config_dir = Path("config") if config_dir is None else config_dir
    app_data = _load_yaml_file(resolved_config_dir / "app.yml")
    env_data = _load_yaml_file(resolved_config_dir / "env.yml")

    app_section = _mapping(app_data, "app", file_name="app.yml")
    paths_section = _mapping(env_data, "paths", file_name="env.yml")
    logging_section = _mapping(env_data, "logging", file_name="env.yml")

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
            file_enabled=_boolean(
                logging_section,
                "file_enabled",
                section="logging",
            ),
            console_enabled=_boolean(
                logging_section,
                "console_enabled",
                section="logging",
            ),
        ),
    )


__all__ = ["load_app_config"]
```

- [ ] **Step 5: Export config API**

Create `src/nl2sqlagent/platform/config/__init__.py`:

```python
from nl2sqlagent.platform.config.loader import load_app_config
from nl2sqlagent.platform.config.models import (
    AppConfig,
    AppSection,
    LoggingSection,
    PathsSection,
)

__all__ = [
    "AppConfig",
    "AppSection",
    "LoggingSection",
    "PathsSection",
    "load_app_config",
]
```

- [ ] **Step 6: Run config tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_config_loader.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Commit**

```powershell
git add src/nl2sqlagent/platform/config tests/unit/platform/test_config_loader.py
git commit -m "feat: add minimal config loader"
```

---

## Task 4: Run Context

**Files:**

- Create: `src/nl2sqlagent/platform/runtime/__init__.py`
- Create: `src/nl2sqlagent/platform/runtime/run_context.py`
- Test: `tests/unit/platform/test_run_context.py`

- [ ] **Step 1: Write run context tests**

Create `tests/unit/platform/test_run_context.py`:

```python
from __future__ import annotations

from datetime import datetime
import re

from nl2sqlagent.platform.runtime import create_run_context


def test_create_run_context_uses_explicit_run_id() -> None:
    now = datetime(2026, 5, 8, 16, 30, 0)

    context = create_run_context(run_id="manual-run", now=now)

    assert context.run_id == "manual-run"
    assert context.run_date == "20260508"
    assert context.started_at == now


def test_create_run_context_generates_short_prefixed_run_id() -> None:
    now = datetime(2026, 5, 8, 16, 30, 0)

    context = create_run_context(now=now)

    assert re.fullmatch(r"run-[0-9a-f]{8}", context.run_id)
    assert context.run_date == "20260508"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_run_context.py -v
```

Expected:

```text
FAIL because platform.runtime does not exist.
```

- [ ] **Step 3: Implement run context**

Create `src/nl2sqlagent/platform/runtime/run_context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_date: str
    started_at: datetime


def create_run_context(
    *,
    run_id: str | None = None,
    now: datetime | None = None,
) -> RunContext:
    started_at = now or datetime.now()
    resolved_run_id = run_id.strip() if run_id is not None else ""
    if not resolved_run_id:
        resolved_run_id = f"run-{uuid4().hex[:8]}"
    return RunContext(
        run_id=resolved_run_id,
        run_date=started_at.strftime("%Y%m%d"),
        started_at=started_at,
    )


__all__ = ["RunContext", "create_run_context"]
```

- [ ] **Step 4: Export runtime API**

Create `src/nl2sqlagent/platform/runtime/__init__.py`:

```python
from nl2sqlagent.platform.runtime.run_context import (
    RunContext,
    create_run_context,
)

__all__ = ["RunContext", "create_run_context"]
```

- [ ] **Step 5: Run run context tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_run_context.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/platform/runtime tests/unit/platform/test_run_context.py
git commit -m "feat: add run context"
```

---

## Task 5: Project Paths

**Files:**

- Create: `src/nl2sqlagent/platform/paths.py`
- Test: `tests/unit/platform/test_paths.py`

- [ ] **Step 1: Write path tests**

Create `tests/unit/platform/test_paths.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_paths.py -v
```

Expected:

```text
FAIL because platform.paths does not exist.
```

- [ ] **Step 3: Implement path helpers**

Create `src/nl2sqlagent/platform/paths.py`:

```python
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
```

- [ ] **Step 4: Run path tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_paths.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/platform/paths.py tests/unit/platform/test_paths.py
git commit -m "feat: add project path resolution"
```

---

## Task 6: Logger Factory

**Files:**

- Create: `src/nl2sqlagent/platform/logging/__init__.py`
- Create: `src/nl2sqlagent/platform/logging/logger_factory.py`
- Test: `tests/unit/platform/test_logger_factory.py`

- [ ] **Step 1: Write logger tests**

Create `tests/unit/platform/test_logger_factory.py`:

```python
from __future__ import annotations

import logging
from pathlib import Path

from nl2sqlagent.platform.logging import build_logger


def test_build_logger_creates_run_log_directory_and_file(tmp_path: Path) -> None:
    runtime = build_logger(
        app_name="TestAgent",
        level="INFO",
        base_log_dir=tmp_path / "logs",
        run_date="20260508",
        run_id="run-test",
        file_enabled=True,
        console_enabled=False,
    )

    runtime.logger.info("hello")

    assert runtime.log_dir == tmp_path / "logs" / "20260508" / "run-test"
    assert runtime.app_log_file == runtime.log_dir / "app.log"
    assert runtime.app_log_file.exists()
    assert "hello" in runtime.app_log_file.read_text(encoding="utf-8")


def test_build_logger_clears_existing_handlers(tmp_path: Path) -> None:
    first = build_logger(
        app_name="RepeatAgent",
        level="INFO",
        base_log_dir=tmp_path / "logs",
        run_date="20260508",
        run_id="run-one",
        file_enabled=True,
        console_enabled=False,
    )
    first_handler_count = len(first.logger.handlers)

    second = build_logger(
        app_name="RepeatAgent",
        level="INFO",
        base_log_dir=tmp_path / "logs",
        run_date="20260508",
        run_id="run-two",
        file_enabled=True,
        console_enabled=False,
    )

    assert len(second.logger.handlers) == first_handler_count
    assert second.logger.propagate is False
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_logger_factory.py -v
```

Expected:

```text
FAIL because platform.logging does not exist.
```

- [ ] **Step 3: Implement logger factory**

Create `src/nl2sqlagent/platform/logging/logger_factory.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import logging
from logging import Logger
from pathlib import Path


@dataclass(frozen=True)
class LoggingRuntime:
    logger: Logger
    log_dir: Path
    app_log_file: Path | None


def _log_level(level: str) -> int:
    normalized = level.strip().upper()
    value = getattr(logging, normalized, None)
    if not isinstance(value, int):
        return logging.INFO
    return value


def build_logger(
    *,
    app_name: str,
    level: str,
    base_log_dir: Path,
    run_date: str,
    run_id: str,
    file_enabled: bool,
    console_enabled: bool,
) -> LoggingRuntime:
    log_dir = base_log_dir / run_date / run_id
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(app_name)
    logger.handlers.clear()
    logger.setLevel(_log_level(level))
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    app_log_file: Path | None = None
    if file_enabled:
        app_log_file = log_dir / "app.log"
        file_handler = logging.FileHandler(app_log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return LoggingRuntime(
        logger=logger,
        log_dir=log_dir,
        app_log_file=app_log_file,
    )


__all__ = ["LoggingRuntime", "build_logger"]
```

- [ ] **Step 4: Export logging API**

Create `src/nl2sqlagent/platform/logging/__init__.py`:

```python
from nl2sqlagent.platform.logging.logger_factory import (
    LoggingRuntime,
    build_logger,
)

__all__ = ["LoggingRuntime", "build_logger"]
```

- [ ] **Step 5: Run logger tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/unit/platform/test_logger_factory.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit**

```powershell
git add src/nl2sqlagent/platform/logging tests/unit/platform/test_logger_factory.py
git commit -m "feat: add minimal logger factory"
```

---

## Task 7: Bootstrap App And Container

**Files:**

- Create: `src/nl2sqlagent/bootstrap/__init__.py`
- Create: `src/nl2sqlagent/bootstrap/app.py`
- Create: `src/nl2sqlagent/bootstrap/container.py`

- [ ] **Step 1: Implement app model**

Create `src/nl2sqlagent/bootstrap/app.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from nl2sqlagent.platform.config import AppConfig
from nl2sqlagent.platform.logging import LoggingRuntime
from nl2sqlagent.platform.paths import ProjectPaths
from nl2sqlagent.platform.runtime import RunContext


@dataclass(frozen=True)
class NL2SQLAgentApp:
    config: AppConfig
    paths: ProjectPaths
    logging: LoggingRuntime
    run_context: RunContext


__all__ = ["NL2SQLAgentApp"]
```

- [ ] **Step 2: Implement container**

Create `src/nl2sqlagent/bootstrap/container.py`:

```python
from __future__ import annotations

from pathlib import Path

from nl2sqlagent.bootstrap.app import NL2SQLAgentApp
from nl2sqlagent.platform.config import load_app_config
from nl2sqlagent.platform.logging import build_logger
from nl2sqlagent.platform.paths import (
    find_project_root,
    resolve_project_paths,
)
from nl2sqlagent.platform.runtime import create_run_context


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
    return NL2SQLAgentApp(
        config=config,
        paths=paths,
        logging=logging_runtime,
        run_context=run_context,
    )


__all__ = ["build_app"]
```

- [ ] **Step 3: Export bootstrap API**

Create `src/nl2sqlagent/bootstrap/__init__.py`:

```python
from nl2sqlagent.bootstrap.app import NL2SQLAgentApp
from nl2sqlagent.bootstrap.container import build_app

__all__ = ["NL2SQLAgentApp", "build_app"]
```

- [ ] **Step 4: Run import smoke**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -c "from nl2sqlagent.bootstrap import build_app; app = build_app(run_id='run-smoke'); print(app.run_context.run_id)"
```

Expected:

```text
run-smoke
```

- [ ] **Step 5: Commit**

```powershell
git add src/nl2sqlagent/bootstrap
git commit -m "feat: add minimal app bootstrap"
```

---

## Task 8: CLI Startup

**Files:**

- Create: `src/nl2sqlagent/interfaces/__init__.py`
- Create: `src/nl2sqlagent/interfaces/cli/__init__.py`
- Create: `src/nl2sqlagent/interfaces/cli/main.py`
- Create: `src/nl2sqlagent/interfaces/cli/commands/__init__.py`
- Create: `src/nl2sqlagent/interfaces/cli/commands/startup.py`
- Test: `tests/integration/test_startup_cli.py`

- [ ] **Step 1: Write CLI integration tests**

Create `tests/integration/test_startup_cli.py`:

```python
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
```

Note: The first test should not assert the generated run_date because `main()` uses current time unless the implementation injects `now`. Parse `log_dir=` from stdout and assert `app.log` exists under that concrete directory.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/integration/test_startup_cli.py -v
```

Expected:

```text
FAIL because interfaces.cli does not exist.
```

- [ ] **Step 3: Create package markers**

Create:

```text
src/nl2sqlagent/interfaces/__init__.py
src/nl2sqlagent/interfaces/cli/__init__.py
src/nl2sqlagent/interfaces/cli/commands/__init__.py
```

Each file:

```python
__all__: list[str] = []
```

- [ ] **Step 4: Implement startup command**

Create `src/nl2sqlagent/interfaces/cli/commands/startup.py`:

```python
from __future__ import annotations

from pathlib import Path

from nl2sqlagent.bootstrap import build_app


def startup_summary(
    *,
    project_root: Path | None = None,
    config_dir: Path | None = None,
    run_id: str | None = None,
) -> str:
    app = build_app(
        project_root=project_root,
        config_dir=config_dir,
        run_id=run_id,
    )
    app.logging.logger.info("%s startup ready", app.config.app.name)
    return "\n".join(
        [
            f"{app.config.app.name} startup ready",
            f"run_id={app.run_context.run_id}",
            f"run_date={app.run_context.run_date}",
            f"log_dir={app.logging.log_dir}",
        ]
    )


__all__ = ["startup_summary"]
```

- [ ] **Step 5: Implement CLI main**

Create `src/nl2sqlagent/interfaces/cli/main.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from nl2sqlagent.interfaces.cli.commands.startup import startup_summary
from nl2sqlagent.platform.errors import NL2SQLAgentError


def _path(value: str | None) -> Path | None:
    if value is None:
        return None
    return Path(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NL2SQLAgent CLI")
    parser.add_argument(
        "command",
        nargs="?",
        default="startup",
        choices=("startup",),
        help="command to run",
    )
    parser.add_argument("--project-root", help="project root directory")
    parser.add_argument("--config-dir", help="config directory")
    parser.add_argument("--run-id", help="optional run id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "startup":
            print(
                startup_summary(
                    project_root=_path(args.project_root),
                    config_dir=_path(args.config_dir),
                    run_id=args.run_id,
                )
            )
            return 0
    except NL2SQLAgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run CLI tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest tests/integration/test_startup_cli.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Run manual startup**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m nl2sqlagent.interfaces.cli.main startup --project-root . --run-id run-manual
```

Expected:

```text
NL2SQLAgent startup ready
run_id=run-manual
run_date=<today in YYYYMMDD>
log_dir=<absolute path ending with workspace\logs\<run_date>\run-manual>
```

- [ ] **Step 8: Commit**

```powershell
git add src/nl2sqlagent/interfaces tests/integration/test_startup_cli.py
git commit -m "feat: add startup cli"
```

---

## Task 9: Final Verification

**Files:**

- All Phase 0 files

- [ ] **Step 1: Run all tests**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m pytest -v
```

Expected:

```text
All tests pass.
```

- [ ] **Step 2: Compile source**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m compileall src/nl2sqlagent
```

Expected:

```text
No SyntaxError.
```

- [ ] **Step 3: Run startup command**

Run:

```powershell
$python = (Get-Content -Raw .\.ai\local\python_path.txt).Trim()
& $python -m nl2sqlagent.interfaces.cli.main startup --project-root . --run-id run-final-check
```

Expected:

```text
Startup summary is printed.
workspace/logs/<run_date>/run-final-check/app.log exists.
```

- [ ] **Step 4: Confirm forbidden directories were not created**

Run:

```powershell
Test-Path .\src\nl2sqlagent\workflows
Test-Path .\src\nl2sqlagent\domain
Test-Path .\src\nl2sqlagent\services
Test-Path .\src\nl2sqlagent\integrations
```

Expected:

```text
False
False
False
False
```

- [ ] **Step 5: Diff check**

Run:

```powershell
git diff --check
```

Expected:

```text
No trailing whitespace errors.
```

- [ ] **Step 6: Final status**

Run:

```powershell
git -c core.quotepath=false status --short
```

Expected:

```text
Only intentional files are modified or untracked.
```

- [ ] **Step 7: Commit final verification notes if needed**

No extra commit is required if all earlier task commits are already clean. If small fixes were needed during final verification:

```powershell
git add <fixed files>
git commit -m "fix: stabilize minimal runtime foundation"
```

---

## Final Report Template

When complete, report:

```text
Implemented Phase 0 minimal runtime foundation.

What changed:
- Added src-layout package metadata.
- Added config loader for app.yml/env.yml.
- Added project path resolution.
- Added run context.
- Added logger factory.
- Added bootstrap app/container.
- Added startup CLI.

Verification:
- pytest -v: passed
- compileall src/nl2sqlagent: passed
- startup CLI manual check: passed
- Forbidden directories not created: confirmed

Remaining:
- LangGraph/thread_id/checkpoint intentionally deferred to Phase 1.
- LLM/database/vectorstore/business logic intentionally deferred.
```

