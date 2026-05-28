"""File-backed services used by the Web API."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.artifacts import ArtifactRecord, register_artifact
from ai_novelist.graph_outline import (
    advance_outline_stage_node,
    build_final_outline_text,
    compare_outline_versions_node,
    extract_outline_stage_memory_for_artifact,
    parse_status_score,
    persist_outline_node,
    review_outline_node,
    revise_outline_node,
    run_outline_stage_node,
    save_outline_stage_outputs,
    stage_full_text,
    summarize_outline_stage_for_artifact,
)
from ai_novelist.graph_volume_write import build_volume_write_graph, parse_chapter_override
from ai_novelist.outline.chapter_outline_structure import (
    chapter_outline_metadata_from_artifact,
    chinese_number_to_int,
    current_volume_spec,
    extract_chapter_outline_volume,
    volume_label,
)
from ai_novelist.outline.stage_contracts import OUTLINE_STAGES, STAGE_LABELS
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError, summarize_text
from ai_novelist.workflow_payloads import set_chapter_batch_payload
from ai_novelist.web.json_utils import parse_json_object
from ai_novelist.web.chapter_service import (
    build_global_review_prompt,
    chapter_outline_review_source_text,
)
from ai_novelist.web.outline_service import (
    action_state_for_status,
    build_outline_repair_suggestions,
    collect_stage_pending_questions,
    default_pending_options,
    ensure_ordinary_stage_mutation,
    ensure_outline_stage_mutable,
    ensure_valid_stage,
    extract_pending_questions_from_stage_markdown,
    has_outline_stage_content,
    latest_outline_review_report,
    latest_outline_review_run,
    load_outline_review_report,
    load_stage_markdown,
    outline_review_source_text,
    outline_stage_action_state,
    outline_stage_list,
    outline_stage_payload,
    pending_display_question,
    pending_item_id,
    selected_outline_revision_instruction,
    write_outline_review_baseline_sections,
    write_outline_review_report,
)

ProgressFunc = Callable[[str, str], None]
ProgressItem = str | dict[str, str]
MAX_WEB_PROGRESS_LOG_ITEMS = 10


@dataclass(frozen=True)
class WebProject:
    project_id: str
    title: str
    path: str


@dataclass(frozen=True)
class WebChapter:
    chapter: int
    title: str
    path: str
    source: str
    version: int | None
    updated_at: str
    summary: str


def list_projects(store: LocalStore) -> list[WebProject]:
    if not store.root.exists():
        return []
    projects: list[WebProject] = []
    for path in sorted(store.root.iterdir()):
        if not path.is_dir() or not (path / "state.json").exists():
            continue
        try:
            state = store.load_state(path.name)
        except LocalStoreError:
            continue
        projects.append(WebProject(project_id=state.project_id, title=state.title, path=str(path)))
    return projects


def create_project(store: LocalStore, title: str, project_id: str | None = None, idea: str = "") -> NovelState:
    state = store.create_project(title.strip() or project_id or "untitled", project_id)
    if idea.strip() and state.idea != idea.strip():
        state.idea = idea.strip()
        store.save_state(state)
    return state


def project_needs_onboarding(state: NovelState) -> bool:
    if state.idea.strip():
        return False
    if state.outline.strip() or state.worldbuilding.strip() or state.chapter_plan.strip():
        return False
    if any(str(summary or "").strip() for summary in state.outline_stage_summaries.values()):
        return False
    for raw_artifact in state.outline_stage_artifacts.values():
        if not isinstance(raw_artifact, dict):
            continue
        status = str(raw_artifact.get("status") or "")
        if status in {"options_ready", "locked", "revision_requested", "done"}:
            return False
        for key in ("summary", "synthesis", "stage_memory", "path"):
            value = raw_artifact.get(key)
            if isinstance(value, list) and any(str(item).strip() for item in value):
                return False
            if isinstance(value, str) and value.strip():
                return False
    return True


def save_project_idea(store: LocalStore, project_id: str, idea: str) -> NovelState:
    text = idea.strip()
    if not text:
        raise LocalStoreError("Novel idea cannot be empty")
    state = store.load_state(project_id)
    state.idea = text
    state.user_request = text
    state.revision_instruction = text
    store.save_state(state)
    return state


def project_progress_log_path(store: LocalStore, project_id: str) -> Path:
    return store.project_dir(project_id) / "web_progress_log.json"


def normalize_progress_log_items(items: Iterable[Any]) -> list[ProgressItem]:
    normalized: list[ProgressItem] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                normalized.append(text)
        elif isinstance(item, dict):
            event = {
                key: str(item.get(key) or "").strip()
                for key in ("label", "elapsed", "tokens", "context", "status")
            }
            key = str(item.get("key") or "").strip()
            if key:
                event["key"] = key
            if event["label"]:
                normalized.append(event)
        if len(normalized) >= MAX_WEB_PROGRESS_LOG_ITEMS:
            break
    return normalized


def build_progress_event(stage: str, message: str) -> dict[str, str]:
    body = str(message or "").strip()
    label = body.split("（", 1)[0].strip() or str(stage or "").strip() or "Progress"
    label = re.sub(r"^(已完成[:：]?)", "", label).strip()
    label = re.sub(r"^(执行失败[:：]?)", "", label).strip()
    elapsed = re.search(r"(?:^|[/（])(\d+(?:\.\d+)?s)(?:[/）]|$)", body)
    tokens = re.search(r"(tok≈[^/）\s]+)", body)
    context = re.search(r"(ctx=[^/）\s]+(?:/[^/）\s]+)?)", body)
    status = "failed" if "失败" in body else "completed" if body.startswith("已完成") else "running"
    return {
        "key": str(stage or "").strip() or label,
        "label": label,
        "elapsed": elapsed.group(1) if elapsed else "",
        "tokens": tokens.group(1) if tokens else "",
        "context": context.group(1) if context else "",
        "status": status,
    }


def load_project_progress_log(store: LocalStore, project_id: str) -> list[ProgressItem]:
    store.load_state(project_id)
    path = project_progress_log_path(store, project_id)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = raw.get("items") if isinstance(raw, dict) else raw
    return normalize_progress_log_items(items if isinstance(items, list) else [])


def save_project_progress_log(store: LocalStore, project_id: str, items: Iterable[Any]) -> list[ProgressItem]:
    store.load_state(project_id)
    normalized = normalize_progress_log_items(items)
    path = project_progress_log_path(store, project_id)
    path.write_text(json.dumps({"items": normalized}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized
def load_outline_stage_payload(store: LocalStore, project_id: str, stage: str) -> dict[str, Any]:
    ensure_valid_stage(stage)
    ensure_ordinary_stage_mutation(stage)
    state = store.load_state(project_id)
    return outline_stage_payload(store, state, stage, include_content=True)
def save_outline_stage_content(store: LocalStore, project_id: str, stage: str, content: str) -> dict[str, Any]:
    ensure_valid_stage(stage)
    ensure_ordinary_stage_mutation(stage)
    state = store.load_state(project_id)
    ensure_outline_stage_mutable(state, stage)
    text = content.rstrip() + "\n" if content.strip() else ""
    if not text.strip():
        raise LocalStoreError("Outline stage content cannot be empty")
    artifact = dict(state.outline_stage_artifacts.get(stage) or {})
    artifact.update(
        {
            "stage": stage,
            "label": STAGE_LABELS.get(stage, stage),
            "status": artifact.get("status") or "options_ready",
            "path": f"outline/{stage}.md",
            "summary": summarize_text(strip_markdown_heading(text)),
            "stage_memory": [summarize_text(strip_markdown_heading(text), max_chars=500)],
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    state.outline_stage_artifacts[stage] = artifact
    state.outline_stage_summaries[stage] = artifact["summary"]
    if stage == state.outline_stage:
        state.outline_stage_status = artifact["status"]  # type: ignore[assignment]
    if stage == "worldbuilding":
        state.worldbuilding = text
        store.save_worldbuilding(state)
    store.save_outline_artifact(state, stage, text)
    store.save_outline_stage(state, stage, text)
    store.save_state(state)
    return outline_stage_payload(store, state, stage, include_content=True)
def chapter_outline_review_report_paths(store: LocalStore, project_id: str, run_id: str) -> tuple[Path, Path]:
    root = store.project_dir(project_id) / "outline" / "chapter_reviews" / run_id
    return root / "report.json", root / "report.md"


def latest_chapter_outline_review_run(store: LocalStore, project_id: str) -> str:
    root = store.project_dir(project_id) / "outline" / "chapter_reviews"
    if not root.exists():
        return ""
    candidates = [path.name for path in root.iterdir() if path.is_dir()]
    return sorted(candidates)[-1] if candidates else ""


def load_chapter_outline_review_report(store: LocalStore, project_id: str, run_id: str) -> dict[str, Any]:
    if not run_id:
        run_id = latest_chapter_outline_review_run(store, project_id)
    if not run_id:
        raise LocalStoreError("No chapter outline review report found")
    report_path, _markdown_path = chapter_outline_review_report_paths(store, project_id, run_id)
    if not report_path.exists():
        raise LocalStoreError(f"Chapter outline review report does not exist: {run_id}")
    return json.loads(report_path.read_text(encoding="utf-8"))


def latest_chapter_outline_review_report(store: LocalStore, project_id: str) -> dict[str, Any]:
    run_id = latest_chapter_outline_review_run(store, project_id)
    if not run_id:
        raise LocalStoreError("No chapter outline review report found")
    return load_chapter_outline_review_report(store, project_id, run_id)


def render_chapter_outline_review_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 章节大纲总体审查报告",
        "",
        f"- 项目：{report.get('project_id') or 'unknown'}",
        f"- run_id：{report.get('run_id') or 'unknown'}",
        f"- 状态：{report.get('status') or 'unknown'}",
        f"- 评分：{report.get('score') or 0}",
        "",
        "## 总体判断",
        str(report.get('summary') or '暂无').strip() or '暂无',
        "",
        "## 审查意见",
        str(report.get('notes') or '暂无').strip() or '暂无',
        "",
        "## 参考大纲",
        str(report.get('source_outline_summary') or '暂无').strip() or '暂无',
    ]
    return '\n'.join(lines).rstrip() + '\n'
def chapter_outline_workspace_payload(
    store: LocalStore,
    project_id: str,
    selected_volume_index: int | None = None,
) -> dict[str, Any]:
    state = store.load_state(project_id)
    artifact = state.outline_stage_artifacts.get("chapter_outline")
    artifact_dict = dict(artifact) if isinstance(artifact, dict) else {}
    volume_artifact = state.outline_stage_artifacts.get("volume_outline")
    volume_dict = dict(volume_artifact) if isinstance(volume_artifact, dict) else {}
    volume_outline = load_stage_markdown(store, state, "volume_outline", volume_dict)
    metadata = chapter_outline_metadata_from_artifact(artifact_dict, volume_outline)
    current_index = int(metadata["current_volume_index"])
    total_volumes = int(metadata["total_volumes"])
    selected_index = int(current_index if selected_volume_index is None else selected_volume_index)
    if selected_index < 1 or selected_index > total_volumes:
        raise LocalStoreError(f"Unknown chapter outline volume: {selected_index}")

    selected_metadata = dict(metadata)
    selected_metadata["current_volume_index"] = selected_index
    spec = current_volume_spec(selected_metadata)
    statuses = dict(metadata.get("volume_statuses") or {})
    completed = list(metadata.get("completed_volumes") or [])
    status = str(
        statuses.get(str(selected_index))
        or (artifact_dict.get("status") if selected_index == current_index else None)
        or ("locked" if selected_index in completed else "not_generated")
    )
    contents = metadata.get("volume_contents") if isinstance(metadata.get("volume_contents"), dict) else {}
    content = str(contents.get(str(selected_index)) or "").strip()
    if not content:
        combined_content = load_stage_markdown(store, state, "chapter_outline", artifact_dict)
        content = extract_chapter_outline_volume(combined_content, selected_index)
    questions = collect_stage_pending_questions(store, state, "chapter_outline") if selected_index == current_index else []
    action_state = action_state_for_status(status, questions, bool(content.strip()))
    if selected_index != current_index and status != "locked":
        action_state = {
            "can_generate": False,
            "can_revise": False,
            "can_lock": False,
            "lock_reason": "请先完成当前卷",
        }
    summary = str(artifact_dict.get("summary") or "") if selected_index == current_index else summarize_text(strip_markdown_heading(content))
    return {
        "volume_specs": list(metadata.get("volume_specs") or []),
        "current_volume_index": current_index,
        "completed_volumes": completed,
        "volume_statuses": statuses,
        "selected_volume": {
            "index": selected_index,
            "label": spec.label,
            "name": spec.name,
            "status": status,
            "summary": summary,
            "content": content,
            **action_state,
        },
    }


def outline_stage_pending_payload(store: LocalStore, project_id: str, stage: str) -> dict[str, Any]:
    ensure_valid_stage(stage)
    state = store.load_state(project_id)
    questions = collect_stage_pending_questions(store, state, stage)
    return {
        "project_id": project_id,
        "stage": stage,
        "items": [
            {
                "id": pending_item_id(stage, question),
                "question": pending_display_question(question, stage),
                "options": default_pending_options(question, stage),
            }
            for question in questions
        ],
    }
def review_outline(store: LocalStore, adapter: AgentAdapter, project_id: str, instruction: str = "", progress: ProgressFunc | None = None) -> dict[str, Any]:
    emit = progress or (lambda _stage, _message: None)
    state = store.load_state(project_id)
    source_outline = outline_review_source_text(state, store)
    if not source_outline:
        raise LocalStoreError("当前没有可审查的大纲")
    emit("OutlineReview", "正在读取当前大纲...")
    state.outline = source_outline
    state.user_request = instruction.strip() or "审查大纲"
    state.revision_instruction = instruction.strip()
    state.director_action = "review_outline"
    state.director_intent = "review"
    state.review_status = "draft"
    store.save_state(state)
    reviewed = NovelState.from_dict(review_outline_node(state.to_dict(), adapter, store))
    run_id = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    report = {
        "project_id": project_id,
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": reviewed.review_status,
        "decision": reviewed.editor_decision,
        "score": reviewed.quality_score,
        "summary": summarize_text(reviewed.editor_notes or reviewed.director_message or reviewed.revision_instruction or "审查完成", max_chars=240),
        "notes": reviewed.editor_notes,
        "revision_instruction": reviewed.revision_instruction,
        "source_outline": source_outline,
        "source_outline_summary": summarize_text(strip_markdown_heading(source_outline), max_chars=360),
    }
    report["repair_suggestions"] = build_outline_repair_suggestions(
        str(report.get("notes") or ""),
        str(report.get("revision_instruction") or ""),
        str(report.get("summary") or ""),
    )
    report_path, _markdown_path = write_outline_review_report(store, reviewed, report)
    reviewed.outline_review_run_id = run_id
    reviewed.outline_review_status = str(report["status"])
    reviewed.outline_review_score = int(report.get("score") or 0)
    reviewed.outline_review_summary = str(report["summary"])
    reviewed.outline_review_report_path = report_path.relative_to(store.project_dir(project_id)).as_posix()
    store.save_state(reviewed)
    emit("OutlineReview", "大纲总体审查报告已保存。")
    return report


def apply_outline_review(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    run_id: str,
    progress: ProgressFunc | None = None,
    selected_issue_ids: list[str] | None = None,
    decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    emit = progress or (lambda _stage, _message: None)
    report = load_outline_review_report(store, project_id, run_id)
    state = store.load_state(project_id)
    source_outline = str(report.get("source_outline") or "").strip() or outline_review_source_text(state, store)
    if not source_outline:
        raise LocalStoreError("当前没有可应用的大纲审查结果")
    decision = str(report.get("decision") or "").strip().lower()
    if decision == "stop":
        raise LocalStoreError("当前审查结果要求停止，不能直接应用")
    if decision == "pass" and selected_issue_ids is None and decisions is None:
        state.outline = source_outline
        state.review_status = "approved"
        state.editor_decision = "pass"
        state.outline_review_applied_run_id = run_id
        state.outline_review_run_id = run_id
        state.outline_review_status = str(report.get("status") or "reviewed")
        state.outline_review_score = int(report.get("score") or 0)
        state.outline_review_summary = str(report.get("summary") or "")
        state.outline_review_report_path = store.outline_review_report_path(project_id, run_id).relative_to(store.project_dir(project_id)).as_posix()
        store.save_outline(state)
        store.save_state(state)
        return {
            "project_id": project_id,
            "run_id": run_id,
            "applied": True,
            "path": store.outline_path(project_id).relative_to(store.project_dir(project_id)).as_posix(),
            "version_count": len(state.outline_versions),
        }
    emit("OutlineReview", "正在应用大纲审查建议...")
    state.outline = source_outline
    state.revision_instruction = selected_outline_revision_instruction(report, selected_issue_ids, decisions)
    state.editor_notes = state.revision_instruction if selected_issue_ids is not None or decisions is not None else str(report.get("notes") or "")
    state.review_status = "draft"
    store.save_state(state)
    revised = NovelState.from_dict(revise_outline_node(state.to_dict(), adapter, store))
    compared = NovelState.from_dict(compare_outline_versions_node(revised.to_dict(), adapter, store))
    compared.outline_review_applied_run_id = run_id
    compared.outline_review_run_id = run_id
    compared.outline_review_status = str(report.get("status") or "reviewed")
    compared.outline_review_score = int(report.get("score") or 0)
    compared.outline_review_summary = str(report.get("summary") or "")
    compared.outline_review_report_path = store.outline_review_report_path(project_id, run_id).relative_to(store.project_dir(project_id)).as_posix()
    compared.review_status = "approved"
    compared.editor_decision = "pass" if decision == "pass" else compared.editor_decision
    compared.director_message = f"已采纳大纲审查建议并保存：{store.outline_path(project_id)}"
    updated_stages, skipped_stages = write_outline_review_baseline_sections(store, compared, compared.outline)
    store.save_outline(compared)
    store.save_state(compared)
    emit("OutlineReview", "大纲审查建议已应用并保存。")
    return {
        "project_id": project_id,
        "run_id": run_id,
        "applied": True,
        "path": store.outline_path(project_id).relative_to(store.project_dir(project_id)).as_posix(),
        "version_count": len(compared.outline_versions),
        "updated_stages": updated_stages,
        "skipped_stages": skipped_stages,
    }
def review_chapter_outline(store: LocalStore, adapter: AgentAdapter, project_id: str, instruction: str = '', progress: ProgressFunc | None = None) -> dict[str, Any]:
    emit = progress or (lambda _stage, _message: None)
    state = store.load_state(project_id)
    source_outline = chapter_outline_review_source_text(state, store)
    if not source_outline:
        raise LocalStoreError('当前没有可审查的章节大纲')
    emit('ChapterOutlineReview', '正在读取当前章节大纲...')
    state.outline = source_outline
    state.user_request = instruction.strip() or '审查章节大纲'
    state.revision_instruction = instruction.strip()
    state.director_action = 'review_outline'
    state.director_intent = 'review'
    state.review_status = 'draft'
    store.save_state(state)
    reviewed = NovelState.from_dict(review_outline_node(state.to_dict(), adapter, store))
    run_id = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    report = {
        'project_id': project_id,
        'run_id': run_id,
        'created_at': datetime.now(UTC).isoformat(timespec='seconds'),
        'status': reviewed.review_status,
        'decision': reviewed.editor_decision,
        'score': reviewed.quality_score,
        'summary': summarize_text(reviewed.editor_notes or reviewed.director_message or reviewed.revision_instruction or '审查完成', max_chars=240),
        'notes': reviewed.editor_notes,
        'revision_instruction': reviewed.revision_instruction,
        'source_outline': source_outline,
        'source_outline_summary': summarize_text(strip_markdown_heading(source_outline), max_chars=360),
    }
    report['repair_suggestions'] = build_outline_repair_suggestions(
        str(report.get('notes') or ''),
        str(report.get('revision_instruction') or ''),
        str(report.get('summary') or ''),
    )
    report_path, markdown_path = chapter_outline_review_report_paths(store, project_id, run_id)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    markdown_path.write_text(render_chapter_outline_review_markdown(report), encoding='utf-8')
    reviewed.outline_review_run_id = run_id
    reviewed.outline_review_status = str(report['status'])
    reviewed.outline_review_score = int(report.get('score') or 0)
    reviewed.outline_review_summary = str(report['summary'])
    reviewed.outline_review_report_path = report_path.relative_to(store.project_dir(project_id)).as_posix()
    store.save_state(reviewed)
    emit('ChapterOutlineReview', '章节大纲总体审查报告已保存。')
    return report


def apply_chapter_outline_review(store: LocalStore, adapter: AgentAdapter, project_id: str, run_id: str, progress: ProgressFunc | None = None, selected_issue_ids: list[str] | None = None) -> dict[str, Any]:
    emit = progress or (lambda _stage, _message: None)
    report = load_chapter_outline_review_report(store, project_id, run_id)
    state = store.load_state(project_id)
    source_outline = str(report.get('source_outline') or '').strip() or chapter_outline_review_source_text(state, store)
    if not source_outline:
        raise LocalStoreError('当前没有可应用的章节大纲审查结果')
    decision = str(report.get('decision') or '').strip().lower()
    if decision == 'stop':
        raise LocalStoreError('当前审查结果要求停止，不能直接应用')
    state.outline = source_outline
    state.outline_stage = 'chapter_outline'  # type: ignore[assignment]
    state.current_stage = 'chapter_outline'
    state.active_workflow = 'outline'
    state.revision_instruction = selected_outline_revision_instruction(report, selected_issue_ids)
    state.user_request = state.revision_instruction
    state.editor_notes = state.revision_instruction if selected_issue_ids is not None else str(report.get('notes') or '')
    state.review_status = 'draft'
    artifact = dict(state.outline_stage_artifacts.get('chapter_outline') or {})
    artifact.update({
        'stage': 'chapter_outline',
        'label': STAGE_LABELS.get('chapter_outline', 'chapter_outline'),
        'status': artifact.get('status') or 'options_ready',
        'path': 'outline/chapter_outline.md',
        'summary': summarize_text(strip_markdown_heading(source_outline)),
        'stage_memory': [summarize_text(strip_markdown_heading(source_outline), max_chars=500)],
        'updated_at': datetime.now(UTC).isoformat(timespec='seconds'),
    })
    state.outline_stage_artifacts['chapter_outline'] = artifact
    state.outline_stage_summaries['chapter_outline'] = str(artifact.get('summary') or '')
    store.save_outline_artifact(state, 'chapter_outline', source_outline)
    store.save_outline_stage(state, 'chapter_outline', source_outline)
    store.save_state(state)
    emit('ChapterOutlineReview', '正在应用章节大纲审查建议...')
    revised = NovelState.from_dict(run_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None)))
    revised.outline_review_applied_run_id = run_id
    revised.outline_review_run_id = run_id
    revised.outline_review_status = str(report.get('status') or 'reviewed')
    revised.outline_review_score = int(report.get('score') or 0)
    revised.outline_review_summary = str(report.get('summary') or '')
    revised.outline_review_report_path = report_path = chapter_outline_review_report_paths(store, project_id, run_id)[0].relative_to(store.project_dir(project_id)).as_posix()
    revised.review_status = 'approved'
    revised.director_message = f'已采纳章节大纲审查建议并保存：{store.outline_artifact_path(project_id, "chapter_outline")}'
    store.save_state(revised)
    emit('ChapterOutlineReview', '章节大纲审查建议已应用并保存。')
    return {
        'project_id': project_id,
        'run_id': run_id,
        'applied': True,
        'path': store.outline_artifact_path(project_id, 'chapter_outline').relative_to(store.project_dir(project_id)).as_posix(),
        'version_count': len(revised.outline_versions),
    }


def normalize_pending_answers(answers: Any) -> list[dict[str, str]]:
    if not isinstance(answers, list) or not answers:
        raise LocalStoreError("请至少提交一条待确认项答案")
    normalized: list[dict[str, str]] = []
    for raw in answers:
        if not isinstance(raw, dict):
            raise LocalStoreError("待确认项答案格式无效")
        question = str(raw.get("question") or "").strip()
        answer = str(raw.get("answer") or raw.get("custom_answer") or "").strip()
        selected_option_id = str(raw.get("selected_option_id") or "").strip()
        if not question or not answer:
            raise LocalStoreError("每条待确认项都需要选择默认方案或填写自定义答案")
        normalized.append(
            {
                "question": question,
                "answer": answer,
                "selected_option_id": selected_option_id,
            }
        )
    return normalized


def build_pending_revision_instruction(answers: list[dict[str, str]]) -> str:
    lines = ["针对当前阶段待确认项，按以下答案修订："]
    for index, item in enumerate(answers, 1):
        lines.append(f"{index}. 问题：{item['question']}")
        lines.append(f"   答案：{item['answer']}")
    return "\n".join(lines)


def submit_stage_pending_answers(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    stage: str,
    answers: Any,
    progress: ProgressFunc | None = None,
) -> NovelState:
    ensure_valid_stage(stage)
    ensure_ordinary_stage_mutation(stage)
    state = store.load_state(project_id)
    ensure_outline_stage_mutable(state, stage)
    if not has_outline_stage_content(store, state, stage):
        raise LocalStoreError("没有可修订内容")
    normalized = normalize_pending_answers(answers)
    instruction = build_pending_revision_instruction(normalized)
    state.outline_stage = stage  # type: ignore[assignment]
    state.outline_stage_status = "collecting"
    state.current_stage = stage
    state.active_workflow = "outline"
    state.user_request = instruction
    state.revision_instruction = instruction
    state.director_action = "run_outline_stage"
    state.director_intent = "answer_pending_questions"
    store.save_state(state)
    result = run_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None))
    result_state = NovelState.from_dict(result)
    store.save_state(result_state)
    return store.load_state(project_id)



def generate_outline_stage(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    stage: str,
    instruction: str = "",
    progress: ProgressFunc | None = None,
) -> NovelState:
    ensure_valid_stage(stage)
    ensure_ordinary_stage_mutation(stage)
    state = store.load_state(project_id)
    ensure_outline_stage_mutable(state, stage)
    state.outline_stage = stage  # type: ignore[assignment]
    state.outline_stage_status = "collecting"
    state.current_stage = stage
    state.active_workflow = "outline"
    state.user_request = instruction.strip() or f"生成{STAGE_LABELS.get(stage, stage)}"
    state.revision_instruction = ""
    state.director_action = "run_outline_stage"
    state.director_intent = "create"
    store.save_state(state)
    result = run_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None))
    return NovelState.from_dict(result)


def revise_outline_stage(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    stage: str,
    instruction: str = "",
    progress: ProgressFunc | None = None,
) -> NovelState:
    ensure_valid_stage(stage)
    ensure_ordinary_stage_mutation(stage)
    state = store.load_state(project_id)
    ensure_outline_stage_mutable(state, stage)
    if not has_outline_stage_content(store, state, stage):
        raise LocalStoreError("没有可修订内容")
    revision_instruction = instruction.strip()
    if not revision_instruction:
        raise LocalStoreError("Revision instruction cannot be empty")
    state.outline_stage = stage  # type: ignore[assignment]
    state.outline_stage_status = "collecting"
    state.current_stage = stage
    state.active_workflow = "outline"
    state.user_request = revision_instruction
    state.revision_instruction = revision_instruction
    state.director_action = "run_outline_stage"
    state.director_intent = "revise"
    store.save_state(state)
    result = run_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None))
    return NovelState.from_dict(result)


def lock_outline_stage(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    stage: str,
    instruction: str = "",
    progress: ProgressFunc | None = None,
) -> NovelState:
    ensure_valid_stage(stage)
    ensure_ordinary_stage_mutation(stage)
    state = store.load_state(project_id)
    action_state = outline_stage_action_state(
        store,
        state,
        stage,
        str((state.outline_stage_artifacts.get(stage) or {}).get("status") or "not_generated"),
    )
    if not action_state["can_lock"]:
        raise LocalStoreError(str(action_state["lock_reason"]))
    state.outline_stage = stage  # type: ignore[assignment]
    state.current_stage = stage
    state.active_workflow = "outline"
    state.user_request = instruction.strip() or f"锁定{STAGE_LABELS.get(stage, stage)}并进入下一阶段"
    state.director_action = "advance_outline_stage"
    store.save_state(state)
    result = advance_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None))
    return NovelState.from_dict(result)


def prepare_chapter_outline_volume_action(
    store: LocalStore,
    project_id: str,
    volume_index: int,
    action: str,
) -> NovelState:
    payload = chapter_outline_workspace_payload(store, project_id, selected_volume_index=volume_index)
    state = store.load_state(project_id)
    artifact = dict(state.outline_stage_artifacts.get("chapter_outline") or {})
    metadata = dict(artifact.get("metadata") or {})
    current_index = int(metadata.get("current_volume_index") or payload["current_volume_index"] or 1)
    if volume_index != current_index:
        raise LocalStoreError("章节大纲只能操作当前卷，请先完成当前卷")

    selected = payload["selected_volume"]
    capability = f"can_{action}"
    if not bool(selected.get(capability)):
        if action == "revise" and str(selected.get("status") or "") != "locked" and not str(selected.get("content") or "").strip():
            raise LocalStoreError("没有可修订内容")
        raise LocalStoreError(str(selected.get("lock_reason") or "当前卷不可执行此操作"))

    metadata["current_volume_index"] = volume_index
    artifact["metadata"] = metadata
    artifact["status"] = str(selected["status"])
    state.outline_stage_artifacts["chapter_outline"] = artifact
    state.outline_stage = "chapter_outline"
    state.outline_stage_status = str(selected["status"])  # type: ignore[assignment]
    state.current_stage = "chapter_outline"
    state.active_workflow = "outline"
    return state


def generate_chapter_outline_volume(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    volume_index: int,
    instruction: str = "",
    progress: ProgressFunc | None = None,
) -> NovelState:
    state = prepare_chapter_outline_volume_action(store, project_id, volume_index, "generate")
    state.outline_stage_status = "collecting"
    state.user_request = instruction.strip() or "生成章节大纲当前卷"
    state.revision_instruction = ""
    state.director_action = "run_outline_stage"
    state.director_intent = "create"
    store.save_state(state)
    result = run_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None))
    return NovelState.from_dict(result)


def revise_chapter_outline_volume(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    volume_index: int,
    instruction: str = "",
    progress: ProgressFunc | None = None,
) -> NovelState:
    state = prepare_chapter_outline_volume_action(store, project_id, volume_index, "revise")
    revision_instruction = instruction.strip()
    if not revision_instruction:
        raise LocalStoreError("Revision instruction cannot be empty")
    state.outline_stage_status = "collecting"
    state.user_request = revision_instruction
    state.revision_instruction = revision_instruction
    state.director_action = "run_outline_stage"
    state.director_intent = "revise"
    store.save_state(state)
    result = run_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None))
    return NovelState.from_dict(result)


def lock_chapter_outline_volume(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    volume_index: int,
    instruction: str = "",
    progress: ProgressFunc | None = None,
) -> NovelState:
    state = prepare_chapter_outline_volume_action(store, project_id, volume_index, "lock")
    state.user_request = instruction.strip() or f"锁定章节大纲第 {volume_index} 卷"
    state.director_action = "advance_outline_stage"
    store.save_state(state)
    result = advance_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None))
    return NovelState.from_dict(result)


def generate_chapter_batch(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    *,
    volume: int = 1,
    requested_count: int | None = None,
    chapters: str | Iterable[int] | None = None,
    max_workers: int = 3,
    progress: ProgressFunc | None = None,
) -> NovelState:
    import os

    if volume < 1:
        raise LocalStoreError("Volume must be greater than 0")
    state = store.load_state(project_id)
    state.director_action = "write_volume"
    state.director_task_args = {}
    set_chapter_batch_payload(state, volume=volume)
    if requested_count is not None:
        workspace = chapter_batch_workspace_payload(store, project_id, volume)
        remaining_numbers = list(workspace.get("remaining_chapter_numbers") or [])
        requested_total = max(1, min(int(requested_count or 1), len(remaining_numbers)))
        selected_numbers = remaining_numbers[:requested_total]
        if not selected_numbers:
            raise LocalStoreError(f"第 {volume} 卷没有剩余章节可生成")
        os.environ["AI_NOVELIST_PARALLEL_AGENTS"] = "1"
        os.environ["AI_NOVELIST_MAX_PARALLEL_AGENTS"] = str(max(1, requested_total))
        set_chapter_batch_payload(state, volume=volume, requested_count=requested_total, chapters=selected_numbers)
        state.user_request = f"批量生成第 {volume} 卷 {requested_total} 章"
    else:
        os.environ["AI_NOVELIST_PARALLEL_AGENTS"] = "1"
        os.environ["AI_NOVELIST_MAX_PARALLEL_AGENTS"] = str(max(1, min(int(max_workers or 3), 8)))
        chapter_text = normalize_chapter_selector(chapters)
        if chapter_text:
            set_chapter_batch_payload(state, volume=volume, chapters=chapter_text)
        state.user_request = f"批量生成第 {volume} 卷"
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    result = build_volume_write_graph(adapter, store, progress=progress).invoke(state.to_dict())
    return NovelState.from_dict(result)


def latest_volume_batch_manifest(store: LocalStore, project_id: str, volume: int) -> dict[str, Any]:
    root = store.project_dir(project_id) / "chapters" / "batches" / f"volume_{volume:03d}"
    if not root.exists():
        return {}
    candidates = sorted((path for path in root.glob('*/manifest.json') if path.is_file()), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    return {}


def extract_volume_chapter_numbers(volume_outline: str, spec: Any | None = None) -> list[int]:
    content = str(volume_outline or "").strip()
    if not content:
        return []
    numbers: list[int] = []
    seen: set[int] = set()
    for match in re.finditer(r"第\s*([一二两三四五六七八九十\d]+)\s*章", content):
        number = chinese_number_to_int(match.group(1))
        if number and number not in seen:
            seen.add(number)
            numbers.append(number)
    if numbers:
        return numbers
    chapter_range = str(getattr(spec, "chapter_range", "") or "").strip()
    if chapter_range:
        return parse_chapter_override(chapter_range)
    return []


def chapter_batch_workspace_payload(store: LocalStore, project_id: str, volume: int) -> dict[str, Any]:
    workspace = chapter_outline_workspace_payload(store, project_id, selected_volume_index=volume)
    selected_volume = workspace["selected_volume"]
    selected_index = int(selected_volume.get("index") or volume)
    spec = current_volume_spec(
        {
            "current_volume_index": selected_index,
            "volume_specs": list(workspace.get("volume_specs") or []),
        }
    )
    volume_outline = str(selected_volume.get("content") or "")
    planned_chapter_numbers = extract_volume_chapter_numbers(volume_outline, spec)
    generated_items = list_chapters(store, project_id, volume=selected_index)
    if planned_chapter_numbers and not generated_items:
        planned_set = set(planned_chapter_numbers)
        generated_items = [item for item in list_chapters(store, project_id) if int(item.get("chapter") or 0) in planned_set]
    generated_set: set[int] = set()
    normalized_generated_items: list[dict[str, Any]] = []
    for item in generated_items:
        chapter = int(item.get("chapter") or 0)
        if chapter in generated_set:
            continue
        generated_set.add(chapter)
        normalized_generated_items.append(item)
    remaining_chapter_numbers = [chapter for chapter in planned_chapter_numbers if chapter not in generated_set]
    selected_name = str(selected_volume.get("name") or "").strip()
    return {
        "volume_index": selected_index,
        "volume_label": str(selected_volume.get("label") or spec.label or volume_label(selected_index)),
        "volume_name": selected_name,
        "total_chapters": len(planned_chapter_numbers),
        "generated_chapters": len(normalized_generated_items),
        "remaining_chapters": len(remaining_chapter_numbers),
        "next_chapter_number": remaining_chapter_numbers[0] if remaining_chapter_numbers else None,
        "planned_chapter_numbers": planned_chapter_numbers,
        "remaining_chapter_numbers": remaining_chapter_numbers,
        "chapters": normalized_generated_items,
    }


def list_chapters(store: LocalStore, project_id: str, volume: int | None = None) -> list[dict[str, Any]]:
    store.load_state(project_id)
    if volume is None:
        return [
            chapter_payload(store, project_id, chapter, path, content, include_content=False)
            for chapter, path, content in collect_latest_chapters(store, project_id)
        ]
    manifest = latest_volume_batch_manifest(store, project_id, volume)
    latest = manifest.get('chapters') if isinstance(manifest.get('chapters'), dict) else {}
    chapter_items: list[dict[str, Any]] = []
    for raw_chapter, raw_item in sorted(latest.items(), key=lambda item: int(item[0])):
        try:
            chapter = int(raw_chapter)
        except (TypeError, ValueError):
            continue
        path_value = str(raw_item.get('path') or '').strip() if isinstance(raw_item, dict) else ''
        path = store.project_dir(project_id) / path_value if path_value else latest_chapter_path(store, project_id, chapter)
        if not path or not path.exists():
            continue
        chapter_items.append(chapter_payload(store, project_id, chapter, path, path.read_text(encoding='utf-8'), include_content=False))
    return chapter_items


def load_chapter_payload(store: LocalStore, project_id: str, chapter: int) -> dict[str, Any]:
    if chapter < 1:
        raise LocalStoreError("Chapter must be greater than 0")
    store.load_state(project_id)
    path = latest_chapter_path(store, project_id, chapter)
    if not path:
        raise LocalStoreError(f"Chapter does not exist: {chapter}")
    return chapter_payload(store, project_id, chapter, path, path.read_text(encoding="utf-8"), include_content=True)


def review_all_chapters(store: LocalStore, adapter: AgentAdapter, project_id: str, progress: ProgressFunc | None = None) -> dict[str, Any]:
    emit = progress or (lambda _stage, _message: None)
    emit("GlobalReview", "正在扫描已生成章节...")
    state = store.load_state(project_id)
    chapters = collect_latest_chapters(store, project_id)
    base_issues = local_chapter_review_issues(chapters)
    model_report: dict[str, Any] | None = None
    if chapters:
        emit("GlobalReview", "正在调用模型审查章节连续性...")
        try:
            output = adapter.complete(build_global_review_prompt(state, store, chapters), store.project_dir(project_id)).strip()
            model_report = normalize_global_review_output(output)
        except AgentAdapterError as exc:
            base_issues.append({"severity": "normal", "chapter": None, "category": "model_review_error", "message": f"模型审查失败，已回退本地扫描：{exc}"})
    issues = merge_review_issues(base_issues, model_report.get("issues", []) if model_report else [])
    run_id = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    status = model_report.get("status") if model_report else ""
    if any(item["severity"] == "serious" for item in issues):
        status = "needs_repair"
    elif status not in {"reviewed", "needs_repair"}:
        status = "reviewed"
    summary = model_report.get("summary") if model_report else ""
    if not summary:
        source = "模型审查" if model_report else "本地扫描"
        summary = f"{source} {len(chapters)} 章，发现 {len(issues)} 个问题。"
    report = {
        "project_id": project_id,
        "run_id": run_id,
        "status": status,
        "review_source": "model" if model_report else "local",
        "chapters": [{"chapter": chapter, "path": path.relative_to(store.project_dir(project_id)).as_posix()} for chapter, path, _content in chapters],
        "issues": issues,
        "repair_suggestions": build_repair_suggestions(issues),
        "summary": summary,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    write_global_review_report(store, project_id, run_id, report)
    emit("GlobalReview", "全章节审查报告已保存。")
    return report


def local_chapter_review_issues(chapters: list[tuple[int, Path, str]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not chapters:
        issues.append({"severity": "serious", "chapter": None, "category": "coverage", "message": "未找到可审查的章节正文。"})
    for chapter, _path, content in chapters:
        if len(content.strip()) < 80:
            issues.append({"severity": "serious", "chapter": chapter, "category": "draft_length", "message": f"第 {chapter} 章正文过短，可能不是完整草稿。"})
        if re.search(r"(TODO|待补|占位|FIXME)", content, re.IGNORECASE):
            issues.append({"severity": "normal", "chapter": chapter, "category": "placeholder", "message": f"第 {chapter} 章包含待补或占位标记。"})
    for left, right in zip(chapters, chapters[1:]):
        if right[0] != left[0] + 1:
            issues.append({"severity": "normal", "chapter": right[0], "category": "chapter_gap", "message": f"第 {left[0]} 章后直接跳到第 {right[0]} 章。"})
    return issues
def normalize_global_review_output(output: str) -> dict[str, Any]:
    data = parse_json_object(output)
    issues = []
    for item in data.get("issues", []) if isinstance(data.get("issues"), list) else []:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "normal").strip().lower()
        if severity not in {"serious", "normal"}:
            severity = "normal"
        raw_chapter = item.get("chapter")
        chapter = normalize_issue_chapter(raw_chapter)
        message = str(item.get("message") or item.get("issue") or "").strip()
        if not message:
            continue
        issues.append(
            {
                "severity": severity,
                "chapter": chapter,
                "category": str(item.get("category") or "model_review").strip() or "model_review",
                "message": message,
            }
        )
    repair_suggestions = normalize_repair_suggestions(data.get("repair_suggestions") or data.get("repairs"), issues)
    status = str(data.get("status") or "").strip().lower()
    if status not in {"reviewed", "needs_repair"}:
        status = "needs_repair" if any(item["severity"] == "serious" for item in issues) else "reviewed"
    return {"status": status, "summary": str(data.get("summary") or "").strip(), "issues": issues, "repair_suggestions": repair_suggestions}


def merge_review_issues(local_issues: list[dict[str, Any]], model_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, str, str]] = set()
    for item in [*local_issues, *model_issues]:
        key = (item.get("chapter"), str(item.get("category") or ""), str(item.get("message") or ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def build_repair_suggestions(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for issue in issues:
        chapter = normalize_issue_chapter(issue.get("chapter"))
        recommendation = issue_recommendation(issue)
        if not recommendation:
            continue
        suggestions.append(
            {
                "id": issue_identifier(issue),
                "chapter": chapter,
                "severity": str(issue.get("severity") or "normal").strip().lower() or "normal",
                "category": str(issue.get("category") or "review").strip() or "review",
                "message": str(issue.get("message") or "").strip(),
                "recommendation": recommendation,
                "selected": True,
            }
        )
    return suggestions


def normalize_repair_suggestions(raw: Any, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            chapter = normalize_issue_chapter(item.get("chapter"))
            recommendation = str(item.get("recommendation") or item.get("summary") or "").strip()
            if not recommendation:
                continue
            suggestions.append(
                {
                    "id": issue_identifier(
                        {
                            "chapter": chapter,
                            "category": str(item.get("category") or "repair"),
                            "message": str(item.get("message") or recommendation),
                        }
                    ),
                    "chapter": chapter,
                    "severity": str(item.get("severity") or "normal").strip().lower() or "normal",
                    "category": str(item.get("category") or "repair").strip() or "repair",
                    "message": str(item.get("message") or recommendation).strip(),
                    "recommendation": recommendation,
                    "selected": bool(item.get("selected", True)),
                }
            )
    if suggestions:
        return suggestions
    return build_repair_suggestions(issues)


def issue_identifier(issue: dict[str, Any]) -> str:
    text = "|".join(
        [
            str(normalize_issue_chapter(issue.get("chapter"))),
            str(issue.get("category") or ""),
            str(issue.get("message") or ""),
        ]
    )
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def normalize_issue_chapter(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    return int(text) if text.isdigit() and int(text) > 0 else None


def issue_recommendation(issue: dict[str, Any]) -> str:
    category = str(issue.get("category") or "").strip().lower()
    message = str(issue.get("message") or "").strip()
    chapter = normalize_issue_chapter(issue.get("chapter"))
    chapter_label = f"第 {chapter} 章" if chapter else "全局"
    if category == "coverage":
        return "先补齐可审查章节，再重新执行全章节审查。"
    if category == "draft_length":
        return f"补充{chapter_label}正文长度，确保开头、冲突、转折和收束都完整。"
    if category == "placeholder":
        return f"删除{chapter_label}中的 TODO / 待补 / 占位标记，并补成可读正文。"
    if category == "chapter_gap":
        return f"补齐缺失章节或修正章节顺序，避免{chapter_label}与前后章节断档。"
    if category in {"timeline", "continuity", "state", "setting"}:
        return f"围绕{chapter_label}问题重排事件顺序并统一设定，确保与前后章节连续。"
    if message:
        return f"根据该问题修正{chapter_label}，并同步检查前后章节的承接关系。"
    return f"根据审查结果修正{chapter_label}，并保持与前后章节一致。"


def group_repair_suggestions_by_chapter(suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for item in suggestions:
        grouped[normalize_issue_chapter(item.get("chapter"))].append(item)
    ordered: list[dict[str, Any]] = []
    for chapter in sorted((item for item in grouped.keys() if item is not None)):
        ordered.append({"chapter": chapter, "items": grouped[chapter]})
    if grouped.get(None):
        ordered.append({"chapter": None, "items": grouped[None]})
    return ordered


def latest_global_review(store: LocalStore, project_id: str) -> dict[str, Any]:
    root = global_review_root(store, project_id)
    candidates = sorted(path for path in root.iterdir() if path.is_dir()) if root.exists() else []
    for path in reversed(candidates):
        report_path = path / "report.json"
        if report_path.exists():
            return json.loads(report_path.read_text(encoding="utf-8"))
    raise LocalStoreError("No global consistency review report found")


def generate_repair_proposals(store: LocalStore, adapter: AgentAdapter, project_id: str, run_id: str) -> dict[str, Any]:
    safe_id = safe_run_id(run_id)
    report = load_global_review(store, project_id, safe_id)
    suggestions = [item for item in report.get("repair_suggestions", []) if isinstance(item, dict)]
    chapter_paths: dict[int, str] = {}
    for group in group_repair_suggestions_by_chapter(suggestions):
        chapter = group["chapter"]
        if chapter is None:
            continue
        chapter = int(chapter)
        draft = load_latest_chapter_text(store, project_id, chapter)
        prompt = build_chapter_repair_prompt(store, project_id, chapter, draft, group["items"], report)
        try:
            content = adapter.complete(prompt, store.project_dir(project_id)).strip()
        except AgentAdapterError:
            content = ""
        if not content:
            content = fallback_repair_text(
                chapter,
                draft,
                "; ".join(
                    str(item.get("recommendation") or item.get("message") or "")
                    for item in group["items"]
                    if str(item.get("recommendation") or item.get("message") or "").strip()
                ),
            )
        path = proposed_repair_path(store, project_id, chapter, safe_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        chapter_paths[chapter] = path.relative_to(store.project_dir(project_id)).as_posix()
    proposals = []
    for item in suggestions:
        chapter = normalize_issue_chapter(item.get("chapter"))
        proposal = {
            "chapter": item.get("chapter"),
            "id": item.get("id"),
            "message": item.get("message", ""),
            "recommendation": item.get("recommendation", ""),
            "selected": bool(item.get("selected", True)),
        }
        if chapter is not None and chapter in chapter_paths:
            proposal["path"] = chapter_paths[chapter]
        proposals.append(proposal)
    return {"project_id": project_id, "run_id": safe_id, "proposals": proposals}


def apply_repair(
    store: LocalStore,
    adapter_or_project_id: AgentAdapter | str,
    project_id_or_chapter: str | int,
    chapter_or_run_id: int | str,
    run_id: str | None = None,
    selected_issue_ids: list[str] | None = None,
) -> dict[str, Any]:
    if isinstance(adapter_or_project_id, str):
        adapter: AgentAdapter | None = None
        project_id = adapter_or_project_id
        chapter = int(project_id_or_chapter)
        safe_id = safe_run_id(str(chapter_or_run_id))
    else:
        adapter = adapter_or_project_id
        project_id = str(project_id_or_chapter)
        chapter = int(chapter_or_run_id)
        safe_id = safe_run_id(str(run_id or ""))
    if chapter < 1:
        raise LocalStoreError("Chapter must be greater than 0")
    report = load_global_review(store, project_id, safe_id)
    suggestions = [
        item
        for item in report.get("repair_suggestions", [])
        if isinstance(item, dict) and normalize_issue_chapter(item.get("chapter")) == chapter
    ]
    if not suggestions:
        raise LocalStoreError(f"Repair proposal does not exist: chapter {chapter}, run {safe_id}")
    selected_ids = [str(item) for item in (selected_issue_ids or []) if str(item).strip()]
    if selected_issue_ids is not None and not selected_ids:
        raise LocalStoreError("请选择至少一条修改建议")
    if selected_ids:
        suggestions = [item for item in suggestions if str(item.get("id") or "") in selected_ids]
    if not suggestions:
        raise LocalStoreError("未找到选中的修改建议")
    draft = load_latest_chapter_text(store, project_id, chapter)
    proposed_path = proposed_repair_path(store, project_id, chapter, safe_id)
    content = ""
    if adapter is None and selected_issue_ids is None and proposed_path.exists():
        content = proposed_path.read_text(encoding="utf-8").strip()
    if not content and adapter is not None:
        prompt = build_chapter_repair_prompt(store, project_id, chapter, draft, suggestions, report)
        try:
            content = adapter.complete(prompt, store.project_dir(project_id)).strip()
        except AgentAdapterError:
            content = ""
    if not content and selected_issue_ids is None and proposed_path.exists():
        content = proposed_path.read_text(encoding="utf-8").strip()
    if not content:
        content = fallback_repair_text(
            chapter,
            draft,
            "; ".join(
                str(item.get("recommendation") or item.get("message") or "")
                for item in suggestions
                if str(item.get("recommendation") or item.get("message") or "").strip()
            ),
        )
    version = next_draft_version(store, project_id, chapter)
    state = store.load_state(project_id)
    state.active_chapter = chapter
    state.current_chapter = chapter
    state.chapter_draft = content
    draft_path = store.save_chapter_draft(state, version=version)
    store.save_chapter(state)
    store.save_state(state)
    return {
        "project_id": project_id,
        "chapter": chapter,
        "run_id": safe_id,
        "version": version,
        "path": draft_path.relative_to(store.project_dir(project_id)).as_posix(),
    }


def build_chapter_repair_prompt(
    store: LocalStore,
    project_id: str,
    chapter: int,
    draft: str,
    suggestions: list[dict[str, Any]],
    report: dict[str, Any],
) -> str:
    outline = store.load_outline_artifact(project_id, "chapter_outline").strip()
    suggestion_lines = []
    for item in suggestions:
        label = f"[{item.get('severity', 'normal')}] {item.get('category', '')}: {item.get('message', '')}"
        suggestion_lines.append(f"- {label} -> {item.get('recommendation', '')}")
    selected = "\n".join(suggestion_lines) if suggestion_lines else "暂无"
    return (
        "AGENT: global_consistency_repair\n"
        f"PROJECT_ID: {project_id}\n"
        f"CHAPTER: {chapter}\n"
        "请基于下列已勾选的修改建议，重写当前章节草稿。"
        "请保持章节标题、事件顺序和叙事风格一致，只输出修订后的 Markdown，不要解释。\n\n"
        f"## Review Summary\n{report.get('summary', '')}\n\n"
        f"## Selected Suggestions\n{selected}\n\n"
        f"## Chapter Outline\n{outline or '暂无'}\n\n"
        f"## Current Draft\n{draft or '暂无'}\n"
    )
def strip_markdown_heading(text: str) -> str:
    return re.sub(r"^\s*#+\s*", "", text.strip(), flags=re.MULTILINE)


def normalize_chapter_selector(chapters: str | Iterable[int] | None) -> str:
    if chapters is None:
        return ""
    if isinstance(chapters, str):
        return chapters.strip()
    values = sorted({int(item) for item in chapters if int(item) > 0})
    return ",".join(str(item) for item in values)


def collect_latest_chapters(store: LocalStore, project_id: str) -> list[tuple[int, Path, str]]:
    chapters: list[tuple[int, Path, str]] = []
    root = store.chapters_dir(project_id)
    if not root.exists():
        return chapters
    chapter_numbers = set()
    for path in root.glob("chapter_*.md"):
        match = re.fullmatch(r"chapter_(\d{3})\.md", path.name)
        if match:
            chapter_numbers.add(int(match.group(1)))
    for path in root.glob("chapter_*"):
        if path.is_dir():
            match = re.fullmatch(r"chapter_(\d{3})", path.name)
            if match:
                chapter_numbers.add(int(match.group(1)))
    for chapter in sorted(chapter_numbers):
        path = latest_chapter_path(store, project_id, chapter)
        if path and path.exists():
            chapters.append((chapter, path, path.read_text(encoding="utf-8")))
    return chapters


def chapter_payload(store: LocalStore, project_id: str, chapter: int, path: Path, content: str, *, include_content: bool) -> dict[str, Any]:
    source, version = chapter_source(store, project_id, chapter, path)
    relative = path.relative_to(store.project_dir(project_id)).as_posix()
    payload = WebChapter(
        chapter=chapter,
        title=chapter_title(chapter, content),
        path=relative,
        source=source,
        version=version,
        updated_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(timespec="seconds"),
        summary=summarize_text(strip_markdown_heading(content), max_chars=180),
    ).__dict__
    if include_content:
        payload["content"] = content
    return payload


def chapter_source(store: LocalStore, project_id: str, chapter: int, path: Path) -> tuple[str, int | None]:
    if path == store.final_chapter_path(project_id, chapter):
        return "final", None
    match = re.fullmatch(r"draft_v(\d+)\.md", path.name)
    if match:
        return "draft", int(match.group(1))
    return "legacy", None


def chapter_title(chapter: int, content: str) -> str:
    for line in content.splitlines():
        match = re.match(r"^\s*#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return f"第 {chapter} 章"


def latest_chapter_path(store: LocalStore, project_id: str, chapter: int) -> Path | None:
    final = store.final_chapter_path(project_id, chapter)
    if final.exists():
        return final
    drafts: list[tuple[int, Path]] = []
    chapter_dir = store.chapter_artifact_dir(project_id, chapter)
    if chapter_dir.exists():
        for path in chapter_dir.glob("draft_v*.md"):
            match = re.fullmatch(r"draft_v(\d+)\.md", path.name)
            if match:
                drafts.append((int(match.group(1)), path))
    if drafts:
        return max(drafts, key=lambda item: item[0])[1]
    legacy = store.chapter_path(project_id, chapter)
    return legacy if legacy.exists() else None


def load_latest_chapter_text(store: LocalStore, project_id: str, chapter: int) -> str:
    path = latest_chapter_path(store, project_id, chapter)
    return path.read_text(encoding="utf-8") if path else ""


def global_review_root(store: LocalStore, project_id: str) -> Path:
    return store.chapters_dir(project_id) / "global_consistency"


def write_global_review_report(store: LocalStore, project_id: str, run_id: str, report: dict[str, Any]) -> None:
    root = global_review_root(store, project_id) / run_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"# 全章节连贯性审查 {run_id}", "", report.get("summary", ""), ""]
    for issue in report.get("issues", []):
        if not isinstance(issue, dict):
            continue
        chapter = issue.get("chapter")
        label = f"第 {chapter} 章" if chapter else "全局"
        lines.append(f"- [{issue.get('severity', 'normal')}] {label} {issue.get('category', '')}: {issue.get('message', '')}")
    repair_suggestions = report.get("repair_suggestions", [])
    if isinstance(repair_suggestions, list) and repair_suggestions:
        lines.extend(["", "## 修改建议"])
        for group in group_repair_suggestions_by_chapter([item for item in repair_suggestions if isinstance(item, dict)]):
            label = f"第 {group['chapter']} 章" if group["chapter"] else "全局"
            lines.extend(["", f"### {label}"])
            for item in group["items"]:
                lines.append(f"- [x] {item.get('recommendation', '')}")
    (root / "report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_global_review(store: LocalStore, project_id: str, run_id: str) -> dict[str, Any]:
    path = global_review_root(store, project_id) / run_id / "report.json"
    if not path.exists():
        raise LocalStoreError(f"Global review report does not exist: {run_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def proposed_repair_path(store: LocalStore, project_id: str, chapter: int, run_id: str) -> Path:
    return store.chapter_artifact_dir(project_id, chapter) / f"proposed_repair_{safe_run_id(run_id)}.md"


def safe_run_id(run_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "", str(run_id))
    if not cleaned:
        raise LocalStoreError("Invalid run_id")
    return cleaned


def next_draft_version(store: LocalStore, project_id: str, chapter: int) -> int:
    for version in range(50, 0, -1):
        if store.chapter_draft_path(project_id, chapter, version).exists():
            return version + 1
    return 1


def fallback_repair_text(chapter: int, draft: str, issue: str) -> str:
    base = draft.strip() or f"# 第 {chapter} 章\n\n"
    return f"{base}\n\n<!-- global consistency repair: {issue} -->\n"
