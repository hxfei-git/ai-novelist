"""File-backed services used by the Web API."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.graph_outline import (
    advance_outline_stage_node,
    run_outline_stage_node,
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
    return [outline_stage_payload(store, state, stage, include_content=False) for stage in OUTLINE_STAGES]


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
        "schema: {status, summary, issues}",
        "status 只能是 reviewed 或 needs_repair。",
        "issues 每项 schema: {severity, chapter, category, message}。",
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
        chapter = int(raw_chapter) if str(raw_chapter).isdigit() else None
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
    status = str(data.get("status") or "").strip().lower()
    if status not in {"reviewed", "needs_repair"}:
        status = "needs_repair" if any(item["severity"] == "serious" for item in issues) else "reviewed"
    return {"status": status, "summary": str(data.get("summary") or "").strip(), "issues": issues}


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
    report = load_global_review(store, project_id, run_id)
    serious = [item for item in report.get("issues", []) if isinstance(item, dict) and item.get("severity") == "serious" and item.get("chapter")]
    proposals = []
    for issue in serious:
        chapter = int(issue["chapter"])
        draft = load_latest_chapter_text(store, project_id, chapter)
        prompt = (
            "AGENT: global_consistency_repair\n"
            f"PROJECT_ID: {project_id}\nCHAPTER: {chapter}\n"
            f"ISSUE: {issue.get('message')}\n\n"
            "请只输出修复后的章节草稿 Markdown，不要解释。\n\n"
            f"## Current Draft\n{draft or '暂无'}\n"
        )
        try:
            repaired = adapter.complete(prompt, store.project_dir(project_id)).strip()
        except AgentAdapterError:
            repaired = ""
        if not repaired:
            repaired = fallback_repair_text(chapter, draft, str(issue.get("message") or "严重连续性问题"))
        path = proposed_repair_path(store, project_id, chapter, run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(repaired.rstrip() + "\n", encoding="utf-8")
        proposals.append({"chapter": chapter, "path": path.relative_to(store.project_dir(project_id)).as_posix(), "issue": issue})
    return {"project_id": project_id, "run_id": run_id, "proposals": proposals}


def apply_repair(store: LocalStore, project_id: str, chapter: int, run_id: str) -> dict[str, Any]:
    if chapter < 1:
        raise LocalStoreError("Chapter must be greater than 0")
    source = proposed_repair_path(store, project_id, chapter, run_id)
    if not source.exists():
        raise LocalStoreError(f"Repair proposal does not exist: chapter {chapter}, run {run_id}")
    content = source.read_text(encoding="utf-8")
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
        "run_id": run_id,
        "version": version,
        "path": draft_path.relative_to(store.project_dir(project_id)).as_posix(),
    }


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

