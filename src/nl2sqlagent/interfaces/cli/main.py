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
