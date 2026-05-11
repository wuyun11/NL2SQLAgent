from __future__ import annotations

from pathlib import Path

import pytest

from nl2sqlagent.workflows.nl2sql.sql_generator import (
    FakeSqlGenerator,
    OpenAICompatibleSqlGenerator,
    SqlGenerationError,
    load_dotenv_file,
    resolve_env_value,
    strip_sql_markdown_fences,
)


def test_strip_sql_markdown_fences_removes_fenced_block() -> None:
    raw = "```sql\nSELECT 1 AS x\n```"
    assert strip_sql_markdown_fences(raw) == "SELECT 1 AS x"


def test_fake_sql_generator_returns_configured_sql() -> None:
    gen = FakeSqlGenerator(sql="SELECT 2")
    result = gen.generate("ignored prompt")
    assert result.generated_sql == "SELECT 2"
    assert result.model_name == "fake-sql-generator"
    assert result.raw_text == "SELECT 2"


def test_openai_compatible_generator_raises_when_api_key_missing(tmp_path: Path) -> None:
    gen = OpenAICompatibleSqlGenerator(
        chat_model_name="glm-5",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="NL2SQL_MISSING_KEY_FOR_TEST",
        temperature=0.0,
        timeout_seconds=30,
        project_root=tmp_path,
    )
    with pytest.raises(SqlGenerationError, match="NL2SQL_MISSING_KEY_FOR_TEST"):
        gen.generate("SELECT 1")


def test_resolve_env_value_prefers_process_environ_over_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".env").write_text("NL2SQL_TEST_ENV=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("NL2SQL_TEST_ENV", raising=False)
    assert resolve_env_value("NL2SQL_TEST_ENV", tmp_path) == "from-dotenv"
    monkeypatch.setenv("NL2SQL_TEST_ENV", "from-os")
    assert resolve_env_value("NL2SQL_TEST_ENV", tmp_path) == "from-os"


def test_load_dotenv_file_ignores_comments_and_blanks(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "\n# c\nNL2SQL_A=1\n  NL2SQL_B = quoted \n",
        encoding="utf-8",
    )
    assert load_dotenv_file(tmp_path) == {
        "NL2SQL_A": "1",
        "NL2SQL_B": "quoted",
    }
