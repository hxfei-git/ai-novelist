"""Progress callback helpers for long-running workflows."""

from __future__ import annotations

import time
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


def format_elapsed(seconds: float) -> str:
    if seconds < 10:
        return f"{seconds:.1f}s"
    return f"{seconds:.0f}s"


def describe_agent_call(
    adapter: object,
    agent: str = "",
    elapsed_seconds: float | None = None,
    context_chars: int | None = None,
    estimated_tokens: int | None = None,
) -> str:
    """Return compact model/effort metadata for progress messages."""
    if getattr(adapter, "mock", False):
        parts = ["mock", "n/a"]
    else:
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
            parts = [model, effort]
        else:
            codex_bin = str(getattr(adapter, "codex_bin", "codex")).strip() or "codex"
            parts = [codex_bin, "cli-default"]
    if elapsed_seconds is not None:
        parts.append(format_elapsed(elapsed_seconds))
    if context_chars is not None:
        parts.append(f"ctx={format_compact_number(estimate_context_tokens(context_chars))}/{context_capacity_label(parts[0])}")
    if estimated_tokens is not None:
        parts.append(f"tok≈{format_compact_number(estimated_tokens)}")
    return " | ".join(parts)


def with_agent_metadata(
    message: str,
    adapter: object,
    agent: str = "",
    elapsed_seconds: float | None = None,
    context_chars: int | None = None,
    estimated_tokens: int | None = None,
) -> str:
    return f"{message}（{describe_agent_call(adapter, agent, elapsed_seconds, context_chars, estimated_tokens)}）"


def estimate_context_tokens(context_chars: int) -> int:
    if context_chars <= 0:
        return 0
    return max(1, context_chars // 2)


def context_capacity_label(model: str) -> str:
    normalized = model.strip().lower()
    if normalized in {"codex", "codex-cli"} or "codex" in normalized:
        return "258K"
    if normalized in {"deepseek-v4-pro", "deepseek-v4-flash"}:
        return "1M"
    if normalized == "deepseek-chat":
        return "64K"
    return "?"


def format_compact_number(value: int) -> str:
    if value < 1000:
        return str(value)
    if value < 1_000_000:
        amount = value / 1000
        return f"{amount:.1f}K" if amount < 10 else f"{round(amount)}K"
    amount = value / 1_000_000
    return f"{amount:.1f}M" if amount < 10 else f"{round(amount)}M"


def completion_progress_message(message: str, elapsed_seconds: float) -> str:
    metadata = ""
    body = message
    if "（" in message and message.endswith("）"):
        body, metadata = message.rsplit("（", 1)
        metadata = metadata[:-1]
    body = body.rstrip(".。…")
    if body.startswith("正在"):
        body = "已完成" + body[2:]
    else:
        body = "已完成：" + body
    if metadata:
        return f"{body}（{metadata}/{format_elapsed(elapsed_seconds)}）"
    return f"{body}（{format_elapsed(elapsed_seconds)}）"


def run_with_progress(progress: ProgressFunc | None, stage: str, message: str, fn):
    emit_progress(progress, stage, message)
    start = time.perf_counter()
    try:
        result = fn()
    except Exception:
        elapsed = time.perf_counter() - start
        emit_progress(progress, stage, completion_progress_message("执行失败：" + message, elapsed))
        raise
    elapsed = time.perf_counter() - start
    emit_progress(progress, stage, completion_progress_message(message, elapsed))
    return result


def complete_with_timing(adapter: object, prompt: str, workspace, options=None) -> tuple[str, float]:
    start = time.perf_counter()
    output = adapter.complete(prompt, workspace, options=options)
    return output, time.perf_counter() - start
