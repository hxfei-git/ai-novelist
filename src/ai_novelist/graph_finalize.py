"""Chapter finalization graph and Novel Bible continuity update."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.artifacts import ArtifactRecord, get_latest_artifact, load_artifact_text, load_artifacts, register_artifact
from ai_novelist.bible import bible_to_dict, load_bible, merge_bible_updates, save_bible
from ai_novelist.context_builder import build_context
from ai_novelist.pacing import infer_hook_strength, infer_function, parse_pacing_target_from_card
from ai_novelist.progress import ProgressFunc, emit_progress, noop_progress, run_with_progress, with_agent_metadata
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


class FinalizeSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> None:
        self.adapter = adapter
        self.store = store
        self.progress = progress

    def invoke(self, state: dict) -> dict:
        emit_progress(self.progress, "Finalize 1/6", "正在读取最新章节草稿...")
        current = load_latest_draft_node(state, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "Finalize 2/6", "正在保存定稿章节...")
        current = save_final_chapter_node(current, self.store)
        emit_progress(self.progress, "Finalize 3/6", with_agent_metadata("正在生成章节摘要...", self.adapter, "chapter_summarizer"))
        current = summarize_chapter_node(current, self.adapter, self.store)
        emit_progress(self.progress, "Finalize 4/6", "正在保存章节摘要...")
        current = save_chapter_summary_node(current, self.store)
        emit_progress(self.progress, "Finalize 5/6", with_agent_metadata("正在抽取小说圣经更新...", self.adapter, "final_bible_update_extractor"))
        current = extract_bible_updates_from_final_node(current, self.adapter, self.store)
        emit_progress(self.progress, "Finalize 6/6", "正在写回小说圣经...")
        current = update_bible_from_final_node(current, self.store)
        return current


def build_finalize_graph(adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc | None = None) -> CompiledGraph:
    progress_func = progress or noop_progress
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return FinalizeSequentialGraph(adapter, store, progress_func)

    graph = StateGraph(dict)
    graph.add_node("load_latest_draft", lambda data: progress_node(progress_func, "Finalize 1/6", "正在读取最新章节草稿...", lambda: load_latest_draft_node(data, store)))
    graph.add_node("save_final_chapter", lambda data: progress_node(progress_func, "Finalize 2/6", "正在保存定稿章节...", lambda: save_final_chapter_node(data, store)))
    graph.add_node("summarize_chapter", lambda data: progress_node(progress_func, "Finalize 3/6", with_agent_metadata("正在生成章节摘要...", adapter, "chapter_summarizer"), lambda: summarize_chapter_node(data, adapter, store)))
    graph.add_node("save_chapter_summary", lambda data: progress_node(progress_func, "Finalize 4/6", "正在保存章节摘要...", lambda: save_chapter_summary_node(data, store)))
    graph.add_node("extract_bible_updates_from_final", lambda data: progress_node(progress_func, "Finalize 5/6", with_agent_metadata("正在抽取小说圣经更新...", adapter, "final_bible_update_extractor"), lambda: extract_bible_updates_from_final_node(data, adapter, store)))
    graph.add_node("update_bible", lambda data: progress_node(progress_func, "Finalize 6/6", "正在写回小说圣经...", lambda: update_bible_from_final_node(data, store)))
    graph.set_entry_point("load_latest_draft")
    graph.add_conditional_edges("load_latest_draft", route_after_load, {"continue": "save_final_chapter", "end": END})
    graph.add_edge("save_final_chapter", "summarize_chapter")
    graph.add_edge("summarize_chapter", "save_chapter_summary")
    graph.add_edge("save_chapter_summary", "extract_bible_updates_from_final")
    graph.add_edge("extract_bible_updates_from_final", "update_bible")
    graph.add_edge("update_bible", END)
    return graph.compile()


def progress_node(progress: ProgressFunc, stage: str, message: str, fn) -> dict:
    return run_with_progress(progress, stage, message, fn)


def route_after_load(data: dict) -> str:
    return "end" if data.get("review_status") == "error" else "continue"


def load_latest_draft_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    chapter = int(state.director_task_args.get("chapter") or state.current_chapter or state.active_chapter or 1)
    state.active_chapter = max(1, chapter)
    state.current_chapter = state.active_chapter
    state.active_graph = "finalize"
    state.active_stage = "load_latest_draft"
    state.active_artifact = "final_chapter"
    draft = load_latest_draft(state, store)
    if not draft.strip():
        state.review_status = "error"
        state.error = f"缺少第 {state.active_chapter} 章草稿，无法定稿。"
        state.director_message = state.error
        store.save_state(state)
        return state.to_dict()
    if state.editor_decision != "pass" and not explicit_finalize_requested(state):
        state.review_status = "error"
        state.error = f"第 {state.active_chapter} 章尚未通过审稿。请先审稿通过，或明确输入“定稿第 {state.active_chapter} 章”。"
        state.director_message = state.error
        store.save_state(state)
        return state.to_dict()
    state.current_final_chapter = draft.strip() + "\n"
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def save_final_chapter_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    path = store.save_final_chapter(state)
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="final_chapter",
            path=path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="finalize_graph",
            graph="finalize",
            stage="final",
            chapter=state.active_chapter,
            summary=summary_line(state.current_final_chapter),
        ),
    )
    state.active_stage = "save_final_chapter"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "finalize_graph", "final_saved", {"artifact_id": record.id, "path": record.path})
    store.save_state(state)
    return state.to_dict()


def summarize_chapter_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_finalize_prompt(state, "chapter_summarizer")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError:
        output = fallback_chapter_summary(state.current_final_chapter)
    summary = normalize_summary(output) or fallback_chapter_summary(state.current_final_chapter)
    state.chapter_summaries[str(state.active_chapter)] = summary
    state.active_stage = "summarize_chapter"
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "chapter_summarizer", "ok", {"chars": len(summary)})
    store.save_state(state)
    return state.to_dict()


def save_chapter_summary_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    path = store.save_chapter_summary(state)
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="chapter_summary",
            path=path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="chapter_summarizer",
            graph="finalize",
            stage="chapter_summary",
            chapter=state.active_chapter,
            summary=state.chapter_summaries.get(str(state.active_chapter), "")[:160],
        ),
    )
    state.active_stage = "save_chapter_summary"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "chapter_summarizer", "saved", {"artifact_id": record.id, "path": record.path})
    store.save_state(state)
    return state.to_dict()


def extract_bible_updates_from_final_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    context = build_context(state, store, "bible_update", chapter=state.active_chapter, max_chars=16000)
    prompt = build_finalize_prompt(state, "final_bible_update_extractor", context=context)
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
        updates = parse_json_object(output)
    except AgentAdapterError:
        updates = {}
    if not updates:
        updates = fallback_bible_updates(state)
    state.director_task_args["bible_updates"] = updates
    state.last_context_digest = context[:1200]
    state.active_stage = "extract_bible_updates_from_final"
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "final_bible_update_extractor", "ok", {"keys": sorted(updates.keys())})
    store.save_state(state)
    return state.to_dict()


def update_bible_from_final_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    project_dir = store.project_dir(state.project_id)
    bible = load_bible(project_dir)
    updates = state.director_task_args.get("bible_updates", {})
    if not isinstance(updates, dict):
        updates = fallback_bible_updates(state)
    merged = merge_bible_updates(bible, updates)
    save_bible(project_dir, merged)
    bible_record = register_artifact(
        project_dir,
        ArtifactRecord(
            id="",
            type="novel_bible",
            path="novel_bible.md",
            source_agent="final_bible_update_extractor",
            graph="finalize",
            stage="bible_update",
            chapter=state.active_chapter,
            summary=state.chapter_summaries.get(str(state.active_chapter), "")[:160],
            metadata={"bible_version": merged.version},
        ),
    )
    pacing_report = build_pacing_report(state)
    pacing_path = store.pacing_report_path(state.project_id, state.active_chapter)
    pacing_path.parent.mkdir(parents=True, exist_ok=True)
    pacing_path.write_text(json.dumps(pacing_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state.director_task_args["pacing_report"] = pacing_report

    state.bible_version = merged.version
    state.bible_updated_at = bible_record.updated_at or datetime.now(UTC).isoformat(timespec="seconds")
    state.review_status = "approved"
    state.next_action = "export_project"
    state.active_graph = "finalize"
    state.active_stage = "bible_update"
    state.active_artifact = "final_chapter"
    state.director_action = "finalize_chapter"
    final_path = store.final_chapter_path(state.project_id, state.active_chapter)
    summary_path = store.chapter_summary_path(state.project_id, state.active_chapter)
    state.director_message = (
        f"第 {state.active_chapter} 章已定稿：{final_path}\n"
        f"章节摘要已保存：{summary_path}\n"
        f"节奏报告已保存：{pacing_path}\n"
        f"小说圣经已更新到版本 {state.bible_version}。下一步可以说：导出小说。"
    )
    state.artifact_registry = [item.to_dict() for item in load_artifacts(project_dir)][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "finalize", "bible_updated", {"artifact_id": bible_record.id})
    store.save_state(state)
    return state.to_dict()


def build_finalize_prompt(state: NovelState, prompt_name: str, context: str = "") -> str:
    template = load_prompt(prompt_name)
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"CHAPTER: {state.active_chapter or state.current_chapter}\n\n"
        f"## Task Context\n{context or '暂无'}\n\n"
        f"## Final Chapter\n{state.current_final_chapter or '暂无'}\n\n"
        f"## Chapter Summary\n{state.chapter_summaries.get(str(state.active_chapter), '') or '暂无'}\n"
    )


def load_latest_draft(state: NovelState, store: LocalStore) -> str:
    final_path = store.final_chapter_path(state.project_id, state.active_chapter)
    if final_path.exists():
        return final_path.read_text(encoding="utf-8")
    for version in (2, 1):
        path = store.chapter_draft_path(state.project_id, state.active_chapter, version)
        if path.exists():
            return path.read_text(encoding="utf-8")
    record = get_latest_artifact(store.project_dir(state.project_id), "chapter_draft", chapter=state.active_chapter)
    if record:
        return load_artifact_text(store.project_dir(state.project_id), record)
    legacy = store.chapter_path(state.project_id, state.active_chapter)
    if legacy.exists():
        return legacy.read_text(encoding="utf-8")
    return state.chapter_draft if state.current_chapter == state.active_chapter else ""


def explicit_finalize_requested(state: NovelState) -> bool:
    if state.director_action == "finalize_chapter":
        return True
    if state.director_task_args.get("explicit_finalize") is True:
        return True
    return any(marker in state.user_request for marker in ("定稿", "最终稿", "finalize"))


def build_pacing_report(state: NovelState) -> dict[str, Any]:
    chapter = state.active_chapter or state.current_chapter
    card_target = parse_pacing_target_from_card(chapter, state.current_chapter_card or "")
    summary = state.chapter_summaries.get(str(chapter), "")
    actual_intensity = card_target.intensity
    if any(key in summary for key in ("爆", "决战", "大战", "崩溃", "死亡")):
        actual_intensity = min(5, actual_intensity + 1)
    if any(key in summary for key in ("余波", "回响", "收束", "静默")):
        actual_intensity = max(1, actual_intensity - 1)
    actual_hook_strength = infer_hook_strength(card_target.ending_mode, card_target.function, actual_intensity)
    reveals = []
    for marker in ("真相", "揭示", "身份", "秘密"):
        if marker in summary:
            reveals.append(marker)
    return {
        "chapter": chapter,
        "target": card_target.to_dict(),
        "actual_intensity": actual_intensity,
        "actual_hook_strength": actual_hook_strength,
        "actual_reveals": reveals,
        "deviation": {
            "intensity_delta": actual_intensity - card_target.intensity,
            "hook_changed": actual_hook_strength != card_target.hook_strength,
        },
    }


def parse_json_object(output: str) -> dict[str, Any]:
    text = output.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def fallback_bible_updates(state: NovelState) -> dict[str, Any]:
    chapter = state.active_chapter or state.current_chapter
    summary = state.chapter_summaries.get(str(chapter), "") or fallback_chapter_summary(state.current_final_chapter)
    return {
        "chapter_summaries": {str(chapter): summary},
        "timeline": [
            {
                "id": f"chapter-{chapter:03d}-final",
                "order": chapter,
                "chapter": chapter,
                "event": summary,
                "characters": extract_character_names(state.current_final_chapter),
                "location": extract_location(state.current_final_chapter),
                "source_hint": f"final_chapter: 第 {chapter} 章定稿",
            }
        ],
        "foreshadowing": [
            {
                "id": f"CH{chapter:03d}-HOOK",
                "setup_chapter": chapter,
                "setup_text": summary_line(state.current_final_chapter),
                "status": "setup",
                "source_hint": f"final_chapter: 第 {chapter} 章结尾钩子",
            }
        ],
        "open_questions": [f"第 {chapter} 章后续需要回收本章结尾钩子。"],
    }


def normalize_summary(output: str, max_chars: int = 180) -> str:
    text = output.strip()
    if text.startswith("{"):
        data = parse_json_object(text)
        text = str(data.get("summary", ""))
    lines = [re.sub(r"^[-*#\d.、\s]+", "", line).strip() for line in text.splitlines()]
    text = " ".join(line for line in lines if line)
    return text[:max_chars].rstrip()


def fallback_chapter_summary(text: str, max_chars: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:max_chars].rstrip() or "本章已定稿。"


def extract_character_names(text: str) -> list[str]:
    names = []
    for name in ("林澈", "许岚", "沈博士"):
        if name in text:
            names.append(name)
    return names


def extract_location(text: str) -> str:
    for location in ("银湾城", "第三维修站", "东七气闸", "月背冷库"):
        if location in text:
            return location
    return ""


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
