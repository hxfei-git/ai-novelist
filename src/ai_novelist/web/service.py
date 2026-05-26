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
    parse_status_score,
    persist_outline_node,
    review_outline_node,
    revise_outline_node,
    run_outline_stage_node,
    stage_full_text,
)
from ai_novelist.graph_volume_write import build_volume_write_graph
from ai_novelist.outline.stage_contracts import OUTLINE_STAGES, STAGE_LABELS
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError, summarize_text

ProgressFunc = Callable[[str, str], None]


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


def outline_stage_list(store: LocalStore, project_id: str) -> list[dict[str, Any]]:
    state = store.load_state(project_id)
    return [outline_stage_payload(store, state, stage, include_content=False) for stage in OUTLINE_STAGES if stage != "review_lock"]


def outline_stage_payload(store: LocalStore, state: NovelState, stage: str, *, include_content: bool = True) -> dict[str, Any]:
    ensure_valid_stage(stage)
    artifact = state.outline_stage_artifacts.get(stage)
    artifact_dict = dict(artifact) if isinstance(artifact, dict) else {}
    content = ""
    if include_content:
        content = load_stage_markdown(store, state, stage, artifact_dict)
    status = str(artifact_dict.get("status") or ("collecting" if stage == state.outline_stage else "not_generated"))
    issues = artifact_dict.get("review_lock_issues") if isinstance(artifact_dict.get("review_lock_issues"), dict) else {}
    return {
        "stage": stage,
        "label": STAGE_LABELS.get(stage, stage),
        "status": status,
        "active": stage == state.outline_stage,
        "path": artifact_dict.get("path") or f"outline/{stage}.md",
        "summary": artifact_dict.get("summary") or state.outline_stage_summaries.get(stage, ""),
        "pending_questions": artifact_dict.get("pending_questions") or [],
        "review_lock_issues": {
            "blocking": list(issues.get("blocking", [])) if isinstance(issues, dict) else [],
            "detail": list(issues.get("detail", [])) if isinstance(issues, dict) else [],
            "revision_targets": list(issues.get("revision_targets", [])) if isinstance(issues, dict) else [],
        },
        "content": content,
    }


def load_outline_stage_payload(store: LocalStore, project_id: str, stage: str) -> dict[str, Any]:
    state = store.load_state(project_id)
    return outline_stage_payload(store, state, stage, include_content=True)


def save_outline_stage_content(store: LocalStore, project_id: str, stage: str, content: str) -> dict[str, Any]:
    ensure_valid_stage(stage)
    text = content.rstrip() + "\n" if content.strip() else ""
    if not text.strip():
        raise LocalStoreError("Outline stage content cannot be empty")
    state = store.load_state(project_id)
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



def outline_review_source_text(state: NovelState, store: LocalStore) -> str:
    if state.outline.strip():
        return state.outline.strip()
    has_stage_content = any(
        stage_full_text(state, store, stage).strip()
        for stage in OUTLINE_STAGES
        if stage != "review_lock"
    )
    if not has_stage_content:
        return ""
    return build_final_outline_text(state, store).strip()


def outline_review_report_paths(store: LocalStore, project_id: str, run_id: str) -> tuple[Path, Path]:
    return store.outline_review_report_path(project_id, run_id), store.outline_review_markdown_path(project_id, run_id)


def latest_outline_review_run(store: LocalStore, project_id: str) -> str:
    root = store.outline_review_dir(project_id)
    if not root.exists():
        return ""
    candidates = [path.name for path in root.iterdir() if path.is_dir()]
    return sorted(candidates)[-1] if candidates else ""


def load_outline_review_report(store: LocalStore, project_id: str, run_id: str) -> dict[str, Any]:
    if not run_id:
        run_id = latest_outline_review_run(store, project_id)
    if not run_id:
        raise LocalStoreError("No outline review report found")
    path = store.outline_review_report_path(project_id, run_id)
    if not path.exists():
        raise LocalStoreError(f"Outline review report does not exist: {run_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def latest_outline_review_report(store: LocalStore, project_id: str) -> dict[str, Any]:
    run_id = latest_outline_review_run(store, project_id)
    if not run_id:
        raise LocalStoreError("No outline review report found")
    return load_outline_review_report(store, project_id, run_id)


def render_outline_review_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 大纲总体审查报告",
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


def extract_markdown_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = re.sub(r"^[-*+\u2022]\s+", "", stripped)
        cleaned = re.sub(r"^\d+[.)、]\s*", "", cleaned)
        if cleaned != stripped or re.match(r"^\d+[.)、]", stripped):
            cleaned = cleaned.strip()
            if cleaned:
                bullets.append(cleaned)
    return bullets


def outline_suggestion_identifier(message: str, recommendation: str) -> str:
    text = f"outline_review|{message}|{recommendation}"
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def build_outline_repair_suggestions(notes: str, revision_instruction: str, summary: str) -> list[dict[str, Any]]:
    raw_items = [*extract_markdown_bullets(notes), *extract_markdown_bullets(revision_instruction)]
    if not raw_items:
        fallback = str(revision_instruction or summary or notes or "").strip()
        if fallback:
            raw_items = [fallback]
    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_items:
        text = summarize_text(item, max_chars=180).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        category = "revision" if re.search(r"建议|补|改|修|强化|调整|明确", text) else "issue"
        suggestion = {
            "id": outline_suggestion_identifier(text, text),
            "severity": "normal",
            "category": category,
            "message": text,
            "recommendation": text,
            "selected": True,
        }
        suggestions.append(suggestion)
    return suggestions


def selected_outline_revision_instruction(report: dict[str, Any], selected_issue_ids: list[str] | None) -> str:
    suggestions = [item for item in report.get("repair_suggestions", []) if isinstance(item, dict)]
    selected_ids = [str(item) for item in (selected_issue_ids or []) if str(item).strip()]
    if selected_issue_ids is not None and not selected_ids:
        raise LocalStoreError("请选择至少一条大纲审查建议")
    if selected_ids:
        suggestions = [item for item in suggestions if str(item.get("id") or "") in selected_ids]
        if not suggestions:
            raise LocalStoreError("未找到选中的大纲审查建议")
    if suggestions:
        lines = []
        for item in suggestions:
            message = str(item.get("message") or "").strip()
            recommendation = str(item.get("recommendation") or message).strip()
            if message and recommendation and message != recommendation:
                lines.append(f"- {message} -> {recommendation}")
            elif recommendation:
                lines.append(f"- {recommendation}")
        if lines:
            return "仅采纳以下选中的大纲审查建议：\n" + "\n".join(lines)
    return str(report.get("revision_instruction") or report.get("summary") or report.get("notes") or "").strip()


def write_outline_review_report(store: LocalStore, state: NovelState, report: dict[str, Any]) -> tuple[Path, Path]:
    run_id = str(report.get("run_id") or "").strip()
    if not run_id:
        raise LocalStoreError("Outline review run_id is required")
    report_path, markdown_path = outline_review_report_paths(store, state.project_id, run_id)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_outline_review_markdown(report), encoding="utf-8")
    register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="outline_review",
            path=report_path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="outline_editor",
            graph="outline",
            stage="outline_review",
            summary=str(report.get("summary") or "").strip(),
            metadata={
                "markdown_path": markdown_path.relative_to(store.project_dir(state.project_id)).as_posix(),
                "decision": str(report.get("decision") or ""),
            },
        ),
    )
    return report_path, markdown_path


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


def apply_outline_review(store: LocalStore, adapter: AgentAdapter, project_id: str, run_id: str, progress: ProgressFunc | None = None, selected_issue_ids: list[str] | None = None) -> dict[str, Any]:
    emit = progress or (lambda _stage, _message: None)
    report = load_outline_review_report(store, project_id, run_id)
    state = store.load_state(project_id)
    source_outline = str(report.get("source_outline") or "").strip() or outline_review_source_text(state, store)
    if not source_outline:
        raise LocalStoreError("当前没有可应用的大纲审查结果")
    decision = str(report.get("decision") or "").strip().lower()
    if decision == "stop":
        raise LocalStoreError("当前审查结果要求停止，不能直接应用")
    if decision == "pass":
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
    state.revision_instruction = selected_outline_revision_instruction(report, selected_issue_ids)
    state.editor_notes = state.revision_instruction if selected_issue_ids is not None else str(report.get("notes") or "")
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
    store.save_outline(compared)
    store.save_state(compared)
    emit("OutlineReview", "大纲审查建议已应用并保存。")
    return {
        "project_id": project_id,
        "run_id": run_id,
        "applied": True,
        "path": store.outline_path(project_id).relative_to(store.project_dir(project_id)).as_posix(),
        "version_count": len(compared.outline_versions),
    }



def generate_outline_stage(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    stage: str,
    instruction: str = "",
    progress: ProgressFunc | None = None,
) -> NovelState:
    ensure_valid_stage(stage)
    state = store.load_state(project_id)
    state.outline_stage = stage  # type: ignore[assignment]
    state.outline_stage_status = "collecting"
    state.current_stage = stage
    state.active_workflow = "outline"
    state.user_request = instruction.strip() or f"生成{STAGE_LABELS.get(stage, stage)}"
    state.revision_instruction = instruction.strip()
    state.director_action = "run_outline_stage"
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
    state = store.load_state(project_id)
    state.outline_stage = stage  # type: ignore[assignment]
    state.current_stage = stage
    state.active_workflow = "outline"
    state.user_request = instruction.strip() or f"锁定{STAGE_LABELS.get(stage, stage)}并进入下一阶段"
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
    chapters: str | Iterable[int] | None = None,
    max_workers: int = 3,
    progress: ProgressFunc | None = None,
) -> NovelState:
    import os

    if volume < 1:
        raise LocalStoreError("Volume must be greater than 0")
    os.environ["AI_NOVELIST_PARALLEL_AGENTS"] = "1"
    os.environ["AI_NOVELIST_MAX_PARALLEL_AGENTS"] = str(max(1, min(int(max_workers or 3), 8)))
    state = store.load_state(project_id)
    state.director_action = "write_volume"
    state.director_task_args = {"volume": volume}
    chapter_text = normalize_chapter_selector(chapters)
    if chapter_text:
        state.director_task_args["chapters"] = chapter_text
    state.user_request = f"批量生成第 {volume} 卷"
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    result = build_volume_write_graph(adapter, store, progress=progress).invoke(state.to_dict())
    return NovelState.from_dict(result)


def list_chapters(store: LocalStore, project_id: str) -> list[dict[str, Any]]:
    store.load_state(project_id)
    return [
        chapter_payload(store, project_id, chapter, path, content, include_content=False)
        for chapter, path, content in collect_latest_chapters(store, project_id)
    ]


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


def build_global_review_prompt(state: NovelState, store: LocalStore, chapters: list[tuple[int, Path, str]]) -> str:
    outline = store.load_outline_artifact(state.project_id, "chapter_outline").strip()
    parts = [
        "AGENT: global_consistency_reviewer",
        f"PROJECT_ID: {state.project_id}",
        f"TITLE: {state.title}",
        "",
        "请审查已生成章节之间的连续性、设定一致性、人物状态、时间线、重复/断裂问题。",
        "只输出 JSON，不要 Markdown，不要解释。",
        "schema: {status, summary, issues, repair_suggestions}",
        "status 只能是 reviewed 或 needs_repair。",
        "issues 每项 schema: {severity, chapter, category, message}。",
        "repair_suggestions 每项 schema: {id, chapter, severity, category, message, recommendation, selected}。",
        "severity 只能是 serious 或 normal；chapter 可为章节号或 null。",
        "serious 用于时间线硬冲突、同一事件重复/覆盖、人物状态矛盾、关键设定冲突、章节正文不完整。",
        "normal 用于轻微衔接、命名不统一、可读性提示。",
        "",
        "## Chapter Outline",
        outline[:12000] or "暂无",
    ]
    for chapter, path, content in chapters:
        relative = path.relative_to(store.project_dir(state.project_id)).as_posix()
        parts.extend(["", f"## Chapter {chapter} ({relative})", content[:18000]])
    return "\n".join(parts).rstrip() + "\n"


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


def ensure_valid_stage(stage: str) -> None:
    if stage not in OUTLINE_STAGES:
        raise LocalStoreError(f"Unknown outline stage: {stage}")


def load_stage_markdown(store: LocalStore, state: NovelState, stage: str, artifact: dict[str, Any]) -> str:
    artifact_text = store.load_outline_artifact(state.project_id, stage).strip()
    if artifact_text:
        return artifact_text
    stage_text = store.load_outline_stage(state.project_id, stage).strip()
    if stage_text:
        return stage_text
    return str(artifact.get("synthesis") or "").strip()


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

