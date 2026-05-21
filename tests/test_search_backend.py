import json
import urllib.error

import pytest

from ai_novelist.research import (
    LocalFirstSearchBackend,
    LocalRAGSearchBackend,
    SearchBackendError,
    SearchResult,
    WebSearchBackend,
)


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


def test_local_rag_backend_reads_txt_md_and_returns_metadata(tmp_path):
    corpus = tmp_path / "corpus"
    (corpus / "nested").mkdir(parents=True)
    (corpus / "chapter1.txt").write_text("月影城有一座静默钟塔。主角在钟塔下发现失忆线索。", encoding="utf-8")
    (corpus / "nested" / "chapter2.md").write_text("# 第二章\n银色档案馆记录月影城的旧案。", encoding="utf-8")
    (corpus / "skip.pdf").write_text("月影城", encoding="utf-8")

    backend = LocalRAGSearchBackend(corpus, chunk_size=20, chunk_overlap=5)
    results = backend.search("月影城", limit=5)

    assert results
    assert {item.source for item in results} == {"local_corpus"}
    assert all(item.metadata for item in results)
    assert results[0].url.startswith("local://corpus/")
    assert "chunk=" in results[0].url
    assert results[0].metadata["relative_path"].endswith(("chapter1.txt", "chapter2.md"))
    assert results[0].metadata["chapter_name"] in {"chapter1", "chapter2"}
    assert isinstance(results[0].metadata["start_offset"], int)
    assert isinstance(results[0].metadata["end_offset"], int)


def test_local_rag_backend_orders_keyword_hits(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.txt").write_text("星门 星门 星门 冷湖", encoding="utf-8")
    (corpus / "b.txt").write_text("星门 冷湖", encoding="utf-8")

    results = LocalRAGSearchBackend(corpus).search("星门", limit=2)

    assert results[0].metadata["relative_path"] == "a.txt"
    assert results[1].metadata["relative_path"] == "b.txt"


def test_local_rag_backend_returns_empty_for_missing_or_empty_dir(tmp_path):
    assert LocalRAGSearchBackend(tmp_path / "missing").search("月影城") == []

    empty = tmp_path / "empty"
    empty.mkdir()
    assert LocalRAGSearchBackend(empty).search("月影城") == []


def test_local_rag_backend_ignores_single_chinese_character_noise(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "chapter.md").write_text("主角在山中修行，尚未出现目标作品。", encoding="utf-8")

    assert LocalRAGSearchBackend(corpus).search("苟在初圣") == []


class CountingFallbackBackend:
    def __init__(self):
        self.calls = 0

    def search(self, query: str, limit: int = 5):
        self.calls += 1
        return [SearchResult(title="fallback", url="mock://fallback", snippet=query)]


def test_local_first_backend_skips_fallback_when_local_hits(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "chapter.md").write_text("青铜门后是月影城。", encoding="utf-8")
    fallback = CountingFallbackBackend()

    results = LocalFirstSearchBackend(LocalRAGSearchBackend(corpus), fallback).search("月影城")

    assert results[0].source == "local_corpus"
    assert fallback.calls == 0


def test_local_first_backend_uses_fallback_when_local_misses(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "chapter.md").write_text("青铜门后没有目标词。", encoding="utf-8")
    fallback = CountingFallbackBackend()

    results = LocalFirstSearchBackend(LocalRAGSearchBackend(corpus), fallback).search("月影城")

    assert results[0].title == "fallback"
    assert fallback.calls == 1

