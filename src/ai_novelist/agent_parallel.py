"""Controlled parallel execution for independent agent calls."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_novelist.agent_metrics import complete_with_metrics, estimate_tokens


@dataclass(frozen=True)
class AgentJob:
    key: str
    agent: str
    prompt: str
    graph: str
    node: str
    prompt_profile: str | None = None
    context_sources: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class AgentJobResult:
    key: str
    agent: str
    output: str
    elapsed_ms: int | None = None
    prompt_chars: int = 0
    output_chars: int = 0
    estimated_prompt_tokens: int = 0
    estimated_output_tokens: int = 0

    @property
    def estimated_total_tokens(self) -> int:
        return self.estimated_prompt_tokens + self.estimated_output_tokens


def parallel_agents_enabled() -> bool:
    return os.getenv("AI_NOVELIST_PARALLEL_AGENTS", "0").strip() == "1"


def max_parallel_agents(default: int = 3) -> int:
    raw = os.getenv("AI_NOVELIST_MAX_PARALLEL_AGENTS", str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, min(value, 8))


def run_agent_jobs(*, adapter, project_dir: Path, project_id: str, jobs: list[AgentJob]) -> list[AgentJobResult]:
    if not jobs:
        return []
    if not parallel_agents_enabled() or len(jobs) == 1:
        return [run_one_job(adapter, project_dir, project_id, job) for job in jobs]

    results: dict[str, AgentJobResult] = {}
    with ThreadPoolExecutor(max_workers=min(max_parallel_agents(), len(jobs))) as executor:
        future_to_key = {
            executor.submit(run_one_job, adapter, project_dir, project_id, job): job.key
            for job in jobs
        }
        for future in as_completed(future_to_key):
            result = future.result()
            results[result.key] = result
    return [results[job.key] for job in jobs]


def run_one_job(adapter, project_dir: Path, project_id: str, job: AgentJob) -> AgentJobResult:
    start = time.perf_counter()
    output = complete_with_metrics(
        adapter=adapter,
        prompt=job.prompt,
        project_dir=project_dir,
        project_id=project_id,
        graph=job.graph,
        node=job.node,
        agent=job.agent,
        prompt_profile=job.prompt_profile,
        context_sources=job.context_sources,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return AgentJobResult(
        key=job.key,
        agent=job.agent,
        output=output,
        elapsed_ms=elapsed_ms,
        prompt_chars=len(job.prompt),
        output_chars=len(output),
        estimated_prompt_tokens=estimate_tokens(job.prompt),
        estimated_output_tokens=estimate_tokens(output),
    )
