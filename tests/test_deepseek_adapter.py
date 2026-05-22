import json
import urllib.error

import pytest

from ai_novelist.adapters.base import AgentCallOptions
from ai_novelist.adapters.deepseek import DeepSeekAdapter, DeepSeekAPIError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def capture_deepseek_payload(monkeypatch, response_payload=None):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(response_payload or {"choices": [{"message": {"content": "完成"}}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return captured


def test_deepseek_adapter_posts_chat_completion(monkeypatch, tmp_path):
    captured = capture_deepseek_payload(monkeypatch)
    adapter = DeepSeekAdapter(api_key="sk-test", model="deepseek-chat", timeout_seconds=12)

    assert adapter.complete("写一个大纲", tmp_path) == "完成"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["timeout"] == 12
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["payload"]["model"] == "deepseek-chat"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "写一个大纲"}]


@pytest.mark.parametrize("agent", ["director", "chapter_goal_agent"])
def test_deepseek_disables_thinking_for_fast_agents(monkeypatch, tmp_path, agent):
    captured = capture_deepseek_payload(monkeypatch)
    adapter = DeepSeekAdapter(api_key="sk-test", temperature=0.4)

    assert adapter.complete(f"AGENT: {agent}\n写作任务", tmp_path) == "完成"

    payload = captured["payload"]
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["temperature"] == 0.4
    assert "reasoning_effort" not in payload


@pytest.mark.parametrize(
    "agent",
    ["retrieval_context_synthesizer", "chapter_writer", "review_synthesizer"],
)
def test_deepseek_enables_medium_thinking_for_synthesis_agents(monkeypatch, tmp_path, agent):
    captured = capture_deepseek_payload(monkeypatch)
    adapter = DeepSeekAdapter(api_key="sk-test")

    assert adapter.complete(f"AGENT: {agent}\n写作任务", tmp_path) == "完成"

    payload = captured["payload"]
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "medium"
    assert "temperature" not in payload


def test_deepseek_defaults_unknown_prompt_to_medium_thinking(monkeypatch, tmp_path):
    captured = capture_deepseek_payload(monkeypatch)
    adapter = DeepSeekAdapter(api_key="sk-test")

    assert adapter.complete("没有 AGENT 头的任务", tmp_path) == "完成"

    payload = captured["payload"]
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "medium"
    assert "temperature" not in payload


def test_deepseek_options_agent_overrides_prompt_header(monkeypatch, tmp_path):
    captured = capture_deepseek_payload(monkeypatch)
    adapter = DeepSeekAdapter(api_key="sk-test")

    assert (
        adapter.complete(
            "AGENT: director\n写作任务",
            tmp_path,
            options=AgentCallOptions(agent="chapter_writer", task="draft", stage="chapter"),
        )
        == "完成"
    )

    payload = captured["payload"]
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "medium"
    assert "temperature" not in payload


def test_deepseek_ignores_reasoning_content(monkeypatch, tmp_path):
    captured = capture_deepseek_payload(
        monkeypatch,
        {"choices": [{"message": {"content": "正文", "reasoning_content": "内部推理"}}]},
    )
    adapter = DeepSeekAdapter(api_key="sk-test")

    assert adapter.complete("AGENT: chapter_writer\n写作任务", tmp_path) == "正文"
    assert captured["payload"]["reasoning_effort"] == "medium"


def test_deepseek_adapter_requires_api_key(tmp_path):
    adapter = DeepSeekAdapter(api_key="")

    with pytest.raises(DeepSeekAPIError, match="DEEPSEEK_API_KEY"):
        adapter.complete("prompt", tmp_path)


def test_deepseek_adapter_raises_on_http_error(monkeypatch, tmp_path):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    adapter = DeepSeekAdapter(api_key="sk-test")

    with pytest.raises(DeepSeekAPIError, match="HTTP 401"):
        adapter.complete("prompt", tmp_path)
