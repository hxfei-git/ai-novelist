"""Structural helpers for the story_flow outline stage."""

from __future__ import annotations

import re

from ai_novelist.story_flow_framework import story_flow_required_headings


STORY_FLOW_REQUIRED_HEADINGS: tuple[str, ...] = story_flow_required_headings()
STORY_FLOW_TITLE = "故事流程稿"

_HEADING_ALIASES: dict[str, tuple[str, ...]] = {
    "故事主线推进": ("故事主线", "主线推进", "主线因果链", "主线因果推进"),
    "故事阶段划分": ("阶段划分", "故事阶段", "全书阶段划分"),
    "核心冲突升级路径": ("冲突升级", "冲突升级路径", "核心冲突升级", "冲突递进路径"),
    "关键剧情节点": ("剧情节点", "关键节点", "全书关键节点"),
    "人物弧光嵌入流程": ("人物弧光", "人物弧光嵌入", "人物成长嵌入流程", "关系变化流程"),
    "伏笔、悬念与揭示节奏": ("伏笔悬念与揭示节奏", "伏笔与悬念", "伏笔悬念", "揭示节奏", "伏笔布置与回收方向"),
    "爽点 / 卖点兑现节奏": ("爽点/卖点兑现节奏", "爽点与卖点兑现节奏", "爽点兑现", "卖点兑现节奏", "爽点卖点兑现节奏"),
    "情绪节奏与阅读体验": ("情绪节奏", "阅读体验", "情绪曲线"),
    "世界观展开顺序": ("世界观展开", "设定展开顺序", "世界设定展开顺序"),
    "阵营与势力推进": ("阵营推进", "势力推进", "阵营势力推进"),
    "代价与失败机制": ("失败代价", "代价机制", "失败机制", "代价失败机制"),
    "反转与认知升级": ("反转认知", "认知升级", "反转层级", "反转与升级"),
    "分卷衔接方向": ("分卷衔接", "卷级衔接方向", "分卷骨架", "卷间衔接方向"),
    "结局路径": ("终局路径", "结局方向", "终局方向"),
}


def normalize_heading(text: str) -> str:
    """Normalize headings so common model variants map to a stable key."""
    value = re.sub(r"^#+\s*", "", str(text or "").strip())
    value = re.sub(r"[`*_~\s/／、,，.。:：;；()（）\[\]【】{}《》<>]+", "", value)
    canonical = _NORMALIZED_LOOKUP.get(value.lower())
    return canonical.lower() if canonical else value.lower()


_NORMALIZED_LOOKUP: dict[str, str] = {}
for _heading in STORY_FLOW_REQUIRED_HEADINGS:
    _NORMALIZED_LOOKUP[normalize_heading(_heading)] = _heading
    for _alias in _HEADING_ALIASES.get(_heading, ()):
        _NORMALIZED_LOOKUP[normalize_heading(_alias)] = _heading


def canonical_story_flow_heading(text: str) -> str | None:
    return _NORMALIZED_LOOKUP.get(normalize_heading(text))


def extract_markdown_sections(text: str) -> dict[str, str]:
    """Extract story_flow sections keyed by canonical required heading."""
    matches: list[tuple[str, int, int]] = []
    for match in re.finditer(r"^\s*#{1,6}\s+(.+?)\s*$", text or "", re.MULTILINE):
        heading_text = match.group(1).strip()
        canonical = canonical_story_flow_heading(heading_text)
        if canonical:
            matches.append((canonical, match.start(), match.end()))
    matches.sort(key=lambda item: item[1])

    sections: dict[str, str] = {}
    for index, (heading, _start, end) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(text or "")
        sections.setdefault(heading, (text or "")[end:next_start].strip())
    return sections


def missing_story_flow_headings(text: str) -> list[str]:
    sections = extract_markdown_sections(text)
    return [heading for heading in STORY_FLOW_REQUIRED_HEADINGS if heading not in sections]


def has_nonempty_story_flow_section(text: str, heading: str) -> bool:
    section = extract_markdown_sections(text).get(heading, "")
    lines = [
        _clean_content_line(line)
        for line in section.splitlines()
        if _clean_content_line(line)
    ]
    return any(not _is_placeholder(line) for line in lines)


def empty_story_flow_sections(text: str) -> list[str]:
    return [heading for heading in STORY_FLOW_REQUIRED_HEADINGS if not has_nonempty_story_flow_section(text, heading)]


def validate_story_flow_outline(text: str, min_chars: int = 500) -> tuple[bool, list[str]]:
    """Return (ok, issues). Issues contain missing or empty section headings."""
    content = str(text or "").strip()
    issues = missing_story_flow_headings(content)
    issues.extend(heading for heading in empty_story_flow_sections(content) if heading not in issues)
    if STORY_FLOW_TITLE not in content:
        issues.insert(0, STORY_FLOW_TITLE)
    if _cjk_len(content) < min_chars:
        issues.append("内容过短")
    if _contains_chapter_list(content):
        issues.append("疑似逐章列表")
    return not issues, issues


def append_missing_story_flow_sections(text: str, missing: list[str] | None = None) -> str:
    """Last-resort deterministic repair for structurally incomplete story_flow output."""
    content = str(text or "").strip()
    sections = extract_markdown_sections(content)
    missing_set = set(missing or [])
    lines: list[str] = ["## 故事流程稿", ""]
    if content and not sections:
        lines.append("- 原始草稿摘录：以下内容来自结构修复前输出，需要再归入对应故事流程模块。")
        for raw_line in content.splitlines()[:18]:
            line = raw_line.strip()
            if line and not line.startswith("#"):
                lines.append(f"  {line}")
        lines.append("")

    for heading in STORY_FLOW_REQUIRED_HEADINGS:
        lines.append(f"### {heading}")
        body = sections.get(heading, "").strip()
        if body and heading not in missing_set and has_nonempty_story_flow_section(content, heading):
            lines.extend(body.splitlines())
        else:
            lines.extend(_fallback_lines_for_heading(heading))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def split_story_flow_sections(text: str) -> dict[str, str]:
    return extract_markdown_sections(text)


def story_flow_bullets(section_text: str) -> list[str]:
    bullets: list[str] = []
    for raw_line in section_text.splitlines():
        line = _clean_content_line(raw_line)
        if not line or line.startswith("#") or "仍需确认" in line:
            continue
        if _is_placeholder(line):
            continue
        bullets.append(line)
    return bullets


def first_story_flow_bullet(section_text: str) -> str:
    bullets = story_flow_bullets(section_text)
    return bullets[0] if bullets else ""


def summarize_story_flow_outline(text: str, max_chars: int = 1800) -> str:
    sections = split_story_flow_sections(text)
    priority = [
        "故事主线推进",
        "故事阶段划分",
        "核心冲突升级路径",
        "关键剧情节点",
        "人物弧光嵌入流程",
        "伏笔、悬念与揭示节奏",
        "分卷衔接方向",
        "结局路径",
    ]
    lines = []
    for heading in priority:
        bullet = first_story_flow_bullet(sections.get(heading, ""))
        if bullet:
            lines.append(f"{heading}：{bullet}")
    if not lines:
        return _summarize_text(text, max_chars=420)
    summary = "；".join(lines)
    return summary[:max_chars].rstrip() + ("..." if len(summary) > max_chars else "")


def extract_story_flow_memory(text: str, max_items: int = 18, max_chars: int = 1800) -> list[str]:
    sections = split_story_flow_sections(text)
    priority = [
        "故事主线推进",
        "故事阶段划分",
        "核心冲突升级路径",
        "关键剧情节点",
        "人物弧光嵌入流程",
        "伏笔、悬念与揭示节奏",
        "爽点 / 卖点兑现节奏",
        "世界观展开顺序",
        "阵营与势力推进",
        "代价与失败机制",
        "反转与认知升级",
        "分卷衔接方向",
        "结局路径",
    ]
    result: list[str] = []
    total = 0
    for heading in priority:
        for bullet in story_flow_bullets(sections.get(heading, ""))[:2]:
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
    fallback = _summarize_text(text, max_chars=max_chars)
    return [fallback] if fallback else []


def _clean_content_line(line: str) -> str:
    value = str(line or "").strip()
    value = re.sub(r"^[-*+•\s]*", "", value)
    value = re.sub(r"^\d+[.、)]\s*", "", value)
    return value.strip()


def _is_placeholder(line: str) -> bool:
    value = str(line or "").strip()
    return (
        not value
        or value in {"...", "暂无", "暂无。", "待确认", "待确认。"}
        or value.startswith("待补充：结构兜底占位")
    )


def _fallback_lines_for_heading(heading: str) -> list[str]:
    common = "- 待补充：结构兜底占位。本节需要结合已锁定方向、世界观和人物关系补写具体流程内容。"
    if heading == "故事主线推进":
        return [
            common,
            "- 候选方向：先以主角初始处境、引发事件、阶段性目标升级和终局目标形成因果链；未锁定信息标为待确认。",
        ]
    if heading == "故事阶段划分":
        return [
            common,
            "- 候选方向：按开局、成长、扩张、转折、高潮、结局六个阶段组织，不拆成逐章列表。",
        ]
    if heading == "核心冲突升级路径":
        return [
            common,
            "- 候选方向：冲突从个人困境升级到组织阵营、制度规则和终极价值矛盾，并标注胜利代价与失败损失。",
        ]
    if heading == "人物弧光嵌入流程":
        return [
            common,
            "- 候选方向：主角缺陷、关系变化、关键人物影响和反派镜像应由剧情节点推动，具体关系以 characters 阶段为准。",
        ]
    if heading == "分卷衔接方向":
        return [
            common,
            "- 候选方向：只提供卷级功能、核心问题、阶段高潮和卷尾钩子，不替代后续分卷大纲。",
        ]
    if heading == "结局路径":
        return [
            common,
            "- 候选方向：提前约束主线、人物、关系、世界和主题落点；未锁定终局只写为候选。",
        ]
    return [common, "- 候选方向：信息不足时保留待确认，不硬造已锁定正典。"]


def _cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def _contains_chapter_list(text: str) -> bool:
    matches = re.findall(r"第\s*\d+\s*章", text or "")
    return len(matches) >= 3


def _summarize_text(text: str, max_chars: int = 420) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return ""
    return cleaned[:max_chars].rstrip() + ("..." if len(cleaned) > max_chars else "")
