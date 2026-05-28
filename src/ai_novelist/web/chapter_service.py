"""Chapter review helpers used by the Web service layer."""

from __future__ import annotations

from pathlib import Path

from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore
from ai_novelist.web.outline_service import load_stage_markdown


def chapter_outline_review_source_text(state: NovelState, store: LocalStore) -> str:
    artifact = dict(state.outline_stage_artifacts.get('chapter_outline') or {})
    text = load_stage_markdown(store, state, 'chapter_outline', artifact).strip()
    return text


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
