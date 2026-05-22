"""Progress callback helpers for long-running workflows."""

from __future__ import annotations

from collections.abc import Callable

ProgressFunc = Callable[[str, str], None]


def noop_progress(_stage: str, _message: str) -> None:
    return


def emit_progress(progress: ProgressFunc | None, stage: str, message: str) -> None:
    callback = progress or noop_progress
    try:
        callback(stage, message)
    except Exception:
        # Progress reporting must never fail the writing workflow.
        return
