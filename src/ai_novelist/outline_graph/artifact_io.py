"""Artifact summarization, formatting, and persistence helpers for outline stages."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from ai_novelist.characters_framework import extract_characters_memory, summarize_characters_outline
from ai_novelist.outline.chapter_outline_structure import chapter_outline_summary, extract_chapter_outline_memory
from ai_novelist.outline.renderers import (
    extract_direction_memory,
    render_direction_stage_markdown,
    summarize_direction_outline,
)
from ai_novelist.outline.stage_contracts import OUTLINE_STAGES, STAGE_LABELS
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def summarize_worldbuilding_outline(text: str, max_chars: int = 1800) -> str:
    sections = split_worldbuilding_sections(text)
    key_headings = [
        "一、世界核心设定",
        "二、世界格局",
        "六、世界规则",
        "七、力量体系",
        "八、成长体系",
        "十四、势力体系",
        "二十八、核心矛盾",
        "二十九、主角与世界的关系",
        "三十一、主线时间线",
        "三十二、隐藏真相",
        "三十三、结局后的世界格局",
    ]
    lines: list[str] = []
    for heading in key_headings:
        bullet = first_worldbuilding_bullet(sections.get(heading, ""))
        if bullet:
            lines.append(f"{heading}：{bullet}")
    if not lines:
        return summarize_stage_text(text, max_chars=420)
    summary = "；".join(lines)
    return summary[:max_chars].rstrip() + ("..." if len(summary) > max_chars else "")


def extract_worldbuilding_memory(text: str, max_items: int = 18, max_chars: int = 1800) -> list[str]:
    sections = split_worldbuilding_sections(text)
    priority = [
        "一、世界核心设定",
        "二、世界格局",
        "六、世界规则",
        "七、力量体系",
        "八、成长体系",
        "十一、资源体系",
        "十四、势力体系",
        "二十、法律与秩序体系",
        "二十三、重要地点体系",
        "二十八、核心矛盾",
        "二十九、主角与世界的关系",
        "三十、主要人物群体",
        "三十一、主线时间线",
        "三十二、隐藏真相",
        "三十三、结局后的世界格局",
    ]
    result: list[str] = []
    total = 0
    for heading in priority:
        for bullet in worldbuilding_bullets(sections.get(heading, ""))[:2]:
            item = f"{heading}：{bullet}"
            if item in result:
                continue
            if total + len(item) > max_chars and result:
                return result
            result.append(item)
            total += len(item)
            if len(result) >= max_items:
                return result
    if result:
        return result
    return extract_stage_memory(text, max_items=12, max_chars=1100)


def split_worldbuilding_sections(text: str) -> dict[str, str]:
    from ai_novelist.worldbuilding_framework import full_worldbuilding_headings

    headings = full_worldbuilding_headings()
    matches: list[tuple[str, int, int]] = []
    for heading in headings:
        pattern = re.compile(rf"^\s*#{{1,6}}\s*{re.escape(heading)}(?:\s|$)", re.MULTILINE)
        match = pattern.search(text or "")
        if match:
            matches.append((heading, match.start(), match.end()))
    matches.sort(key=lambda item: item[1])
    sections: dict[str, str] = {}
    for index, (heading, _start, end) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(text)
        sections[heading] = text[end:next_start].strip()
    return sections


def worldbuilding_bullets(section_text: str) -> list[str]:
    bullets: list[str] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "仍需确认" in line:
            continue
        line = re.sub(r"^[-*+•\s]*", "", line)
        line = re.sub(r"^\d+[.、)]\s*", "", line).strip()
        if not line or line in {"暂无", "暂无。"}:
            continue
        if line.startswith("待补充：结构兜底占位"):
            continue
        bullets.append(line)
    return bullets


def first_worldbuilding_bullet(section_text: str) -> str:
    bullets = worldbuilding_bullets(section_text)
    return bullets[0] if bullets else ""


def summarize_outline_stage_for_artifact(stage: str, synthesis: str) -> str:
    if stage == "direction":
        return summarize_direction_outline(synthesis)
    if stage == "worldbuilding":
        return summarize_worldbuilding_outline(synthesis)
    if stage == "characters":
        return summarize_characters_outline(synthesis)
    if stage == "story_flow":
        from ai_novelist.outline.story_flow_structure import summarize_story_flow_outline

        return summarize_story_flow_outline(synthesis)
    if stage == "volume_outline":
        from ai_novelist.outline.volume_outline_structure import summarize_volume_outline

        return summarize_volume_outline(synthesis)
    if stage == "chapter_outline":
        return chapter_outline_summary(synthesis)
    return summarize_stage_text(synthesis)


def extract_outline_stage_memory_for_artifact(stage: str, synthesis: str) -> list[str]:
    if stage == "direction":
        return extract_direction_memory(synthesis)
    if stage == "worldbuilding":
        return extract_worldbuilding_memory(synthesis)
    if stage == "characters":
        return extract_characters_memory(synthesis)
    if stage == "story_flow":
        from ai_novelist.outline.story_flow_structure import extract_story_flow_memory

        return extract_story_flow_memory(synthesis)
    if stage == "volume_outline":
        from ai_novelist.outline.volume_outline_structure import extract_volume_outline_memory

        return extract_volume_outline_memory(synthesis)
    if stage == "chapter_outline":
        return extract_chapter_outline_memory(synthesis)
    return extract_stage_memory(synthesis)


def summarize_stage_text(text: str, max_chars: int = 420) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    return cleaned[:max_chars].rstrip() + ("..." if len(cleaned) > max_chars else "")


def extract_stage_memory(text: str, max_items: int = 12, max_chars: int = 1100) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        line = re.sub(r"^[-*+•\s]*", "", line)
        line = re.sub(r"^\d+[.、)]\s*", "", line).strip()
        if not line or line.startswith("#") or "仍需确认" in line or "暂无" == line:
            continue
        lines.append(line)
    if not lines and text.strip():
        lines = [summarize_stage_text(text, max_chars=max_chars)]
    result: list[str] = []
    total = 0
    for line in lines:
        if line in result:
            continue
        total += len(line)
        if total > max_chars and result:
            break
        result.append(line)
        if len(result) >= max_items:
            break
    return result


def stage_memory_context(artifact: dict, max_chars: int) -> str:
    memory = artifact.get("stage_memory")
    if isinstance(memory, list) and memory:
        context = "\n".join(f"- {str(item).strip()}" for item in memory if str(item).strip())
    else:
        context = str(artifact.get("summary") or artifact.get("synthesis", "")).strip()
    if len(context) > max_chars:
        context = context[:max_chars].rstrip() + "\n..."
    return context


def stage_full_text(state: NovelState, store: LocalStore, stage: str) -> str:
    saved = store.load_outline_artifact(state.project_id, stage).strip()
    if saved:
        return saved
    artifact = state.outline_stage_artifacts.get(stage, {})
    if isinstance(artifact, dict):
        return str(artifact.get("synthesis") or artifact.get("summary") or "").strip()
    return ""


def previous_stage_context(state: NovelState, stage: str, max_chars_per_stage: int = 1800) -> str:
    if stage not in OUTLINE_STAGES:
        return "暂无"
    parts: list[str] = []
    for previous_stage in OUTLINE_STAGES[: OUTLINE_STAGES.index(stage)]:
        artifact = state.outline_stage_artifacts.get(previous_stage)
        if not isinstance(artifact, dict):
            continue
        context = stage_memory_context(artifact, max_chars_per_stage)
        if not context:
            continue
        status = str(artifact.get("status") or "draft")
        parts.append(f"## {STAGE_LABELS[previous_stage]}（{status}）\n{context}")
    return "\n\n".join(parts) or "暂无"


def current_stage_context(state: NovelState, stage: str, max_chars: int = 2400) -> str:
    artifact = state.outline_stage_artifacts.get(stage)
    if not isinstance(artifact, dict):
        return "暂无"
    context = stage_memory_context(artifact, max_chars)
    if not context:
        return "暂无"
    status = str(artifact.get("status") or state.outline_stage_status or "draft")
    return f"## {STAGE_LABELS.get(stage, stage)}（{status}）\n{context}"


def format_stage_markdown(artifact: dict) -> str:
    from ai_novelist.outline_graph.repair import (
        replace_pending_questions_section,
        sanitize_direction_stage_output,
    )

    if not artifact:
        return ""
    stage = str(artifact.get("stage", ""))
    if stage == "direction":
        synthesis = sanitize_direction_stage_output(
            str(artifact.get("synthesis", "")).strip(),
            str(artifact.get("user_feedback", "")).strip(),
        )
        questions = artifact.get("pending_questions")
        pending_questions = [str(item).strip() for item in questions if str(item).strip()] if isinstance(questions, list) else None
        return render_direction_stage_markdown(synthesis, pending_questions=pending_questions)
    lines = [f"# {artifact.get('label') or STAGE_LABELS.get(stage, '阶段产物')}", ""]
    user_feedback = str(artifact.get("user_feedback", "")).strip()
    if user_feedback and stage != "direction":
        lines.append("## 用户本轮反馈")
        lines.append(user_feedback)
        lines.append("")
    synthesis = str(artifact.get("synthesis", "")).strip()
    if synthesis:
        if re.match(r"^#{1,6}\s+", synthesis):
            lines.append(synthesis)
        else:
            lines.append("## Director 汇总")
            lines.append(synthesis)
    markdown = "\n".join(lines).rstrip() + "\n"
    questions = artifact.get("pending_questions")
    pending_questions = [str(item).strip() for item in questions if str(item).strip()] if isinstance(questions, list) else None
    return replace_pending_questions_section(markdown, pending_questions)


def build_final_outline_text(state: NovelState, store: LocalStore) -> str:
    sections = []
    for stage in OUTLINE_STAGES:
        synthesis = stage_full_text(state, store, stage).strip()
        if synthesis:
            sections.append(f"## {STAGE_LABELS[stage]}\n\n{synthesis}")
    concept_artifact = state.outline_stage_artifacts.get("concept")
    if isinstance(concept_artifact, dict):
        concept_text = str(concept_artifact.get("synthesis") or concept_artifact.get("summary") or "").strip()
        if concept_text:
            sections.append("## 旧版故事概念参考\n\n" + concept_text)
    return "# 最终锁定总大纲\n\n" + "\n\n".join(sections)


def finalize_locked_outline(state: NovelState, store: LocalStore) -> None:
    state.outline = build_final_outline_text(state, store)
    state.outline_stage = "done"
    state.outline_stage_status = "done"
    state.review_status = "approved"
    state.editor_decision = "pass"
    state.active_workflow = ""
    state.current_stage = "chapter_plan"
    state.director_action = "advance_outline_stage"
    state.director_message = f"七阶段大纲已锁定，并保存为最终大纲：{store.outline_path(state.project_id)}"
    add_outline_version(state, "outline", state.outline, "七阶段锁定大纲")
    store.save_outline(state)


def add_outline_version(state: NovelState, kind: str, content: str, label: str) -> None:
    state.outline_versions.append(
        {
            "kind": kind,
            "label": label,
            "content": content,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    state.selected_outline_version = len(state.outline_versions) - 1
