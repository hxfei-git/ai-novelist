import time

import pytest

from ai_novelist.adapters.base import AgentAdapterError
from ai_novelist.agent_parallel import AgentJob, run_agent_jobs


class SlowAdapter:
    def complete(self, prompt, workspace, options=None):
        time.sleep(0.01)
        return f"output for {options.agent}"


class FailingAdapter:
    def complete(self, prompt, workspace, options=None):
        raise AgentAdapterError("fail")


def test_run_agent_jobs_preserves_input_order_when_parallel_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    jobs = [AgentJob(key=str(i), agent=f"agent_{i}", prompt="prompt", graph="g", node="n") for i in range(4)]

    results = run_agent_jobs(adapter=SlowAdapter(), project_dir=tmp_path / "demo", project_id="demo", jobs=jobs)

    assert [item.key for item in results] == ["0", "1", "2", "3"]
    assert [item.output for item in results] == [f"output for agent_{i}" for i in range(4)]


def test_run_agent_jobs_reraises_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    jobs = [AgentJob(key="a", agent="agent", prompt="prompt", graph="g", node="n")]

    with pytest.raises(AgentAdapterError):
        run_agent_jobs(adapter=FailingAdapter(), project_dir=tmp_path / "demo", project_id="demo", jobs=jobs)
