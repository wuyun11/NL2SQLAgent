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
