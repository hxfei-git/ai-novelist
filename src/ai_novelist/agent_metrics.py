"""Agent call metrics and trace helpers."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai_novelist.adapters.base import AgentCallOptions


@dataclass(frozen=True)
class ContextSourceTrace:
    section: str
    source_type: str
    path: str | None
    original_chars: int
    included_chars: int
    truncated: bool = False
    digest: str | None = None


@dataclass(frozen=True)
class AgentRunTrace:
    run_id: str
    project_id: str
    graph: str
    node: str
    agent: str
    prompt_profile: str | None
    prompt_chars: int
    estimated_prompt_tokens: int
    output_chars: int
    estimated_output_tokens: int
    elapsed_ms: int
    status: str
    error: str | None
    model_provider: str | None
    model_name: str | None
    context_sources: list[dict[str, Any]]
    created_at: str


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 2)


def debug_dir(project_dir: Path) -> Path:
    return project_dir / "debug"


def append_agent_trace(project_dir: Path, trace: AgentRunTrace) -> None:
    directory = debug_dir(project_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "agent_runs.jsonl"
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(asdict(trace), ensure_ascii=False, sort_keys=True) + "\n")


def complete_with_metrics(
    *,
    adapter,
    prompt: str,
    project_dir: Path,
    project_id: str,
    graph: str,
    node: str,
    agent: str,
    prompt_profile: str | None = None,
    context_sources: list[dict[str, Any]] | None = None,
) -> str:
    start = time.perf_counter()
    status = "ok"
    error: str | None = None
    output = ""
    try:
        output = adapter.complete(
            prompt,
            project_dir,
            options=AgentCallOptions(agent=agent, task=graph, stage=node),
        )
        return output
    except Exception as exc:
        status = "error"
        error = f"{exc.__class__.__name__}: {exc}"
        raise
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        trace = AgentRunTrace(
            run_id=uuid4().hex,
            project_id=project_id,
            graph=graph,
            node=node,
            agent=agent,
            prompt_profile=prompt_profile,
            prompt_chars=len(prompt),
            estimated_prompt_tokens=estimate_tokens(prompt),
            output_chars=len(output),
            estimated_output_tokens=estimate_tokens(output),
            elapsed_ms=elapsed_ms,
            status=status,
            error=error,
            model_provider=model_provider(adapter),
            model_name=model_name(adapter),
            context_sources=list(context_sources or []),
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        append_agent_trace(project_dir, trace)


def model_provider(adapter: object) -> str | None:
    name = adapter.__class__.__name__.lower()
    if getattr(adapter, "mock", False):
        return "mock"
    if "deepseek" in name:
        return "deepseek"
    if "codex" in name:
        return "codex"
    return adapter.__class__.__name__


def model_name(adapter: object) -> str | None:
    if getattr(adapter, "mock", False):
        return "mock"
    model = getattr(adapter, "model", None)
    if model:
        return str(model)
    codex_bin = getattr(adapter, "codex_bin", None)
    if codex_bin:
        return str(codex_bin)
    return None
