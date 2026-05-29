"""Chapter-outline Web actions."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai_novelist.adapters.base import AgentAdapter
from ai_novelist.graph_outline import (
    advance_outline_stage_node,
    review_outline_node,
    run_outline_stage_node,
)
from ai_novelist.outline.chapter_outline_structure import (
    chapter_outline_metadata_from_artifact,
    current_volume_spec,
    extract_chapter_outline_volume,
)
from ai_novelist.outline.stage_contracts import STAGE_LABELS
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError, summarize_text
from ai_novelist.web.chapter_service import chapter_outline_review_source_text
from ai_novelist.web.outline_actions import strip_markdown_heading
from ai_novelist.web.outline_service import (
    action_state_for_status,
    build_outline_repair_suggestions,
    collect_stage_pending_questions,
    load_stage_markdown,
    selected_outline_revision_instruction,
)

ProgressFunc = Callable[[str, str], None]


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

def mark_chapter_outline_review_applied(store: LocalStore, project_id: str, report: dict[str, Any], path: Path) -> dict[str, Any]:
    updated = dict(report)
    updated["status"] = "applied"
    updated["applied"] = True
    updated["applied_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    updated["applied_path"] = path.relative_to(store.project_dir(project_id)).as_posix()
    report_path, markdown_path = chapter_outline_review_report_paths(store, project_id, str(updated.get("run_id") or ""))
    report_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_chapter_outline_review_markdown(updated), encoding="utf-8")
    return updated

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
    artifact_path = store.outline_artifact_path(project_id, 'chapter_outline')
    default_applied_path = artifact_path.relative_to(store.project_dir(project_id)).as_posix()
    if report.get('applied') is True or str(report.get('status') or '').strip().lower() == 'applied':
        applied_path = str(report.get('applied_path') or default_applied_path)
        return {
            'project_id': project_id,
            'run_id': run_id,
            'status': str(report.get('status') or 'applied'),
            'applied': True,
            'already_applied': True,
            'applied_at': str(report.get('applied_at') or ''),
            'applied_path': applied_path,
            'path': applied_path,
            'report': report,
            'version_count': len(state.outline_versions),
        }
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
    baseline_content = source_outline.rstrip() + '\n'
    emit('ChapterOutlineReview', '正在应用章节大纲审查建议...')
    revised = NovelState.from_dict(run_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None)))
    revised_artifact = dict(revised.outline_stage_artifacts.get('chapter_outline') or {})
    synthesis = str(revised_artifact.get('synthesis') or '').strip()
    if synthesis:
        artifact_content = synthesis.rstrip() + '\n'
        store.save_outline_artifact(revised, 'chapter_outline', artifact_content)
        store.save_outline_stage(revised, 'chapter_outline', artifact_content)
    else:
        artifact_content = store.load_outline_artifact(project_id, 'chapter_outline') if artifact_path.exists() else ''
        if artifact_content and artifact_content != baseline_content:
            store.save_outline_stage(revised, 'chapter_outline', artifact_content)
    revised.outline_review_applied_run_id = run_id
    revised.outline_review_run_id = run_id
    revised.outline_review_status = 'applied'
    revised.outline_review_score = int(report.get('score') or 0)
    revised.outline_review_summary = str(report.get('summary') or '')
    revised.outline_review_report_path = chapter_outline_review_report_paths(store, project_id, run_id)[0].relative_to(store.project_dir(project_id)).as_posix()
    revised.review_status = 'approved'
    revised.director_message = f'已采纳章节大纲审查建议并保存：{artifact_path}'
    store.save_state(revised)
    applied_report = mark_chapter_outline_review_applied(store, project_id, report, artifact_path)
    emit('ChapterOutlineReview', '章节大纲审查建议已应用并保存。')
    return {
        'project_id': project_id,
        'run_id': run_id,
        'status': applied_report.get('status'),
        'applied': True,
        'applied_at': applied_report.get('applied_at'),
        'applied_path': applied_report.get('applied_path'),
        'path': default_applied_path,
        'report': applied_report,
        'version_count': len(revised.outline_versions),
    }
