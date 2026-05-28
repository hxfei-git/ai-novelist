"""Structure repair helpers for outline graph stage outputs."""

from __future__ import annotations

import re

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.agent_metrics import complete_with_metrics
from ai_novelist.outline.chapter_outline_structure import (
    append_missing_chapter_outline_volume_sections,
    build_chapter_outline_target_context,
    chapter_outline_metadata_from_artifact,
    merge_chapter_outline_volumes,
    normalize_generated_volume_outline,
    validate_chapter_outline_volume,
)
from ai_novelist.outline.renderers import render_direction_stage_markdown
from ai_novelist.outline.stage_guard import guard_stage_output
from ai_novelist.outline_graph.artifact_io import current_stage_context, previous_stage_context, stage_full_text
from ai_novelist.outline_graph.prompts import chapter_outline_framework_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def ensure_worldbuilding_outline_structure(
    synthesis: str,
    state: NovelState,
    adapter: AgentAdapter,
    store: LocalStore,
    author_craft: str = "",
) -> str:
    from ai_novelist.worldbuilding_framework import (
        append_missing_worldbuilding_sections,
        render_worldbuilding_framework,
        validate_worldbuilding_outline,
    )

    ok, missing = validate_worldbuilding_outline(synthesis, mode="full")
    if ok:
        return synthesis

    repair_prompt = (
        "AGENT: worldbuilding_structure_repair\n"
        "你要修复世界观阶段输出结构。不要分析，不要解释，只输出完整 Markdown。\n"
        f"缺失或顺序异常标题：{missing}\n\n"
        "必须使用完整 33 项世界大纲标题，且继承原文内容。\n"
        "不要按题材分类，不得只输出世界运行原则/关键边界/冲突资源/代价红线四段摘要。\n"
        "每个小节写 2-5 条当前小说的具体 bullet；信息不足时给出合理默认建议。\n\n"
        f"框架：\n{render_worldbuilding_framework(mode='full')}\n\n"
        f"作者构思参考：\n{author_craft or '暂无'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, 'worldbuilding')}\n\n"
        f"原始世界观草稿：\n{synthesis}\n"
    )
    try:
        repaired = complete_with_metrics(
            adapter=adapter,
            prompt=repair_prompt,
            project_dir=store.project_dir(state.project_id),
            project_id=state.project_id,
            graph="outline",
            node="worldbuilding_structure_repair",
            agent="worldbuilding_structure_repair",
            prompt_profile="outline_worldbuilding_repair",
        )
    except AgentAdapterError:
        repaired = synthesis

    ok, missing = validate_worldbuilding_outline(repaired, mode="full")
    if ok:
        return repaired
    return append_missing_worldbuilding_sections(repaired, missing)


def ensure_characters_outline_structure(
    synthesis: str,
    state: NovelState,
    adapter: AgentAdapter,
    store: LocalStore,
    author_craft: str = "",
) -> str:
    from ai_novelist.characters_framework import (
        append_missing_characters_sections,
        render_characters_framework,
        validate_characters_outline,
    )

    ok, missing = validate_characters_outline(synthesis, mode="full")
    if ok:
        return synthesis

    repair_prompt = (
        "AGENT: characters_structure_repair\n"
        "你要修复人物关系阶段输出结构。不要分析，不要解释，只输出完整 Markdown。\n"
        f"缺失或顺序异常标题：{missing}\n\n"
        "必须使用完整人物关系蓝图标题，且继承原文内容。\n"
        "不要写成人物小传、静态人设表、章节正文、故事流程或场景卡。\n"
        "阵营 / 组织关系只能从前序世界观中提取；没有相关设定时写“暂无，不强行生成”。\n"
        "每个小节写 2-6 条当前小说的具体 bullet；信息不足时写待确认或合理默认建议。\n\n"
        f"框架：\n{render_characters_framework(mode='full')}\n\n"
        f"作者构思参考：\n{author_craft or '暂无'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, 'characters')}\n\n"
        f"原始人物关系草稿：\n{synthesis}\n"
    )
    try:
        repaired = complete_with_metrics(
            adapter=adapter,
            prompt=repair_prompt,
            project_dir=store.project_dir(state.project_id),
            project_id=state.project_id,
            graph="outline",
            node="characters_structure_repair",
            agent="characters_structure_repair",
            prompt_profile="outline_characters_repair",
        )
    except AgentAdapterError:
        repaired = synthesis

    ok, missing = validate_characters_outline(repaired, mode="full")
    if ok:
        return repaired
    return append_missing_characters_sections(repaired, missing)


def ensure_story_flow_outline_structure(
    synthesis: str,
    state: NovelState,
    adapter: AgentAdapter,
    store: LocalStore,
    author_craft: str = "",
    role_reviews: list[dict[str, str]] | None = None,
) -> str:
    from ai_novelist.outline.story_flow_structure import (
        STORY_FLOW_REQUIRED_HEADINGS,
        append_missing_story_flow_sections,
        empty_story_flow_sections,
        validate_story_flow_outline,
    )
    from ai_novelist.story_flow_framework import render_story_flow_framework

    ok, issues = validate_story_flow_outline(synthesis)
    if ok:
        return synthesis

    empty = empty_story_flow_sections(synthesis)
    role_outputs = "\n\n".join(
        f"## {item.get('role', '角色短评')}\n{item.get('content', '')}" for item in (role_reviews or [])
    )
    headings = "\n".join(f"- {heading}" for heading in STORY_FLOW_REQUIRED_HEADINGS)
    repair_prompt = (
        "AGENT: story_flow_structure_repair\n"
        "你正在修复 story_flow 阶段输出。当前输出结构不完整。不要分析，不要解释，只输出完整 Markdown。\n"
        f"缺失、过短或异常项：{issues}\n"
        f"空内容模块：{empty}\n\n"
        "请在不写章节正文、不替代分卷大纲的前提下，重写为完整故事流程稿。\n"
        "必须以 `## 故事流程稿` 开始，并包含以下 14 个标题：\n"
        f"{headings}\n\n"
        "必须承接 direction、worldbuilding、characters 的已锁定内容。未锁定信息只能写为“候选方向”或“待确认”。\n"
        "保留当前草稿和角色短评中有价值的剧情方向。每个模块写具体、可执行的内容。\n\n"
        f"框架：\n{render_story_flow_framework(mode='full')}\n\n"
        f"作者构思参考：\n{author_craft or '暂无'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, 'story_flow')}\n\n"
        f"角色短评：\n{role_outputs or '暂无'}\n\n"
        f"原始故事流程草稿：\n{synthesis}\n"
    )
    try:
        repaired = complete_with_metrics(
            adapter=adapter,
            prompt=repair_prompt,
            project_dir=store.project_dir(state.project_id),
            project_id=state.project_id,
            graph="outline",
            node="story_flow_structure_repair",
            agent="story_flow_structure_repair",
            prompt_profile="outline_story_flow_repair",
        )
    except AgentAdapterError:
        repaired = synthesis

    ok, issues = validate_story_flow_outline(repaired)
    if ok:
        return repaired
    return append_missing_story_flow_sections(repaired, issues)


def ensure_volume_outline_structure(
    synthesis: str,
    state: NovelState,
    adapter: AgentAdapter,
    store: LocalStore,
    author_craft: str = "",
    role_reviews: list[dict[str, str]] | None = None,
) -> str:
    from ai_novelist.outline.volume_outline_structure import (
        append_missing_volume_outline_sections,
        missing_volume_outline_headings,
        validate_volume_outline,
    )
    from ai_novelist.volume_outline_framework import render_volume_outline_framework

    ok, issues = validate_volume_outline(synthesis)
    if ok:
        return synthesis

    role_outputs = "\n\n".join(
        f"## {item.get('role', '角色短评')}\n{item.get('content', '')}" for item in (role_reviews or [])
    )
    missing = missing_volume_outline_headings(synthesis)
    repair_prompt = (
        "AGENT: volume_outline_structure_repair\n"
        "你正在修复 volume_outline 阶段输出。当前输出结构不完整。不要分析，不要解释，只输出完整 Markdown。\n"
        f"缺失或异常标题：{issues}\n"
        f"缺失的核心模块：{missing}\n\n"
        "请在不写逐章细纲、不替代章节大纲、不写正文场景的前提下，重写为完整分卷大纲稿。\n"
        "必须以 `## 分卷大纲稿` 开始，并包含 14 个核心模块。\n"
        "必须保留原文中已有的有效内容，并把旧结构归入对应模块。未锁定内容只能写为候选方向或待确认。\n\n"
        f"框架：\n{render_volume_outline_framework(mode='full')}\n\n"
        f"作者构思参考：\n{author_craft or '暂无'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, 'volume_outline')}\n\n"
        f"当前阶段已有内容：\n{current_stage_context(state, 'volume_outline')}\n\n"
        f"角色短评：\n{role_outputs or '暂无'}\n\n"
        f"原始分卷草稿：\n{synthesis}\n"
    )
    try:
        repaired = complete_with_metrics(
            adapter=adapter,
            prompt=repair_prompt,
            project_dir=store.project_dir(state.project_id),
            project_id=state.project_id,
            graph="outline",
            node="volume_outline_structure_repair",
            agent="volume_outline_structure_repair",
            prompt_profile="outline_volume_outline_repair",
        )
    except AgentAdapterError:
        repaired = synthesis

    ok, issues = validate_volume_outline(repaired)
    if ok:
        return repaired
    return append_missing_volume_outline_sections(repaired, issues)


def ensure_chapter_outline_structure(
    synthesis: str,
    state: NovelState,
    adapter: AgentAdapter,
    store: LocalStore,
    author_craft: str = "",
    role_reviews: list[dict[str, str]] | None = None,
) -> tuple[str, dict]:
    volume_outline_text = stage_full_text(state, store, "volume_outline")
    artifact = state.outline_stage_artifacts.get("chapter_outline")
    metadata = chapter_outline_metadata_from_artifact(artifact if isinstance(artifact, dict) else None, volume_outline_text)
    current_key = str(metadata.get("current_volume_index") or 1)
    volume_text = normalize_generated_volume_outline(synthesis, metadata)
    ok, issues = validate_chapter_outline_volume(volume_text, metadata)
    if not ok:
        role_outputs = "\n\n".join(
            f"## {item.get('role', '角色短评')}\n{item.get('content', '')}" for item in (role_reviews or [])
        )
        repair_prompt = (
            "AGENT: chapter_outline_structure_repair\n"
            "你正在修复 chapter_outline 阶段当前目标卷输出。不要分析，不要解释，只输出完整 Markdown。\n"
            f"结构问题：{issues}\n\n"
            "必须只修复当前目标卷，不重写已确认卷；必须包含卷内章节总体规划、章节列表总表、每章 profile、PacingTarget、稳定结构模块状态和连续性字段。\n"
            "不要机械填满能力池 26 项；按 profile 决定详写、简写或本章不适用。不要写场景卡、正文或对白。\n\n"
            f"目标卷上下文：\n{build_chapter_outline_target_context(metadata)}\n\n"
            f"章节大纲框架：\n{chapter_outline_framework_prompt('chapter_outline', state)}\n\n"
            f"作者构思参考：\n{author_craft or '暂无'}\n\n"
            f"前序已保存阶段内容：\n{previous_stage_context(state, 'chapter_outline')}\n\n"
            f"角色短评：\n{role_outputs or '暂无'}\n\n"
            f"原始当前卷章纲：\n{volume_text}\n"
        )
        try:
            repaired = complete_with_metrics(
                adapter=adapter,
                prompt=repair_prompt,
                project_dir=store.project_dir(state.project_id),
                project_id=state.project_id,
                graph="outline",
                node="chapter_outline_structure_repair",
                agent="chapter_outline_structure_repair",
                prompt_profile="outline_chapter_outline_repair",
            )
            volume_text = normalize_generated_volume_outline(repaired, metadata)
        except AgentAdapterError:
            pass

    ok, issues = validate_chapter_outline_volume(volume_text, metadata)
    if not ok:
        volume_text = append_missing_chapter_outline_volume_sections(volume_text, metadata, issues)

    contents = metadata.get("volume_contents") if isinstance(metadata.get("volume_contents"), dict) else {}
    contents[current_key] = volume_text.strip()
    metadata["volume_contents"] = contents
    statuses = metadata.get("volume_statuses") if isinstance(metadata.get("volume_statuses"), dict) else {}
    statuses[current_key] = "options_ready"
    metadata["volume_statuses"] = statuses
    return merge_chapter_outline_volumes(metadata), metadata


def chapter_outline_has_next_volume(metadata: dict) -> bool:
    current = int(metadata.get("current_volume_index") or 1)
    total = int(metadata.get("total_volumes") or 1)
    return current < total


def confirm_current_chapter_outline_volume(artifact: dict, state: NovelState, store: LocalStore) -> tuple[dict, int | None]:
    volume_outline_text = stage_full_text(state, store, "volume_outline")
    metadata = chapter_outline_metadata_from_artifact(artifact, volume_outline_text)
    current = int(metadata.get("current_volume_index") or 1)
    total = int(metadata.get("total_volumes") or 1)
    completed = sorted({int(item) for item in metadata.get("completed_volumes", []) if str(item).isdigit()} | {current})
    metadata["completed_volumes"] = [item for item in completed if 1 <= item <= total]
    statuses = metadata.get("volume_statuses") if isinstance(metadata.get("volume_statuses"), dict) else {}
    statuses[str(current)] = "locked"
    metadata["current_volume_index"] = current
    metadata["volume_statuses"] = statuses
    artifact = dict(artifact)
    artifact["metadata"] = metadata
    return artifact, None


def replace_pending_questions_section(markdown: str, pending_questions: list[str] | None = None) -> str:
    if pending_questions is None:
        return markdown

    questions = [str(item).strip() for item in pending_questions if str(item).strip()]
    replacement = ["## 仍需确认的问题"]
    if questions:
        replacement.extend(f"- {question}" for question in questions)
    else:
        replacement.append("- 暂无，当前阶段可继续修改或确认进入下一阶段。")

    lines = markdown.splitlines()
    section_start = None
    section_level = 2
    for index, raw_line in enumerate(lines):
        match = re.match(r"^(#{2,6})\s*(仍需确认的问题|待确认问题|待确认的问题)\s*$", raw_line.strip())
        if match:
            section_start = index
            section_level = len(match.group(1))
            break

    if section_start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(replacement)
        return "\n".join(lines).rstrip() + "\n"

    section_end = len(lines)
    for index in range(section_start + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[index].strip())
        if match and len(match.group(1)) <= section_level:
            section_end = index
            break

    prefix = lines[:section_start]
    suffix = lines[section_end:]
    while prefix and not prefix[-1].strip():
        prefix.pop()
    while suffix and not suffix[0].strip():
        suffix.pop(0)

    result = prefix[:]
    if result:
        result.append("")
    result.extend(replacement)
    if suffix:
        result.append("")
        result.extend(suffix)
    return "\n".join(result).rstrip() + "\n"


DIRECTION_FORBIDDEN_REPLACEMENTS = {
    "项目审批": "关键选择必须服务核心冲突",
    "申请表": "关系把柄",
    "审批": "关键选择必须服务核心冲突",
    "考评": "关系压力必须服务主线推进",
    "备案": "关系登记或把柄压力",
    "绩效": "权力评价压力",
    "制度条款": "抽象规则边界",
    "规则清单": "原则边界",
    "KPI": "外部压力",
    "宗门流程": "主角优先利用既有规则求生，具体规则留到世界观阶段展开",
    "组织流程": "主角优先利用既有规则求生，具体规则留到世界观阶段展开",
    "流程": "推进原则",
}


def sanitize_direction_stage_output(markdown: str, user_text: str = "") -> str:
    state = NovelState(project_id="sanitize", title="sanitize", idea=user_text, user_request=user_text)
    result = guard_stage_output(markdown or "", "direction", state)
    text = result.text.strip()
    if not text:
        return render_direction_stage_markdown("")

    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^#{1,6}\s*方向定位\s*$", line):
            continue
        if re.match(r"^#{1,6}\s*方向控制稿\s*$", line):
            continue
        if line == "## 方向定位稿":
            continue
        for forbidden, replacement in DIRECTION_FORBIDDEN_REPLACEMENTS.items():
            if forbidden in user_text:
                continue
            line = line.replace(forbidden, replacement)
        cleaned_lines.append(line)

    return render_direction_stage_markdown("\n".join(cleaned_lines))
