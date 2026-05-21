"""Search backend abstractions for reference research."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol


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
    """Placeholder for future SerpAPI/Tavily/Exa implementations."""

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        raise NotImplementedError("WebSearchBackend is not configured yet. Use MockSearchBackend for now.")


def slugify_query(value: str) -> str:
    return "-".join(value.lower().split())[:80] or "query"
