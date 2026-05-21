"""Minimal outline generation graph."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore

ReviewFunc = Callable[[NovelState], str]


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


class SequentialGraph:
    def __init__(self, nodes: list[Callable[[dict], dict]]) -> None:
        self.nodes = nodes

    def invoke(self, state: dict) -> dict:
        current = dict(state)
        for node in self.nodes:
            current.update(node(current))
        return current


def build_minimal_graph(
    adapter: AgentAdapter,
    store: LocalStore,
    review_func: ReviewFunc,
) -> CompiledGraph:
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return SequentialGraph(
            [
                lambda data: generate_outline(data, adapter, store),
                lambda data: human_review(data, review_func),
                lambda data: persist_outline(data, store),
            ]
        )

    graph = StateGraph(dict)
    graph.add_node("generate_outline", lambda data: generate_outline(data, adapter, store))
    graph.add_node("human_review", lambda data: human_review(data, review_func))
    graph.add_node("persist_outline", lambda data: persist_outline(data, store))
    graph.set_entry_point("generate_outline")
    graph.add_edge("generate_outline", "human_review")
    graph.add_edge("human_review", "persist_outline")
    graph.add_edge("persist_outline", END)
    return graph.compile()


def generate_outline(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_outline_prompt(state)
    workspace = store.project_dir(state.project_id)
    try:
        outline = adapter.complete(prompt, workspace)
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()

    state.outline = outline
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def human_review(data: dict, review_func: ReviewFunc) -> dict:
    state = NovelState.from_dict(data)
    if state.review_status == "error":
        return state.to_dict()

    decision = review_func(state).strip().lower()
    if decision in {"approve", "approved", "y", "yes", "确认", "通过"}:
        state.review_status = "approved"
    elif decision in {"reject", "rejected", "n", "no", "驳回", "拒绝"}:
        state.review_status = "rejected"
    else:
        state.review_status = "rejected"
        state.error = f"Unknown review decision: {decision}"
    return state.to_dict()


def persist_outline(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if state.review_status == "approved":
        store.save_outline(state)
    store.save_state(state)
    return state.to_dict()


def build_outline_prompt(state: NovelState) -> str:
    return (
        "你是一个资深中文小说策划。请基于用户创意输出一份简洁但可执行的小说总大纲。\n"
        "要求：使用 Markdown；包含核心卖点、主角、世界观、三幕结构、主要冲突和下一步细纲建议。\n"
        f"小说标题：{state.title}\n"
        f"用户创意：{state.idea}"
    )
