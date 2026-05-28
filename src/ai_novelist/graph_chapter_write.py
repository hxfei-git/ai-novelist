"""Direct chapter writing graph based on Novel Bible and chapter outline."""

from __future__ import annotations

import json
import re
from typing import Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.artifacts import ArtifactRecord, load_artifacts, register_artifact
from ai_novelist.bible import load_bible, render_bible_markdown
from ai_novelist.corpus.craft_resolver import resolve_author_craft
from ai_novelist.context_builder import build_context_bundle, build_context_manifest
from ai_novelist.corpus.similarity_guard import save_similarity_report_for_state
from ai_novelist.graph_chapter_plan import collect_chapter_outline
from ai_novelist.progress import ProgressFunc, emit_progress, noop_progress, run_with_progress, with_agent_metadata
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


class DirectChapterWriteSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> None:
        self.adapter = adapter
        self.store = store
        self.progress = progress

    def invoke(self, state: dict) -> dict:
        emit_progress(self.progress, "ChapterWrite 1/5", "正在读取小说圣经和章节大纲...")
        current = load_direct_write_context_node(state, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "ChapterWrite 2/5", with_agent_metadata("正在直接生成章节正文...", self.adapter, "direct_chapter_writer"))
        current = draft_chapter_node(current, self.adapter, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "ChapterWrite 3/5", "正在保存初稿...")
        current = save_direct_draft_node(current, self.store, version=1, source_agent="direct_chapter_writer", stage="draft")
        emit_progress(self.progress, "ChapterWrite 4/5", with_agent_metadata("正在执行自动一致性修订...", self.adapter, "chapter_auto_reviser"))
        current = auto_revise_chapter_node(current, self.adapter, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "ChapterWrite 5/5", "正在保存修订稿...")
        current = save_direct_draft_node(current, self.store, version=2, source_agent="chapter_auto_reviser", stage="auto_revision")
        return current


def build_chapter_write_graph(adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc | None = None) -> CompiledGraph:
    progress_func = progress or noop_progress
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return DirectChapterWriteSequentialGraph(adapter, store, progress_func)

    graph = StateGraph(dict)
    graph.add_node("load_context", lambda data: progress_node(progress_func, "ChapterWrite 1/5", "正在读取小说圣经和章节大纲...", lambda: load_direct_write_context_node(data, store)))
    graph.add_node("draft_chapter", lambda data: progress_node(progress_func, "ChapterWrite 2/5", with_agent_metadata("正在直接生成章节正文...", adapter, "direct_chapter_writer"), lambda: draft_chapter_node(data, adapter, store)))
    graph.add_node("save_draft", lambda data: progress_node(progress_func, "ChapterWrite 3/5", "正在保存初稿...", lambda: save_direct_draft_node(data, store, version=1, source_agent="direct_chapter_writer", stage="draft")))
    graph.add_node("auto_revise", lambda data: progress_node(progress_func, "ChapterWrite 4/5", with_agent_metadata("正在执行自动一致性修订...", adapter, "chapter_auto_reviser"), lambda: auto_revise_chapter_node(data, adapter, store)))
    graph.add_node("save_revision", lambda data: progress_node(progress_func, "ChapterWrite 5/5", "正在保存修订稿...", lambda: save_direct_draft_node(data, store, version=2, source_agent="chapter_auto_reviser", stage="auto_revision")))
    graph.set_entry_point("load_context")
    graph.add_conditional_edges("load_context", route_after_load, {"continue": "draft_chapter", "end": END})
    graph.add_conditional_edges("draft_chapter", route_after_load, {"continue": "save_draft", "end": END})
    graph.add_edge("save_draft", "auto_revise")
    graph.add_conditional_edges("auto_revise", route_after_load, {"continue": "save_revision", "end": END})
    graph.add_edge("save_revision", END)
    return graph.compile()


def progress_node(progress: ProgressFunc, stage: str, message: str, fn) -> dict:
    return run_with_progress(progress, stage, message, fn)


def route_after_load(data: dict) -> str:
    return "end" if data.get("review_status") == "error" else "continue"


def load_direct_write_context_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    chapter = int(state.director_task_args.get("chapter") or state.current_chapter or state.active_chapter or 1)
    state.active_chapter = max(1, chapter)
    state.current_chapter = state.active_chapter
    state.active_graph = "chapter_write"
    state.active_stage = "load_context"
    state.active_artifact = "chapter_draft"
    state.current_chapter_card = ""
    state.current_scene_cards = ""
    chapter_outline = collect_chapter_outline(state, store)
    if not chapter_outline.strip() or chapter_outline.strip() == "暂无":
        chapter_outline = f"第 {state.active_chapter} 章：章节大纲缺失，按小说圣经、锁定约束和用户请求生成兼容草稿。"
    state.director_task_args["selected_chapter_outline"] = chapter_outline
    state = resolve_author_craft(state, store, "drafting", chapter=state.active_chapter)
    bundle = build_context_bundle(state, store, "direct_chapter_drafting", chapter=state.active_chapter)
    context = bundle.text
    state.director_task_args["direct_chapter_context_manifest"] = build_context_manifest(bundle)
    state.director_task_args["direct_chapter_context"] = context
    state.last_context_digest = context[:1200]
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def draft_chapter_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if state.review_status == "error":
        return state.to_dict()
    prompt = build_direct_chapter_prompt(state, "direct_chapter_writer")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.chapter_draft = normalize_markdown(output)
    state.active_stage = "draft"
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "direct_chapter_writer", "ok", {"chars": len(output)})
    store.save_state(state)
    return state.to_dict()


def auto_revise_chapter_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if state.review_status == "error":
        return state.to_dict()
    prompt = build_direct_chapter_prompt(state, "chapter_auto_reviser")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.chapter_draft = normalize_markdown(output)
    state.current_revision_plan = "自动一致性修订：检查并修复章节大纲完成度、小说圣经一致性、前后文连贯性、人物状态和设定边界。"
    state.revision_count = max(state.revision_count, 1)
    state.active_stage = "auto_revision"
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "chapter_auto_reviser", "ok", {"chars": len(output)})
    store.save_state(state)
    return state.to_dict()


def save_direct_draft_node(data: dict, store: LocalStore, *, version: int, source_agent: str, stage: str) -> dict:
    state = NovelState.from_dict(data)
    if state.review_status == "error":
        return state.to_dict()
    path = store.save_chapter_draft(state, version=version)
    legacy = store.save_chapter(state)
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="chapter_draft",
            path=path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent=source_agent,
            graph="chapter_write",
            stage=stage,
            chapter=state.active_chapter,
            summary=summary_line(state.chapter_draft),
            metadata={"legacy_path": legacy.relative_to(store.project_dir(state.project_id)).as_posix(), "draft_version": version},
        ),
    )
    state.active_graph = "chapter_write"
    state.active_stage = stage
    state.active_artifact = "chapter_draft"
    state.director_action = state.director_action or "write_chapter"
    state.next_action = "human_review"
    state.review_status = "draft"
    state.director_message = f"第 {state.active_chapter} 章已生成并完成自动修订：{path}"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, source_agent, "saved", {"artifact_id": record.id, "path": record.path})
    state = save_similarity_report_for_state(state, store, f"draft_v{version}", state.chapter_draft)
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    store.save_state(state)
    return state.to_dict()


def build_direct_chapter_prompt(state: NovelState, prompt_name: str) -> str:
    template = load_prompt(prompt_name)
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"CHAPTER: {state.active_chapter or state.current_chapter}\n\n"
        f"## Direct Chapter Context\n{state.director_task_args.get('direct_chapter_context') or '暂无'}\n\n"
        f"## Current Draft\n{state.chapter_draft or '暂无'}\n"
    )


def build_direct_chapter_context_bundle(state: NovelState, store: LocalStore, max_chars: int = 18000):
    chapter = state.active_chapter or state.current_chapter
    return build_context_bundle(state, store, "direct_chapter_drafting", chapter=chapter, max_chars=max_chars)


def build_direct_chapter_context(state: NovelState, store: LocalStore, max_chars: int = 18000) -> str:
    return build_direct_chapter_context_bundle(state, store, max_chars=max_chars).text


def build_bible_text(state: NovelState, store: LocalStore) -> str:
    path = store.novel_bible_markdown_path(state.project_id)
    if path.exists():
        return path.read_text(encoding="utf-8")
    bible = load_bible(store.project_dir(state.project_id))
    return render_bible_markdown(bible) or "暂无"


def build_previous_summaries(state: NovelState) -> str:
    current = state.active_chapter or state.current_chapter or 1
    lines = []
    for key, summary in sorted(state.chapter_summaries.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 0):
        if str(key).isdigit() and int(key) < current and str(summary).strip():
            lines.append(f"- 第 {key} 章：{str(summary).strip()}")
    return "\n".join(lines) or "暂无"


def build_author_craft_text(state: NovelState, store: LocalStore) -> str:
    if state.craft_mode == "off" or not state.active_craft_brief_path:
        return "暂无"
    path = store.project_dir(state.project_id) / state.active_craft_brief_path
    if path.exists():
        return path.read_text(encoding="utf-8")
    return state.craft_context_digest or "暂无"


def truncate_sections(sections: list[tuple[str, str]], max_chars: int) -> str:
    rendered: list[str] = []
    remaining = max_chars
    for title, content in sections:
        body = str(content or "暂无").strip() or "暂无"
        header = f"## {title}\n"
        budget = max(400, remaining // max(1, len(sections) - len(rendered)))
        if len(body) > budget:
            body = body[:budget].rstrip() + "\n..."
        part = header + body
        rendered.append(part)
        remaining -= len(part)
        if remaining <= 0:
            break
    return "\n\n".join(rendered)


def normalize_markdown(text: str) -> str:
    return str(text or "").strip() + "\n"


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


def parse_json_object(raw: str) -> dict:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def chapter_number_from_text(text: str) -> int | None:
    match = re.search(r"第\s*(\d+)\s*章", str(text or ""))
    return int(match.group(1)) if match else None
