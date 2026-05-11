from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from nl2sqlagent.interfaces.cli.commands.nl2sql_cases import run_nl2sql_cases_summary
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
        choices=("startup", "run-nl2sql-cases"),
        help="command to run",
    )
    parser.add_argument("--project-root", help="project root directory")
    parser.add_argument("--config-dir", help="config directory")
    parser.add_argument("--run-id", help="optional run id")
    parser.add_argument(
        "--cases-path",
        default="examples/nl2sql_cases/phase8_cases.json",
        help="manual case JSON path",
    )
    parser.add_argument("--case-id", help="only run a specific case_id")
    parser.add_argument(
        "--real-llm",
        action="store_true",
        help="use configured SQL generator provider instead of fake",
    )
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
        if args.command == "run-nl2sql-cases":
            print(
                run_nl2sql_cases_summary(
                    cases_path=Path(args.cases_path),
                    case_id=args.case_id,
                    project_root=_path(args.project_root),
                    config_dir=_path(args.config_dir),
                    run_id=args.run_id,
                    real_llm=bool(args.real_llm),
                )
            )
            return 0
    except NL2SQLAgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
