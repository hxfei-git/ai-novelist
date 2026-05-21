import json
import urllib.error

import pytest

from ai_novelist.research import SearchBackendError, WebSearchBackend


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_serpapi_backend_gets_and_parses_organic_results(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "organic_results": [
                    {"title": "条目", "link": "https://example.test/a", "snippet": "摘要"},
                    {"title": "无链接", "snippet": "跳过"},
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = WebSearchBackend("serpapi", "serp-key", timeout_seconds=7)

    results = backend.search("苟在初圣", limit=3)

    assert captured["method"] == "GET"
    assert captured["timeout"] == 7
    assert "api_key=serp-key" in captured["url"]
    assert results[0].title == "条目"
    assert results[0].url == "https://example.test/a"
    assert results[0].snippet == "摘要"
    assert results[0].source == "serpapi"
    assert len(results) == 1


def test_tavily_backend_posts_and_parses_results(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"results": [{"title": "页面", "url": "https://example.test/b", "content": "正文摘要"}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = WebSearchBackend("tavily", "tavily-key")

    results = backend.search("月球城市", limit=2)

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["payload"]["api_key"] == "tavily-key"
    assert captured["payload"]["query"] == "月球城市"
    assert captured["payload"]["max_results"] == 2
    assert results[0].source == "tavily"
    assert results[0].snippet == "正文摘要"


def test_exa_backend_posts_x_api_key_and_parses_highlights(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"requestId": "req", "results": [{"title": "资料", "url": "https://example.test/c", "highlights": ["重点一", "重点二"]}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = WebSearchBackend("exa", "exa-key")

    results = backend.search("原作设定", limit=1)

    assert captured["headers"]["X-api-key"] == "exa-key"
    assert captured["payload"]["type"] == "auto"
    assert captured["payload"]["numResults"] == 1
    assert captured["payload"]["contents"] == {"highlights": True}
    assert results[0].source == "exa"
    assert results[0].snippet == "重点一 重点二"


def test_web_search_backend_requires_supported_provider_and_key():
    with pytest.raises(SearchBackendError, match="Unsupported search provider"):
        WebSearchBackend("unknown", "key")
    with pytest.raises(SearchBackendError, match="requires an API key"):
        WebSearchBackend("serpapi", "")


def test_web_search_backend_raises_on_http_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    backend = WebSearchBackend("serpapi", "serp-key")

    with pytest.raises(SearchBackendError, match="HTTP 401"):
        backend.search("query")

