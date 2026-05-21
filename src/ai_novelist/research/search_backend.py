"""Search backend abstractions for reference research."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = "mock"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class SearchBackend(Protocol):
    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Return search results for the query."""


class SearchBackendError(RuntimeError):
    """Raised when a real search provider cannot return usable results."""


class MockSearchBackend:
    """Deterministic local backend used by tests and mock CLI flows."""

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        normalized = query.strip() or "未知作品"
        if "苟在初圣" in normalized:
            results = [
                SearchResult(
                    title="苟在初圣 - 模拟百科条目",
                    url="mock://novel/gou-zai-chu-sheng/wiki",
                    snippet="模拟资料：网络小说名。主角长期低调求生，在初圣阶段积累资源，核心看点是谨慎成长、境界压制和隐藏身份。",
                ),
                SearchResult(
                    title="苟在初圣 角色与设定讨论 - 模拟论坛",
                    url="mock://novel/gou-zai-chu-sheng/forum",
                    snippet="模拟资料：常见读者印象包括苟道、稳健升级、宗门压力、资源争夺。具体角色名和完整世界观仍需用户确认。",
                ),
                SearchResult(
                    title="苟道修仙类型参考 - 模拟资料",
                    url="mock://genre/cautious-cultivation",
                    snippet="模拟资料：同类作品通常强调保命优先、信息差、隐藏底牌、避免高调冲突。",
                ),
            ]
        else:
            results = [
                SearchResult(
                    title=f"{normalized} - 模拟搜索结果 1",
                    url=f"mock://search/{slugify_query(normalized)}/1",
                    snippet=f"模拟资料：与“{normalized}”相关的公开信息摘要。需要用户确认专有名词、人物关系和原作规则。",
                ),
                SearchResult(
                    title=f"{normalized} - 模拟搜索结果 2",
                    url=f"mock://search/{slugify_query(normalized)}/2",
                    snippet=f"模拟资料：可作为参考的题材、风格或原作信息，但当前 mock 无法保证完整准确。",
                ),
            ]
        return results[:limit]


class WebSearchBackend:
    """Real web search backend for SerpAPI, Tavily, and Exa."""

    DEFAULT_BASE_URLS = {
        "serpapi": "https://serpapi.com/search.json",
        "tavily": "https://api.tavily.com/search",
        "exa": "https://api.exa.ai/search",
    }

    def __init__(
        self,
        provider: str,
        api_key: str,
        base_url: str = "",
        timeout_seconds: int = 20,
    ) -> None:
        self.provider = provider.strip().lower()
        self.api_key = api_key.strip()
        self.base_url = base_url.strip() or self.DEFAULT_BASE_URLS.get(self.provider, "")
        self.timeout_seconds = timeout_seconds
        if self.provider not in self.DEFAULT_BASE_URLS:
            raise SearchBackendError(f"Unsupported search provider: {provider}")
        if not self.api_key:
            raise SearchBackendError(f"Search provider {self.provider} requires an API key")

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        normalized = query.strip()
        if not normalized:
            return []
        if limit < 1:
            return []
        if self.provider == "serpapi":
            payload = self._get_serpapi(normalized, limit)
            return self._parse_serpapi(payload, limit)
        if self.provider == "tavily":
            payload = self._post_json(
                self.base_url,
                {
                    "api_key": self.api_key,
                    "query": normalized,
                    "max_results": limit,
                    "search_depth": "basic",
                    "include_answer": False,
                    "include_raw_content": False,
                },
                {},
            )
            return self._parse_tavily(payload, limit)
        payload = self._post_json(
            self.base_url,
            {
                "query": normalized,
                "numResults": limit,
                "contents": {"text": {"maxCharacters": 500}},
            },
            {"Authorization": f"Bearer {self.api_key}"},
        )
        return self._parse_exa(payload, limit)

    def _get_serpapi(self, query: str, limit: int) -> dict[str, Any]:
        params = urllib.parse.urlencode(
            {"engine": "google", "q": query, "api_key": self.api_key, "num": limit},
            doseq=True,
        )
        separator = "&" if "?" in self.base_url else "?"
        return self._request_json(f"{self.base_url}{separator}{params}", None, {})

    def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        return self._request_json(url, data, {"Content-Type": "application/json", **headers})

    def _request_json(self, url: str, data: bytes | None, headers: dict[str, str]) -> dict[str, Any]:
        request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise SearchBackendError(f"{self.provider} search failed with HTTP {exc.code}: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise SearchBackendError(f"{self.provider} search request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SearchBackendError(f"{self.provider} search timed out after {self.timeout_seconds}s") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SearchBackendError(f"{self.provider} search returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SearchBackendError(f"{self.provider} search returned unexpected JSON")
        return payload

    def _parse_serpapi(self, payload: dict[str, Any], limit: int) -> list[SearchResult]:
        error = payload.get("error")
        if error:
            raise SearchBackendError(f"serpapi search failed: {error}")
        results = []
        for item in payload.get("organic_results", []):
            if not isinstance(item, dict):
                continue
            results.append(
                SearchResult(
                    title=clean_text(item.get("title")),
                    url=clean_text(item.get("link")),
                    snippet=clean_text(item.get("snippet") or nested_get(item, "rich_snippet", "top", "detected_extensions")),
                    source="serpapi",
                )
            )
        return valid_results(results, limit)

    def _parse_tavily(self, payload: dict[str, Any], limit: int) -> list[SearchResult]:
        error = payload.get("error") or payload.get("detail")
        if error:
            raise SearchBackendError(f"tavily search failed: {error}")
        results = []
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            results.append(
                SearchResult(
                    title=clean_text(item.get("title")),
                    url=clean_text(item.get("url")),
                    snippet=clean_text(item.get("content") or item.get("snippet")),
                    source="tavily",
                )
            )
        return valid_results(results, limit)

    def _parse_exa(self, payload: dict[str, Any], limit: int) -> list[SearchResult]:
        error = payload.get("error") or payload.get("message")
        if error and not payload.get("results"):
            raise SearchBackendError(f"exa search failed: {error}")
        results = []
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            snippet = item.get("text") or item.get("summary") or item.get("highlights") or ""
            results.append(
                SearchResult(
                    title=clean_text(item.get("title")),
                    url=clean_text(item.get("url")),
                    snippet=clean_text(snippet),
                    source="exa",
                )
            )
        return valid_results(results, limit)


def nested_get(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current


def valid_results(results: list[SearchResult], limit: int) -> list[SearchResult]:
    valid = [item for item in results if item.title and item.url]
    return valid[:limit]


def clean_text(value: Any) -> str:
    if isinstance(value, list):
        parts = [clean_text(item) for item in value]
        return " ".join(part for part in parts if part)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "").strip()


def slugify_query(value: str) -> str:
    return "-".join(value.lower().split())[:80] or "query"
