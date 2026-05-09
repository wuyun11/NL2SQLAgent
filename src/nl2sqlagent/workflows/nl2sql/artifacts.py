from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from nl2sqlagent.platform.runtime import RunContext
from nl2sqlagent.workflows.nl2sql.input import Nl2SqlInput
from nl2sqlagent.workflows.nl2sql.output import Nl2SqlOutput


class Nl2SqlArtifactMetadata(TypedDict):
    artifact_manifest_path: str | None
    input_path: str | None
    prompt_payload_path: str | None
    final_prompt_path: str | None
    graph_updates_path: str | None
    output_path: str | None
    token_usage_path: str | None
    artifact_error: str | None


class NormalizedGraphUpdate(TypedDict):
    node: str
    update: dict[str, Any]


@dataclass(frozen=True)
class Nl2SqlArtifactPaths:
    artifact_dir: Path
    input_path: Path
    prompt_payload_path: Path
    final_prompt_path: Path
    graph_updates_path: Path
    output_path: Path
    manifest_path: Path
    token_usage_path: Path | None = None


@dataclass(frozen=True)
class Nl2SqlArtifactResult:
    paths: Nl2SqlArtifactPaths | None
    metadata: Nl2SqlArtifactMetadata
    artifact_error: str | None = None


def _safe_artifact_id(value: str, *, fallback: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_-]+", "_", value).strip("_")
    return safe or fallback


def build_nl2sql_artifact_paths(
    *,
    log_dir: Path,
    run_context: RunContext,
    input: Nl2SqlInput,
    resolved_thread_id: str,
) -> Nl2SqlArtifactPaths:
    raw_artifact_id = input.request_id or resolved_thread_id
    artifact_id = _safe_artifact_id(raw_artifact_id, fallback=run_context.run_id)
    artifact_dir = log_dir / "artifacts" / "nl2sql" / artifact_id
    return Nl2SqlArtifactPaths(
        artifact_dir=artifact_dir,
        input_path=artifact_dir / "input.json",
        prompt_payload_path=artifact_dir / "prompt_payload.json",
        final_prompt_path=artifact_dir / "final_prompt.txt",
        graph_updates_path=artifact_dir / "graph_updates.jsonl",
        output_path=artifact_dir / "output.json",
        manifest_path=artifact_dir / "manifest.json",
        token_usage_path=None,
    )


def normalize_graph_updates(
    graph_updates: list[dict[str, Any]],
) -> list[NormalizedGraphUpdate]:
    rows: list[NormalizedGraphUpdate] = []
    for chunk in graph_updates:
        for node, update in chunk.items():
            rows.append({"node": str(node), "update": dict(update or {})})
    return rows


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _write_json(path: Path, data: Any, *, indent: int | None = 2) -> None:
    path.write_text(
        json.dumps(_json_safe(data), ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(
            json.dumps(_json_safe(row), ensure_ascii=False, separators=(",", ":"))
            for row in rows
        ),
        encoding="utf-8",
    )


def _empty_error_metadata(error: str) -> Nl2SqlArtifactMetadata:
    return {
        "artifact_manifest_path": None,
        "input_path": None,
        "prompt_payload_path": None,
        "final_prompt_path": None,
        "graph_updates_path": None,
        "output_path": None,
        "token_usage_path": None,
        "artifact_error": error,
    }


def _to_metadata(
    *,
    paths: Nl2SqlArtifactPaths,
    input_written: bool,
    prompt_payload_written: bool,
    final_prompt_written: bool,
    graph_updates_written: bool,
    output_written: bool,
    manifest_written: bool,
    artifact_error: str | None,
) -> Nl2SqlArtifactMetadata:
    return {
        "artifact_manifest_path": str(paths.manifest_path) if manifest_written else None,
        "input_path": str(paths.input_path) if input_written else None,
        "prompt_payload_path": (
            str(paths.prompt_payload_path) if prompt_payload_written else None
        ),
        "final_prompt_path": str(paths.final_prompt_path) if final_prompt_written else None,
        "graph_updates_path": (
            str(paths.graph_updates_path) if graph_updates_written else None
        ),
        "output_path": str(paths.output_path) if output_written else None,
        "token_usage_path": None,
        "artifact_error": artifact_error,
    }


def write_nl2sql_artifacts(
    *,
    log_dir: Path,
    run_context: RunContext,
    input: Nl2SqlInput,
    resolved_thread_id: str,
    final_state: dict[str, Any],
    output: Nl2SqlOutput,
    graph_updates: list[dict[str, Any]],
    started_at: datetime,
    finished_at: datetime,
    artifact_required: bool = False,
) -> Nl2SqlArtifactResult:
    try:
        paths = build_nl2sql_artifact_paths(
            log_dir=log_dir,
            run_context=run_context,
            input=input,
            resolved_thread_id=resolved_thread_id,
        )
        paths.artifact_dir.mkdir(parents=True, exist_ok=True)

        input_data = {
            "run_id": run_context.run_id,
            "run_date": run_context.run_date,
            "thread_id": resolved_thread_id,
            "request_id": input.request_id,
            "user_id": input.user_id,
            "database_key": input.database_key,
            "raw_question": input.question,
            "options": dict(input.options),
        }
        _write_json(paths.input_path, input_data)
        input_written = True

        prompt_payload = final_state.get("prompt_payload")
        prompt_payload_written = bool(prompt_payload)
        if prompt_payload_written:
            _write_json(paths.prompt_payload_path, prompt_payload)

        final_prompt = final_state.get("final_prompt")
        final_prompt_text = str(final_prompt).strip() if final_prompt is not None else ""
        final_prompt_written = bool(final_prompt_text)
        if final_prompt_written:
            paths.final_prompt_path.write_text(final_prompt_text, encoding="utf-8")

        normalized_updates = normalize_graph_updates(graph_updates)
        _write_jsonl(paths.graph_updates_path, normalized_updates)
        graph_updates_written = True

        metadata_without_manifest = _to_metadata(
            paths=paths,
            input_written=input_written,
            prompt_payload_written=prompt_payload_written,
            final_prompt_written=final_prompt_written,
            graph_updates_written=graph_updates_written,
            output_written=False,
            manifest_written=True,
            artifact_error=None,
        )

        output_json = {
            "status": output.status,
            "message": output.message,
            "sql": output.sql,
            "columns": list(output.columns),
            "rows": list(output.rows),
            "trace_id": output.trace_id,
            "metadata": {**dict(output.metadata), **metadata_without_manifest},
        }
        _write_json(paths.output_path, output_json)
        output_written = True

        artifact_id = paths.artifact_dir.name
        manifest = {
            "run_id": run_context.run_id,
            "run_date": run_context.run_date,
            "thread_id": resolved_thread_id,
            "request_id": input.request_id,
            "artifact_id": artifact_id,
            "workflow": "nl2sql",
            "write_mode": "overwrite",
            "status": output.status,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "artifact_dir": str(paths.artifact_dir),
            "artifact_files": {
                "input": str(paths.input_path),
                "prompt_payload": (
                    str(paths.prompt_payload_path) if prompt_payload_written else None
                ),
                "final_prompt": (
                    str(paths.final_prompt_path) if final_prompt_written else None
                ),
                "graph_updates": str(paths.graph_updates_path),
                "output": str(paths.output_path),
                "manifest": str(paths.manifest_path),
                "token_usage": None,
            },
            "sizes": {
                "graph_updates_rows": len(normalized_updates),
                "final_prompt_size_chars": len(final_prompt_text),
                "result_rows_count": len(output.rows),
            },
            "artifact_error": None,
        }
        _write_json(paths.manifest_path, manifest)
        manifest_written = True

        metadata = _to_metadata(
            paths=paths,
            input_written=input_written,
            prompt_payload_written=prompt_payload_written,
            final_prompt_written=final_prompt_written,
            graph_updates_written=graph_updates_written,
            output_written=output_written,
            manifest_written=manifest_written,
            artifact_error=None,
        )
        return Nl2SqlArtifactResult(
            paths=paths,
            metadata=metadata,
            artifact_error=None,
        )
    except OSError as exc:
        if artifact_required:
            raise
        error = str(exc)
        return Nl2SqlArtifactResult(
            paths=None,
            metadata=_empty_error_metadata(error),
            artifact_error=error,
        )


__all__ = [
    "Nl2SqlArtifactMetadata",
    "NormalizedGraphUpdate",
    "Nl2SqlArtifactPaths",
    "Nl2SqlArtifactResult",
    "build_nl2sql_artifact_paths",
    "normalize_graph_updates",
    "write_nl2sql_artifacts",
]
