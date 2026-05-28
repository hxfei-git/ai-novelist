"""Global chapter review and repair actions for the Web API."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.storage.local_store import LocalStore, LocalStoreError
from ai_novelist.web.chapter_actions import (
    collect_latest_chapters,
    fallback_repair_text,
    latest_chapter_path,
    load_latest_chapter_text,
    next_draft_version,
)
from ai_novelist.web.chapter_service import build_global_review_prompt
from ai_novelist.web.json_utils import parse_json_object

ProgressFunc = Callable[[str, str], None]


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
