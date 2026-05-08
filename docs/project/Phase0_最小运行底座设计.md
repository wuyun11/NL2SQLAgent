# 最小运行底座设计

> 本文只讨论新项目最小运行底座。
>
> 不讨论 NL2SQL 业务流程，不讨论 LangGraph graph，不讨论 token 统计，不讨论 LangSmith，不讨论 LLM，不讨论数据库，不讨论向量库。
>
> 核心目标：先让项目具备稳定的配置、路径、日志、错误、运行上下文、bootstrap 和 CLI startup 能力。这个底座要足够小，但后续接入 LangGraph、LLM、数据库时不用推倒重来。

## 1. 当前阶段目标

第一阶段只解决一个问题：

```text
新项目如何稳定启动，并形成统一的运行上下文。
```

也就是先跑通：

```text
CLI startup
  -> load config
  -> resolve paths
  -> build logger
  -> create run context
  -> build app
  -> output startup summary
```

第一阶段不追求：

```text
调用 LLM
运行 LangGraph
连接数据库
写入向量库
统计 token
生成 SQL
执行 SQL
```

## 2. 第一阶段目录结构

建议第一阶段只创建这些目录和文件：

```text
src/nl2sqlagent/
  platform/
    config/
      __init__.py
      models.py
      loader.py
    logging/
      __init__.py
      logger_factory.py
    runtime/
      __init__.py
      run_context.py
    paths.py
    errors.py

  bootstrap/
    __init__.py
    app.py
    container.py

  interfaces/
    cli/
      __init__.py
      main.py
      commands/
        __init__.py
        startup.py

config/
  app.yml
  env.yml

tests/
  unit/
    platform/
      test_config_loader.py
      test_paths.py
      test_run_context.py
  integration/
    test_startup_cli.py
```

暂时不创建：

```text
workflows/
domain/
services/
integrations/
```

这些目录后续一定会有，但第一阶段先不创建，避免空目录和空抽象诱导 AI 过早补业务代码。

## 3. 分层职责

### 3.1 platform

`platform` 是项目运行底座。

第一阶段只包含：

```text
config
logging
runtime
paths
errors
```

它负责：

```text
配置读取
路径解析
日志创建
运行上下文创建
统一错误类型
```

它不负责：

```text
业务流程
LangGraph invoke
LLM 调用
数据库连接
向量库连接
token 统计
```

### 3.2 bootstrap

`bootstrap` 负责装配应用。

第一阶段只装配：

```text
config
paths
logger
run_context
```

它不装配：

```text
LLM
database
vectorstore
workflow graph
service
```

### 3.3 interfaces

`interfaces` 是外部入口。

第一阶段只做 CLI startup。

CLI 负责：

```text
解析参数
调用 build_app
输出 startup summary
返回 exit code
```

CLI 不负责：

```text
读配置细节
创建 logger
创建运行目录
决定业务流程
```

## 4. 配置设计

第一阶段只需要两个配置文件：

```text
config/app.yml
config/env.yml
```

### 4.1 app.yml

建议内容：

```yaml
app:
  name: NL2SQLAgent
  environment: local
```

### 4.2 env.yml

建议内容：

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

### 4.3 配置模型

建议在 `platform/config/models.py` 中定义：

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
```

### 4.4 配置读取规则

`platform/config/loader.py` 负责：

```text
1. 读取 config/app.yml。
2. 读取 config/env.yml。
3. 合并成 AppConfig。
4. 如果配置缺失，抛 ConfigurationError。
5. 不做任何外部连接。
```

配置读取函数建议：

```python
def load_app_config(config_dir: Path | None = None) -> AppConfig:
    ...
```

第一阶段不要支持复杂 override。

暂时不要做：

```text
环境变量覆盖
多环境配置继承
命令行动态覆盖
远程配置中心
```

这些以后需要时再加。

## 5. 路径设计

`platform/paths.py` 负责把配置里的相对路径解析成绝对路径。

建议模型：

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
```

职责：

```text
1. 找到 project_root。
2. 将 workspace_dir / run_dir / log_dir 解析为绝对路径。
3. 创建必要目录。
```

建议函数：

```python
def resolve_project_paths(
    *,
    project_root: Path,
    workspace_dir: str,
    run_dir: str,
    log_dir: str,
) -> ProjectPaths:
    ...
```

路径规则：

```text
1. 配置中可以写相对路径。
2. 相对路径以 project_root 为基准。
3. 代码内部使用绝对 Path。
4. 不在业务代码里拼字符串路径。
5. ProjectPaths.log_dir 表示基础日志目录，不表示本次运行日志目录。
```

`project_root` 查找规则：

```text
1. 如果 build_app(project_root=...) 显式传入，则使用该路径。
2. 否则从当前工作目录向上查找 pyproject.toml。
3. 如果找不到 pyproject.toml，则使用 Path.cwd()。
```

这条规则用于避免测试或从子目录运行 CLI 时，配置路径和 workspace 路径漂移。

## 6. 运行上下文设计

`platform/runtime/run_context.py` 负责一次运行的基础身份。

第一阶段只需要：

```text
run_id
run_date
started_at
```

建议模型：

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_date: str
    started_at: datetime
```

建议函数：

```python
def create_run_context(
    *,
    run_id: str | None = None,
    now: datetime | None = None,
) -> RunContext:
    ...
```

规则：

```text
1. run_date 格式为 YYYYMMDD。
2. 如果外部没有传 run_id，则自动生成短 ID。
3. run_id 只表达一次 app/command 运行，不等于 LangGraph thread_id。
4. 第一阶段不引入 request_id / thread_id / trace_id。
5. 默认 run_id 格式建议为 run-短随机ID，例如 run-a1b2c3d4。
```

`request_id`、`thread_id`、`trace_id` 等到接入 CLI ask / LangGraph 后再引入。

## 7. 日志设计

`platform/logging/logger_factory.py` 负责创建 logger。

第一阶段只做普通 Python logging。

建议日志文件：

```text
workspace/logs/{run_date}/{run_id}/app.log
```

建议模型：

```python
from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
from pathlib import Path


@dataclass(frozen=True)
class LoggingRuntime:
    logger: Logger
    log_dir: Path
    app_log_file: Path | None
```

建议函数：

```python
def build_logger(
    *,
    app_name: str,
    level: str,
    log_dir: Path,
    file_enabled: bool,
    console_enabled: bool,
) -> LoggingRuntime:
    ...
```

第一阶段日志只负责：

```text
启动日志
配置加载完成
路径解析完成
startup command 成功 / 失败
```

第一阶段不要做：

```text
chain log
node log
token summary
LangSmith trace
JSON structured logging
复杂 log rotation
```

这些等业务和 LangGraph 接入后再定。

日志路径边界：

```text
ProjectPaths.log_dir
  基础日志目录，例如 workspace/logs。

LoggingRuntime.log_dir
  本次运行日志目录，例如 workspace/logs/20260508/run-a1b2c3d4。
```

实现规则：

```text
1. build_logger 必须先清理同名 logger 的已有 handlers，避免测试或多次 build_app 时重复输出。
2. build_logger 必须设置 logger.propagate = False，避免日志被 root logger 重复处理。
3. 文件日志启用时，app_log_file 指向 LoggingRuntime.log_dir / "app.log"。
```

## 8. 错误设计

`platform/errors.py` 定义项目级异常。

第一阶段只需要：

```python
class NL2SQLAgentError(Exception):
    """Base project error."""


class ConfigurationError(NL2SQLAgentError):
    """Raised when config is missing or invalid."""


class StartupError(NL2SQLAgentError):
    """Raised when application startup fails."""
```

后续再补：

```text
WorkflowError
IntegrationError
PolicyViolationError
```

不要第一阶段就定义一大堆尚未使用的异常。

## 9. Bootstrap 设计

### 9.1 app.py

第一阶段的应用对象只需要：

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
```

### 9.2 container.py

第一阶段装配流程：

```text
load config
create run context
resolve paths
build logger
return NL2SQLAgentApp
```

说明：

```text
create run context 必须早于 build logger，因为本次运行日志目录需要 run_date / run_id。
resolve paths 只解析基础目录；本次运行日志目录由 build_logger 根据 run_context 创建。
```

建议函数：

```python
def build_app(
    *,
    project_root: Path | None = None,
    config_dir: Path | None = None,
    run_id: str | None = None,
) -> NL2SQLAgentApp:
    ...
```

注意：

```text
container 可以调用 config / paths / runtime / logging。
container 不做业务判断。
container 不引入 LangGraph。
container 不创建 LLM / database / vectorstore。
```

## 10. CLI startup 设计

### 10.1 CLI 命令

第一阶段只做：

```text
python -m nl2sqlagent.interfaces.cli.main startup
```

可选参数：

```text
--run-id
--config-dir
--project-root
```

### 10.2 startup 输出

建议输出：

```text
NL2SQLAgent startup ready
run_id=...
run_date=...
log_dir=...
```

### 10.3 main.py 职责

`interfaces/cli/main.py` 负责：

```text
1. 创建 argparse parser。
2. 分发 startup command。
3. 捕获 NL2SQLAgentError。
4. 返回合适 exit code。
```

CLI 路径规则：

```text
--project-root 用于显式指定项目根目录。
--config-dir 如果是相对路径，则以 project_root 为基准解析。
```

### 10.4 commands/startup.py 职责

`commands/startup.py` 负责：

```text
1. 调用 build_app。
2. 写一条 startup ready 日志。
3. 返回 startup summary 字符串。
```

## 11. 第一阶段测试

第一阶段测试只覆盖运行底座。

### 11.1 config loader

测试：

```text
能读取 app.yml + env.yml。
缺失配置时报 ConfigurationError。
```

### 11.2 paths

测试：

```text
相对路径按 project_root 解析。
必要目录会创建。
返回值都是绝对 Path。
```

### 11.3 run_context

测试：

```text
自动生成 run_id。
run_date 为 YYYYMMDD。
显式 run_id 会被保留。
```

### 11.4 startup CLI

测试：

```text
startup 返回 exit code 0。
输出包含 startup ready / run_id / log_dir。
日志文件存在。
```

### 11.5 logger factory

测试：

```text
多次 build_logger 使用同一个 app_name 时，不会重复添加 handler。
logger.propagate 为 False。
```

### 11.6 startup failure

测试：

```text
配置缺失时 startup 返回非 0 exit code。
stderr 包含可读错误信息。
不打印完整内部堆栈给普通 CLI 用户。
```

暂时不测：

```text
LangGraph
LLM
数据库
token
业务 response
```

## 12. 第一阶段完成标准

第一阶段完成时，应该能做到：

```text
1. `load_app_config()` 能返回 AppConfig。
2. `resolve_project_paths()` 能创建 workspace/logs 等目录。
3. `create_run_context()` 能生成 run_id / run_date。
4. `build_logger()` 能创建 console/file logger。
5. `build_app()` 能返回 NL2SQLAgentApp。
6. `python -m nl2sqlagent.interfaces.cli.main startup` 能输出启动摘要。
7. 启动日志能写入 workspace/logs/{run_date}/{run_id}/app.log。
8. 从非项目根目录运行时，可以通过 --project-root 稳定定位配置和 workspace。
9. 多次构建 app/logger 不会导致日志重复输出。
```

这就是最小运行底座。

## 13. 明确暂缓事项

以下内容不要在第一阶段实现：

```text
LangGraph graph
thread_id
checkpoint
trace_id
request_id
token usage
LangSmith
LLM runtime
database
vectorstore
embedding
domain business model
services
schema grounding
schema index
SQL generation
SQL execution
HTTP API
```

这些不是不重要，而是需要在最小运行底座稳定之后再进入第二阶段。

## 14. 第二阶段预告

第二阶段可以开始接入 LangGraph 运行底座，但仍不急着做 NL2SQL 业务。

第二阶段可能包含：

```text
workflows/runtime/thread_id.py
workflows/runtime/graph_runtime.py
platform/persistence/checkpointer_factory.py
一个 hello graph / startup graph
```

目标是：

```text
验证 LangGraph invoke / stream / checkpoint 的统一入口。
```

等第二阶段完成后，再讨论 LLM、数据库、NL2SQL 业务。
