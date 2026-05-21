"""Research workflow for canon/reference briefs."""

from __future__ import annotations

import re
from typing import Callable, Protocol

from ai_novelist.research import SearchBackend, SearchResult
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore

ProgressFunc = Callable[[str, str], None]


def noop_progress(_stage: str, _message: str) -> None:
    return


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


class ResearchSequentialGraph:
    def __init__(self, search_backend: SearchBackend, store: LocalStore, progress: ProgressFunc) -> None:
        self.search_backend = search_backend
        self.store = store
        self.progress = progress

    def invoke(self, state: dict) -> dict:
        current = detect_research_need(state, self.store, self.progress)
        current = build_research_queries(current, self.store)
        current = search_sources(current, self.search_backend, self.store, self.progress)
        current = synthesize_reference_brief(current, self.store)
        current = save_research_result(current, self.store)
        return ask_user_confirm(current, self.store)


def build_research_graph(search_backend: SearchBackend, store: LocalStore, progress: ProgressFunc | None = None) -> CompiledGraph:
    progress_func = progress or noop_progress
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return ResearchSequentialGraph(search_backend, store, progress_func)

    graph = StateGraph(dict)
    graph.add_node("detect_research_need", lambda data: detect_research_need(data, store, progress_func))
    graph.add_node("build_research_queries", lambda data: build_research_queries(data, store))
    graph.add_node("search_sources", lambda data: search_sources(data, search_backend, store, progress_func))
    graph.add_node("synthesize_reference_brief", lambda data: synthesize_reference_brief(data, store))
    graph.add_node("save_research_result", lambda data: save_research_result(data, store))
    graph.add_node("ask_user_confirm", lambda data: ask_user_confirm(data, store))
    graph.set_entry_point("detect_research_need")
    graph.add_edge("detect_research_need", "build_research_queries")
    graph.add_edge("build_research_queries", "search_sources")
    graph.add_edge("search_sources", "synthesize_reference_brief")
    graph.add_edge("synthesize_reference_brief", "save_research_result")
    graph.add_edge("save_research_result", "ask_user_confirm")
    graph.add_edge("ask_user_confirm", END)
    return graph.compile()


def detect_research_need(data: dict, store: LocalStore, progress: ProgressFunc = noop_progress) -> dict:
    progress("Research", "正在识别需要调研的原作信息...")
    state = NovelState.from_dict(data)
    state.active_workflow = "research"
    state.current_stage = "detect_research_need"
    state.director_action = "research"
    state.active_artifact = "reference"
    state.review_status = "draft"
    store.save_state(state)
    return state.to_dict()


def build_research_queries(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    query = extract_research_query(state.user_request) or state.idea or state.user_request
    state.open_decisions = [f"research_query:{query}"]
    state.current_stage = "build_research_queries"
    store.save_state(state)
    return state.to_dict()


def search_sources(data: dict, search_backend: SearchBackend, store: LocalStore, progress: ProgressFunc = noop_progress) -> dict:
    state = NovelState.from_dict(data)
    query = research_query_from_state(state)
    progress("Search", f"正在搜索：{query}")
    results = search_backend.search(query, limit=5)
    state.research_sources = [result.to_dict() for result in results]
    state.current_stage = "search_sources"
    store.save_state(state)
    return state.to_dict()


def synthesize_reference_brief(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    query = research_query_from_state(state)
    results = [SearchResult(**item) for item in state.research_sources if item.get("title")]
    facts = canon_facts_from_results(results)
    uncertainties = [
        "当前为 mock 调研结果，不能保证覆盖完整原作设定。",
        "具体人物关系、境界体系、剧情节点需要用户确认后再用于同人创作。",
    ]
    state.canon_facts = facts
    state.research_uncertainties = uncertainties
    source_lines = "\n".join(f"- {item.title}: {item.snippet} ({item.url})" for item in results) or "- 暂无来源"
    fact_lines = "\n".join(f"- {fact}" for fact in facts) or "- 暂无可靠事实"
    uncertainty_lines = "\n".join(f"- {item}" for item in uncertainties)
    state.reference_brief = (
        f"# 参考简报：{query}\n\n"
        "## 可用原作/题材事实\n"
        f"{fact_lines}\n\n"
        "## 来源摘要\n"
        f"{source_lines}\n\n"
        "## 不确定点\n"
        f"{uncertainty_lines}\n\n"
        "## 使用建议\n"
        "在生成同人大纲前，请让用户确认这些事实是否可作为创作基础；不确定信息不得擅自当作原作设定。"
    )
    state.current_stage = "synthesize_reference_brief"
    store.save_state(state)
    return state.to_dict()


def save_research_result(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if state.reference_brief.strip():
        store.save_reference_brief(state)
    store.save_research_sources(state)
    state.current_stage = "save_research_result"
    store.save_state(state)
    return state.to_dict()


def ask_user_confirm(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    state.director_message = "参考调研已完成。请确认是否把这份简报作为同人创作基础，或指出需要修正的原作设定。"
    state.active_workflow = "outline"
    state.current_stage = "confirm_reference_brief"
    state.director_action = "research"
    store.save_state(state)
    return state.to_dict()


def detect_research_need_text(text: str, has_reference_brief: bool = False) -> bool:
    if text.strip().lower().startswith("/research"):
        return True
    if has_reference_brief:
        return False
    if "苟在初圣" in text:
        return True
    lowered = text.lower()
    markers = ("同人", "原作", "参考网络", "查一下", "调研", "research", "小说名")
    if any(marker in lowered or marker in text for marker in markers):
        return True
    return bool(re.search(r"写\s*[《\"]?[^，。,.!！?？]{2,20}[》\"]?同人", text))


def extract_research_query(text: str) -> str:
    raw = text.strip()
    if raw.lower().startswith("/research"):
        return raw[len("/research"):].strip()
    quote_match = re.search(r"[《\"]([^》\"]+)[》\"]", raw)
    if quote_match:
        return quote_match.group(1).strip()
    fanfic_match = re.search(r"写\s*([^，。,.!！?？]{2,30}?)(?:的)?同人", raw)
    if fanfic_match:
        return fanfic_match.group(1).strip()
    for marker in ("查一下", "调研", "research"):
        if marker in raw:
            return raw.split(marker, 1)[1].strip(" ：:，,")
    return raw


def research_query_from_state(state: NovelState) -> str:
    for item in reversed(state.open_decisions):
        if item.startswith("research_query:"):
            return item.split(":", 1)[1]
    return extract_research_query(state.user_request) or state.idea or state.user_request


def canon_facts_from_results(results: list[SearchResult]) -> list[str]:
    facts: list[str] = []
    for result in results[:5]:
        snippet = result.snippet.strip()
        if snippet and snippet not in facts:
            facts.append(snippet)
    return facts
