import json

import pytest

from ai_novelist.adapters.base import AgentAdapterError
from ai_novelist.agent_metrics import complete_with_metrics


class FakeAdapter:
    model = "fake-model"

    def complete(self, prompt, workspace, options=None):
        assert options.agent == "fake_agent"
        return "short output"


class FailingAdapter:
    def complete(self, prompt, workspace, options=None):
        raise AgentAdapterError("boom")


def read_traces(project_dir):
    path = project_dir / "debug" / "agent_runs.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_complete_with_metrics_writes_success_trace_without_prompt_or_output(tmp_path):
    project_dir = tmp_path / "demo"
    prompt = "secret prompt " * 100

    output = complete_with_metrics(
        adapter=FakeAdapter(),
        prompt=prompt,
        project_dir=project_dir,
        project_id="demo",
        graph="graph",
        node="node",
        agent="fake_agent",
        prompt_profile="profile",
        context_sources=[{"section": "task", "included_chars": 12}],
    )

    assert output == "short output"
    trace = read_traces(project_dir)[0]
    assert trace["status"] == "ok"
    assert trace["prompt_chars"] == len(prompt)
    assert trace["estimated_prompt_tokens"] > 0
    assert trace["output_chars"] == len(output)
    assert trace["estimated_output_tokens"] > 0
    assert trace["prompt_profile"] == "profile"
    assert "secret prompt" not in json.dumps(trace, ensure_ascii=False)
    assert "short output" not in json.dumps(trace, ensure_ascii=False)


def test_complete_with_metrics_writes_error_trace_and_reraises(tmp_path):
    project_dir = tmp_path / "demo"

    with pytest.raises(AgentAdapterError):
        complete_with_metrics(
            adapter=FailingAdapter(),
            prompt="prompt",
            project_dir=project_dir,
            project_id="demo",
            graph="graph",
            node="node",
            agent="fake_agent",
        )

    trace = read_traces(project_dir)[0]
    assert trace["status"] == "error"
    assert "boom" in trace["error"]
