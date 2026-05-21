"""Search backend abstractions for reference research."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = "mock"
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.metadata is None:
            data.pop("metadata")
        return data


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


class LocalRAGSearchBackend:
    """Lightweight keyword retrieval over local .txt/.md corpus files."""

    SUPPORTED_SUFFIXES = {".txt", ".md"}

    def __init__(self, corpus_dir: str | Path, chunk_size: int = 800, chunk_overlap: int = 120) -> None:
        self.corpus_dir = Path(corpus_dir).expanduser()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        if self.chunk_size < 1:
            raise SearchBackendError("Local RAG chunk_size must be greater than 0")
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_size:
            raise SearchBackendError("Local RAG chunk_overlap must be >= 0 and smaller than chunk_size")

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        normalized = query.strip()
        if not normalized or limit < 1 or not self.corpus_dir.is_dir():
            return []

        terms = query_terms(normalized)
        scored: list[tuple[float, str, int, SearchResult]] = []
        for file_path in sorted(self._corpus_files()):
            text = read_text_file(file_path)
            if not text.strip():
                continue
            relative_path = file_path.relative_to(self.corpus_dir).as_posix()
            for chunk_id, start_offset, end_offset, chunk in chunk_text(text, self.chunk_size, self.chunk_overlap):
                score = local_keyword_score(normalized, terms, chunk, relative_path)
                if score <= 0:
                    continue
                metadata = {
                    "file_path": str(file_path),
                    "relative_path": relative_path,
                    "chapter_name": file_path.stem,
                    "chunk_id": chunk_id,
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "score": score,
                }
                scored.append(
                    (
                        score,
                        relative_path,
                        chunk_id,
                        SearchResult(
                            title=f"{file_path.stem} #{chunk_id}",
                            url=local_corpus_url(relative_path, chunk_id),
                            snippet=clean_snippet(chunk),
                            source="local_corpus",
                            metadata=metadata,
                        ),
                    )
                )
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [item[3] for item in scored[:limit]]

    def _corpus_files(self) -> list[Path]:
        return [
            path
            for path in self.corpus_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_SUFFIXES
        ]


class LocalFirstSearchBackend:
    """Use local corpus results when available, otherwise delegate to fallback."""

    def __init__(self, local_backend: SearchBackend, fallback_backend: SearchBackend) -> None:
        self.local_backend = local_backend
        self.fallback_backend = fallback_backend

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        local_results = self.local_backend.search(query, limit)
        if local_results:
            return local_results
        return self.fallback_backend.search(query, limit)


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
                "type": "auto",
                "numResults": limit,
                "contents": {"highlights": True},
            },
            {"x-api-key": self.api_key},
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


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[tuple[int, int, int, str]]:
    chunks: list[tuple[int, int, int, str]] = []
    start = 0
    chunk_id = 1
    text_length = len(text)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end]
        if chunk.strip():
            chunks.append((chunk_id, start, end, chunk))
            chunk_id += 1
        if end >= text_length:
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks


def query_terms(query: str) -> list[str]:
    lowered = query.lower()
    terms: list[str] = []
    if lowered:
        terms.append(lowered)
    for match in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", lowered):
        if not match.strip() or match in terms:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", match) and len(match) > 2:
            terms.extend(match[idx : idx + 2] for idx in range(len(match) - 1))
        terms.append(match)
    return list(dict.fromkeys(term for term in terms if len(term) > 1 or len(lowered) == 1))


def local_keyword_score(query: str, terms: list[str], text: str, relative_path: str) -> float:
    haystack = f"{relative_path}\n{text}".lower()
    score = 0.0
    lowered_query = query.lower()
    if lowered_query in haystack:
        score += 5.0
    for term in terms:
        if not term:
            continue
        score += haystack.count(term)
    return score


def clean_snippet(text: str, max_length: int = 300) -> str:
    snippet = re.sub(r"\s+", " ", text).strip()
    if len(snippet) <= max_length:
        return snippet
    return snippet[: max_length - 1].rstrip() + "..."


def local_corpus_url(relative_path: str, chunk_id: int) -> str:
    return f"local://corpus/{urllib.parse.quote(relative_path)}#chunk={chunk_id}"

