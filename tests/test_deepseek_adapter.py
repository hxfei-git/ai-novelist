import json
import urllib.error

import pytest

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


def test_deepseek_adapter_posts_chat_completion(monkeypatch, tmp_path):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"choices": [{"message": {"content": "完成"}}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    adapter = DeepSeekAdapter(api_key="sk-test", model="deepseek-chat", timeout_seconds=12)

    assert adapter.complete("写一个大纲", tmp_path) == "完成"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["timeout"] == 12
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["payload"]["model"] == "deepseek-chat"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "写一个大纲"}]


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
