"""Research workflow for reusable retrieval context."""

from __future__ import annotations

import re
from typing import Callable, Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.prompts import load_prompt
from ai_novelist.research import SearchBackend, SearchBackendError, SearchResult
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore

ProgressFunc = Callable[[str, str], None]


def noop_progress(_stage: str, _message: str) -> None:
    return


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


class ResearchSequentialGraph:
    def __init__(
        self,
        search_backend: SearchBackend,
        store: LocalStore,
        adapter: AgentAdapter | None,
        progress: ProgressFunc,
    ) -> None:
        self.search_backend = search_backend
        self.store = store
        self.adapter = adapter
        self.progress = progress

    def invoke(self, state: dict) -> dict:
        current = detect_research_need(state, self.store, self.progress)
        current = build_research_queries(current, self.store, self.adapter)
        current = search_sources(current, self.search_backend, self.store, self.progress)
        current = synthesize_retrieval_context(current, self.store, self.adapter, self.progress)
        current = synthesize_reference_brief(current, self.store)
        current = save_research_result(current, self.store)
        return ask_user_confirm(current, self.store)


def build_research_graph(
    search_backend: SearchBackend,
    store: LocalStore,
    adapter: AgentAdapter | ProgressFunc | None = None,
    progress: ProgressFunc | None = None,
) -> CompiledGraph:
    if adapter is not None and not hasattr(adapter, "complete"):
        progress = adapter  # Backward compatible with old third positional progress argument.
        adapter = None
    progress_func = progress or noop_progress
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return ResearchSequentialGraph(search_backend, store, adapter, progress_func)

    graph = StateGraph(dict)
    graph.add_node("detect_research_need", lambda data: detect_research_need(data, store, progress_func))
    graph.add_node("build_research_queries", lambda data: build_research_queries(data, store, adapter))
    graph.add_node("search_sources", lambda data: search_sources(data, search_backend, store, progress_func))
    graph.add_node("synthesize_retrieval_context", lambda data: synthesize_retrieval_context(data, store, adapter, progress_func))
    graph.add_node("synthesize_reference_brief", lambda data: synthesize_reference_brief(data, store))
    graph.add_node("save_research_result", lambda data: save_research_result(data, store))
    graph.add_node("ask_user_confirm", lambda data: ask_user_confirm(data, store))
    graph.set_entry_point("detect_research_need")
    graph.add_edge("detect_research_need", "build_research_queries")
    graph.add_edge("build_research_queries", "search_sources")
    graph.add_edge("search_sources", "synthesize_retrieval_context")
    graph.add_edge("synthesize_retrieval_context", "synthesize_reference_brief")
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
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def build_research_queries(data: dict, store: LocalStore, adapter: AgentAdapter | None = None) -> dict:
    state = NovelState.from_dict(data)
    query = research_query_from_director_args(state)
    if not query and adapter is not None:
        try:
            output = adapter.complete(build_research_intent_prompt(state), store.project_dir(state.project_id))
            decision = parse_research_intent_output(output)
            if decision["need_research"] != "no":
                query = decision["query"] or decision["work_title"] or decision["author"]
        except AgentAdapterError:
            query = ""
    query = query or extract_research_query(state.user_request) or state.idea or state.user_request
    state.open_decisions = [item for item in state.open_decisions if not item.startswith("research_query:")]
    state.open_decisions.append(f"research_query:{query}")
    state.retrieval_query = query
    state.current_stage = "build_research_queries"
    store.save_state(state)
    return state.to_dict()


def research_query_from_director_args(state: NovelState) -> str:
    task_args = state.director_task_args if isinstance(state.director_task_args, dict) else {}
    for key in ("research_query", "work_title", "author"):
        value = str(task_args.get(key, "")).strip()
        if value:
            return value
    if state.retrieval_query.strip():
        return state.retrieval_query.strip()
    for item in reversed(state.open_decisions):
        if item.startswith("research_query:"):
            return item.split(":", 1)[1].strip()
    return ""


def search_sources(data: dict, search_backend: SearchBackend, store: LocalStore, progress: ProgressFunc = noop_progress) -> dict:
    state = NovelState.from_dict(data)
    query = research_query_from_state(state)
    state.retrieval_query = query
    progress("Search", f"正在搜索：{query}")
    try:
        results = search_backend.search(query, limit=5)
    except SearchBackendError as exc:
        state.error = str(exc)
        state.review_status = "error"
        state.current_stage = "search_sources"
        store.save_state(state)
        return state.to_dict()
    state.research_sources = [result.to_dict() for result in results]
    state.retrieval_sources = list(state.research_sources)
    state.current_stage = "search_sources"
    store.save_state(state)
    return state.to_dict()


def synthesize_retrieval_context(
    data: dict,
    store: LocalStore,
    adapter: AgentAdapter | None = None,
    progress: ProgressFunc = noop_progress,
) -> dict:
    state = NovelState.from_dict(data)
    if state.error:
        store.save_state(state)
        return state.to_dict()
    progress("Retrieval", "正在整理通用检索上下文...")
    results = search_results_from_state(state)
    if adapter is None:
        state.retrieval_context = fallback_retrieval_context(state, results, "未配置 LLM adapter，使用规则 fallback。")
    else:
        try:
            output = adapter.complete(build_retrieval_context_prompt(state, results), store.project_dir(state.project_id))
        except AgentAdapterError as exc:
            state.retrieval_context = fallback_retrieval_context(state, results, f"LLM 检索总结失败，使用规则 fallback：{exc}")
        else:
            state.retrieval_context = output.strip() or fallback_retrieval_context(state, results, "LLM 返回空内容，使用规则 fallback。")
    state.current_stage = "synthesize_retrieval_context"
    store.save_state(state)
    return state.to_dict()


def synthesize_reference_brief(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if state.error:
        store.save_state(state)
        return state.to_dict()
    query = research_query_from_state(state)
    results = search_results_from_state(state)
    facts = canon_facts_from_results(results)
    uncertainties = [
        "检索结果可能不完整或包含二手资料，不能保证覆盖完整原作设定。",
        "具体人物关系、境界体系、剧情节点需要用户确认后再用于同人创作。",
    ]
    state.canon_facts = facts
    state.research_uncertainties = uncertainties
    source_lines = "\n".join(f"- {item.title}: {item.snippet} ({item.url})" for item in results) or "- 暂无来源"
    fact_lines = "\n".join(f"- {fact}" for fact in facts) or "- 暂无可靠事实"
    uncertainty_lines = "\n".join(f"- {item}" for item in uncertainties)
    retrieval_block = state.retrieval_context.strip() or "暂无"
    state.reference_brief = (
        f"# 参考简报：{query}\n\n"
        "## 通用检索上下文\n"
        f"{retrieval_block}\n\n"
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
    if state.error:
        store.save_state(state)
        return state.to_dict()
    if state.reference_brief.strip():
        store.save_reference_brief(state)
    store.save_research_sources(state)
    state.current_stage = "save_research_result"
    store.save_state(state)
    return state.to_dict()


def ask_user_confirm(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if state.error:
        state.director_message = f"参考调研失败：{state.error}"
        state.active_workflow = ""
        store.save_state(state)
        return state.to_dict()
    state.director_message = "参考调研已完成。请确认是否把这份简报作为同人创作基础，或指出需要修正的原作设定。"
    state.active_workflow = "outline"
    state.current_stage = "confirm_reference_brief"
    state.director_action = "research"
    store.save_state(state)
    return state.to_dict()


def build_research_intent_prompt(state: NovelState) -> str:
    template = load_prompt("research_intent")
    history = "\n".join(f"{msg['role']}: {msg['content']}" for msg in state.messages[-8:])
    return (
        f"{template.rstrip()}\n\n"
        "## 当前项目状态\n"
        f"项目：{state.project_id}\n"
        f"标题：{state.title}\n"
        f"创意：{state.idea or '暂无'}\n"
        f"已有参考简报：{'是' if state.reference_brief else '否'}\n\n"
        f"## 最近对话\n{history or '暂无'}\n\n"
        f"最新用户输入：{state.user_request}\n"
    )


def parse_research_intent_output(output: str) -> dict[str, str]:
    need_research = research_intent_field(output, "NEED_RESEARCH").lower()
    if need_research not in {"yes", "no"}:
        need_research = "yes"
    return {
        "need_research": need_research,
        "query": research_intent_field(output, "QUERY"),
        "work_title": research_intent_field(output, "WORK_TITLE"),
        "author": research_intent_field(output, "AUTHOR"),
        "intent": research_intent_field(output, "INTENT").lower() or "unknown",
        "reason": research_intent_field(output, "REASON"),
    }


def research_intent_field(output: str, field: str) -> str:
    match = re.search(rf"^{field}:\s*(.*)$", output, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def build_retrieval_context_prompt(state: NovelState, results: list[SearchResult]) -> str:
    template = load_prompt("retrieval_context_synthesizer")
    source_lines = "\n".join(
        f"[{idx}] 标题：{item.title}\nURL：{item.url}\n来源：{item.source}\n摘要：{item.snippet}"
        for idx, item in enumerate(results, start=1)
    )
    return (
        f"{template.rstrip()}\n\n"
        "## 检索任务\n"
        f"查询：{state.retrieval_query or research_query_from_state(state)}\n"
        f"用户原始请求：{state.user_request or '暂无'}\n\n"
        "## 原始搜索结果\n"
        f"{source_lines or '暂无搜索结果'}\n"
    )


def fallback_retrieval_context(state: NovelState, results: list[SearchResult], note: str = "") -> str:
    query = state.retrieval_query or research_query_from_state(state)
    source_lines = "\n".join(f"- [source_id: {idx}] {item.title}: {item.snippet} ({item.url})" for idx, item in enumerate(results, start=1)) or "- 暂无来源"
    facts = canon_facts_from_results(results)
    fact_lines = "\n".join(f"- [source_id: {idx}] {fact}" for idx, fact in enumerate(facts, start=1)) or "- 暂无可提取事实"
    note_line = f"\n## 生成说明\n- {note}\n" if note else ""
    return (
        f"# 检索上下文：{query}\n\n"
        "## 查询意图\n"
        f"- {query}\n\n"
        "## 可用事实\n"
        f"{fact_lines}\n\n"
        "## 创作相关线索\n"
        "- 仅作为素材参考，不能直接写成 stable canon。\n\n"
        "## 不确定点\n"
        "- 原作设定、人物关系和专有名词仍需用户确认。\n\n"
        "## 来源索引\n"
        f"{source_lines}\n\n"
        "## 使用边界\n"
        "- 以上内容来自搜索摘要，可能不完整或过时。\n"
        "- 涉及原作设定、人物关系和专有名词时，应要求用户确认后再固化为创作约束。\n"
        "- 不得把二手资料、搜索摘要或论坛猜测直接当作原作正史、硬设定或 stable canon。"
        f"{note_line}"
    )


def search_results_from_state(state: NovelState) -> list[SearchResult]:
    source_items = state.retrieval_sources or state.research_sources
    results: list[SearchResult] = []
    for item in source_items:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        results.append(
            SearchResult(
                title=str(item.get("title", "")),
                url=str(item.get("url", "")),
                snippet=str(item.get("snippet", "")),
                source=str(item.get("source", "search")),
                metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else None,
            )
        )
    return results


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
    for fanfic_match in re.finditer(r"([^，。,.!！?？]{2,30}?)(?:的)?同人(?:小说|文|作品)?", raw):
        candidate = clean_research_query_candidate(fanfic_match.group(1))
        if candidate:
            return candidate
    for marker in ("查一下", "调研", "research"):
        if marker in raw:
            return raw.split(marker, 1)[1].strip(" ：:，,")
    return raw


def clean_research_query_candidate(candidate: str) -> str:
    cleaned = candidate.strip(" ：:，,。.!！?？ ")
    prefixes = (
        "我想写",
        "我想要写",
        "想写",
        "想要写",
        "我要写",
        "请写",
        "帮我写",
        "写",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip(" ：:，,。.!！?？ ")
                changed = True
    generic_terms = {"一本", "一部", "一篇", "一个", "同人", "同人小说", "同人文", "小说"}
    if cleaned in generic_terms:
        return ""
    for generic_prefix in ("一本", "一部", "一篇", "一个"):
        if cleaned.startswith(generic_prefix) and len(cleaned) > len(generic_prefix) + 1:
            cleaned = cleaned[len(generic_prefix):].strip(" ：:，,。.!！?？ ")
    if cleaned in generic_terms or not cleaned:
        return ""
    return cleaned


def research_query_from_state(state: NovelState) -> str:
    if state.retrieval_query.strip():
        return state.retrieval_query.strip()
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
