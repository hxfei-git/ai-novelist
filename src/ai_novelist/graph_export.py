"""Export graph for finalized manuscript files."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ai_novelist.artifacts import ArtifactRecord, load_artifacts, register_artifact
from ai_novelist.context_builder import build_context
from ai_novelist.progress import ProgressFunc, emit_progress, noop_progress
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


@dataclass(frozen=True)
class FinalChapter:
    chapter: int
    path: Path
    content: str


class ExportSequentialGraph:
    def __init__(self, store: LocalStore, progress: ProgressFunc = noop_progress) -> None:
        self.store = store
        self.progress = progress

    def invoke(self, state: dict) -> dict:
        emit_progress(self.progress, "Export 1/6", "正在收集已定稿章节...")
        current = collect_final_chapters_node(state, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "Export 2/6", "正在整理章节格式...")
        current = normalize_format_node(current, self.store)
        emit_progress(self.progress, "Export 3/6", "正在生成整本手稿...")
        current = build_manuscript_node(current, self.store)
        emit_progress(self.progress, "Export 4/6", "正在生成分卷稿...")
        current = build_volume_node(current, self.store)
        emit_progress(self.progress, "Export 5/6", "正在复制小说圣经导出副本...")
        current = copy_bible_export_node(current, self.store)
        emit_progress(self.progress, "Export 6/6", "正在保存导出文件...")
        current = save_export_node(current, self.store)
        return current


def build_export_graph(store: LocalStore, progress: ProgressFunc | None = None) -> CompiledGraph:
    progress_func = progress or noop_progress
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return ExportSequentialGraph(store, progress_func)

    graph = StateGraph(dict)
    graph.add_node("collect_final_chapters", lambda data: progress_node(progress_func, "Export 1/6", "正在收集已定稿章节...", lambda: collect_final_chapters_node(data, store)))
    graph.add_node("normalize_format", lambda data: progress_node(progress_func, "Export 2/6", "正在整理章节格式...", lambda: normalize_format_node(data, store)))
    graph.add_node("build_manuscript", lambda data: progress_node(progress_func, "Export 3/6", "正在生成整本手稿...", lambda: build_manuscript_node(data, store)))
    graph.add_node("build_volume", lambda data: progress_node(progress_func, "Export 4/6", "正在生成分卷稿...", lambda: build_volume_node(data, store)))
    graph.add_node("copy_bible_export", lambda data: progress_node(progress_func, "Export 5/6", "正在复制小说圣经导出副本...", lambda: copy_bible_export_node(data, store)))
    graph.add_node("save_export", lambda data: progress_node(progress_func, "Export 6/6", "正在保存导出文件...", lambda: save_export_node(data, store)))
    graph.set_entry_point("collect_final_chapters")
    graph.add_conditional_edges("collect_final_chapters", route_after_collect, {"continue": "normalize_format", "end": END})
    graph.add_edge("normalize_format", "build_manuscript")
    graph.add_edge("build_manuscript", "build_volume")
    graph.add_edge("build_volume", "copy_bible_export")
    graph.add_edge("copy_bible_export", "save_export")
    graph.add_edge("save_export", END)
    return graph.compile()


def progress_node(progress: ProgressFunc, stage: str, message: str, fn) -> dict:
    emit_progress(progress, stage, message)
    return fn()


def route_after_collect(data: dict) -> str:
    return "end" if data.get("review_status") == "error" else "continue"


def collect_final_chapters_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    state.active_graph = "export"
    state.active_stage = "collect_final_chapters"
    state.active_artifact = "export"
    chapters = collect_final_chapters(state, store)
    if not chapters:
        state.review_status = "error"
        state.error = "没有可导出的定稿章节。请先定稿至少一章。"
        state.director_message = state.error
        store.save_state(state)
        return state.to_dict()
    state.director_task_args["export_chapters"] = [
        {"chapter": item.chapter, "path": item.path.relative_to(store.project_dir(state.project_id)).as_posix(), "content": item.content}
        for item in chapters
    ]
    state.last_context_digest = build_context(state, store, "export", max_chars=1200)
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def normalize_format_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    chapters = []
    for item in state.director_task_args.get("export_chapters", []):
        if not isinstance(item, dict):
            continue
        content = normalize_chapter_markdown(str(item.get("content", "")), int(item.get("chapter", 0)))
        chapters.append({"chapter": int(item.get("chapter", 0)), "path": str(item.get("path", "")), "content": content})
    state.director_task_args["export_chapters"] = chapters
    state.active_stage = "normalize_format"
    store.save_state(state)
    return state.to_dict()


def build_manuscript_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    chapters = sorted(state.director_task_args.get("export_chapters", []), key=lambda item: int(item.get("chapter", 0)))
    content = render_export(state.title, chapters, "manuscript")
    state.director_task_args["manuscript_export"] = content
    state.active_stage = "build_manuscript"
    store.save_state(state)
    return state.to_dict()


def build_volume_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    chapters = sorted(state.director_task_args.get("export_chapters", []), key=lambda item: int(item.get("chapter", 0)))
    content = render_export(state.title, chapters, "volume_001")
    state.director_task_args["volume_export"] = content
    state.active_stage = "build_volume"
    store.save_state(state)
    return state.to_dict()


def copy_bible_export_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    source = store.novel_bible_markdown_path(state.project_id)
    target = store.bible_export_path(state.project_id)
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        state.director_task_args["bible_export_path"] = target.relative_to(store.project_dir(state.project_id)).as_posix()
    state.active_stage = "copy_bible_export"
    store.save_state(state)
    return state.to_dict()


def save_export_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    manuscript_path = store.manuscript_export_path(state.project_id)
    volume_path = store.volume_export_path(state.project_id)
    manuscript_path.parent.mkdir(parents=True, exist_ok=True)
    manuscript_path.write_text(str(state.director_task_args.get("manuscript_export", "")).rstrip() + "\n", encoding="utf-8")
    volume_path.write_text(str(state.director_task_args.get("volume_export", "")).rstrip() + "\n", encoding="utf-8")
    project_dir = store.project_dir(state.project_id)
    manuscript_record = register_artifact(
        project_dir,
        ArtifactRecord(
            id="",
            type="export",
            path=manuscript_path.relative_to(project_dir).as_posix(),
            source_agent="export_graph",
            graph="export",
            stage="manuscript",
            summary=f"导出 {len(state.director_task_args.get('export_chapters', []))} 章。",
        ),
    )
    volume_record = register_artifact(
        project_dir,
        ArtifactRecord(
            id="",
            type="export",
            path=volume_path.relative_to(project_dir).as_posix(),
            source_agent="export_graph",
            graph="export",
            stage="volume_001",
            summary=f"导出 {len(state.director_task_args.get('export_chapters', []))} 章。",
        ),
    )
    state.active_graph = "export"
    state.active_stage = "export"
    state.active_artifact = "export"
    state.director_action = "export_project"
    state.review_status = "approved"
    state.next_action = "stop"
    lines = [f"小说已导出：{manuscript_path}", f"分卷已导出：{volume_path}"]
    bible_export = store.bible_export_path(state.project_id)
    if bible_export.exists():
        lines.append(f"小说圣经已导出：{bible_export}")
    state.director_message = "\n".join(lines)
    state.artifact_registry = [item.to_dict() for item in load_artifacts(project_dir)][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "export_graph", "saved", {"manuscript_artifact_id": manuscript_record.id, "volume_artifact_id": volume_record.id})
    store.save_state(state)
    return state.to_dict()


def collect_final_chapters(state: NovelState, store: LocalStore) -> list[FinalChapter]:
    chapters: list[FinalChapter] = []
    root = store.chapters_dir(state.project_id)
    for path in sorted(root.glob("chapter_*/final.md")):
        match = re.search(r"chapter_(\d+)", path.as_posix())
        if not match:
            continue
        content = path.read_text(encoding="utf-8").strip()
        if content:
            chapters.append(FinalChapter(chapter=int(match.group(1)), path=path, content=content))
    return sorted(chapters, key=lambda item: item.chapter)


def normalize_chapter_markdown(content: str, chapter: int) -> str:
    text = content.strip()
    if not text.startswith("#"):
        text = f"# 第 {chapter} 章\n\n{text}"
    return text.rstrip() + "\n"


def render_export(title: str, chapters: list[dict], export_name: str) -> str:
    lines = [f"# {title or '未命名小说'}", "", f"<!-- export: {export_name} -->", ""]
    for item in chapters:
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(content)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def append_agent_report(reports: list[dict], agent: str, status: str, data: dict) -> list[dict]:
    updated = list(reports)
    updated.append({"agent": agent, "status": status, **data})
    return updated[-20:]
