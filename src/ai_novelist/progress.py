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


def describe_agent_call(adapter: object, agent: str = "") -> str:
    """Return provider/model/effort metadata for progress messages."""
    if getattr(adapter, "mock", False):
        return "model=mock, effort=n/a"
    model = str(getattr(adapter, "model", "")).strip()
    if model:
        effort = "medium"
        thinking = getattr(adapter, "_thinking_strategy", None)
        if callable(thinking):
            strategy = str(thinking(agent or ""))
            if strategy == "enabled-high":
                effort = "high"
            elif strategy == "disabled-medium":
                effort = "disabled-medium"
            elif strategy == "enabled-medium":
                effort = "medium"
            else:
                effort = strategy or "medium"
        return f"model={model}, effort={effort}"
    codex_bin = str(getattr(adapter, "codex_bin", "codex")).strip() or "codex"
    return f"model={codex_bin}, effort=cli-default"


def with_agent_metadata(message: str, adapter: object, agent: str = "") -> str:
    return f"{message}（{describe_agent_call(adapter, agent)}）"
