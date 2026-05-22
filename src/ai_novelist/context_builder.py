"""Task-specific context assembly helpers."""

from __future__ import annotations

from collections.abc import Iterable

from ai_novelist.artifacts import get_latest_artifact, load_artifact_text
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore

Section = tuple[str, str]

PURPOSE_ARTIFACT_TYPES = {
    "chapter_planning": ["chapter_outline", "novel_bible"],
    "scene_design": ["chapter_card"],
    "drafting": ["chapter_card", "scene_cards"],
    "review": ["chapter_card", "scene_cards", "chapter_draft"],
    "revision": ["chapter_draft", "review_report", "revision_plan", "chapter_card", "scene_cards"],
    "bible_update": ["review_lock", "final_chapter", "chapter_summary"],
    "export": ["final_chapter", "chapter_summary", "novel_bible"],
    "outline_stage": ["reference_brief"],
    "director": ["novel_bible"],
}


def build_context(
    state: NovelState,
    store: LocalStore,
    purpose: str,
    chapter: int | None = None,
    stage: str | None = None,
    max_chars: int = 12000,
) -> str:
    selected_chapter = chapter or state.active_chapter or state.current_chapter
    selected_stage = stage or state.outline_stage
    sections: list[Section] = [
        ("用户当前请求", state.user_request or "暂无"),
        ("当前任务", build_task_summary(purpose, selected_chapter, selected_stage)),
        ("锁定约束", build_locked_constraints_section(state)),
        ("小说圣经", build_bible_section(state, store)),
        ("当前任务 Artifact", build_artifact_section(state, store, purpose, selected_chapter, selected_stage)),
        ("项目上下文", store.load_project_context(state.project_id) or "暂无"),
        ("参考资料", build_reference_section(state, store)),
        ("当前章节相关信息", build_chapter_section(state, store, selected_chapter)),
        ("已写前文摘要", build_chapter_summaries_section(state, selected_chapter)),
        ("最近对话摘要", build_messages_summary_section(state)),
    ]
    return truncate_sections(sections, max_chars=max_chars)


def build_task_summary(purpose: str, chapter: int | None, stage: str | None) -> str:
    lines = [f"- purpose: {purpose}"]
    if chapter:
        lines.append(f"- chapter: {chapter}")
    if stage:
        lines.append(f"- stage: {stage}")
    return "\n".join(lines)


def build_locked_constraints_section(state: NovelState) -> str:
    if not state.locked_constraints:
        return "暂无"
    return "\n".join(f"- {item}" for item in state.locked_constraints)


def build_project_brief_section(state: NovelState) -> str:
    lines = [f"- 标题：{state.title}"]
    if state.idea:
        lines.append(f"- 创意：{state.idea}")
    if state.style_preferences:
        lines.append("- 风格偏好：" + "，".join(state.style_preferences))
    return "\n".join(lines)


def build_bible_section(state: NovelState, store: LocalStore) -> str:
    path = store.novel_bible_markdown_path(state.project_id)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return build_project_brief_section(state)


def build_artifact_section(
    state: NovelState,
    store: LocalStore,
    purpose: str,
    chapter: int | None,
    stage: str | None,
) -> str:
    project_dir = store.project_dir(state.project_id)
    parts: list[str] = []
    for artifact_type in PURPOSE_ARTIFACT_TYPES.get(purpose, []):
        record = get_latest_artifact(project_dir, artifact_type, chapter=chapter)
        if record is None and stage:
            record = get_latest_artifact(project_dir, artifact_type, stage=stage)
        if record is None:
            record = get_latest_artifact(project_dir, artifact_type)
        if record is None:
            continue
        text = load_artifact_text(project_dir, record).strip()
        parts.append(f"## {artifact_type} ({record.path})\n{text or '暂无'}")
    fallback = build_state_artifact_fallback(state, purpose)
    if fallback:
        parts.append(fallback)
    return "\n\n".join(parts) if parts else "暂无"


def build_state_artifact_fallback(state: NovelState, purpose: str) -> str:
    parts = []
    if purpose in {"scene_design", "drafting", "review", "revision"} and state.current_chapter_card.strip():
        parts.append("## current_chapter_card\n" + state.current_chapter_card.strip())
    if purpose in {"drafting", "review", "revision"} and state.current_scene_cards.strip():
        parts.append("## current_scene_cards\n" + state.current_scene_cards.strip())
    if purpose in {"review", "revision"} and state.chapter_draft.strip():
        parts.append("## chapter_draft\n" + state.chapter_draft.strip())
    if purpose == "revision" and state.current_review_report.strip():
        parts.append("## current_review_report\n" + state.current_review_report.strip())
    return "\n\n".join(parts)


def build_reference_section(state: NovelState, store: LocalStore) -> str:
    path = store.reference_brief_path(state.project_id)
    parts = []
    if state.reference_brief.strip():
        parts.append(state.reference_brief.strip())
    elif path.exists():
        parts.append(path.read_text(encoding="utf-8").strip())
    if state.retrieval_context.strip():
        parts.append("## 检索上下文\n" + state.retrieval_context.strip())
    if state.research_uncertainties:
        parts.append("## 不确定点\n" + "\n".join(f"- {item}" for item in state.research_uncertainties))
    return "\n\n".join(parts) if parts else "暂无"


def build_chapter_section(state: NovelState, store: LocalStore, chapter: int | None) -> str:
    selected = chapter or state.current_chapter
    parts = []
    legacy_path = store.chapter_path(state.project_id, selected)
    if legacy_path.exists():
        relative_path = legacy_path.relative_to(store.project_dir(state.project_id)).as_posix()
        parts.append(f"## 旧章节正文路径：{relative_path}\n" + legacy_path.read_text(encoding="utf-8"))
    if state.chapter_draft.strip() and selected == state.current_chapter:
        parts.append("## 当前章节草稿\n" + state.chapter_draft.strip())
    return "\n\n".join(parts) if parts else "暂无"


def build_chapter_summaries_section(state: NovelState, chapter: int | None) -> str:
    if not state.chapter_summaries:
        return "暂无"
    selected = chapter or state.current_chapter
    lines = []
    for key, summary in sorted(state.chapter_summaries.items(), key=chapter_sort_key):
        if str(key).isdigit() and int(key) >= selected:
            continue
        lines.append(f"- 第 {key} 章：{summary}")
    return "\n".join(lines) if lines else "暂无"


def build_messages_summary_section(state: NovelState, max_items: int = 6, max_chars_per_message: int = 240) -> str:
    lines = []
    for message in state.messages[-max_items:]:
        role = str(message.get("role", "")).strip()
        content = str(message.get("content", "")).strip()
        if not role or not content:
            continue
        if len(content) > max_chars_per_message:
            content = content[:max_chars_per_message].rstrip() + "..."
        lines.append(f"- {role}: {content}")
    return "\n".join(lines) if lines else "暂无"


def truncate_sections(sections: list[Section], max_chars: int) -> str:
    if max_chars < 1:
        max_chars = 1
    rendered = render_sections(sections)
    if len(rendered) <= max_chars:
        return rendered

    protected_titles = {"用户当前请求", "当前任务", "锁定约束"}
    protected = [(title, content) for title, content in sections if title in protected_titles]
    flexible = [(title, content) for title, content in sections if title not in protected_titles]
    protected_text = render_sections(protected)
    if len(protected_text) >= max_chars:
        return protected_text[:max_chars].rstrip() + "\n\n[已截断，锁定约束或任务描述过长]"

    remaining = max_chars - len(protected_text) - 2
    per_section = max(120, remaining // max(1, len(flexible)))
    clipped: list[Section] = list(protected)
    for title, content in flexible:
        text = content.strip() or "暂无"
        if len(text) > per_section:
            text = text[: max(40, per_section - 28)].rstrip() + "\n[已截断，完整内容见 artifact path]"
        clipped.append((title, text))
    result = render_sections(clipped)
    if len(result) > max_chars:
        result = result[:max_chars].rstrip() + "\n[已截断]"
    return result


def render_sections(sections: Iterable[Section]) -> str:
    lines = ["# Task Context", ""]
    for title, content in sections:
        lines.append(f"## {title}")
        lines.append((content or "暂无").strip() or "暂无")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def chapter_sort_key(item: tuple[str, str]) -> tuple[int, str]:
    key = item[0]
    if str(key).isdigit():
        return (0, f"{int(key):06d}")
    return (1, str(key))
