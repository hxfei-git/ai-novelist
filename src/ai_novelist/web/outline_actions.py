"""Outline-stage Web actions."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from ai_novelist.adapters.base import AgentAdapter
from ai_novelist.graph_outline import (
    advance_outline_stage_node,
    compare_outline_versions_node,
    review_outline_node,
    revise_outline_node,
    run_outline_stage_node,
)
from ai_novelist.outline.stage_contracts import STAGE_LABELS
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError, summarize_text
from ai_novelist.web.outline_service import (
    OUTLINE_REVIEW_PRIORITY_CAPS,
    build_outline_repair_suggestions,
    collect_stage_pending_questions,
    default_pending_options,
    ensure_ordinary_stage_mutation,
    ensure_outline_stage_mutable,
    ensure_valid_stage,
    has_outline_stage_content,
    load_outline_review_report,
    mark_outline_review_applied,
    outline_review_source_text,
    outline_stage_action_state,
    outline_stage_payload,
    pending_display_question,
    pending_item_id,
    selected_outline_revision_instruction,
    write_outline_review_baseline_sections,
    write_outline_review_report,
)

ProgressFunc = Callable[[str, str], None]

_OUTLINE_REVIEW_APPLY_LOCKS_LOCK = Lock()
_OUTLINE_REVIEW_APPLY_LOCKS: dict[tuple[str, str], Lock] = {}


def outline_review_apply_lock(project_id: str, run_id: str) -> Lock:
    key = (project_id, run_id)
    with _OUTLINE_REVIEW_APPLY_LOCKS_LOCK:
        lock = _OUTLINE_REVIEW_APPLY_LOCKS.get(key)
        if lock is None:
            lock = Lock()
            _OUTLINE_REVIEW_APPLY_LOCKS[key] = lock
        return lock


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


def outline_review_high_priority_count(suggestions: list[dict[str, Any]]) -> int:
    return sum(1 for item in suggestions if str(item.get("priority") or "low") == "high")


def outline_review_needs_high_priority_continuation(
    suggestions: list[dict[str, Any]],
    last_high_priority_batch_count: int,
) -> bool:
    del suggestions, last_high_priority_batch_count
    return False


def outline_review_high_priority_continuation_prompt(
    state: NovelState,
    report: dict[str, Any],
    suggestions: list[dict[str, Any]],
) -> str:
    existing = [
        str(item.get("message") or "").strip()
        for item in suggestions
        if str(item.get("priority") or "low") == "high" and str(item.get("message") or "").strip()
    ]
    existing_lines = "\n".join(f"{index}. {message}" for index, message in enumerate(existing, 1)) or "暂无"
    return (
        "AGENT: outline_editor\n\n"
        "任务：继续审查尚未列出的高优先级阻塞项。上一批高优先级问题正好停在 10 条，"
        "这通常表示输出被默认列表长度截断；请只补充未列出的高优先级阻塞项。\n\n"
        "要求：\n"
        "- 只寻找会阻塞章节细纲、违反 locked_constraints、造成硬冲突或必须先决策的结构缺口。\n"
        "- 不得重复已列问题；没有新增阻塞项则在 `## 高优先级问题` 下写“暂无”。\n"
        f"- 本轮最多补充 {OUTLINE_REVIEW_PRIORITY_CAPS['high'] - len(existing)} 条，总数达到工程安全上限即停止。\n"
        "- 每条必须使用编号列表，并包含“——推荐修改意见：”。\n"
        "- 不输出低优先级问题、建议问题或长篇分析。\n\n"
        "## 已列高优先级问题\n"
        f"{existing_lines}\n\n"
        "## 当前审查摘要\n"
        f"{str(report.get('summary') or '暂无')}\n\n"
        "## 当前大纲\n"
        f"{state.outline or report.get('source_outline') or '暂无'}\n\n"
        "## 锁定约束\n"
        f"{', '.join(state.locked_constraints) or '暂无'}\n\n"
        "输出格式：\n"
        "## 高优先级问题\n"
        "1. 问题描述。——推荐修改意见：具体修复建议。\n"
    )


def continue_outline_review_high_priority_items(
    store: LocalStore,
    adapter: AgentAdapter,
    state: NovelState,
    report: dict[str, Any],
) -> None:
    suggestions = [item for item in report.get("repair_suggestions", []) if isinstance(item, dict)]
    last_high_priority_batch_count = outline_review_high_priority_count(suggestions)
    continuation_rounds = 0
    while (
        outline_review_needs_high_priority_continuation(suggestions, last_high_priority_batch_count)
        and continuation_rounds < 4
    ):
        continuation_rounds += 1
        prompt = outline_review_high_priority_continuation_prompt(state, report, suggestions)
        try:
            continuation = adapter.complete(prompt, store.project_dir(state.project_id))
        except AgentAdapterError:
            break
        continuation_suggestions = build_outline_repair_suggestions(continuation, "", "")
        existing_ids = {str(item.get("id") or "") for item in suggestions}
        new_high_items = [
            item
            for item in continuation_suggestions
            if item.get("priority") == "high" and str(item.get("id") or "") not in existing_ids
        ]
        if not new_high_items:
            break
        report["notes"] = f"{str(report.get('notes') or '').rstrip()}\n\n{continuation.strip()}".strip()
        report["repair_suggestions"] = build_outline_repair_suggestions(
            str(report.get("notes") or ""),
            str(report.get("revision_instruction") or ""),
            str(report.get("summary") or ""),
        )
        last_high_priority_batch_count = len(new_high_items)
        suggestions = [item for item in report.get("repair_suggestions", []) if isinstance(item, dict)]

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
    continue_outline_review_high_priority_items(store, adapter, reviewed, report)
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
    with outline_review_apply_lock(project_id, run_id):
        return _apply_outline_review_locked(
            store,
            adapter,
            project_id,
            run_id,
            emit,
            selected_issue_ids,
            decisions,
        )


def _apply_outline_review_locked(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    run_id: str,
    emit: ProgressFunc,
    selected_issue_ids: list[str] | None = None,
    decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    report = load_outline_review_report(store, project_id, run_id)
    state = store.load_state(project_id)
    if report.get("applied") is True or str(report.get("status") or "").strip().lower() == "applied":
        updated_stages = report.get("updated_stages")
        skipped_stages = report.get("skipped_stages")
        applied_path = str(
            report.get("applied_path")
            or store.outline_path(project_id).relative_to(store.project_dir(project_id)).as_posix()
        )
        return {
            "project_id": project_id,
            "run_id": run_id,
            "status": str(report.get("status") or "applied"),
            "applied": True,
            "already_applied": True,
            "applied_at": str(report.get("applied_at") or ""),
            "applied_path": applied_path,
            "path": applied_path,
            "version_count": len(state.outline_versions),
            "updated_stages": [str(item) for item in updated_stages] if isinstance(updated_stages, list) else [],
            "skipped_stages": [str(item) for item in skipped_stages] if isinstance(skipped_stages, list) else [],
        }
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
        applied_report = mark_outline_review_applied(
            store,
            state,
            report,
            path=store.outline_path(project_id),
        )
        return {
            "project_id": project_id,
            "run_id": run_id,
            "status": applied_report.get("status"),
            "applied": True,
            "applied_at": applied_report.get("applied_at"),
            "applied_path": applied_report.get("applied_path"),
            "path": store.outline_path(project_id).relative_to(store.project_dir(project_id)).as_posix(),
            "version_count": len(state.outline_versions),
            "updated_stages": applied_report.get("updated_stages", []),
            "skipped_stages": applied_report.get("skipped_stages", []),
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
    applied_report = mark_outline_review_applied(
        store,
        compared,
        report,
        path=store.outline_path(project_id),
        updated_stages=updated_stages,
        skipped_stages=skipped_stages,
    )
    emit("OutlineReview", "大纲审查建议已应用并保存。")
    return {
        "project_id": project_id,
        "run_id": run_id,
        "status": applied_report.get("status"),
        "applied": True,
        "applied_at": applied_report.get("applied_at"),
        "applied_path": applied_report.get("applied_path"),
        "path": store.outline_path(project_id).relative_to(store.project_dir(project_id)).as_posix(),
        "version_count": len(compared.outline_versions),
        "updated_stages": applied_report.get("updated_stages", []),
        "skipped_stages": applied_report.get("skipped_stages", []),
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

def strip_markdown_heading(text: str) -> str:
    return re.sub(r"^\s*#+\s*", "", text.strip(), flags=re.MULTILINE)
