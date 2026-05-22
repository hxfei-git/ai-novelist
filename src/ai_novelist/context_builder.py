"""Task-specific context assembly helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from ai_novelist.agent_metrics import estimate_tokens
from ai_novelist.artifacts import get_latest_artifact, load_artifact_text
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore

Section = tuple[str, str]


@dataclass(frozen=True)
class ContextSource:
    section: str
    source_type: str
    path: str | None
    original_chars: int
    included_chars: int
    truncated: bool = False
    digest: str | None = None


@dataclass(frozen=True)
class ContextBundle:
    text: str
    sources: list[ContextSource]
    total_chars: int
    estimated_tokens: int
    truncated: bool


@dataclass(frozen=True)
class ContextProfile:
    name: str
    purpose: str
    max_chars: int
    sections: tuple[str, ...]
    artifact_types: tuple[str, ...] = ()
    per_section_budget: dict[str, int] = field(default_factory=dict)
    include_full_draft: bool = False
    include_reference: Literal["none", "brief", "full"] = "brief"
    include_bible: Literal["none", "summary", "full"] = "summary"
    include_project_context: bool = False
    include_recent_messages: bool = True


PURPOSE_ARTIFACT_TYPES = {
    "chapter_planning": ["chapter_outline", "novel_bible"],
    "scene_design": ["chapter_card"],
    "drafting": ["chapter_card", "scene_cards"],
    "review": ["chapter_card", "scene_cards"],
    "revision": ["chapter_draft", "review_report", "revision_plan", "chapter_card", "scene_cards"],
    "bible_update": ["review_lock", "final_chapter", "chapter_summary"],
    "export": ["final_chapter", "chapter_summary", "novel_bible"],
    "outline_stage": ["reference_brief"],
    "director": ["novel_bible"],
}


CONTEXT_PROFILES = {
    "director": ContextProfile(
        name="director",
        purpose="director",
        max_chars=4000,
        sections=("user_request", "task", "locked_constraints", "project_brief", "recent_messages"),
        include_reference="none",
        include_bible="summary",
        include_project_context=True,
    ),
    "review_context": ContextProfile(
        name="review_context",
        purpose="review",
        max_chars=9000,
        sections=("user_request", "task", "locked_constraints", "chapter_artifacts", "previous_chapter_summaries", "style_or_bible_digest"),
        artifact_types=("chapter_card", "scene_cards"),
        include_full_draft=False,
        include_reference="none",
        include_bible="summary",
    ),
    "review_editor": ContextProfile(
        name="review_editor",
        purpose="review",
        max_chars=10000,
        sections=("task", "locked_constraints", "chapter_artifacts", "previous_chapter_summaries", "style_or_bible_digest"),
        artifact_types=("chapter_card", "scene_cards"),
        include_full_draft=False,
        include_reference="none",
        include_bible="summary",
    ),
    "review_synthesizer": ContextProfile(
        name="review_synthesizer",
        purpose="review",
        max_chars=8000,
        sections=("task", "locked_constraints", "chapter_artifacts"),
        artifact_types=("chapter_card", "scene_cards"),
        include_full_draft=False,
        include_reference="none",
        include_bible="summary",
    ),
    "chapter_planning": ContextProfile(
        name="chapter_planning",
        purpose="chapter_planning",
        max_chars=8000,
        sections=("user_request", "task", "locked_constraints", "chapter_outline_slice", "previous_chapter_summaries", "bible_digest"),
        artifact_types=("chapter_outline",),
        include_reference="brief",
        include_bible="summary",
    ),
    "outline_role": ContextProfile(
        name="outline_role",
        purpose="outline_stage",
        max_chars=6000,
        sections=("user_request", "idea", "locked_constraints", "reference_brief", "previous_stage_memory", "current_stage_context"),
        artifact_types=("reference_brief",),
        include_reference="brief",
        include_bible="none",
    ),
    "outline_synthesizer": ContextProfile(
        name="outline_synthesizer",
        purpose="outline_stage",
        max_chars=9000,
        sections=("user_request", "idea", "locked_constraints", "previous_stage_memory", "current_stage_context", "role_reviews"),
        include_reference="brief",
        include_bible="none",
    ),
    "revision": ContextProfile(
        name="revision",
        purpose="revision",
        max_chars=12000,
        sections=("task", "locked_constraints", "chapter_artifacts", "review_tasks", "previous_chapter_summaries"),
        artifact_types=("chapter_card", "scene_cards", "revision_plan"),
        include_full_draft=True,
        include_reference="none",
        include_bible="summary",
    ),
}

PURPOSE_PROFILE_ALIASES = {
    "review": "review_context",
    "chapter_planning": "chapter_planning",
    "outline_stage": "outline_role",
    "revision": "revision",
    "director": "director",
}


def build_context(
    state: NovelState,
    store: LocalStore,
    purpose: str,
    chapter: int | None = None,
    stage: str | None = None,
    max_chars: int = 12000,
) -> str:
    profile_name = purpose if purpose in CONTEXT_PROFILES else PURPOSE_PROFILE_ALIASES.get(purpose)
    if profile_name:
        return build_context_bundle(state, store, profile_name, chapter=chapter, stage=stage, max_chars=max_chars).text

    selected_chapter = chapter or state.active_chapter or state.current_chapter
    selected_stage = stage or state.outline_stage
    sections: list[Section] = [
        ("用户当前请求", state.user_request or "暂无"),
        ("当前任务", build_task_summary(purpose, selected_chapter, selected_stage)),
        ("锁定约束", build_locked_constraints_section(state)),
        ("小说圣经", build_bible_section(state, store, mode="full")),
        ("当前任务 Artifact", build_artifact_section(state, store, purpose, selected_chapter, selected_stage)),
        ("项目上下文", store.load_project_context(state.project_id) or "暂无"),
        ("参考资料", build_reference_section(state, store, mode="full")),
        ("当前章节相关信息", build_chapter_section(state, store, selected_chapter, include_full_draft=True)),
        ("已写前文摘要", build_chapter_summaries_section(state, selected_chapter)),
        ("最近对话摘要", build_messages_summary_section(state)),
    ]
    return truncate_sections(sections, max_chars=max_chars)


def build_context_bundle(
    state: NovelState,
    store: LocalStore,
    profile_name: str,
    chapter: int | None = None,
    stage: str | None = None,
    max_chars: int | None = None,
) -> ContextBundle:
    profile = CONTEXT_PROFILES.get(profile_name)
    if profile is None:
        raise ValueError(f"Unknown context profile: {profile_name}")
    selected_chapter = chapter or state.active_chapter or state.current_chapter
    selected_stage = stage or state.outline_stage
    limit = min(max_chars or profile.max_chars, profile.max_chars)
    sections = [build_profile_section(key, state, store, profile, selected_chapter, selected_stage) for key in profile.sections]
    text, sources = render_profile_sections(sections, profile, limit)
    return ContextBundle(
        text=text,
        sources=sources,
        total_chars=len(text),
        estimated_tokens=estimate_tokens(text),
        truncated=any(source.truncated for source in sources) or len(render_sections(sections)) > limit,
    )


def build_context_manifest(bundle: ContextBundle) -> list[dict[str, object]]:
    return [source.__dict__.copy() for source in bundle.sources]


def build_profile_section(
    key: str,
    state: NovelState,
    store: LocalStore,
    profile: ContextProfile,
    chapter: int | None,
    stage: str | None,
) -> Section:
    if key == "user_request":
        return "用户当前请求", state.user_request or "暂无"
    if key == "task":
        return "当前任务", build_task_summary(profile.purpose, chapter, stage)
    if key == "locked_constraints":
        return "锁定约束", build_locked_constraints_section(state)
    if key == "project_brief":
        return "项目简介", build_project_brief_section(state)
    if key == "recent_messages":
        return "最近对话摘要", build_messages_summary_section(state) if profile.include_recent_messages else "暂无"
    if key in {"bible_digest", "style_or_bible_digest"}:
        return "小说圣经摘要", build_bible_section(state, store, mode=profile.include_bible)
    if key == "chapter_artifacts":
        return "当前任务 Artifact", build_artifact_section(state, store, profile.purpose, chapter, stage, artifact_types=profile.artifact_types)
    if key == "chapter_outline_slice":
        return "章节大纲切片", build_artifact_section(state, store, profile.purpose, chapter, "chapter_outline", artifact_types=profile.artifact_types)
    if key == "previous_chapter_summaries":
        return "已写前文摘要", build_chapter_summaries_section(state, chapter)
    if key == "reference_brief":
        return "参考资料", build_reference_section(state, store, mode=profile.include_reference)
    if key == "idea":
        return "创意", state.idea or "暂无"
    if key == "previous_stage_memory":
        return "前序阶段记忆", build_previous_stage_memory(state, stage)
    if key == "current_stage_context":
        return "当前阶段上下文", build_current_stage_context(state, stage)
    if key == "role_reviews":
        return "角色短评", str(state.director_task_args.get("role_reviews", "暂无"))
    if key == "review_tasks":
        return "审稿任务", state.current_review_report or str(state.director_task_args.get("review_json", "")) or "暂无"
    return key, "暂无"


def render_profile_sections(sections: list[Section], profile: ContextProfile, max_chars: int) -> tuple[str, list[ContextSource]]:
    protected_titles = {"用户当前请求", "当前任务", "锁定约束"}
    rendered_parts: list[Section] = []
    sources: list[ContextSource] = []
    fixed_overhead = len("# Task Context\n\n") + sum(len(f"## {title}\n\n") + 2 for title, _ in sections)
    remaining = max(1, max_chars - fixed_overhead)
    default_budget = max(120, remaining // max(1, len(sections)))
    for title, content in sections:
        original = (content or "暂无").strip() or "暂无"
        budget = profile.per_section_budget.get(title, default_budget)
        if title in protected_titles:
            budget = max(budget, min(len(original), 1200))
        included = original
        truncated = False
        if len(included) > budget:
            included = included[: max(40, budget - 28)].rstrip() + "\n[已截断，完整内容见 artifact path]"
            truncated = True
        rendered_parts.append((title, included))
        sources.append(
            ContextSource(
                section=title,
                source_type=profile.name,
                path=None,
                original_chars=len(original),
                included_chars=len(included),
                truncated=truncated,
                digest=sha256_text(original),
            )
        )
    text = render_sections(rendered_parts)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n[已截断]"
        if sources:
            sources[-1] = ContextSource(
                section=sources[-1].section,
                source_type=sources[-1].source_type,
                path=sources[-1].path,
                original_chars=sources[-1].original_chars,
                included_chars=sources[-1].included_chars,
                truncated=True,
                digest=sources[-1].digest,
            )
    return text, sources


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


def build_bible_section(state: NovelState, store: LocalStore, mode: str = "summary") -> str:
    if mode == "none":
        return "暂无"
    path = store.novel_bible_markdown_path(state.project_id)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        return text if mode == "full" else summarize_text(text, max_chars=1600)
    return build_project_brief_section(state)


def build_artifact_section(
    state: NovelState,
    store: LocalStore,
    purpose: str,
    chapter: int | None,
    stage: str | None,
    artifact_types: tuple[str, ...] | None = None,
) -> str:
    project_dir = store.project_dir(state.project_id)
    parts: list[str] = []
    for artifact_type in artifact_types or tuple(PURPOSE_ARTIFACT_TYPES.get(purpose, [])):
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
    if purpose == "revision" and state.chapter_draft.strip():
        parts.append("## chapter_draft\n" + state.chapter_draft.strip())
    if purpose == "revision" and state.current_review_report.strip():
        parts.append("## current_review_report\n" + state.current_review_report.strip())
    return "\n\n".join(parts)


def build_reference_section(state: NovelState, store: LocalStore, mode: str = "full") -> str:
    if mode == "none":
        return "暂无"
    path = store.reference_brief_path(state.project_id)
    parts = []
    if state.reference_brief.strip():
        parts.append(state.reference_brief.strip())
    elif path.exists():
        parts.append(path.read_text(encoding="utf-8").strip())
    if mode == "full" and state.retrieval_context.strip():
        parts.append("## 检索上下文\n" + state.retrieval_context.strip())
    if mode == "full" and state.research_uncertainties:
        parts.append("## 不确定点\n" + "\n".join(f"- {item}" for item in state.research_uncertainties))
    text = "\n\n".join(parts) if parts else "暂无"
    return summarize_text(text, max_chars=1800) if mode == "brief" else text


def build_chapter_section(state: NovelState, store: LocalStore, chapter: int | None, include_full_draft: bool = True) -> str:
    if not include_full_draft:
        return "暂无"
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


def build_previous_stage_memory(state: NovelState, stage: str | None) -> str:
    if not stage:
        return "暂无"
    order = ["direction", "concept", "worldbuilding", "characters", "story_flow", "volume_outline", "chapter_outline", "review_lock"]
    if stage not in order:
        return "暂无"
    lines = []
    for item_stage in order[: order.index(stage)]:
        artifact = state.outline_stage_artifacts.get(item_stage)
        if not isinstance(artifact, dict):
            continue
        label = artifact.get("label") or item_stage
        memory = artifact.get("stage_memory") or artifact.get("summary") or ""
        if isinstance(memory, list):
            memory_text = "\n".join(f"- {item}" for item in memory if str(item).strip())
        else:
            memory_text = str(memory).strip()
        if memory_text:
            lines.append(f"## {label}\n{memory_text}")
    return "\n\n".join(lines) if lines else "暂无"


def build_current_stage_context(state: NovelState, stage: str | None) -> str:
    artifact = state.outline_stage_artifacts.get(stage or "")
    if not isinstance(artifact, dict):
        return "暂无"
    return str(artifact.get("summary") or artifact.get("synthesis") or "暂无").strip() or "暂无"


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


def summarize_text(text: str, max_chars: int = 420) -> str:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return ""
    return cleaned[:max_chars].rstrip() + ("..." if len(cleaned) > max_chars else "")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
