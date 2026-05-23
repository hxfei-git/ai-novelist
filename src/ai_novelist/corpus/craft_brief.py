"""Stage Craft Brief synthesis."""

from __future__ import annotations

import hashlib
from typing import Any

from ai_novelist.corpus.craft_schema import CraftContext, StageCraftBrief


def build_stage_craft_brief(
    context: CraftContext,
    pacing_target: dict[str, Any] | None,
    max_chars: int,
    project_id: str = "",
    craft_mode: str = "assist",
) -> StageCraftBrief:
    target = pacing_target or {}
    lines = [
        "# 作者构思参考",
        "",
        "## 使用规则",
        "- 只学习构思方法，不复刻原文。",
        "- 只学习结构策略，不模仿具体作者表达。",
        "- 当前项目的锁定约束、小说圣经、Pacing Target 优先级更高。",
        "- 如果参考方法与本章节奏目标冲突，必须放弃该参考方法。",
        "",
        "## 当前阶段",
        f"- purpose: {context.purpose}",
        f"- chapter: {context.chapter if context.chapter is not None else 'none'}",
        f"- stage: {context.stage or 'none'}",
        f"- craft_mode: {craft_mode}",
        "",
        "## 与 Pacing Target 的对齐",
        f"- 本章功能：{target.get('function', 'unknown')}",
        f"- 目标强度：{target.get('intensity', 3)}",
        f"- 钩子强度：{target.get('hook_strength', 'medium')}",
        f"- 冲突模式：{target.get('conflict_mode', target.get('tension_source', 'mixed'))}",
        f"- 本次可用方法：{allowed_methods(context, target)}",
        f"- 本次禁止方法：{forbidden_methods(target)}",
        "",
        "## 可采用的真实作者构思方法",
    ]
    if not context.selected_notes:
        lines.append("- 暂无可用作者构思参考。")
    for index, note in enumerate(context.selected_notes, start=1):
        lines.extend(
            [
                f"{index}. 方法名：{note.title}",
                f"   - 方法：{note.pattern}",
                f"   - 为什么有效：{note.why_it_works}",
                f"   - 适用条件：{'；'.join(note.use_when) or '当前阶段需要类似构思策略时'}",
                f"   - 当前项目可如何转化：把该结构方法转写为本项目人物、设定和章节目标，不搬运原作内容。",
                f"   - 避免事项：{'；'.join(note.avoid_when) or '不要复刻原文或模仿作者表达'}",
            ]
        )
    lines.extend(["", "## 本阶段应用建议"])
    lines.extend(stage_suggestions(context, target))
    lines.extend(["", "## 不应采纳的方向"])
    lines.extend(stage_rejections(target))
    lines.extend(["", "## 来源摘要"])
    for evidence in context.sources[:10]:
        lines.append(
            f"- {evidence.work_id} / {evidence.source_id} / {evidence.location_label or evidence.chapter_id} / {evidence.summary}"
        )
    content = "\n".join(lines).rstrip() + "\n"
    if max_chars > 0 and len(content) > max_chars:
        content = trim_brief(content, max_chars)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return StageCraftBrief(
        project_id=project_id,
        purpose=context.purpose,
        chapter=context.chapter,
        stage=context.stage,
        content=content,
        source_profile_ids=context.source_profile_ids,
        source_note_ids=[note.note_id for note in context.selected_notes],
        source_evidence=context.sources,
        digest=digest,
        metadata={"craft_mode": craft_mode, "query_terms": context.query_terms[:20]},
    )


def allowed_methods(context: CraftContext, target: dict[str, Any]) -> str:
    facets = [note.facet for note in context.selected_notes[:5]]
    if not facets:
        facets = ["pacing", "information_release"]
    return "、".join(dict.fromkeys(facets))


def forbidden_methods(target: dict[str, Any]) -> str:
    intensity = int(target.get("intensity", 3) or 3)
    function = str(target.get("function", "unknown"))
    if intensity <= 2 or function in {"aftermath", "breather", "setup"}:
        return "强反转、重大真相揭示、硬 cliffhanger、无依据升级冲突"
    return "搬运原作设定、复刻原文段落、为了钩子破坏 Pacing Target"


def stage_suggestions(context: CraftContext, target: dict[str, Any]) -> list[str]:
    suggestions = [
        "- 先把参考方法翻译成当前项目自己的行动目标、阻碍和信息释放。",
        "- 每次只采纳与当前 purpose 直接相关的 1-3 个方法。",
        "- 低强度章节优先采用克制、氛围、关系微变和软信息释放。",
    ]
    if int(target.get("intensity", 3) or 3) >= 4:
        suggestions.append("- 高强度章节可以使用转折和对抗，但仍要保留已锁定设定边界。")
    if context.purpose == "review":
        suggestions.append("- 审稿时检查输出是否为了贴近参考方法而破坏原创性或节奏目标。")
    if context.purpose == "revision":
        suggestions.append("- 修订时只执行能降低复刻风险、强化原创表达的参考方法。")
    return suggestions[:6]


def stage_rejections(target: dict[str, Any]) -> list[str]:
    items = [
        "- 不搬运原作品人物、设定、情节或专有名词。",
        "- 不模仿某个具体作者的独特表达。",
        "- 不用参考方法覆盖用户要求、锁定约束、小说圣经或 Pacing Target。",
    ]
    if int(target.get("intensity", 3) or 3) <= 2:
        items.append("- 当前低强度目标下，不采用硬钩子、爆点式反转或额外外部冲突。")
    return items


def trim_brief(content: str, max_chars: int) -> str:
    if len(content) <= max_chars:
        return content
    priority_markers = ("# 作者构思参考", "## 使用规则", "## 与 Pacing Target 的对齐", "## 本阶段应用建议", "## 不应采纳的方向")
    sections = content.split("\n## ")
    kept = []
    for index, section in enumerate(sections):
        text = section if index == 0 else "## " + section
        if any(marker in text for marker in priority_markers) or len("".join(kept)) + len(text) < max_chars:
            kept.append(text)
    trimmed = "\n".join(kept)
    if len(trimmed) > max_chars:
        trimmed = trimmed[: max(1, max_chars - 20)].rstrip() + "\n[已截断]\n"
    return trimmed
