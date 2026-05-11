from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI


class SqlGenerationError(Exception):
    """Raised when the LLM returns unusable SQL or configuration is invalid."""


@dataclass(frozen=True)
class SqlGenerationResult:
    generated_sql: str
    model_name: str
    raw_text: str


@runtime_checkable
class SqlGenerator(Protocol):
    def generate(self, final_prompt: str) -> SqlGenerationResult: ...


def load_dotenv_file(project_root: Path) -> dict[str, str]:
    path = project_root / ".env"
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        result[key] = value
    return result


def resolve_env_value(name: str, project_root: Path) -> str | None:
    """Resolve env var: os.environ overrides values from project .env."""
    if name in os.environ:
        return os.environ[name]
    file_vars = load_dotenv_file(project_root)
    return file_vars.get(name)


def strip_sql_markdown_fences(text: str) -> str:
    s = text.strip()
    lines = s.splitlines()
    if not lines:
        return ""
    if lines[0].strip().startswith("```"):
        lines = lines[1:]
    while lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


@dataclass(frozen=True)
class FakeSqlGenerator:
    """Deterministic generator for tests and offline runs."""

    sql: str = "SELECT 1 AS value"

    def generate(self, final_prompt: str) -> SqlGenerationResult:
        _ = final_prompt
        return SqlGenerationResult(
            generated_sql=self.sql,
            model_name="fake-sql-generator",
            raw_text=self.sql,
        )


@dataclass
class OpenAICompatibleSqlGenerator:
    chat_model_name: str
    base_url: str
    api_key_env: str
    temperature: float
    timeout_seconds: int
    project_root: Path

    _chat: ChatOpenAI | None = None

    def _ensure_chat(self) -> ChatOpenAI:
        if self._chat is not None:
            return self._chat
        api_key = resolve_env_value(self.api_key_env, self.project_root)
        if not api_key or not str(api_key).strip():
            raise SqlGenerationError(
                f"Missing API key: environment variable {self.api_key_env!r} is not set"
            )
        self._chat = ChatOpenAI(
            model_name=self.chat_model_name,
            openai_api_key=str(api_key).strip(),
            openai_api_base=self.base_url,
            temperature=self.temperature,
            request_timeout=float(self.timeout_seconds),
        )
        return self._chat

    def generate(self, final_prompt: str) -> SqlGenerationResult:
        chat = self._ensure_chat()
        message = HumanMessage(content=final_prompt)
        response = chat.invoke([message])
        raw = response.content
        if isinstance(raw, list):
            raw_text = "".join(
                str(part.get("text", part)) if isinstance(part, dict) else str(part)
                for part in raw
            )
        else:
            raw_text = str(raw)
        cleaned = strip_sql_markdown_fences(raw_text)
        if not cleaned:
            raise SqlGenerationError("LLM returned empty SQL")
        return SqlGenerationResult(
            generated_sql=cleaned,
            model_name=self.chat_model_name,
            raw_text=raw_text,
        )


__all__ = [
    "FakeSqlGenerator",
    "OpenAICompatibleSqlGenerator",
    "SqlGenerationError",
    "SqlGenerationResult",
    "SqlGenerator",
    "load_dotenv_file",
    "resolve_env_value",
    "strip_sql_markdown_fences",
]
