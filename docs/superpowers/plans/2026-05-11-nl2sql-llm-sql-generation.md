# NL2SQL LLM SQL Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current mock `generate_sql` behavior with an injected SQL generator so `final_prompt -> LLM -> generated_sql` can be verified while keeping LangGraph as the only workflow controller.

**Architecture:** Keep workflow control in `graph.py`: `generate_sql` writes `generated_sql` or `generate_error`, then `route_after_generate` sends the run to `check_sql` or `failed_response`. Add a thin `SqlGenerator` dependency for model calls; tests use `FakeSqlGenerator`, real LLM verification uses `OpenAICompatibleSqlGenerator`. Do not add Chain/Stage/Orchestration layers, `use_llm_generate`, token usage, retry, vector, history SQL, or real DB execution in this plan.

**Tech Stack:** Python 3.12, LangGraph `StateGraph`, `TypedDict` / dataclass contracts, `langchain-openai` for OpenAI-compatible chat calls, existing JSON artifacts, `pytest`.

---

## Source Documents

Read these before editing:

- `.ai/guide/00_协作方式.md`
- `.ai/guide/01_决策偏好.md`
- `.ai/guide/02_风险提醒.md`
- `.ai/guide/03_乱码处理.md`
- `.ai/guide/10_运行方式.md`
- `.ai/guide/04_验证汇报.md`
- `docs/temp/Phase7_LLM接入前置口径统计.md`
- `docs/project/Phase7_NL2SQL_LLM接入设计.md`

Run Python through the project-local interpreter:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest ...
```

Use UTF-8 in PowerShell when reading/writing Chinese files:

```powershell
[Console]::InputEncoding=[System.Text.Encoding]::UTF8
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$OutputEncoding=[System.Text.Encoding]::UTF8
chcp 65001 > $null
```

## Non-Goals

- Do not add `use_llm_generate`.
- Do not implement token usage, LangSmith, retry, repair, vector retrieval, history SQL templates, real DB execution, automatic `ProcessedQuestion`, or automatic `ProcessedDatabaseKnowledge`.
- Do not create `engine/chains`, `application/stages`, `GenerateStage`, `Nl2SqlChain`, `MainOrchestration`, or a second workflow controller.
- Do not let `nodes.py` import or initialize `ChatOpenAI`, read API keys, read model config, write files, or write artifacts.
- Do not let real API key values enter graph state, output JSON, graph update JSONL, artifacts, or app logs.
- Do not run cloud tests unless explicitly requested and `DASHSCOPE_API_KEY` is configured.

## File Structure

Create:

- `config/model.yml`
  - Owns model configuration for the SQL generator.
  - Stores environment variable name only, never the real API key.

- `src/nl2sqlagent/workflows/nl2sql/sql_generator.py`
  - Owns `SqlGenerationResult`, `SqlGenerationError`, `SqlGenerator`, `FakeSqlGenerator`, `OpenAICompatibleSqlGenerator`, and small helper functions for `.env` loading and SQL text cleanup.
  - No LangGraph imports, no artifact writing, no retry, no token usage.

- `tests/unit/workflows/nl2sql/test_sql_generator.py`
  - Covers fake generator, SQL cleanup, missing prompt, missing API key, and secret non-leak behavior at generator level.

- `tests/cloud/README.md`
  - Documents how to run real LLM tests manually.

- `tests/cloud/test_nl2sql_llm_generate.py`
  - Explicit `@pytest.mark.cloud` test that calls the real provider only when requested.

Modify:

- `pyproject.toml`
  - Add `langchain-core`, `langchain-openai`.
  - Add `cloud` marker.
  - Add default `addopts = "-m not cloud"` so normal `pytest -q` does not run cloud tests.

- `src/nl2sqlagent/platform/config/models.py`
  - Add model config dataclasses.

- `src/nl2sqlagent/platform/config/loader.py`
  - Load `config/model.yml`.
  - Parse string and numeric model fields.

- `src/nl2sqlagent/bootstrap/container.py`
  - Build `OpenAICompatibleSqlGenerator` from config.
  - Accept an optional `sql_generator` override for tests.
  - Pass the generator into `build_nl2sql_graph`.

- `src/nl2sqlagent/workflows/nl2sql/__init__.py`
  - Export SQL generator types if tests or callers need them.

- `src/nl2sqlagent/workflows/nl2sql/graph.py`
  - Require `sql_generator`.
  - Inject it into `generate_sql_node`.
  - Add `route_after_generate`.

- `src/nl2sqlagent/workflows/nl2sql/edges.py`
  - Add `route_after_generate`.

- `src/nl2sqlagent/workflows/nl2sql/nodes.py`
  - Replace mock SQL generation with injected generator call.
  - Preserve node thinness.

- `src/nl2sqlagent/workflows/nl2sql/state.py`
  - Add `llm_result` and `generate_error`.

- `src/nl2sqlagent/workflows/nl2sql/response_builder.py`
  - Include `llm_result` / `generate_error` in debug metadata.
  - Make failed message prefer `generate_error`.

- Existing tests:
  - `tests/unit/platform/test_config_loader.py`
  - `tests/integration/test_startup_cli.py`
  - `tests/integration/test_nl2sql_workflow.py`
  - `tests/unit/workflows/nl2sql/test_nodes.py`
  - `tests/unit/workflows/nl2sql/test_edges.py`
  - `tests/unit/workflows/nl2sql/test_response_builder.py`
  - `tests/unit/workflows/nl2sql/test_contracts.py`

## Task 1: Add Model Configuration

**Files:**

- Create: `config/model.yml`
- Modify: `src/nl2sqlagent/platform/config/models.py`
- Modify: `src/nl2sqlagent/platform/config/loader.py`
- Modify tests that write temporary config directories:
  - `tests/unit/platform/test_config_loader.py`
  - `tests/integration/test_startup_cli.py`
  - `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Add failing config loader tests**

In `tests/unit/platform/test_config_loader.py`, update existing config fixtures to also write `model.yml`:

```yaml
model:
  sql_generator:
    provider: openai_compatible
    chat_model_name: glm-5
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
    temperature: 0
    timeout_seconds: 60
```

Add a test like:

```python
def test_load_app_config_loads_model_sql_generator_section(tmp_path: Path) -> None:
    _write_config(tmp_path)

    config = load_app_config(tmp_path)

    assert config.model.sql_generator.provider == "openai_compatible"
    assert config.model.sql_generator.chat_model_name == "glm-5"
    assert config.model.sql_generator.api_key_env == "DASHSCOPE_API_KEY"
    assert config.model.sql_generator.temperature == 0
    assert config.model.sql_generator.timeout_seconds == 60
```

- [ ] **Step 2: Run focused failing tests**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/unit/platform/test_config_loader.py -q
```

Expected: FAIL because `AppConfig` has no `model` field and `loader.py` does not load `model.yml`.

- [ ] **Step 3: Add model dataclasses**

In `src/nl2sqlagent/platform/config/models.py`, add:

```python
@dataclass(frozen=True)
class SqlGeneratorModelSection:
    provider: str
    chat_model_name: str
    base_url: str
    api_key_env: str
    temperature: float
    timeout_seconds: float


@dataclass(frozen=True)
class ModelSection:
    sql_generator: SqlGeneratorModelSection
```

Add `model: ModelSection` to `AppConfig`.

Update `__all__`.

- [ ] **Step 4: Load `model.yml`**

In `src/nl2sqlagent/platform/config/loader.py`:

- Import `ModelSection` and `SqlGeneratorModelSection`.
- Load `model_data = _load_yaml_file(resolved_config_dir / "model.yml")`.
- Add a numeric helper:

```python
def _number(data: dict[str, Any], key: str, *, section: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"config field '{section}.{key}' must be a number")
    return float(value)
```

- Parse `model.sql_generator`.
- Return `AppConfig(..., model=ModelSection(...))`.

- [ ] **Step 5: Create root `config/model.yml`**

Create `config/model.yml`:

```yaml
model:
  sql_generator:
    provider: openai_compatible
    chat_model_name: glm-5
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
    temperature: 0
    timeout_seconds: 60
```

- [ ] **Step 6: Update temporary config helpers**

Update `_write_config(...)` helpers in:

- `tests/integration/test_startup_cli.py`
- `tests/integration/test_nl2sql_workflow.py`

so they write `model.yml` too. Startup should still succeed without a real API key because generator API key lookup must be lazy.

- [ ] **Step 7: Run config and startup tests**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/unit/platform/test_config_loader.py tests/integration/test_startup_cli.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add config/model.yml src/nl2sqlagent/platform/config/models.py src/nl2sqlagent/platform/config/loader.py tests/unit/platform/test_config_loader.py tests/integration/test_startup_cli.py tests/integration/test_nl2sql_workflow.py
git commit -m "feat: add nl2sql model configuration"
```

## Task 2: Add SQL Generator Adapter

**Files:**

- Create: `src/nl2sqlagent/workflows/nl2sql/sql_generator.py`
- Create: `tests/unit/workflows/nl2sql/test_sql_generator.py`
- Modify: `pyproject.toml`
- Optionally modify: `src/nl2sqlagent/workflows/nl2sql/__init__.py`

- [ ] **Step 1: Add failing generator tests**

Create `tests/unit/workflows/nl2sql/test_sql_generator.py` with tests for:

```python
def test_fake_sql_generator_returns_configured_sql() -> None: ...
def test_clean_generated_sql_strips_markdown_fence() -> None: ...
def test_clean_generated_sql_rejects_empty_text() -> None: ...
def test_openai_generator_missing_api_key_error_mentions_env_name_not_secret(monkeypatch, tmp_path) -> None: ...
```

For missing API key, clear the env var:

```python
monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
generator = OpenAICompatibleSqlGenerator(
    chat_model_name="glm-5",
    base_url="https://example.test/v1",
    api_key_env="DASHSCOPE_API_KEY",
    temperature=0,
    timeout_seconds=1,
    env_path=tmp_path / ".env",
)

with pytest.raises(SqlGenerationError, match="DASHSCOPE_API_KEY"):
    generator.generate("prompt")
```

- [ ] **Step 2: Run focused failing tests**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/unit/workflows/nl2sql/test_sql_generator.py -q
```

Expected: FAIL because `sql_generator.py` does not exist.

- [ ] **Step 3: Add dependencies**

Modify `pyproject.toml`:

```toml
dependencies = [
    "PyYAML>=6.0",
    "langgraph>=1.0",
    "langchain-core>=0.3",
    "langchain-openai>=0.3",
]
```

Do not add `langchain`, `langchain-ollama`, or `python-dotenv`.

- [ ] **Step 4: Implement `sql_generator.py`**

Create `src/nl2sqlagent/workflows/nl2sql/sql_generator.py` with:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class SqlGenerationError(RuntimeError):
    """Raised when SQL generation cannot produce SQL."""


@dataclass(frozen=True)
class SqlGenerationResult:
    generated_sql: str
    model_name: str
    raw_text: str


class SqlGenerator(Protocol):
    def generate(self, final_prompt: str) -> SqlGenerationResult: ...
```

Add `FakeSqlGenerator`:

```python
@dataclass(frozen=True)
class FakeSqlGenerator:
    generated_sql: str = "SELECT 1 AS value"
    model_name: str = "fake-sql-generator"

    def generate(self, final_prompt: str) -> SqlGenerationResult:
        if not final_prompt.strip():
            raise SqlGenerationError("final_prompt is required before SQL generation")
        return SqlGenerationResult(
            generated_sql=self.generated_sql,
            model_name=self.model_name,
            raw_text=self.generated_sql,
        )
```

Add helpers:

```python
def clean_generated_sql(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if not text:
        raise SqlGenerationError("LLM returned empty SQL")
    return text
```

Add `.env` loading and `OpenAICompatibleSqlGenerator`:

```python
def load_env_values(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")
    return values
```

`OpenAICompatibleSqlGenerator` should:

- Store constructor config.
- Resolve API key inside `generate()`, not during construction.
- Merge `.env` values then `os.environ`, with `os.environ` winning.
- Raise `SqlGenerationError(f"missing API key env: {self.api_key_env}")` if missing.
- Lazy import `ChatOpenAI` inside a private method or inside `generate()`.
- Call `chat_model.invoke(final_prompt)`.
- Extract text from `message.content`.
- Return `SqlGenerationResult(generated_sql=cleaned, model_name=self.chat_model_name, raw_text=raw_text)`.

Do not extract token usage.

- [ ] **Step 5: Export useful names**

If tests or container import from package root, update `src/nl2sqlagent/workflows/nl2sql/__init__.py` to export:

```python
FakeSqlGenerator
OpenAICompatibleSqlGenerator
SqlGenerationError
SqlGenerationResult
SqlGenerator
```

Otherwise direct imports from `nl2sqlagent.workflows.nl2sql.sql_generator` are fine.

- [ ] **Step 6: Run generator tests**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/unit/workflows/nl2sql/test_sql_generator.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add pyproject.toml src/nl2sqlagent/workflows/nl2sql/sql_generator.py src/nl2sqlagent/workflows/nl2sql/__init__.py tests/unit/workflows/nl2sql/test_sql_generator.py
git commit -m "feat: add sql generator adapter"
```

## Task 3: Wire Generator Into LangGraph

**Files:**

- Modify: `src/nl2sqlagent/workflows/nl2sql/graph.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/edges.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/nodes.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/state.py`
- Modify: `src/nl2sqlagent/workflows/nl2sql/response_builder.py`
- Modify tests:
  - `tests/unit/workflows/nl2sql/test_nodes.py`
  - `tests/unit/workflows/nl2sql/test_edges.py`
  - `tests/unit/workflows/nl2sql/test_response_builder.py`
  - `tests/integration/test_nl2sql_workflow.py`

- [ ] **Step 1: Add failing node and edge tests**

In `tests/unit/workflows/nl2sql/test_edges.py`, add:

```python
def test_route_after_generate_returns_failed_response_for_generate_error() -> None:
    assert route_after_generate({"generate_error": "boom"}) == "failed_response"


def test_route_after_generate_returns_check_sql_without_generate_error() -> None:
    assert route_after_generate({"generated_sql": "SELECT 1"}) == "check_sql"
```

In `tests/unit/workflows/nl2sql/test_nodes.py`, add tests:

```python
def test_generate_sql_node_uses_injected_sql_generator() -> None:
    result = generate_sql_node(
        {"final_prompt": "prompt"},
        sql_generator=FakeSqlGenerator("SELECT dept_id, COUNT(*) FROM hr_emp_base"),
    )
    assert result["generated_sql"].startswith("SELECT dept_id")
    assert result["llm_result"]["model_name"] == "fake-sql-generator"
    assert result["generate_error"] is None
```

```python
class RaisingSqlGenerator:
    def generate(self, final_prompt: str):
        raise SqlGenerationError("provider failed")


def test_generate_sql_node_records_generate_error() -> None:
    result = generate_sql_node(
        {"final_prompt": "prompt"},
        sql_generator=RaisingSqlGenerator(),
    )
    assert result["status"] == "failed"
    assert result["generate_error"] == "provider failed"
```

- [ ] **Step 2: Run focused failing tests**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/unit/workflows/nl2sql/test_edges.py tests/unit/workflows/nl2sql/test_nodes.py -q
```

Expected: FAIL because `route_after_generate` and injected generator node behavior do not exist.

- [ ] **Step 3: Update graph state**

In `src/nl2sqlagent/workflows/nl2sql/state.py`, add:

```python
llm_result: dict[str, Any]
generate_error: str | None
```

Keep `total=False`.

- [ ] **Step 4: Add `route_after_generate`**

In `src/nl2sqlagent/workflows/nl2sql/edges.py`, add:

```python
def route_after_generate(
    state: Nl2SqlGraphState,
) -> Literal["failed_response", "check_sql"]:
    if state.get("generate_error"):
        return "failed_response"
    return "check_sql"
```

Export it in `__all__`.

- [ ] **Step 5: Update `generate_sql_node`**

In `src/nl2sqlagent/workflows/nl2sql/nodes.py`:

- Import `SqlGenerator`.
- Change signature to:

```python
def generate_sql_node(
    state: Nl2SqlGraphState,
    *,
    sql_generator: SqlGenerator,
) -> dict:
```

- Implement:

```python
final_prompt = state.get("final_prompt") or ""
if not final_prompt.strip():
    return {
        "generate_error": "final_prompt is required before SQL generation",
        "status": "failed",
    }
try:
    result = sql_generator.generate(final_prompt)
except Exception as exc:
    return {
        "generate_error": str(exc),
        "status": "failed",
    }
return {
    "generated_sql": result.generated_sql,
    "llm_result": {
        "model_name": result.model_name,
        "raw_text": result.raw_text,
    },
    "generate_error": None,
}
```

Do not import `ChatOpenAI`, `os`, or config modules in `nodes.py`.

- [ ] **Step 6: Update failed response handling**

In both `nodes.py` and `response_builder.py`, failed message order should be:

```text
generate_error
check_error
execute_error
message
NL2SQL workflow failed.
```

In `response_builder.py`, add `llm_result` and `generate_error` to `build_prompt_debug_metadata(...)`.

- [ ] **Step 7: Inject generator into graph**

In `src/nl2sqlagent/workflows/nl2sql/graph.py`:

- Import `partial` from `functools`.
- Import `route_after_generate`.
- Import `SqlGenerator`.
- Change signature:

```python
def build_nl2sql_graph(*, checkpointer, sql_generator: SqlGenerator):
```

- Register node:

```python
graph.add_node(
    "generate_sql",
    partial(generate_sql_node, sql_generator=sql_generator),
)
```

- Replace direct edge:

```python
graph.add_edge("generate_sql", "check_sql")
```

with conditional edges:

```python
graph.add_conditional_edges(
    "generate_sql",
    route_after_generate,
    {
        "failed_response": "failed_response",
        "check_sql": "check_sql",
    },
)
```

- [ ] **Step 8: Update tests that build graphs**

Every test call to `build_nl2sql_graph(checkpointer=...)` must pass a fake generator:

```python
build_nl2sql_graph(
    checkpointer=checkpointer,
    sql_generator=FakeSqlGenerator(),
)
```

Update helpers in `tests/integration/test_nl2sql_workflow.py`.

- [ ] **Step 9: Run focused workflow tests**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/unit/workflows/nl2sql/test_edges.py tests/unit/workflows/nl2sql/test_nodes.py tests/unit/workflows/nl2sql/test_response_builder.py tests/integration/test_nl2sql_workflow.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add src/nl2sqlagent/workflows/nl2sql/graph.py src/nl2sqlagent/workflows/nl2sql/edges.py src/nl2sqlagent/workflows/nl2sql/nodes.py src/nl2sqlagent/workflows/nl2sql/state.py src/nl2sqlagent/workflows/nl2sql/response_builder.py tests/unit/workflows/nl2sql/test_edges.py tests/unit/workflows/nl2sql/test_nodes.py tests/unit/workflows/nl2sql/test_response_builder.py tests/integration/test_nl2sql_workflow.py
git commit -m "feat: route nl2sql generation through sql generator"
```

## Task 4: Wire Container and App Startup

**Files:**

- Modify: `src/nl2sqlagent/bootstrap/container.py`
- Modify: `tests/integration/test_startup_cli.py`
- Modify: `tests/integration/test_nl2sql_workflow.py`
- Modify: `tests/unit/workflows/nl2sql/test_contracts.py`

- [ ] **Step 1: Add failing app wiring test**

In `tests/integration/test_nl2sql_workflow.py`, update the app wiring test to pass a fake override:

```python
app = build_app(
    project_root=tmp_path,
    run_id="run-nl2sql-app",
    sql_generator=FakeSqlGenerator(
        "SELECT dept_id, COUNT(*) AS employee_count FROM hr_emp_base GROUP BY dept_id"
    ),
)
```

Keep assertions that:

```text
output.status == "success"
output.metadata["llm_result"]["model_name"] == "fake-sql-generator"
artifact_manifest_path exists
```

Expected initial failure: `build_app` does not accept `sql_generator`.

- [ ] **Step 2: Run focused failing app wiring test**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/integration/test_nl2sql_workflow.py::test_build_app_exposes_only_nl2sql_workflow -q
```

Use the actual current test name if it differs.

- [ ] **Step 3: Add optional `sql_generator` override to `build_app`**

In `src/nl2sqlagent/bootstrap/container.py`:

- Import `SqlGenerator` and `OpenAICompatibleSqlGenerator`.
- Change `build_app` signature:

```python
def build_app(
    *,
    project_root: Path | None = None,
    config_dir: Path | None = None,
    run_id: str | None = None,
    sql_generator: SqlGenerator | None = None,
) -> NL2SQLAgentApp:
```

- Build default generator when override is not provided:

```python
def _build_sql_generator(config: AppConfig, *, project_root: Path) -> SqlGenerator:
    section = config.model.sql_generator
    provider = section.provider.strip().lower()
    if provider != "openai_compatible":
        raise ConfigurationError(
            f"unsupported model.sql_generator.provider: {section.provider}"
        )
    return OpenAICompatibleSqlGenerator(
        chat_model_name=section.chat_model_name,
        base_url=section.base_url,
        api_key_env=section.api_key_env,
        temperature=section.temperature,
        timeout_seconds=section.timeout_seconds,
        env_path=project_root / ".env",
    )
```

- Use:

```python
effective_sql_generator = sql_generator or _build_sql_generator(...)
nl2sql_graph = build_nl2sql_graph(
    checkpointer=checkpointer,
    sql_generator=effective_sql_generator,
)
```

Do not resolve API key in `build_app`.

- [ ] **Step 4: Update startup fixtures**

Ensure temporary config writers in startup and workflow integration tests write `model.yml`.

Startup CLI should still pass with no `.env` and no `DASHSCOPE_API_KEY`.

- [ ] **Step 5: Add architecture guard for nodes**

In `tests/unit/workflows/nl2sql/test_contracts.py`, add or update a test:

```python
def test_generate_sql_node_does_not_initialize_llm_provider() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/nodes.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "ChatOpenAI",
        "DASHSCOPE_API_KEY",
        "api_key",
        "base_url",
        "langchain_openai",
        "os.environ",
    ]
    assert all(token not in source for token in forbidden)
```

- [ ] **Step 6: Run startup and app wiring tests**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/integration/test_startup_cli.py tests/integration/test_nl2sql_workflow.py tests/unit/workflows/nl2sql/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/nl2sqlagent/bootstrap/container.py tests/integration/test_startup_cli.py tests/integration/test_nl2sql_workflow.py tests/unit/workflows/nl2sql/test_contracts.py
git commit -m "feat: wire sql generator into app container"
```

## Task 5: Add Artifact and Secret Protection Coverage

**Files:**

- Modify: `tests/unit/workflows/nl2sql/test_artifacts.py`
- Modify: `tests/unit/workflows/nl2sql/test_contracts.py`
- Modify only if needed: `src/nl2sqlagent/workflows/nl2sql/artifacts.py`

- [ ] **Step 1: Add artifact metadata test for LLM result**

In `tests/unit/workflows/nl2sql/test_artifacts.py`, add or update a test that writes artifacts with final state containing:

```python
final_state = {
    "final_prompt": "prompt",
    "generated_sql": "SELECT 1",
    "llm_result": {
        "model_name": "fake-sql-generator",
        "raw_text": "SELECT 1",
    },
    "generate_error": None,
}
```

Ensure `output.metadata` also contains `llm_result`, then assert `output.json` contains:

```text
metadata.llm_result.model_name == fake-sql-generator
```

The artifact writer may already pass this once `response_builder` includes metadata.

- [ ] **Step 2: Add secret non-leak test**

Add a test that sets a fake secret:

```python
secret = "sk-test-secret-should-not-leak"
```

Write artifacts for a run whose input/options/state do not contain the secret. Then read:

```text
output.json
graph_updates.jsonl
manifest.json
```

and assert the secret is absent.

Also add a static guard in `test_contracts.py`:

```python
def test_artifact_and_response_layers_do_not_read_api_secrets() -> None:
    for path in [
        Path("src/nl2sqlagent/workflows/nl2sql/artifacts.py"),
        Path("src/nl2sqlagent/workflows/nl2sql/response_builder.py"),
    ]:
        source = path.read_text(encoding="utf-8")
        assert "os.environ" not in source
        assert "DASHSCOPE_API_KEY" not in source
```

- [ ] **Step 3: Run artifact tests**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/unit/workflows/nl2sql/test_artifacts.py tests/unit/workflows/nl2sql/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add tests/unit/workflows/nl2sql/test_artifacts.py tests/unit/workflows/nl2sql/test_contracts.py src/nl2sqlagent/workflows/nl2sql/artifacts.py
git commit -m "test: protect nl2sql llm artifacts from secret leakage"
```

## Task 6: Add Cloud Test Isolation

**Files:**

- Modify: `pyproject.toml`
- Create: `tests/cloud/README.md`
- Create: `tests/cloud/test_nl2sql_llm_generate.py`

- [ ] **Step 1: Configure pytest cloud marker**

Modify `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-m not cloud"
markers = [
    "cloud: tests that call remote LLM services and consume token",
]
```

If `markers` or `addopts` already exist, merge instead of overwriting unrelated settings.

- [ ] **Step 2: Add cloud README**

Create `tests/cloud/README.md`:

````markdown
# Cloud Tests

This directory contains tests that call remote LLM services and may consume token.

## Rules

- Every test must use `@pytest.mark.cloud`.
- Default `pytest -q` excludes these tests via `addopts = "-m not cloud"`.
- Run them manually only when `DASHSCOPE_API_KEY` is configured.

## Run

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/cloud -q -m cloud
```
````

- [ ] **Step 3: Add cloud LLM smoke test**

Create `tests/cloud/test_nl2sql_llm_generate.py`:

```python
from __future__ import annotations

import os

import pytest

from nl2sqlagent.workflows.nl2sql.sql_generator import (
    OpenAICompatibleSqlGenerator,
)


@pytest.mark.cloud
def test_openai_compatible_sql_generator_returns_sql() -> None:
    if not os.getenv("DASHSCOPE_API_KEY"):
        pytest.skip("DASHSCOPE_API_KEY is required for cloud LLM test")

    generator = OpenAICompatibleSqlGenerator(
        chat_model_name="glm-5",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        temperature=0,
        timeout_seconds=60,
    )

    result = generator.generate(
        "Return only SQL. Generate a SQLite query that selects 1 as value."
    )

    assert result.generated_sql
    assert "```" not in result.generated_sql
    assert "select" in result.generated_sql.lower()
```

- [ ] **Step 4: Verify default tests do not run cloud**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/cloud -q
```

Expected: all cloud tests deselected because of `-m not cloud`.

Run:

```powershell
& $py -m pytest tests/cloud -q -m cloud
```

Expected:

- PASS if `DASHSCOPE_API_KEY` is set and provider is reachable.
- SKIP if `DASHSCOPE_API_KEY` is not set.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml tests/cloud/README.md tests/cloud/test_nl2sql_llm_generate.py
git commit -m "test: add isolated cloud llm smoke test"
```

## Task 7: Add Architecture Protection Tests

**Files:**

- Modify: `tests/unit/workflows/nl2sql/test_contracts.py`

- [ ] **Step 1: Add forbidden switch test**

Add:

```python
def test_phase7_does_not_introduce_use_llm_generate() -> None:
    root = Path("src")
    for path in root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "use_llm_generate" not in source
```

- [ ] **Step 2: Add forbidden layer path test**

Add:

```python
def test_phase7_does_not_add_chain_or_stage_layers() -> None:
    forbidden_paths = [
        Path("src/nl2sqlagent/engine/chains"),
        Path("src/nl2sqlagent/application/stages"),
        Path("src/nl2sqlagent/workflows/nl2sql/stages"),
    ]
    assert all(not path.exists() for path in forbidden_paths)
```

- [ ] **Step 3: Add forbidden class/name test**

Extend existing AST-based guard or add:

```python
def test_phase7_does_not_reintroduce_orchestration_shells() -> None:
    import ast

    forbidden = {
        "GenerateStage",
        "Nl2SqlChain",
        "MainOrchestration",
    }
    used_names: set[str] = set()
    for file in Path("src/nl2sqlagent").rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                used_names.add(node.attr)
            elif isinstance(node, ast.ClassDef):
                used_names.add(node.name)
            elif isinstance(node, ast.FunctionDef):
                used_names.add(node.name)

    assert forbidden.isdisjoint(used_names)
```

If this conflicts with existing names that predate Phase7, narrow the path to `src/nl2sqlagent/workflows/nl2sql` and document why.

- [ ] **Step 4: Add provider dependency boundary test**

Add:

```python
def test_llm_provider_imports_stay_out_of_nodes() -> None:
    source = Path("src/nl2sqlagent/workflows/nl2sql/nodes.py").read_text(
        encoding="utf-8"
    )
    forbidden = [
        "ChatOpenAI",
        "langchain_openai",
        "DASHSCOPE_API_KEY",
        "os.environ",
        "base_url",
        "api_key",
    ]
    assert all(token not in source for token in forbidden)
```

- [ ] **Step 5: Run guard tests**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m pytest tests/unit/workflows/nl2sql/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add tests/unit/workflows/nl2sql/test_contracts.py
git commit -m "test: add nl2sql llm architecture guards"
```

## Task 8: Final Verification

**Files:**

- No new files unless verification reveals a bug.

- [ ] **Step 1: Run compile check**

Run:

```powershell
$py = (Get-Content .\.ai\local\python_path.txt -Encoding UTF8).Trim()
& $py -m compileall src tests
```

Expected: compile completes without syntax errors.

- [ ] **Step 2: Run full non-cloud test suite**

Run:

```powershell
& $py -m pytest -q
```

Expected: all non-cloud tests pass; cloud tests are deselected by default.

- [ ] **Step 3: Run focused architecture searches**

Run:

```powershell
.\.ai\local\tools\rg.exe -n "use_llm_generate" src tests
```

Expected: no matches.

Run:

```powershell
.\.ai\local\tools\rg.exe -n "ChatOpenAI|DASHSCOPE_API_KEY|api_key|base_url" src\nl2sqlagent\workflows\nl2sql\nodes.py
```

Expected: no matches.

Run:

```powershell
.\.ai\local\tools\rg.exe -n "GenerateStage|Nl2SqlChain|MainOrchestration" src\nl2sqlagent
```

Expected: no matches, unless an existing unrelated symbol predates this task. If there is a match, explain it in the handoff.

- [ ] **Step 4: Optional cloud verification**

Only run if explicitly requested and `DASHSCOPE_API_KEY` is configured:

```powershell
& $py -m pytest tests/cloud -q -m cloud
```

Expected: PASS against real provider. If skipped due missing key, record SKIP.

- [ ] **Step 5: Inspect generated artifact manually**

Run a workflow with `FakeSqlGenerator` through existing integration test or a short local script using the project interpreter. Confirm artifact files include:

```text
final_prompt.txt
graph_updates.jsonl with generate_sql update
output.json metadata.llm_result
```

No real API key value should appear in artifacts.

- [ ] **Step 6: Final status**

Report:

```text
Implemented:
- model config
- SqlGenerator adapter
- graph route_after_generate
- generated_sql / llm_result / generate_error state and artifact visibility
- cloud test isolation
- architecture guards

Verification:
- compileall result
- pytest -q result
- cloud test result or not run reason
```

Do not claim cloud LLM works unless `tests/cloud -m cloud` actually ran and passed.
