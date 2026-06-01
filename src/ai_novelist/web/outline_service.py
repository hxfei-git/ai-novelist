"""Outline workflow helpers used by the Web service layer."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_novelist.artifacts import ArtifactRecord, register_artifact
from ai_novelist.graph_outline import (
    build_final_outline_text,
    extract_outline_stage_memory_for_artifact,
    save_outline_stage_outputs,
    stage_full_text,
    summarize_outline_stage_for_artifact,
)
from ai_novelist.outline.stage_contracts import OUTLINE_STAGES, STAGE_LABELS
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError, summarize_text

def outline_stage_list(store: LocalStore, project_id: str) -> list[dict[str, Any]]:
    state = store.load_state(project_id)
    hidden_stages = {"review_lock", "chapter_outline"}
    return [outline_stage_payload(store, state, stage, include_content=False) for stage in OUTLINE_STAGES if stage not in hidden_stages]

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
        "action_state": outline_stage_action_state(store, state, stage, status),
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

def ensure_outline_stage_mutable(state: NovelState, stage: str) -> None:
    artifact = state.outline_stage_artifacts.get(stage)
    if isinstance(artifact, dict) and str(artifact.get("status") or "") == "locked":
        raise LocalStoreError("已锁定")

def ensure_ordinary_stage_mutation(stage: str) -> None:
    if stage == "chapter_outline":
        raise LocalStoreError("章节大纲请使用分卷章节大纲工作区操作")

def has_outline_stage_content(store: LocalStore, state: NovelState, stage: str) -> bool:
    artifact = state.outline_stage_artifacts.get(stage)
    artifact_dict = dict(artifact) if isinstance(artifact, dict) else {}
    return bool(load_stage_markdown(store, state, stage, artifact_dict).strip())

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

OUTLINE_REVIEW_SECTION_STAGES = {
    STAGE_LABELS[stage]: stage
    for stage in OUTLINE_STAGES
    if stage != "review_lock"
}

def outline_review_report_paths(store: LocalStore, project_id: str, run_id: str) -> tuple[Path, Path]:
    return store.outline_review_report_path(project_id, run_id), store.outline_review_markdown_path(project_id, run_id)

def split_outline_review_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_title = ""
    current_lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        stripped = raw_line.strip()
        heading = re.match(r"^##\s+(.+?)\s*$", stripped)
        if heading and heading.group(1) in OUTLINE_REVIEW_SECTION_STAGES:
            if current_title:
                sections[current_title] = "\n".join(current_lines).strip()
            current_title = heading.group(1)
            current_lines = []
            continue
        if current_title:
            current_lines.append(raw_line)
    if current_title:
        sections[current_title] = "\n".join(current_lines).strip()
    return sections

def write_outline_review_baseline_sections(store: LocalStore, state: NovelState, outline_text: str) -> tuple[list[str], list[str]]:
    sections = split_outline_review_sections(outline_text)
    updated_stages: list[str] = []
    skipped_stages: list[str] = []
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    for title, stage in OUTLINE_REVIEW_SECTION_STAGES.items():
        section_text = sections.get(title, "").strip()
        if not section_text:
            if title in sections:
                skipped_stages.append(stage)
            continue
        artifact = dict(state.outline_stage_artifacts.get(stage) or {})
        summary = summarize_outline_stage_for_artifact(stage, section_text)
        stage_memory = extract_outline_stage_memory_for_artifact(stage, section_text)
        pending_questions = collect_pending_questions_from_markdown(section_text)
        artifact.update(
            {
                "stage": stage,
                "label": title,
                "status": str(artifact.get("status") or "options_ready"),
                "path": f"outline/{stage}.md",
                "synthesis": section_text,
                "summary": summary,
                "stage_memory": stage_memory,
                "pending_questions": pending_questions,
                "updated_at": timestamp,
            }
        )
        state.outline_stage_artifacts[stage] = artifact
        state.outline_stage_summaries[stage] = summary
        save_outline_stage_outputs(state, stage, section_text, store, source_agent="outline_review_apply")
        if stage == "worldbuilding":
            state.worldbuilding = section_text
            store.save_worldbuilding(state)
        updated_stages.append(stage)
    return updated_stages, skipped_stages

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


def normalize_outline_review_message(message: str) -> str:
    return re.sub(r"\s+", "", str(message or "")).rstrip("。；;,.，")


OUTLINE_REVIEW_PRIORITY_ORDER = ("high", "low", "suggestion")
OUTLINE_REVIEW_PRIORITY_LABELS = {
    "high": "高优先级问题",
    "low": "低优先级问题",
    "suggestion": "建议问题",
}
OUTLINE_REVIEW_PRIORITY_TITLES = {
    "高优先级问题": "high",
    "高优先级": "high",
    "阻塞问题": "high",
    "低优先级问题": "low",
    "低优先级": "low",
    "建议问题": "suggestion",
    "建议项": "suggestion",
}
OUTLINE_REVIEW_PRIORITY_CAPS = {
    "high": 50,
    "low": 20,
    "suggestion": 10,
}


def markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            current = re.sub(r"^#+\s*", "", stripped).strip()
            sections.setdefault(current, [])
            continue
        if current:
            sections.setdefault(current, []).append(line)
    return {title: "\n".join(lines).strip() for title, lines in sections.items()}


def extract_raw_numbered_markdown_items(text: str) -> dict[int, str]:
    items: dict[int, list[str]] = {}
    current: int | None = None
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(\d+)[.)、]\s*(.+)$", stripped)
        if match:
            current = int(match.group(1))
            items[current] = [match.group(2).strip()]
        elif current is not None and not stripped.startswith("#"):
            items[current].append(clean_pending_question_line(stripped))
    return {number: " ".join(parts).strip() for number, parts in items.items()}


def extract_raw_markdown_list_items(text: str) -> list[str]:
    items: list[list[str]] = []
    current: list[str] | None = None
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        numbered_match = re.match(r"^\d+[.)、]\s*(.+)$", stripped)
        bullet_match = re.match(r"^[-*+\u2022]\s+(.+)$", stripped)
        if numbered_match or bullet_match:
            current = [(numbered_match or bullet_match).group(1).strip()]
            items.append(current)
            continue
        if current is not None and not stripped.startswith("#"):
            current.append(clean_pending_question_line(stripped))
    return [" ".join(parts).strip() for parts in items if " ".join(parts).strip()]


def extract_numbered_markdown_items(text: str) -> dict[int, str]:
    return {
        number: summarize_text(item, max_chars=180).strip()
        for number, item in extract_raw_numbered_markdown_items(text).items()
    }


def first_numbered_section_items(sections: dict[str, str], titles: tuple[str, ...]) -> dict[int, str]:
    for title in titles:
        body = sections.get(title, "")
        items = extract_numbered_markdown_items(body)
        if items:
            return items
    return {}


def outline_review_issue_recommendation_pairs(notes: str) -> list[tuple[str, str]]:
    sections = markdown_sections(notes)
    issues = first_numbered_section_items(sections, ("主要问题", "问题", "审查问题", "风险问题"))
    recommendations = first_numbered_section_items(sections, ("修改建议", "修订建议", "建议", "推荐修改意见"))
    pairs: list[tuple[str, str]] = []
    for number in sorted(issues):
        message = issues.get(number, "").strip()
        recommendation = recommendations.get(number, "").strip()
        if message and recommendation:
            pairs.append((message, recommendation))
    return pairs


def normalize_outline_review_priority(value: Any) -> str:
    priority = str(value or "").strip().lower()
    return priority if priority in OUTLINE_REVIEW_PRIORITY_ORDER else "low"


def outline_review_priority_rank(value: Any) -> int:
    priority = normalize_outline_review_priority(value)
    return OUTLINE_REVIEW_PRIORITY_ORDER.index(priority)


def split_recommendation_from_review_item(text: str) -> tuple[str, str]:
    cleaned = str(text or "").strip()
    for marker in ("——推荐修改意见：", "--推荐修改意见：", "推荐修改意见：", "——修改建议：", "修改建议：", "——建议：", "建议："):
        if marker in cleaned:
            message, recommendation = cleaned.split(marker, 1)
            message = message.strip()
            recommendation = recommendation.strip()
            return message, recommendation or message
    return cleaned, cleaned


def build_outline_repair_suggestion(message: str, recommendation: str, priority: str = "low") -> dict[str, Any]:
    normalized_priority = normalize_outline_review_priority(priority)
    category = "revision" if re.search(r"建议|补|改|修|强化|调整|明确|确认|锁定|删除|统一", recommendation) else "issue"
    return {
        "id": outline_suggestion_identifier(message, recommendation),
        "severity": "normal",
        "category": category,
        "message": message,
        "recommendation": recommendation,
        "priority": normalized_priority,
        "selected": True,
    }


def priority_outline_review_pairs(notes: str) -> list[tuple[str, str, str]]:
    sections = markdown_sections(notes)
    pairs: list[tuple[str, str, str]] = []
    for title, body in sections.items():
        priority = OUTLINE_REVIEW_PRIORITY_TITLES.get(title.strip())
        if not priority:
            continue
        items = extract_raw_markdown_list_items(body)
        limit = OUTLINE_REVIEW_PRIORITY_CAPS[priority]
        for text in items[:limit]:
            message, recommendation = split_recommendation_from_review_item(text)
            if message.strip():
                pairs.append((message.strip(), recommendation.strip() or message.strip(), priority))
    return pairs


def build_outline_repair_suggestions(notes: str, revision_instruction: str, summary: str) -> list[dict[str, Any]]:
    raw_pairs = priority_outline_review_pairs(notes)
    if not raw_pairs:
        raw_pairs = [
            (message, recommendation, "low")
            for message, recommendation in outline_review_issue_recommendation_pairs(notes)
        ]
    if not raw_pairs:
        raw_items = [*extract_markdown_bullets(notes), *extract_markdown_bullets(revision_instruction)]
        if not raw_items:
            fallback = str(revision_instruction or summary or notes or "").strip()
            if fallback:
                raw_items = [fallback]
        raw_pairs = [(item, item, "low") for item in raw_items]
    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_message, raw_recommendation, raw_priority in raw_pairs:
        message = summarize_text(raw_message, max_chars=180).strip()
        recommendation = summarize_text(raw_recommendation, max_chars=180).strip()
        if not message or not recommendation:
            continue
        key = normalize_outline_review_message(message)
        if not key or key in seen:
            continue
        seen.add(key)
        suggestions.append(build_outline_repair_suggestion(message, recommendation, raw_priority))
    return suggestions

PENDING_SECTION_RE = re.compile(r"^#{1,6}\s*(?:[一二三四五六七八九十]+、)?(?:待确认问题|仍需确认的问题)\s*$")

PENDING_GENERIC_PATTERNS = (
    "暂无",
    "当前阶段可继续修改或确认进入下一阶段",
    "请确认是否锁定",
    "并进入下一阶段",
)

def is_generic_pending_question(text: str) -> bool:
    normalized = str(text or "").strip().strip("-* 	")
    if not normalized:
        return True
    if normalized in {"暂无", "无", "没有"}:
        return True
    return any(pattern in normalized for pattern in PENDING_GENERIC_PATTERNS)

def clean_pending_question_line(line: str) -> str:
    cleaned = str(line or "").strip()
    cleaned = re.sub(r"^[-*+•]\s+", "", cleaned)
    cleaned = re.sub(r"^\d+[.)、]\s*", "", cleaned)
    return cleaned.strip()

def dedupe_pending_questions(questions: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for question in questions:
        cleaned = clean_pending_question_line(question)
        key = re.sub(r"\s+", "", cleaned)
        if not cleaned or key in seen or is_generic_pending_question(cleaned):
            continue
        seen.add(key)
        result.append(cleaned)
    return result

def extract_pending_questions_from_stage_markdown(text: str) -> list[str]:
    questions: list[str] = []
    in_pending_section = False
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            in_pending_section = bool(PENDING_SECTION_RE.match(stripped))
            continue
        if not in_pending_section:
            continue
        cleaned = clean_pending_question_line(stripped)
        if is_generic_pending_question(cleaned):
            continue
        questions.append(cleaned)
    return dedupe_pending_questions(questions)


def extract_inline_pending_questions_from_stage_markdown(text: str) -> list[str]:
    questions: list[str] = []
    in_pending_section = False
    in_feedback_section = False
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading = re.sub(r"^#+\s*", "", stripped).strip()
            in_pending_section = bool(PENDING_SECTION_RE.match(stripped))
            in_feedback_section = heading in {"用户本轮反馈", "本轮反馈", "修订反馈"}
            continue
        if in_pending_section or in_feedback_section:
            continue
        cleaned = clean_pending_question_line(stripped)
        if is_submitted_pending_answer_line(cleaned):
            continue
        if "待确认" not in cleaned or is_generic_pending_question(cleaned):
            continue
        questions.append(cleaned)
    return dedupe_pending_questions(questions)


def is_submitted_pending_answer_line(text: str) -> bool:
    cleaned = str(text or "").strip()
    return cleaned.startswith(("问题：", "答案：", "针对当前阶段待确认项"))


def collect_pending_questions_from_markdown(text: str) -> list[str]:
    return dedupe_pending_questions(
        [
            *extract_pending_questions_from_stage_markdown(text),
            *extract_inline_pending_questions_from_stage_markdown(text),
        ]
    )

def normalize_pending_source(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list):
        raw = [str(item) for item in value]
    else:
        raw = []
    return dedupe_pending_questions(raw)

def pending_recommendation_answer(question: str, stage: str) -> str:
    text = str(question or "").strip()
    for marker in ("——推荐方案：", "——建议：", "推荐方案：", "建议："):
        if marker in text:
            recommendation = text.split(marker, 1)[1].strip()
            if recommendation:
                return recommendation
    if "——" in text:
        suffix = text.split("——", 1)[1].strip()
        if any(marker in suffix for marker in ("若", "则", "无需", "优先", "保留", "延后")):
            return suffix
    question_text = text.split("——", 1)[0].rstrip("？?。 ")
    label = STAGE_LABELS.get(stage, stage)
    return f"推荐按“是”处理“{question_text}”，将该结论纳入{label}；未确认细节不额外扩写。"

def pending_display_question(question: str, stage: str) -> str:
    text = str(question or "").strip()
    answer = pending_recommendation_answer(text, stage)
    for marker in ("——推荐方案：", "——建议：", "推荐方案：", "建议："):
        if marker in text and text.split(marker, 1)[1].strip() == answer:
            return text.split(marker, 1)[0].strip()
    if "——" in text and text.split("——", 1)[1].strip() == answer:
        return text.split("——", 1)[0].strip()
    return text

def default_pending_options(question: str, stage: str) -> list[dict[str, Any]]:
    return [
        {"id": "accept", "label": "采纳推荐方案", "answer": pending_recommendation_answer(question, stage)},
        {"id": "defer", "label": "暂不确定", "answer": "本项暂不确定，保留为待确认事项，不进入本阶段锁定结论。"},
        {"id": "custom", "label": "我的建议", "answer": "", "requires_input": True},
    ]

def collect_stage_pending_questions(store: LocalStore, state: NovelState, stage: str) -> list[str]:
    artifact = state.outline_stage_artifacts.get(stage)
    artifact_dict = dict(artifact) if isinstance(artifact, dict) else {}
    artifact_questions = normalize_pending_source(artifact_dict.get("pending_questions"))
    if artifact_questions:
        return artifact_questions
    if state.outline_stage == stage:
        state_questions = normalize_pending_source(state.pending_questions)
        if state_questions:
            return state_questions
    markdown = load_stage_markdown(store, state, stage, artifact_dict)
    return collect_pending_questions_from_markdown(markdown)

def pending_item_id(stage: str, question: str) -> str:
    return hashlib.sha1(f"{stage}|{question}".encode("utf-8")).hexdigest()[:12]

def action_state_for_status(
    status: str,
    pending_questions: list[str] | None = None,
    has_content: bool = False,
) -> dict[str, Any]:
    questions = list(pending_questions or [])
    if status == "locked":
        return {
            "can_generate": False,
            "can_revise": False,
            "can_lock": False,
            "lock_reason": "已锁定",
        }
    if questions:
        lock_reason = "存在待确认问题，请先完成确认"
    elif status != "options_ready":
        lock_reason = "当前阶段尚未准备锁定"
    else:
        lock_reason = ""
    return {
        "can_generate": True,
        "can_revise": has_content,
        "can_lock": status == "options_ready" and not questions,
        "lock_reason": lock_reason,
    }

def outline_stage_action_state(store: LocalStore, state: NovelState, stage: str, status: str) -> dict[str, Any]:
    return action_state_for_status(
        status,
        collect_stage_pending_questions(store, state, stage),
        has_outline_stage_content(store, state, stage),
    )

def outline_revision_instruction_lines(suggestions: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in suggestions:
        message = str(item.get("message") or "").strip()
        recommendation = str(item.get("recommendation") or message).strip()
        if message and recommendation and message != recommendation:
            lines.append(f"- {message} -> {recommendation}")
        elif recommendation:
            lines.append(f"- {recommendation}")
    return lines

def outline_revision_instruction_from_decisions(
    report: dict[str, Any],
    suggestions: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> str:
    _ = report
    suggestions_by_id = {str(item.get("id") or ""): item for item in suggestions}
    ranked_lines: list[tuple[int, int, str]] = []
    for decision_index, raw_decision in enumerate(decisions):
        issue_id = str(raw_decision.get("issue_id") or "").strip()
        decision = str(raw_decision.get("decision") or "").strip()
        if issue_id not in suggestions_by_id:
            raise LocalStoreError("未找到选中的大纲审查建议")
        suggestion = suggestions_by_id[issue_id]
        priority_rank = outline_review_priority_rank(suggestion.get("priority"))
        if decision == "skip":
            continue
        if decision == "recommended":
            for line in outline_revision_instruction_lines([suggestion]):
                ranked_lines.append((priority_rank, decision_index, line))
            continue
        if decision == "custom":
            custom_answer = str(raw_decision.get("custom_answer") or "").strip()
            if not custom_answer:
                raise LocalStoreError("我的意见不能为空")
            message = str(suggestion.get("message") or "").strip()
            line = f"- {message} -> {custom_answer}" if message else f"- {custom_answer}"
            ranked_lines.append((priority_rank, decision_index, line))
            continue
        raise LocalStoreError("不支持的大纲审查处理方式")
    lines = [line for _, _, line in sorted(ranked_lines, key=lambda item: (item[0], item[1]))]
    if not lines:
        raise LocalStoreError("请选择至少一条大纲审查建议")
    return "按用户逐项确认采纳以下大纲审查意见：\n" + "\n".join(lines)

def selected_outline_revision_instruction(
    report: dict[str, Any],
    selected_issue_ids: list[str] | None,
    decisions: list[dict[str, Any]] | None = None,
) -> str:
    suggestions = [item for item in report.get("repair_suggestions", []) if isinstance(item, dict)]
    if decisions is not None:
        return outline_revision_instruction_from_decisions(report, suggestions, decisions)
    selected_ids = [str(item) for item in (selected_issue_ids or []) if str(item).strip()]
    if selected_issue_ids is not None and not selected_ids:
        raise LocalStoreError("请选择至少一条大纲审查建议")
    if selected_ids:
        suggestions = [item for item in suggestions if str(item.get("id") or "") in selected_ids]
        if not suggestions:
            raise LocalStoreError("未找到选中的大纲审查建议")
    if suggestions:
        lines = outline_revision_instruction_lines(suggestions)
        if lines:
            return "仅采纳以下选中的大纲审查建议：\n" + "\n".join(lines)
    return str(report.get("revision_instruction") or report.get("summary") or report.get("notes") or "").strip()

def _write_outline_review_report_files(store: LocalStore, project_id: str, report: dict[str, Any]) -> tuple[Path, Path]:
    run_id = str(report.get("run_id") or "").strip()
    if not run_id:
        raise LocalStoreError("Outline review run_id is required")
    report_path, markdown_path = outline_review_report_paths(store, project_id, run_id)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_outline_review_markdown(report), encoding="utf-8")
    return report_path, markdown_path


def write_outline_review_report(store: LocalStore, state: NovelState, report: dict[str, Any]) -> tuple[Path, Path]:
    report_path, markdown_path = _write_outline_review_report_files(store, state.project_id, report)
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


def mark_outline_review_applied(
    store: LocalStore,
    state: NovelState,
    report: dict[str, Any],
    *,
    path: Path,
    updated_stages: list[str] | None = None,
    skipped_stages: list[str] | None = None,
) -> dict[str, Any]:
    applied_report = dict(report)
    applied_report.update(
        {
            "status": "applied",
            "applied": True,
            "applied_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "applied_path": path.relative_to(store.project_dir(state.project_id)).as_posix(),
            "updated_stages": list(updated_stages or []),
            "skipped_stages": list(skipped_stages or []),
        }
    )
    _write_outline_review_report_files(store, state.project_id, applied_report)
    return applied_report

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
