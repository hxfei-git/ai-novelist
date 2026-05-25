"""Structural helpers for the volume_outline outline stage."""

from __future__ import annotations

import re

from ai_novelist.volume_outline_framework import volume_outline_required_headings


VOLUME_OUTLINE_REQUIRED_HEADINGS: tuple[str, ...] = volume_outline_required_headings()
VOLUME_OUTLINE_OPTIONAL_HEADINGS: tuple[str, ...] = (
    "仍需确认的问题",
    "卷级约束与待确认项（可选）",
)
VOLUME_OUTLINE_TITLE = "分卷大纲稿"

_HEADING_ALIASES: dict[str, tuple[str, ...]] = {
    "分卷总体规划": ("分卷结构", "分卷规划", "分卷总规划", "总体规划"),
    "单卷基础定位": ("单卷定位", "卷定位", "卷基础定位", "基础定位"),
    "本卷一句话概括": ("本卷一句话", "一句话概括", "卷一句话概括", "本卷概括"),
    "本卷阶段目标": ("本卷目标", "卷目标", "阶段目标"),
    "本卷核心冲突": ("卷内主要矛盾", "本卷主要矛盾", "核心矛盾", "主要冲突"),
    "本卷剧情推进": ("卷内推进", "卷内剧情", "剧情推进", "推进过程"),
    "本卷关键节点": ("卷级高潮", "关键节点", "高潮事件", "骨架节点"),
    "本卷人物推进": ("人物推进", "人物变化", "角色推进"),
    "本卷世界观释放": ("世界观释放", "世界观展开", "世界信息释放"),
    "本卷爽点与卖点兑现": ("爽点与卖点兑现", "爽点卖点", "爽点兑现", "卖点兑现", "高光兑现"),
    "本卷伏笔、悬念与信息差": ("伏笔悬念", "伏笔与悬念", "悬念与信息差", "信息差", "伏笔信息差"),
    "本卷情绪节奏": ("情绪节奏", "情绪曲线", "阅读体验"),
    "本卷开头与结尾": ("开头与结尾", "开卷与结尾", "开头结尾"),
    "与前后卷的衔接": ("前后卷衔接", "卷间钩子", "衔接方向", "卷间连接"),
    "仍需确认的问题": ("待确认问题", "待确认的问题", "待确认项", "仍需确认问题"),
    "卷级约束与待确认项（可选）": (
        "卷级约束",
        "卷级约束与待确认项",
        "锁定项、可变项、待确认项",
        "锁定项可变项待确认项",
        "约束与待确认项",
        "轻量约束备注",
    ),
}


def normalize_heading(text: str) -> str:
    value = re.sub(r"^#+\s*", "", str(text or "").strip())
    value = re.sub(r"[`*_~\s/／、,，.。:：;；()（）\[\]【】{}《》<>]+", "", value)
    return value.lower()


_NORMALIZED_LOOKUP: dict[str, str] = {}
for _heading in [*VOLUME_OUTLINE_REQUIRED_HEADINGS, *VOLUME_OUTLINE_OPTIONAL_HEADINGS]:
    _NORMALIZED_LOOKUP[normalize_heading(_heading)] = _heading
    for _alias in _HEADING_ALIASES.get(_heading, ()):  # type: ignore[arg-type]
        _NORMALIZED_LOOKUP[normalize_heading(_alias)] = _heading


def canonical_volume_outline_heading(text: str) -> str | None:
    return _NORMALIZED_LOOKUP.get(normalize_heading(text))


def extract_markdown_sections(text: str) -> dict[str, str]:
    matches: list[tuple[str, int, int]] = []
    for match in re.finditer(r"^\s*#{1,6}\s+(.+?)\s*$", text or "", re.MULTILINE):
        heading_text = match.group(1).strip()
        canonical = canonical_volume_outline_heading(heading_text)
        if canonical:
            matches.append((canonical, match.start(), match.end()))
    matches.sort(key=lambda item: item[1])

    sections: dict[str, str] = {}
    for index, (heading, _start, end) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(text or "")
        sections.setdefault(heading, (text or "")[end:next_start].strip())
    return sections


def missing_volume_outline_headings(text: str) -> list[str]:
    sections = extract_markdown_sections(text)
    return [heading for heading in VOLUME_OUTLINE_REQUIRED_HEADINGS if heading not in sections]


def has_nonempty_volume_outline_section(text: str, heading: str) -> bool:
    section = extract_markdown_sections(text).get(heading, "")
    lines = [_clean_content_line(line) for line in section.splitlines() if _clean_content_line(line)]
    return any(not _is_placeholder(line) for line in lines)


def empty_volume_outline_sections(text: str) -> list[str]:
    return [heading for heading in VOLUME_OUTLINE_REQUIRED_HEADINGS if not has_nonempty_volume_outline_section(text, heading)]


def validate_volume_outline(text: str, min_chars: int = 900) -> tuple[bool, list[str]]:
    content = str(text or "").strip()
    issues = missing_volume_outline_headings(content)
    issues.extend(heading for heading in empty_volume_outline_sections(content) if heading not in issues)
    if not _has_title(content):
        issues.insert(0, VOLUME_OUTLINE_TITLE)
    if _cjk_len(content) < min_chars:
        issues.append("内容过短")
    if _contains_chapter_list(content):
        issues.append("疑似逐章列表")
    return not issues, issues


def append_missing_volume_outline_sections(text: str, missing: list[str] | None = None) -> str:
    content = str(text or "").strip()
    sections = extract_markdown_sections(content)
    missing_set = set(missing or [])
    lines: list[str] = [f"## {VOLUME_OUTLINE_TITLE}", ""]
    if content and not sections:
        lines.append("- 原始草稿摘录：以下内容来自结构修复前输出，需要再归入对应分卷模块。")
        for raw_line in content.splitlines()[:24]:
            line = raw_line.strip()
            if line and not line.startswith("#"):
                lines.append(f"  {line}")
        lines.append("")

    for heading in VOLUME_OUTLINE_REQUIRED_HEADINGS:
        lines.append(f"### {heading}")
        body = sections.get(heading, "").strip()
        if body and heading not in missing_set and has_nonempty_volume_outline_section(content, heading):
            lines.extend(body.splitlines())
        else:
            lines.extend(_fallback_lines_for_heading(heading))
        lines.append("")

    for heading in VOLUME_OUTLINE_OPTIONAL_HEADINGS:
        body = sections.get(heading, "").strip()
        if not body:
            continue
        lines.append(f"### {heading}")
        lines.extend(body.splitlines())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def split_volume_outline_sections(text: str) -> dict[str, str]:
    return extract_markdown_sections(text)


def volume_outline_bullets(section_text: str) -> list[str]:
    bullets: list[str] = []
    for raw_line in section_text.splitlines():
        line = _clean_content_line(raw_line)
        if not line or line.startswith("#") or "仍需确认" in line:
            continue
        if _is_placeholder(line):
            continue
        if _is_table_separator(line):
            continue
        bullets.append(line)
    return bullets


def summarize_volume_outline(text: str, max_chars: int = 2200) -> str:
    sections = split_volume_outline_sections(text)
    priority = [
        "分卷总体规划",
        "单卷基础定位",
        "本卷一句话概括",
        "本卷阶段目标",
        "本卷核心冲突",
        "本卷剧情推进",
        "本卷关键节点",
        "本卷人物推进",
        "本卷世界观释放",
        "本卷爽点与卖点兑现",
        "本卷伏笔、悬念与信息差",
        "本卷情绪节奏",
        "本卷开头与结尾",
        "与前后卷的衔接",
        "卷级约束与待确认项（可选）",
    ]
    lines: list[str] = []
    for heading in priority:
        bullet = _first_useful_outline_line(sections.get(heading, ""))
        if bullet:
            lines.append(f"{heading}：{bullet}")
    if not lines:
        return _summarize_text(text, max_chars=420)
    summary = "；".join(lines)
    return summary[:max_chars].rstrip() + ("..." if len(summary) > max_chars else "")


def extract_volume_outline_memory(text: str, max_items: int = 24, max_chars: int = 2200) -> list[str]:
    sections = split_volume_outline_sections(text)
    priority = [
        "分卷总体规划",
        "单卷基础定位",
        "本卷一句话概括",
        "本卷阶段目标",
        "本卷核心冲突",
        "本卷剧情推进",
        "本卷关键节点",
        "本卷人物推进",
        "本卷世界观释放",
        "本卷爽点与卖点兑现",
        "本卷伏笔、悬念与信息差",
        "本卷情绪节奏",
        "本卷开头与结尾",
        "与前后卷的衔接",
        "仍需确认的问题",
        "卷级约束与待确认项（可选）",
    ]
    result: list[str] = []
    total = 0
    for heading in priority:
        section_lines = volume_outline_bullets(sections.get(heading, ""))[:2]
        for bullet in section_lines:
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


def _is_table_separator(line: str) -> bool:
    if not line.startswith("|"):
        return False
    stripped = re.sub(r"[|\s:-]", "", line)
    return not stripped


def _has_title(text: str) -> bool:
    return bool(re.search(rf"^\s*#{{1,6}}\s*{re.escape(VOLUME_OUTLINE_TITLE)}\s*$", text, re.MULTILINE))


def _contains_chapter_list(text: str) -> bool:
    matches = re.findall(r"第\s*\d+\s*章", text or "")
    return len(matches) >= 3


def _first_useful_outline_line(section_text: str) -> str:
    bullets = volume_outline_bullets(section_text)
    return bullets[0] if bullets else ""


def _summarize_text(text: str, max_chars: int = 420) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    return cleaned[:max_chars].rstrip() + ("..." if len(cleaned) > max_chars else "")


def _fallback_lines_for_heading(heading: str) -> list[str]:
    common = "- 待补充：结构兜底占位。本节需要结合已锁定的方向、世界观、人物关系和故事流程补写具体内容。"
    if heading == "分卷总体规划":
        return [
            common,
            "- 候选方向：先明确卷数、卷名、章节/字数范围和每卷阶段位置，再说明每卷在全书中的叙事功能。",
        ]
    if heading == "单卷基础定位":
        return [
            common,
            "- 候选方向：每卷至少写清卷名、主功能、副功能和阶段位置，不要只留抽象标签。",
        ]
    if heading == "本卷一句话概括":
        return [
            common,
            "- 候选方向：用一句话点出这一卷的处境、看点、问题和阶段性承诺。",
        ]
    if heading == "本卷阶段目标":
        return [
            common,
            "- 候选方向：写清这一卷主角要达成什么、会失去什么，以及卷末局势如何变化。",
        ]
    if heading == "本卷核心冲突":
        return [
            common,
            "- 候选方向：把人物、规则、环境和关系的冲突压到同一卷里，不要只写一句话概括。",
        ]
    if heading == "本卷剧情推进":
        return [
            common,
            "- 候选方向：补齐开卷状态、入卷事件、中段转折、高潮、结尾余波和下卷钩子。",
        ]
    if heading == "本卷关键节点":
        return [
            common,
            "- 候选方向：至少给出开卷事件、受挫、中段反转、重大选择和结尾钩子。",
        ]
    if heading == "本卷人物推进":
        return [
            common,
            "- 候选方向：说明主角、关键配角和反派/对手在这一卷中如何变化。",
        ]
    if heading == "本卷世界观释放":
        return [
            common,
            "- 候选方向：写清这一卷要新增哪些地点、势力、规则或隐藏真相。",
        ]
    if heading == "本卷爽点与卖点兑现":
        return [
            common,
            "- 候选方向：明确这一卷要兑现什么爽点、反转、升级或情绪爆点。",
        ]
    if heading == "本卷伏笔、悬念与信息差":
        return [
            common,
            "- 候选方向：说明这一卷埋下什么、揭开什么、暂时不说什么。",
        ]
    if heading == "本卷情绪节奏":
        return [
            common,
            "- 候选方向：写清开卷、中段、高潮和结尾的情绪变化。",
        ]
    if heading == "本卷开头与结尾":
        return [
            common,
            "- 候选方向：说明第一场戏、开头钩子和卷尾遗留问题。",
        ]
    if heading == "与前后卷的衔接":
        return [
            common,
            "- 候选方向：写清上一卷的后果、这一卷的收束和下一卷的起点。",
        ]
    if heading == "仍需确认的问题":
        return [
            "- 暂无，当前阶段可继续修改或确认进入下一阶段。",
        ]
    if heading == "卷级约束与待确认项（可选）":
        return [
            "- 关键约束：暂定为可调整，不要写成硬锁死设定。",
            "- 待确认：若后续卷数变化，再重整卷级范围和钩子。",
        ]
    return [common, "- 候选方向：信息不足时保留待确认，不硬造已锁定正典。"]


def _cjk_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))
