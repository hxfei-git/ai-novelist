"""Drafting graph for chapter prose generation."""

from __future__ import annotations

from typing import Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.artifacts import ArtifactRecord, get_latest_artifact, load_artifact_text, load_artifacts, register_artifact
from ai_novelist.context_builder import build_context
from ai_novelist.progress import ProgressFunc, emit_progress, noop_progress, with_agent_metadata
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


class DraftingSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> None:
        self.adapter = adapter
        self.store = store
        self.progress = progress

    def invoke(self, state: dict) -> dict:
        emit_progress(self.progress, "Drafting 1/8", "正在准备章节卡、场景卡和写作上下文...")
        current = load_drafting_context_node(state, self.adapter, self.store, self.progress)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "Drafting 2/8", with_agent_metadata("正在按场景生成正文草稿...", self.adapter, "chapter_writer"))
        current = draft_scene_batch_node(current, self.adapter, self.store)
        emit_progress(self.progress, "Drafting 3/8", "正在合并场景草稿...")
        current = merge_scenes_node(current, self.store)
        emit_progress(self.progress, "Drafting 4/8", with_agent_metadata("正在增强对白...", self.adapter, "dialogue_enhancer"))
        current = dialogue_enhance_node(current, self.adapter, self.store)
        emit_progress(self.progress, "Drafting 5/8", with_agent_metadata("正在增强氛围和感官描写...", self.adapter, "atmosphere_enhancer"))
        current = atmosphere_enhance_node(current, self.adapter, self.store)
        emit_progress(self.progress, "Drafting 6/8", with_agent_metadata("正在强化章节钩子...", self.adapter, "hook_enhancer"))
        current = hook_enhance_node(current, self.adapter, self.store)
        emit_progress(self.progress, "Drafting 7/8", with_agent_metadata("正在统一风格...", self.adapter, "style_normalizer"))
        current = style_normalize_node(current, self.adapter, self.store)
        emit_progress(self.progress, "Drafting 8/8", "正在保存章节草稿...")
        current = save_draft_node(current, self.store)
        return current


def build_drafting_graph(adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc | None = None) -> CompiledGraph:
    progress_func = progress or noop_progress
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return DraftingSequentialGraph(adapter, store, progress_func)

    graph = StateGraph(dict)
    graph.add_node("load_drafting_context", lambda data: progress_node(progress_func, "Drafting 1/8", "正在准备章节卡、场景卡和写作上下文...", lambda: load_drafting_context_node(data, adapter, store, progress_func)))
    graph.add_node("draft_scene_batch", lambda data: progress_node(progress_func, "Drafting 2/8", with_agent_metadata("正在按场景生成正文草稿...", adapter, "chapter_writer"), lambda: draft_scene_batch_node(data, adapter, store)))
    graph.add_node("merge_scenes", lambda data: progress_node(progress_func, "Drafting 3/8", "正在合并场景草稿...", lambda: merge_scenes_node(data, store)))
    graph.add_node("dialogue_enhance", lambda data: progress_node(progress_func, "Drafting 4/8", with_agent_metadata("正在增强对白...", adapter, "dialogue_enhancer"), lambda: dialogue_enhance_node(data, adapter, store)))
    graph.add_node("atmosphere_enhance", lambda data: progress_node(progress_func, "Drafting 5/8", with_agent_metadata("正在增强氛围和感官描写...", adapter, "atmosphere_enhancer"), lambda: atmosphere_enhance_node(data, adapter, store)))
    graph.add_node("hook_enhance", lambda data: progress_node(progress_func, "Drafting 6/8", with_agent_metadata("正在强化章节钩子...", adapter, "hook_enhancer"), lambda: hook_enhance_node(data, adapter, store)))
    graph.add_node("style_normalize", lambda data: progress_node(progress_func, "Drafting 7/8", with_agent_metadata("正在统一风格...", adapter, "style_normalizer"), lambda: style_normalize_node(data, adapter, store)))
    graph.add_node("save_draft", lambda data: progress_node(progress_func, "Drafting 8/8", "正在保存章节草稿...", lambda: save_draft_node(data, store)))
    graph.set_entry_point("load_drafting_context")
    graph.add_conditional_edges("load_drafting_context", route_after_load, {"continue": "draft_scene_batch", "end": END})
    graph.add_edge("draft_scene_batch", "merge_scenes")
    graph.add_edge("merge_scenes", "dialogue_enhance")
    graph.add_edge("dialogue_enhance", "atmosphere_enhance")
    graph.add_edge("atmosphere_enhance", "hook_enhance")
    graph.add_edge("hook_enhance", "style_normalize")
    graph.add_edge("style_normalize", "save_draft")
    graph.add_edge("save_draft", END)
    return graph.compile()


def progress_node(progress: ProgressFunc, stage: str, message: str, fn) -> dict:
    emit_progress(progress, stage, message)
    return fn()


def route_after_load(data: dict) -> str:
    return "end" if data.get("review_status") == "error" else "continue"


def load_drafting_context_node(data: dict, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> dict:
    state = NovelState.from_dict(data)
    chapter = int(state.director_task_args.get("chapter") or state.current_chapter or state.active_chapter or 1)
    state.active_chapter = max(1, chapter)
    state.current_chapter = state.active_chapter
    state.active_graph = "drafting"
    state.active_stage = "load_drafting_context"
    state.active_artifact = "chapter_draft"
    store.save_state(state)

    state = ensure_chapter_card(state, adapter, store, progress)
    if state.review_status == "error":
        return state.to_dict()
    state = ensure_scene_cards(state, adapter, store, progress)
    if state.review_status == "error":
        return state.to_dict()

    state.current_chapter_card = load_current_chapter_card(state, store)
    state.current_scene_cards = load_current_scene_cards(state, store)
    context = build_context(state, store, "drafting", chapter=state.active_chapter, max_chars=18000)
    state.director_task_args["drafting_context"] = context
    state.last_context_digest = context[:1200]
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def ensure_chapter_card(state: NovelState, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> NovelState:
    if load_current_chapter_card(state, store).strip():
        return state
    from ai_novelist.graph_chapter_plan import build_chapter_plan_graph

    emit_progress(progress, "Drafting", "缺少章节卡，正在自动补齐...")
    result = NovelState.from_dict(build_chapter_plan_graph(adapter, store, progress=progress).invoke(state.to_dict()))
    return result


def ensure_scene_cards(state: NovelState, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> NovelState:
    if load_current_scene_cards(state, store).strip():
        return state
    from ai_novelist.graph_scene import build_scene_graph

    emit_progress(progress, "Drafting", "缺少场景卡，正在自动补齐...")
    result = NovelState.from_dict(build_scene_graph(adapter, store, progress=progress).invoke(state.to_dict()))
    return result


def draft_scene_batch_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    return run_draft_agent(data, adapter, store, "chapter_writer", "draft_scene_batch")


def merge_scenes_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    state.active_stage = "merge_scenes"
    state.chapter_draft = normalize_markdown(state.chapter_draft)
    store.save_state(state)
    return state.to_dict()


def dialogue_enhance_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    return run_draft_agent(data, adapter, store, "dialogue_enhancer", "dialogue_enhance")


def atmosphere_enhance_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    return run_draft_agent(data, adapter, store, "atmosphere_enhancer", "atmosphere_enhance")


def hook_enhance_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    return run_draft_agent(data, adapter, store, "hook_enhancer", "hook_enhance")


def style_normalize_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    return run_draft_agent(data, adapter, store, "style_normalizer", "style_normalize")


def run_draft_agent(data: dict, adapter: AgentAdapter, store: LocalStore, prompt_name: str, stage: str) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_draft_prompt(state, prompt_name)
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.chapter_draft = output.strip()
    state.active_graph = "drafting"
    state.active_stage = stage
    state.review_status = "draft"
    state.error = ""
    state.last_agent_reports = append_agent_report(state.last_agent_reports, prompt_name, "ok", {"chars": len(output)})
    store.save_state(state)
    return state.to_dict()


def save_draft_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    version = 1
    path = store.save_chapter_draft(state, version=version)
    legacy = store.save_chapter(state)
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="chapter_draft",
            path=path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="style_normalizer",
            graph="drafting",
            stage="draft",
            chapter=state.active_chapter,
            summary=summary_line(state.chapter_draft),
            metadata={"legacy_path": legacy.relative_to(store.project_dir(state.project_id)).as_posix(), "draft_version": version},
        ),
    )
    state.active_graph = "drafting"
    state.active_stage = "draft"
    state.active_artifact = "chapter_draft"
    state.director_action = state.director_action or "write_chapter"
    state.director_message = f"第 {state.active_chapter} 章草稿已生成：{path}"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "style_normalizer", "saved", {"artifact_id": record.id, "path": record.path})
    store.save_state(state)
    return state.to_dict()


def build_draft_prompt(state: NovelState, prompt_name: str) -> str:
    template = load_prompt(prompt_name)
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"CHAPTER: {state.active_chapter or state.current_chapter}\n"
        f"REVISION_COUNT: {state.revision_count}\n\n"
        f"## Drafting Context\n{state.director_task_args.get('drafting_context') or '暂无'}\n\n"
        f"## Chapter Card\n{state.current_chapter_card or '暂无'}\n\n"
        f"## Scene Cards\n{state.current_scene_cards or '暂无'}\n\n"
        f"## Current Draft\n{state.chapter_draft or '暂无'}\n"
    )


def load_current_chapter_card(state: NovelState, store: LocalStore) -> str:
    path = store.chapter_card_path(state.project_id, state.active_chapter)
    if path.exists():
        return path.read_text(encoding="utf-8")
    record = get_latest_artifact(store.project_dir(state.project_id), "chapter_card", chapter=state.active_chapter)
    if record:
        return load_artifact_text(store.project_dir(state.project_id), record)
    return state.current_chapter_card if state.current_chapter == state.active_chapter else ""


def load_current_scene_cards(state: NovelState, store: LocalStore) -> str:
    path = store.scene_cards_path(state.project_id, state.active_chapter)
    if path.exists():
        return path.read_text(encoding="utf-8")
    record = get_latest_artifact(store.project_dir(state.project_id), "scene_cards", chapter=state.active_chapter)
    if record:
        return load_artifact_text(store.project_dir(state.project_id), record)
    return state.current_scene_cards if state.current_chapter == state.active_chapter else ""


def normalize_markdown(text: str) -> str:
    return text.strip() + "\n"


def summary_line(content: str, max_chars: int = 160) -> str:
    for line in content.splitlines():
        stripped = line.strip("#：: ")
        if stripped:
            return stripped[:max_chars]
    return content.strip()[:max_chars]


def append_agent_report(reports: list[dict], agent: str, status: str, data: dict) -> list[dict]:
    updated = list(reports)
    updated.append({"agent": agent, "status": status, **data})
    return updated[-20:]
