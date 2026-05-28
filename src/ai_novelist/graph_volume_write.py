"""Volume batch writing graph."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.agent_parallel import AgentJob, run_agent_jobs
from ai_novelist.artifacts import ArtifactRecord, load_artifacts, register_artifact
from ai_novelist.corpus.craft_resolver import resolve_author_craft
from ai_novelist.context_builder import build_context_manifest
from ai_novelist.corpus.similarity_guard import save_similarity_report_for_state
from ai_novelist.graph_chapter_write import (
    append_agent_report,
    build_direct_chapter_context_bundle,
    collect_chapter_outline,
    normalize_markdown,
    summary_line,
)
from ai_novelist.outline.chapter_outline_structure import chinese_number_to_int, extract_chapter_outline_slice, volume_label
from ai_novelist.progress import ProgressFunc, emit_progress, noop_progress, run_with_progress, with_agent_metadata
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore
from ai_novelist.workflow_payloads import chapter_batch_payload, parse_chapter_selector


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


@dataclass(frozen=True)
class ChapterBatchItem:
    chapter: int
    outline: str
    context: str


class VolumeWriteSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> None:
        self.adapter = adapter
        self.store = store
        self.progress = progress

    def invoke(self, state: dict) -> dict:
        emit_progress(self.progress, "VolumeWrite 1/8", "正在解析目标卷和章节范围...")
        current = prepare_volume_batch_node(state, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "VolumeWrite 2/8", with_agent_metadata("正在并行生成章节初稿...", self.adapter, "direct_chapter_writer"))
        current = run_volume_drafts_node(current, self.adapter, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "VolumeWrite 3/8", with_agent_metadata("正在并行执行自动修订...", self.adapter, "chapter_auto_reviser"))
        current = run_volume_auto_revisions_node(current, self.adapter, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "VolumeWrite 4/8", "正在保存章节草稿...")
        current = save_volume_drafts_node(current, self.store)
        emit_progress(self.progress, "VolumeWrite 5/8", with_agent_metadata("正在执行卷级一致性总检...", self.adapter, "volume_consistency_checker"))
        current = run_volume_consistency_check_node(current, self.adapter, self.store, pass_index=1)
        emit_progress(self.progress, "VolumeWrite 6/8", with_agent_metadata("正在按总检问题自动修复...", self.adapter, "volume_blocker_reviser"))
        current = repair_volume_blockers_node(current, self.adapter, self.store)
        emit_progress(self.progress, "VolumeWrite 7/8", with_agent_metadata("正在复查卷级一致性...", self.adapter, "volume_consistency_checker"))
        current = rerun_consistency_if_needed_node(current, self.adapter, self.store)
        emit_progress(self.progress, "VolumeWrite 8/8", "正在保存批量生成清单...")
        return finalize_volume_batch_node(current, self.store)


def build_volume_write_graph(adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc | None = None) -> CompiledGraph:
    progress_func = progress or noop_progress
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return VolumeWriteSequentialGraph(adapter, store, progress_func)

    graph = StateGraph(dict)
    graph.add_node("prepare", lambda data: progress_node(progress_func, "VolumeWrite 1/8", "正在解析目标卷和章节范围...", lambda: prepare_volume_batch_node(data, store)))
    graph.add_node("drafts", lambda data: progress_node(progress_func, "VolumeWrite 2/8", with_agent_metadata("正在并行生成章节初稿...", adapter, "direct_chapter_writer"), lambda: run_volume_drafts_node(data, adapter, store)))
    graph.add_node("auto_revisions", lambda data: progress_node(progress_func, "VolumeWrite 3/8", with_agent_metadata("正在并行执行自动修订...", adapter, "chapter_auto_reviser"), lambda: run_volume_auto_revisions_node(data, adapter, store)))
    graph.add_node("save_drafts", lambda data: progress_node(progress_func, "VolumeWrite 4/8", "正在保存章节草稿...", lambda: save_volume_drafts_node(data, store)))
    graph.add_node("consistency", lambda data: progress_node(progress_func, "VolumeWrite 5/8", with_agent_metadata("正在执行卷级一致性总检...", adapter, "volume_consistency_checker"), lambda: run_volume_consistency_check_node(data, adapter, store, pass_index=1)))
    graph.add_node("repair", lambda data: progress_node(progress_func, "VolumeWrite 6/8", with_agent_metadata("正在按总检问题自动修复...", adapter, "volume_blocker_reviser"), lambda: repair_volume_blockers_node(data, adapter, store)))
    graph.add_node("recheck", lambda data: progress_node(progress_func, "VolumeWrite 7/8", with_agent_metadata("正在复查卷级一致性...", adapter, "volume_consistency_checker"), lambda: rerun_consistency_if_needed_node(data, adapter, store)))
    graph.add_node("finalize", lambda data: progress_node(progress_func, "VolumeWrite 8/8", "正在保存批量生成清单...", lambda: finalize_volume_batch_node(data, store)))
    graph.set_entry_point("prepare")
    graph.add_conditional_edges("prepare", route_after_step, {"continue": "drafts", "end": END})
    graph.add_conditional_edges("drafts", route_after_step, {"continue": "auto_revisions", "end": END})
    graph.add_conditional_edges("auto_revisions", route_after_step, {"continue": "save_drafts", "end": END})
    graph.add_edge("save_drafts", "consistency")
    graph.add_edge("consistency", "repair")
    graph.add_edge("repair", "recheck")
    graph.add_edge("recheck", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


class VolumeHumanRevisionSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> None:
        self.adapter = adapter
        self.store = store
        self.progress = progress

    def invoke(self, state: dict) -> dict:
        emit_progress(self.progress, "VolumeRevision 1/3", "正在读取人工审核意见和目标章节...")
        current = prepare_volume_batch_node(state, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "VolumeRevision 2/3", with_agent_metadata("正在并行按人工意见修订...", self.adapter, "human_feedback_reviser"))
        current = run_human_feedback_revisions_node(current, self.adapter, self.store)
        emit_progress(self.progress, "VolumeRevision 3/3", "正在保存人工修订清单...")
        return finalize_human_revision_batch_node(current, self.store)


def build_volume_revision_graph(adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc | None = None) -> CompiledGraph:
    progress_func = progress or noop_progress
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return VolumeHumanRevisionSequentialGraph(adapter, store, progress_func)

    graph = StateGraph(dict)
    graph.add_node("prepare", lambda data: progress_node(progress_func, "VolumeRevision 1/3", "正在读取人工审核意见和目标章节...", lambda: prepare_volume_batch_node(data, store)))
    graph.add_node("revise", lambda data: progress_node(progress_func, "VolumeRevision 2/3", with_agent_metadata("正在并行按人工意见修订...", adapter, "human_feedback_reviser"), lambda: run_human_feedback_revisions_node(data, adapter, store)))
    graph.add_node("finalize", lambda data: progress_node(progress_func, "VolumeRevision 3/3", "正在保存人工修订清单...", lambda: finalize_human_revision_batch_node(data, store)))
    graph.set_entry_point("prepare")
    graph.add_conditional_edges("prepare", route_after_step, {"continue": "revise", "end": END})
    graph.add_edge("revise", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def progress_node(progress: ProgressFunc, stage: str, message: str, fn) -> dict:
    return run_with_progress(progress, stage, message, fn)


def route_after_step(data: dict) -> str:
    return "end" if data.get("review_status") == "error" else "continue"


def prepare_volume_batch_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    payload = chapter_batch_payload(state)
    volume = payload.volume
    run_id = payload.run_id or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    full_outline = load_full_chapter_outline(state, store)
    chapters = payload.chapters
    if not chapters:
        chapters = chapters_for_volume(full_outline, volume)
    if not chapters:
        state.review_status = "error"
        state.error = f"无法从章节大纲中解析第 {volume} 卷章节范围。"
        state.director_message = state.error
        store.save_state(state)
        return state.to_dict()

    items: list[dict[str, Any]] = []
    context_manifests: dict[str, list[dict[str, object]]] = {}
    for chapter in chapters:
        chapter_state = NovelState.from_dict(state.to_dict())
        chapter_state.active_chapter = chapter
        chapter_state.current_chapter = chapter
        outline_slice = extract_chapter_outline_slice(full_outline, chapter)
        chapter_state.director_task_args["selected_chapter_outline"] = outline_slice
        chapter_state = resolve_author_craft(chapter_state, store, "drafting", chapter=chapter)
        bundle = build_direct_chapter_context_bundle(chapter_state, store)
        context = bundle.text
        context_manifest = build_context_manifest(bundle)
        context_manifests[str(chapter)] = context_manifest
        items.append({"chapter": chapter, "outline": outline_slice, "context": context, "context_manifest": context_manifest})

    state.director_task_args["volume"] = volume
    state.director_task_args["batch_run_id"] = str(run_id)
    state.director_task_args["batch_items"] = items
    ordered_context_manifests = ordered_chapter_context_manifests(context_manifests)
    state.director_task_args["batch_context_manifests"] = ordered_context_manifests
    if len(ordered_context_manifests) == 1:
        chapter, manifest = next(iter(ordered_context_manifests.items()))
        state.director_task_args["direct_chapter_context_manifest"] = manifest
        state.director_task_args["direct_chapter_context_manifest_chapter"] = int(chapter)
    else:
        state.director_task_args.pop("direct_chapter_context_manifest", None)
        state.director_task_args.pop("direct_chapter_context_manifest_chapter", None)
    state.active_graph = "volume_write"
    state.active_stage = "prepare"
    state.active_artifact = "volume_batch"
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def run_volume_drafts_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    jobs = []
    for item in batch_items(state):
        jobs.append(
            AgentJob(
                key=str(item.chapter),
                agent="direct_chapter_writer",
                prompt=build_batch_prompt(state, item, "direct_chapter_writer"),
                graph="volume_write",
                node="direct_chapter_writer",
                prompt_profile="direct_chapter_write",
            )
        )
    try:
        results = run_agent_jobs(adapter=adapter, project_dir=store.project_dir(state.project_id), project_id=state.project_id, jobs=jobs)
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.director_task_args["batch_drafts_v1"] = {result.key: normalize_markdown(result.output) for result in results}
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "direct_chapter_writer", "batch_ok", {"chapters": len(results)})
    state.active_stage = "drafts"
    store.save_state(state)
    return state.to_dict()


def run_volume_auto_revisions_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    drafts = state.director_task_args.get("batch_drafts_v1", {})
    jobs = []
    for item in batch_items(state):
        jobs.append(
            AgentJob(
                key=str(item.chapter),
                agent="chapter_auto_reviser",
                prompt=build_batch_prompt(state, item, "chapter_auto_reviser", current_draft=str(drafts.get(str(item.chapter), ""))),
                graph="volume_write",
                node="chapter_auto_reviser",
                prompt_profile="chapter_auto_revision",
            )
        )
    try:
        results = run_agent_jobs(adapter=adapter, project_dir=store.project_dir(state.project_id), project_id=state.project_id, jobs=jobs)
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.director_task_args["batch_drafts_v2"] = {result.key: normalize_markdown(result.output) for result in results}
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "chapter_auto_reviser", "batch_ok", {"chapters": len(results)})
    state.active_stage = "auto_revisions"
    store.save_state(state)
    return state.to_dict()


def save_volume_drafts_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    v1 = state.director_task_args.get("batch_drafts_v1", {})
    v2 = state.director_task_args.get("batch_drafts_v2", {})
    latest: dict[str, dict[str, Any]] = {}
    for item in batch_items(state):
        chapter = item.chapter
        draft1 = str(v1.get(str(chapter), "")).strip()
        draft2 = str(v2.get(str(chapter), "")).strip()
        version = next_chapter_draft_version(state, store, chapter, default=1)
        if draft1:
            path = write_chapter_version(state, store, chapter, draft1, version, "direct_chapter_writer", "draft")
            latest[str(chapter)] = {"version": version, "path": path}
            version += 1
        if draft2:
            path = write_chapter_version(state, store, chapter, draft2, version, "chapter_auto_reviser", "auto_revision")
            latest[str(chapter)] = {"version": version, "path": path}
    state.director_task_args["batch_latest_drafts"] = latest
    state.active_stage = "save_drafts"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    store.save_state(state)
    return state.to_dict()


def run_volume_consistency_check_node(data: dict, adapter: AgentAdapter, store: LocalStore, *, pass_index: int) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_volume_consistency_prompt(state, store)
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    report = normalize_consistency_report(output)
    key = f"volume_consistency_report_v{pass_index}"
    state.director_task_args[key] = report
    path = save_consistency_report(state, store, report, pass_index)
    state.director_task_args[f"{key}_path"] = path
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "volume_consistency_checker", "ok", {"pass": pass_index, "blockers": len(report["blocking_issues"])})
    state.active_stage = f"consistency_{pass_index}"
    store.save_state(state)
    return state.to_dict()


def repair_volume_blockers_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    report = state.director_task_args.get("volume_consistency_report_v1", {})
    issues = report.get("blocking_issues") if isinstance(report, dict) else []
    grouped = group_issues_by_chapter(issues)
    if not grouped:
        state.director_task_args["batch_repaired_chapters"] = []
        state.active_stage = "repair_skipped"
        store.save_state(state)
        return state.to_dict()
    jobs = []
    item_by_chapter = {item.chapter: item for item in batch_items(state)}
    for chapter, chapter_issues in grouped.items():
        item = item_by_chapter.get(chapter)
        if not item:
            continue
        draft = load_latest_chapter_draft(state, store, chapter)
        jobs.append(
            AgentJob(
                key=str(chapter),
                agent="volume_blocker_reviser",
                prompt=build_blocker_repair_prompt(state, item, draft, chapter_issues),
                graph="volume_write",
                node="volume_blocker_reviser",
                prompt_profile="volume_blocker_repair",
            )
        )
    try:
        results = run_agent_jobs(adapter=adapter, project_dir=store.project_dir(state.project_id), project_id=state.project_id, jobs=jobs)
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    repaired: list[int] = []
    for result in results:
        chapter = int(result.key)
        version = next_chapter_draft_version(state, store, chapter, default=1)
        path = write_chapter_version(state, store, chapter, normalize_markdown(result.output), version, "volume_blocker_reviser", "consistency_repair")
        state.director_task_args.setdefault("batch_latest_drafts", {})[str(chapter)] = {"version": version, "path": path}
        repaired.append(chapter)
    state.director_task_args["batch_repaired_chapters"] = repaired
    state.active_stage = "repair"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    store.save_state(state)
    return state.to_dict()


def rerun_consistency_if_needed_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if not state.director_task_args.get("batch_repaired_chapters"):
        return state.to_dict()
    return run_volume_consistency_check_node(state.to_dict(), adapter, store, pass_index=2)


def finalize_volume_batch_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    final_report = state.director_task_args.get("volume_consistency_report_v2") or state.director_task_args.get("volume_consistency_report_v1") or {}
    blockers = final_report.get("blocking_issues") if isinstance(final_report, dict) else []
    status = "needs_human_attention" if blockers else "ready_for_human_review"
    manifest = build_manifest(state, status)
    manifest_path = batch_dir(state, store) / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="volume_batch",
            path=manifest_path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="volume_write_graph",
            graph="volume_write",
            stage=status,
            summary=f"第 {state.director_task_args.get('volume', 1)} 卷批量生成 {len(batch_items(state))} 章。",
            metadata={"status": status, "volume": state.director_task_args.get("volume", 1)},
        ),
    )
    state.active_graph = "volume_write"
    state.active_stage = status
    state.active_artifact = "volume_batch"
    state.director_action = "write_volume"
    state.review_status = "draft"
    state.next_action = "human_review"
    state.director_message = f"第 {state.director_task_args.get('volume', 1)} 卷已批量生成，状态：{status}。批次清单：{manifest_path}"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "volume_write_graph", "saved", {"artifact_id": record.id, "status": status})
    store.save_state(state)
    return state.to_dict()


def run_human_feedback_revisions_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    notes = load_human_notes(state)
    if not notes.strip():
        state.review_status = "error"
        state.error = "缺少人工审核意见，无法执行整卷人工修订。"
        state.director_message = state.error
        store.save_state(state)
        return state.to_dict()
    jobs = []
    for item in batch_items(state):
        draft = load_latest_chapter_draft(state, store, item.chapter)
        jobs.append(
            AgentJob(
                key=str(item.chapter),
                agent="human_feedback_reviser",
                prompt=build_human_feedback_prompt(state, item, draft, notes),
                graph="volume_revision",
                node="human_feedback_reviser",
                prompt_profile="human_feedback_revision",
            )
        )
    try:
        results = run_agent_jobs(adapter=adapter, project_dir=store.project_dir(state.project_id), project_id=state.project_id, jobs=jobs)
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    latest: dict[str, dict[str, Any]] = {}
    for result in results:
        chapter = int(result.key)
        version = next_revision_version(state, store, chapter)
        path = write_chapter_version(state, store, chapter, normalize_markdown(result.output), version, "human_feedback_reviser", "human_feedback_revision")
        latest[str(chapter)] = {"version": version, "path": path}
    state.director_task_args["batch_latest_drafts"] = latest
    state.active_stage = "human_feedback_revision"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    store.save_state(state)
    return state.to_dict()


def finalize_human_revision_batch_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    manifest = build_manifest(state, "human_revision_done")
    manifest_path = batch_dir(state, store) / "human_revision_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="volume_batch",
            path=manifest_path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="volume_revision_graph",
            graph="volume_revision",
            stage="human_revision_done",
            summary=f"第 {state.director_task_args.get('volume', 1)} 卷已按人工意见修订。",
            metadata={"status": "human_revision_done", "volume": state.director_task_args.get("volume", 1)},
        ),
    )
    state.active_graph = "volume_revision"
    state.active_stage = "human_revision_done"
    state.active_artifact = "volume_batch"
    state.director_action = "revise_volume"
    state.review_status = "draft"
    state.next_action = "human_review"
    state.director_message = f"第 {state.director_task_args.get('volume', 1)} 卷已按人工审核意见修订：{manifest_path}"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "volume_revision_graph", "saved", {"artifact_id": record.id})
    store.save_state(state)
    return state.to_dict()


def build_batch_prompt(state: NovelState, item: ChapterBatchItem, prompt_name: str, current_draft: str = "") -> str:
    template = load_prompt(prompt_name)
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"VOLUME: {state.director_task_args.get('volume', 1)}\n"
        f"CHAPTER: {item.chapter}\n\n"
        f"## Direct Chapter Context\n{item.context or '暂无'}\n\n"
        f"## Current Draft\n{current_draft or '暂无'}\n"
    )


def build_volume_consistency_prompt(state: NovelState, store: LocalStore) -> str:
    template = load_prompt("volume_consistency_checker")
    chapters = []
    for item in batch_items(state):
        draft = load_latest_chapter_draft(state, store, item.chapter)
        chapters.append(f"## 第 {item.chapter} 章\n{draft[:5000].rstrip()}")
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"VOLUME: {state.director_task_args.get('volume', 1)}\n\n"
        f"## Chapter Drafts\n{chr(10).join(chapters)}\n"
    )


def build_blocker_repair_prompt(state: NovelState, item: ChapterBatchItem, draft: str, issues: list[dict[str, Any]]) -> str:
    template = load_prompt("volume_blocker_reviser")
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"VOLUME: {state.director_task_args.get('volume', 1)}\n"
        f"CHAPTER: {item.chapter}\n\n"
        f"## Direct Chapter Context\n{item.context or '暂无'}\n\n"
        f"## Blocking Issues\n{json.dumps(issues, ensure_ascii=False, indent=2)}\n\n"
        f"## Current Draft\n{draft or '暂无'}\n"
    )


def build_human_feedback_prompt(state: NovelState, item: ChapterBatchItem, draft: str, notes: str) -> str:
    template = load_prompt("human_feedback_reviser")
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"VOLUME: {state.director_task_args.get('volume', 1)}\n"
        f"CHAPTER: {item.chapter}\n\n"
        f"## Direct Chapter Context\n{item.context or '暂无'}\n\n"
        f"## Human Review Notes\n{notes}\n\n"
        f"## Current Draft\n{draft or '暂无'}\n"
    )


def write_chapter_version(state: NovelState, store: LocalStore, chapter: int, content: str, version: int, source_agent: str, stage: str) -> str:
    state.active_chapter = chapter
    state.current_chapter = chapter
    state.chapter_draft = normalize_markdown(content)
    path = store.save_chapter_draft(state, version=version)
    legacy = store.save_chapter(state)
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="chapter_draft",
            path=path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent=source_agent,
            graph="volume_write",
            stage=stage,
            chapter=chapter,
            summary=summary_line(state.chapter_draft),
            metadata={"legacy_path": legacy.relative_to(store.project_dir(state.project_id)).as_posix(), "draft_version": version},
        ),
    )
    save_similarity_report_for_state(state, store, f"draft_v{version}", state.chapter_draft)
    return record.path


def batch_items(state: NovelState) -> list[ChapterBatchItem]:
    items = []
    for raw in state.director_task_args.get("batch_items", []):
        if isinstance(raw, dict):
            items.append(ChapterBatchItem(chapter=int(raw.get("chapter") or 0), outline=str(raw.get("outline") or ""), context=str(raw.get("context") or "")))
    return [item for item in items if item.chapter > 0]


def load_full_chapter_outline(state: NovelState, store: LocalStore) -> str:
    saved = store.load_outline_artifact(state.project_id, "chapter_outline").strip()
    if saved:
        return saved
    artifact = state.outline_stage_artifacts.get("chapter_outline", {})
    if isinstance(artifact, dict):
        for key in ("synthesis", "summary"):
            value = str(artifact.get(key, "")).strip()
            if value:
                return value
    return state.chapter_plan or state.outline


def chapters_for_volume(outline: str, volume: int) -> list[int]:
    content = str(outline or "")
    if not content.strip():
        return []
    label = volume_label(volume)
    volume_heading = re.search(rf"^\s*#{{2,6}}\s*{re.escape(label)}[^\n]*$", content, re.MULTILINE)
    section = content
    if volume_heading:
        start = volume_heading.start()
        next_heading = re.search(r"^\s*#{2,6}\s*第[一二两三四五六七八九十\d]+卷[^\n]*$", content[volume_heading.end() :], re.MULTILINE)
        end = volume_heading.end() + next_heading.start() if next_heading else len(content)
        section = content[start:end]
    elif volume != 1:
        return []
    chapters = set()
    for match in re.finditer(r"第\s*([一二两三四五六七八九十\d]+)\s*章", section):
        value = chinese_number_to_int(match.group(1))
        if value:
            chapters.add(value)
    return sorted(chapters)


def parse_chapter_override(value: Any) -> list[int]:
    return parse_chapter_selector(value)


def normalize_consistency_report(output: str) -> dict[str, Any]:
    data = parse_json_object(output)
    status = str(data.get("status") or "pass").strip().lower()
    if status not in {"pass", "revise", "stop"}:
        status = "pass"
    return {
        "status": status,
        "blocking_issues": normalize_issue_list(data.get("blocking_issues")),
        "issues": normalize_str_list(data.get("issues")),
        "summary": str(data.get("summary") or "").strip(),
    }


def normalize_issue_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            chapters = item.get("chapters") if isinstance(item.get("chapters"), list) else [item.get("chapter")]
            normalized_chapters = [int(chapter) for chapter in chapters if str(chapter).isdigit()]
            result.append(
                {
                    "chapters": normalized_chapters,
                    "issue": str(item.get("issue") or item.get("problem") or "").strip(),
                    "fix": str(item.get("fix") or item.get("suggestion") or "").strip(),
                }
            )
        elif str(item).strip():
            result.append({"chapters": [], "issue": str(item).strip(), "fix": "按卷级总检意见修订。"})
    return [item for item in result if item["issue"]]


def normalize_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def parse_json_object(raw: str) -> dict[str, Any]:
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


def group_issues_by_chapter(issues: Any) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    if not isinstance(issues, list):
        return grouped
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        for chapter in issue.get("chapters", []):
            grouped.setdefault(int(chapter), []).append(issue)
    return grouped


def load_latest_chapter_draft(state: NovelState, store: LocalStore, chapter: int) -> str:
    latest = latest_chapter_draft_path(state, store, chapter)
    if latest:
        return latest.read_text(encoding="utf-8")
    legacy = store.chapter_path(state.project_id, chapter)
    if legacy.exists():
        return legacy.read_text(encoding="utf-8")
    return ""


def latest_chapter_draft_path(state: NovelState, store: LocalStore, chapter: int) -> Path | None:
    chapter_dir = store.chapter_artifact_dir(state.project_id, chapter)
    if not chapter_dir.exists():
        return None
    drafts: list[tuple[int, Path]] = []
    for path in chapter_dir.glob("draft_v*.md"):
        match = re.fullmatch(r"draft_v(\d+)\.md", path.name)
        if match:
            drafts.append((int(match.group(1)), path))
    return max(drafts, key=lambda item: item[0])[1] if drafts else None


def next_chapter_draft_version(state: NovelState, store: LocalStore, chapter: int, *, default: int) -> int:
    latest = latest_chapter_draft_path(state, store, chapter)
    if not latest:
        return default
    match = re.fullmatch(r"draft_v(\d+)\.md", latest.name)
    return int(match.group(1)) + 1 if match else default


def next_revision_version(state: NovelState, store: LocalStore, chapter: int) -> int:
    return next_chapter_draft_version(state, store, chapter, default=3)


def load_human_notes(state: NovelState) -> str:
    raw = str(state.director_task_args.get("human_notes") or "").strip()
    if raw:
        return raw
    path_value = str(state.director_task_args.get("notes_path") or "").strip()
    if not path_value:
        return ""
    path = Path(path_value)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def save_consistency_report(state: NovelState, store: LocalStore, report: dict[str, Any], pass_index: int) -> str:
    path = batch_dir(state, store) / f"consistency_report_v{pass_index}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="volume_consistency_report",
            path=path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="volume_consistency_checker",
            graph="volume_write",
            stage=f"consistency_v{pass_index}",
            summary=f"blockers={len(report.get('blocking_issues', []))}",
            metadata={"volume": state.director_task_args.get("volume", 1), "pass": pass_index},
        ),
    )
    return record.path


def batch_dir(state: NovelState, store: LocalStore) -> Path:
    volume = int(state.director_task_args.get("volume") or 1)
    run_id = str(state.director_task_args.get("batch_run_id") or "latest")
    return store.project_dir(state.project_id) / "chapters" / "batches" / f"volume_{volume:03d}" / run_id


def build_manifest(state: NovelState, status: str) -> dict[str, Any]:
    return {
        "project_id": state.project_id,
        "volume": state.director_task_args.get("volume", 1),
        "run_id": state.director_task_args.get("batch_run_id"),
        "status": status,
        "chapters": state.director_task_args.get("batch_latest_drafts", {}),
        "context_manifests": ordered_chapter_context_manifests(state.director_task_args.get("batch_context_manifests", {})),
        "repaired_chapters": state.director_task_args.get("batch_repaired_chapters", []),
        "consistency_report": state.director_task_args.get("volume_consistency_report_v2_path") or state.director_task_args.get("volume_consistency_report_v1_path"),
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def ordered_chapter_context_manifests(value: Any) -> dict[str, list[dict[str, object]]]:
    if not isinstance(value, dict):
        return {}
    ordered: dict[str, list[dict[str, object]]] = {}
    items = ((str(chapter), manifest) for chapter, manifest in value.items())
    for chapter, manifest in sorted(items, key=lambda item: (0, int(item[0])) if item[0].isdigit() else (1, item[0])):
        if isinstance(manifest, list):
            ordered[chapter] = manifest
    return ordered
