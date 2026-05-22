"""Revision graph for targeted chapter rewrites."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.artifacts import ArtifactRecord, load_artifacts, register_artifact
from ai_novelist.context_builder import build_context
from ai_novelist.graph_review import normalize_review_report
from ai_novelist.graph_writer import parse_editor_review
from ai_novelist.progress import ProgressFunc, emit_progress, noop_progress, with_agent_metadata
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


class RevisionSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> None:
        self.adapter = adapter
        self.store = store
        self.progress = progress

    def invoke(self, state: dict) -> dict:
        emit_progress(self.progress, "Revision 1/7", "正在读取草稿和审稿任务...")
        current = load_revision_context_node(state, self.store)
        loaded = NovelState.from_dict(current)
        if loaded.review_status in {"error", "stopped"}:
            return current
        emit_progress(self.progress, "Revision 2/7", with_agent_metadata("正在生成修订计划...", self.adapter, "revision_planner"))
        current = build_revision_plan_node(current, self.adapter, self.store)
        emit_progress(self.progress, "Revision 3/7", with_agent_metadata("正在定向改写问题段落...", self.adapter, "targeted_reviser"))
        current = revise_targeted_sections_node(current, self.adapter, self.store)
        emit_progress(self.progress, "Revision 4/7", "正在合并修订稿...")
        current = merge_revision_node(current, self.store)
        emit_progress(self.progress, "Revision 5/7", with_agent_metadata("正在做修订自检...", self.adapter, "revision_self_check"))
        current = revision_self_check_node(current, self.adapter, self.store)
        emit_progress(self.progress, "Revision 6/7", "正在保存修订稿...")
        current = save_revised_draft_node(current, self.store)
        emit_progress(self.progress, "Revision 7/7", "正在更新下一步状态...")
        current = maybe_review_again_node(current, self.store)
        return current


def build_revision_graph(adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc | None = None) -> CompiledGraph:
    progress_func = progress or noop_progress
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return RevisionSequentialGraph(adapter, store, progress_func)

    graph = StateGraph(dict)
    graph.add_node("load_revision_context", lambda data: progress_node(progress_func, "Revision 1/7", "正在读取草稿和审稿任务...", lambda: load_revision_context_node(data, store)))
    graph.add_node("build_revision_plan", lambda data: progress_node(progress_func, "Revision 2/7", with_agent_metadata("正在生成修订计划...", adapter, "revision_planner"), lambda: build_revision_plan_node(data, adapter, store)))
    graph.add_node("revise_targeted_sections", lambda data: progress_node(progress_func, "Revision 3/7", with_agent_metadata("正在定向改写问题段落...", adapter, "targeted_reviser"), lambda: revise_targeted_sections_node(data, adapter, store)))
    graph.add_node("merge_revision", lambda data: progress_node(progress_func, "Revision 4/7", "正在合并修订稿...", lambda: merge_revision_node(data, store)))
    graph.add_node("revision_self_check", lambda data: progress_node(progress_func, "Revision 5/7", with_agent_metadata("正在做修订自检...", adapter, "revision_self_check"), lambda: revision_self_check_node(data, adapter, store)))
    graph.add_node("save_revised_draft", lambda data: progress_node(progress_func, "Revision 6/7", "正在保存修订稿...", lambda: save_revised_draft_node(data, store)))
    graph.add_node("maybe_review_again", lambda data: progress_node(progress_func, "Revision 7/7", "正在更新下一步状态...", lambda: maybe_review_again_node(data, store)))
    graph.set_entry_point("load_revision_context")
    graph.add_conditional_edges("load_revision_context", route_after_load, {"continue": "build_revision_plan", "end": END})
    graph.add_edge("build_revision_plan", "revise_targeted_sections")
    graph.add_edge("revise_targeted_sections", "merge_revision")
    graph.add_edge("merge_revision", "revision_self_check")
    graph.add_edge("revision_self_check", "save_revised_draft")
    graph.add_edge("save_revised_draft", "maybe_review_again")
    graph.add_edge("maybe_review_again", END)
    return graph.compile()


def progress_node(progress: ProgressFunc, stage: str, message: str, fn) -> dict:
    emit_progress(progress, stage, message)
    return fn()


def route_after_load(data: dict) -> str:
    return "end" if data.get("review_status") in {"error", "stopped"} else "continue"


def load_revision_context_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    chapter = int(state.director_task_args.get("chapter") or state.current_chapter or state.active_chapter or 1)
    state.active_chapter = max(1, chapter)
    state.current_chapter = state.active_chapter
    state.active_graph = "revision"
    state.active_stage = "load_revision_context"
    state.active_artifact = "chapter_draft"
    if state.revision_count >= state.max_revisions:
        state.review_status = "stopped"
        state.next_action = "stop"
        state.director_message = f"第 {state.active_chapter} 章已达到最大修订次数 {state.max_revisions}，本轮不再自动修订。"
        store.save_state(state)
        return state.to_dict()
    draft = load_latest_draft(state, store)
    if not draft.strip():
        state.review_status = "error"
        state.error = f"缺少第 {state.active_chapter} 章草稿，无法修订。"
        state.director_message = state.error
        store.save_state(state)
        return state.to_dict()
    review = load_latest_review_json(state, store)
    state.chapter_draft = draft
    state.director_task_args["revision_review_json"] = review
    state.current_review_report = state.current_review_report or review_to_markdown(review)
    context = build_context(state, store, "revision", chapter=state.active_chapter, max_chars=18000)
    state.director_task_args["revision_context"] = context
    state.last_context_digest = context[:1200]
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def build_revision_plan_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_revision_prompt(state, "revision_planner")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.current_revision_plan = output.strip()
    state.active_stage = "build_revision_plan"
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "revision_planner", "ok", {"chars": len(output)})
    store.save_state(state)
    return state.to_dict()


def revise_targeted_sections_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_revision_prompt(state, "targeted_reviser")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.chapter_draft = output.strip()
    state.active_stage = "revise_targeted_sections"
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "targeted_reviser", "ok", {"chars": len(output)})
    store.save_state(state)
    return state.to_dict()


def merge_revision_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    state.chapter_draft = state.chapter_draft.strip() + "\n"
    state.active_stage = "merge_revision"
    store.save_state(state)
    return state.to_dict()


def revision_self_check_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_revision_prompt(state, "revision_self_check")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.director_task_args["revision_self_check"] = output.strip()
    state.active_stage = "revision_self_check"
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "revision_self_check", "ok", {"chars": len(output)})
    store.save_state(state)
    return state.to_dict()


def save_revised_draft_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    plan_path = store.save_revision_plan(state, version=1)
    draft_path = store.save_chapter_draft(state, version=2)
    legacy = store.save_chapter(state)
    state.revision_count += 1
    project_dir = store.project_dir(state.project_id)
    plan_record = register_artifact(
        project_dir,
        ArtifactRecord(
            id="",
            type="revision_plan",
            path=plan_path.relative_to(project_dir).as_posix(),
            source_agent="revision_planner",
            graph="revision",
            stage="revision_plan",
            chapter=state.active_chapter,
            summary=summary_line(state.current_revision_plan),
        ),
    )
    draft_record = register_artifact(
        project_dir,
        ArtifactRecord(
            id="",
            type="chapter_draft",
            path=draft_path.relative_to(project_dir).as_posix(),
            source_agent="targeted_reviser",
            graph="revision",
            stage="draft",
            chapter=state.active_chapter,
            summary=summary_line(state.chapter_draft),
            metadata={"legacy_path": legacy.relative_to(project_dir).as_posix(), "draft_version": 2},
        ),
    )
    state.active_graph = "revision"
    state.active_stage = "draft"
    state.active_artifact = "chapter_draft"
    state.director_action = state.director_action or "revise_chapter"
    state.director_message = f"第 {state.active_chapter} 章已修订：{draft_path}"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(project_dir)][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "revision", "saved", {"plan_artifact_id": plan_record.id, "draft_artifact_id": draft_record.id})
    store.save_state(state)
    return state.to_dict()


def maybe_review_again_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    state.review_status = "draft"
    state.next_action = "review_chapter"
    state.active_stage = "maybe_review_again"
    store.save_state(state)
    return state.to_dict()


def build_revision_prompt(state: NovelState, prompt_name: str) -> str:
    template = load_prompt(prompt_name)
    review = json.dumps(state.director_task_args.get("revision_review_json", {}), ensure_ascii=False, indent=2)
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"CHAPTER: {state.active_chapter or state.current_chapter}\n"
        f"REVISION_COUNT: {state.revision_count}\n\n"
        f"## Revision Context\n{state.director_task_args.get('revision_context') or '暂无'}\n\n"
        f"## Review JSON\n{review}\n\n"
        f"## Revision Plan\n{state.current_revision_plan or '暂无'}\n\n"
        f"## Current Draft\n{state.chapter_draft or '暂无'}\n"
    )


def load_latest_draft(state: NovelState, store: LocalStore) -> str:
    for version in (2, 1):
        path = store.chapter_draft_path(state.project_id, state.active_chapter, version)
        if path.exists():
            return path.read_text(encoding="utf-8")
    legacy = store.chapter_path(state.project_id, state.active_chapter)
    if legacy.exists():
        return legacy.read_text(encoding="utf-8")
    return state.chapter_draft if state.current_chapter == state.active_chapter else ""


def load_latest_review_json(state: NovelState, store: LocalStore) -> dict[str, Any]:
    path = store.review_json_path(state.project_id, state.active_chapter, 1)
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return normalize_review_report(data, "")
    if state.current_review_report.strip():
        return normalize_review_report({}, state.current_review_report)
    decision, score = parse_editor_review(state.editor_notes)
    issues = extract_bullets(state.editor_notes)
    return normalize_review_report({"decision": decision, "score": score, "issues": issues, "rewrite_tasks": issues[:3]}, state.editor_notes)


def review_to_markdown(report: dict[str, Any]) -> str:
    return (
        "# 章节审稿报告\n\n"
        f"STATUS: {report.get('decision', 'revise')}\n"
        f"QUALITY_SCORE: {report.get('score', 0)}\n\n"
        "## 定向改写任务\n"
        + "\n".join(f"- {item}" for item in report.get("rewrite_tasks", []) or ["按审稿意见修订。"])
    )


def extract_bullets(text: str) -> list[str]:
    return [re.sub(r"^[-*+\d.、\s]+", "", line).strip() for line in text.splitlines() if line.strip().startswith(("-", "*"))]


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
