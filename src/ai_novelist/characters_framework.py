"""Characters outline framework and structural validation."""

from __future__ import annotations

import re
from typing import Any


CHARACTER_OUTLINE_FULL_SECTIONS: list[dict[str, Any]] = [
    {
        "heading": "人物关系稿",
        "required_points": [
            "全文人物池是否已经覆盖主角、核心配角、重要角色、阶段角色和工具角色",
            "是否区分作者侧真相、角色侧认知、读者侧认知和剧情侧演化",
            "哪些关系必须锁定，哪些可以后续调整",
            "哪些秘密和信息差会真正改变关系网络",
            "哪些关系事件可以直接送入 story_flow",
        ],
    },
    {
        "heading": "一、全角色总表",
        "required_points": [
            "角色 ID",
            "姓名 / 称号 / 暂定名",
            "角色层级",
            "叙事职能",
            "首次登场阶段",
            "所属关系范围",
            "关系重要性",
            "角色弧光类型",
            "最终状态",
            "备注",
        ],
    },
    {
        "heading": "二、角色个人驱动力",
        "required_points": [
            "公开身份",
            "真实身份",
            "当前目标",
            "长期目标",
            "深层需求",
            "核心恐惧",
            "错误信念",
            "价值观",
            "道德底线",
            "关键秘密",
            "关系诉求",
            "回避内容",
            "行动方式",
            "可被改变之处",
        ],
    },
    {
        "heading": "三、主角关系弧光",
        "required_points": [
            "开局时主角如何看待自己、他人和世界",
            "主角在关系层面的缺失",
            "主角真正需要建立、理解或修复的关系",
            "谁逼迫主角面对现实",
            "谁诱惑主角走向错误道路",
            "谁让主角学会信任",
            "谁让主角付出代价",
            "谁让主角做最终选择",
            "结局时主角在关系层面完成了什么变化",
        ],
    },
    {
        "heading": "四、核心人物关系卡",
        "required_points": [
            "关系 ID",
            "参与角色",
            "当前表面关系",
            "作者侧真实关系",
            "未来可能变化成的关系",
            "关系重要性",
            "开局状态",
            "双方认知差异",
            "互相需要的原因",
            "冲突来源",
            "关系演化阶段",
            "终局关系",
            "剧情用途",
            "锁定级别",
        ],
    },
    {
        "heading": "五、关系演化时间轴",
        "required_points": [
            "起点",
            "前期变化",
            "中期变化",
            "后期变化",
            "终局",
            "触发事件",
            "读者知道什么",
            "角色知道什么",
            "关系变化对剧情的影响",
        ],
    },
    {
        "heading": "六、读者认知进度表",
        "required_points": [
            "信息或关系真相 ID",
            "作者侧完整真相",
            "读者最初以为的情况",
            "前期揭露",
            "中期揭露",
            "后期揭露",
            "受影响的关系 ID",
            "揭露后的关系变化",
            "揭露后的剧情变化",
        ],
    },
    {
        "heading": "七、秘密与信息差网络",
        "required_points": [
            "秘密 ID",
            "秘密内容",
            "相关角色",
            "知道秘密的人",
            "不知道秘密的人",
            "误解秘密的人",
            "首次埋伏笔阶段",
            "部分揭露阶段",
            "完全揭露阶段",
            "受影响的关系",
            "揭露后的剧情后果",
            "锁定规则",
        ],
    },
    {
        "heading": "八、阵营 / 组织关系",
        "required_points": [
            "来自世界观的来源",
            "在人物关系中的作用",
            "关键成员",
            "与主角的初始关系",
            "与主角的演化",
            "与其他阵营的关系",
            "内部张力",
            "剧情用途",
        ],
    },
    {
        "heading": "九、关系冲突类型",
        "required_points": [
            "情感冲突",
            "利益冲突",
            "价值观冲突",
            "身份冲突",
            "信息冲突",
            "历史冲突",
            "目标冲突",
            "命运冲突",
        ],
    },
    {
        "heading": "十、关系事件种子",
        "required_points": [
            "事件种子 ID",
            "相关关系",
            "涉及角色",
            "事件类型",
            "触发原因",
            "事件前状态",
            "事件概要",
            "事件后状态",
            "主线影响",
            "是否必须发生",
            "是否可替换",
            "建议发生阶段",
        ],
    },
    {
        "heading": "十一、角色退场与关系遗产",
        "required_points": [
            "角色 ID",
            "变化类型",
            "发生阶段",
            "变化原因",
            "受影响的关系",
            "留下的秘密",
            "留下的目标",
            "留下的误会",
            "留下的债务",
            "留下的道具",
            "留下的情感影响",
            "对后续剧情的影响",
            "锁定级别",
        ],
    },
    {
        "heading": "十二、锁定项与可变项",
        "required_points": [
            "主角核心关系弧光",
            "核心关系起点和终点",
            "主要反派与主角的关系定位",
            "关键秘密揭露顺序",
            "关键背叛、牺牲、和解、决裂",
            "不能提前公开的信息",
            "与世界观强绑定的人物身份",
            "决定性阵营关系",
            "可变的姓名与登场顺序",
        ],
    },
    {
        "heading": "十三、待确认问题",
        "required_points": [
            "是否需要明确的情感线",
            "是单核成长还是团队成长",
            "主要反派是否需要救赎可能",
            "核心队友是否允许背叛",
            "是否允许重要角色死亡",
            "是否存在隐藏血缘、身份反转或前代恩怨",
            "主角最终是修复关系、斩断关系还是重建新秩序",
            "哪些关系必须前期隐藏",
            "哪些组织或阵营必须进入人物关系网络",
        ],
    },
]

CHARACTER_OUTLINE_COMPACT_HEADINGS = [str(item["heading"]) for item in CHARACTER_OUTLINE_FULL_SECTIONS]


def full_characters_headings() -> list[str]:
    return [str(item["heading"]) for item in CHARACTER_OUTLINE_FULL_SECTIONS]


def compact_characters_headings() -> list[str]:
    return list(CHARACTER_OUTLINE_COMPACT_HEADINGS)


def render_characters_framework(mode: str = "full") -> str:
    """Return a concise prompt-friendly markdown description of the framework."""
    if mode == "compact":
        return "\n".join(f"- {heading}" for heading in CHARACTER_OUTLINE_COMPACT_HEADINGS)
    if mode != "full":
        raise ValueError(f"Unsupported characters framework mode: {mode}")
    lines: list[str] = [
        "## 人物关系稿",
        "- 这一阶段不是人物小传，而是全文人物关系蓝图。",
        "- 必须区分作者侧真相、角色侧认知、读者侧认知和剧情侧演化。",
        "- 阵营 / 组织关系只能从前序世界观中已有设定提取，没有就写“暂无”。",
        "- 核心关系必须有起点、变化和终点；秘密揭露必须改变至少一段关系。",
        "- 不要把人物关系写成世界规则、章节正文或静态角色档案。",
        "",
        "## 人物层级说明",
        "- A 级：主角、主要反派、核心搭档、核心情感对象、关键导师、对主线长期施加影响的人物。",
        "- B 级：重要队友、阶段反派、家族 / 组织代表、关键转折人物。",
        "- C 级：服务单卷、单事件或单阶段的人物。",
        "- D 级：提供信息、推进场景、完成局部功能的工具角色。",
        "",
        "## 关系卡 / 认知 / 秘密 / 阵营 输出要求",
        "- 关系卡必须写清起点、变化、终点，以及读者知道什么、角色知道什么。",
        "- 读者认知进度表要区分作者侧真相、初始误解和阶段性揭露。",
        "- 秘密必须能改变至少一段关系，并写清伏笔、部分揭露和完全揭露。",
        "- 阵营 / 组织关系只能从 worldbuilding 继承，没有相关设定时写“暂无，不强行生成”。",
        "- 关系事件种子要能直接送入 story_flow。",
        "- 角色退场后必须留下关系遗产。",
        "",
    ]
    for item in CHARACTER_OUTLINE_FULL_SECTIONS[1:]:
        heading = str(item["heading"])
        required_points = "、".join(str(point) for point in item["required_points"])
        lines.append(f"## {heading}\n- 必须覆盖：{required_points}")
    return "\n\n".join(lines)


def validate_characters_outline(text: str, mode: str = "full") -> tuple[bool, list[str]]:
    """Return (ok, missing_headings). Headings match Markdown headings from # to ######."""
    headings = _headings_for_mode(mode)
    positions: list[int | None] = [_heading_position(text, heading) for heading in headings]
    missing = [heading for heading, position in zip(headings, positions, strict=True) if position is None]
    if missing:
        return False, missing
    ordered = [position for position in positions if position is not None]
    if ordered != sorted(ordered):
        out_of_order = [
            heading
            for index, heading in enumerate(headings)
            if index > 0 and ordered[index] < ordered[index - 1]
        ]
        return False, out_of_order or headings
    return True, []


def append_missing_characters_sections(text: str, missing: list[str]) -> str:
    """Last-resort deterministic repair for structurally incomplete characters output."""
    content = str(text or "").strip()
    if not missing:
        return content

    headings = full_characters_headings()
    existing = _extract_existing_heading_sections(content, headings)
    lines: list[str] = []
    for index, heading in enumerate(headings):
        lines.append(f"## {heading}")
        body = existing.get(heading, "").strip()
        if body:
            lines.extend(body.splitlines())
        else:
            lines.append(
                "- 待补充：结构兜底占位。本节需要补写与当前小说创意、已锁定方向和主线冲突直接相关的具体人物关系设定。"
            )
            if heading == "人物关系稿":
                lines.append("- 需要明确作者侧真相、角色侧认知、读者侧认知和剧情侧演化。")
            elif heading == "一、全角色总表":
                lines.append("- 至少列出主角、核心配角、重要配角、阶段角色和工具角色。")
            elif index == 0 and content and not existing:
                lines.append("- 原始草稿摘录：以下内容来自结构修复前输出，需要再归入对应人物关系章节。")
                for raw_line in content.splitlines()[:20]:
                    line = raw_line.strip()
                    if line:
                        lines.append(f"  {line}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def split_characters_sections(text: str) -> dict[str, str]:
    headings = full_characters_headings()
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


def characters_bullets(section_text: str) -> list[str]:
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


def first_characters_bullet(section_text: str) -> str:
    bullets = characters_bullets(section_text)
    return bullets[0] if bullets else ""


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
        if not line or line.startswith("#") or "仍需确认" in line or line == "暂无":
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


def summarize_characters_outline(text: str, max_chars: int = 1800) -> str:
    sections = split_characters_sections(text)
    key_headings = [
        "人物关系稿",
        "一、全角色总表",
        "三、主角关系弧光",
        "四、核心人物关系卡",
        "六、读者认知进度表",
        "七、秘密与信息差网络",
        "八、阵营 / 组织关系",
        "十一、角色退场与关系遗产",
        "十二、锁定项与可变项",
    ]
    lines: list[str] = []
    for heading in key_headings:
        bullet = first_characters_bullet(sections.get(heading, ""))
        if bullet:
            lines.append(f"{heading}：{bullet}")
    if not lines:
        return summarize_stage_text(text, max_chars=420)
    summary = "；".join(lines)
    return summary[:max_chars].rstrip() + ("..." if len(summary) > max_chars else "")


def extract_characters_memory(text: str, max_items: int = 18, max_chars: int = 1800) -> list[str]:
    sections = split_characters_sections(text)
    priority = [
        "人物关系稿",
        "一、全角色总表",
        "二、角色个人驱动力",
        "三、主角关系弧光",
        "四、核心人物关系卡",
        "五、关系演化时间轴",
        "六、读者认知进度表",
        "七、秘密与信息差网络",
        "八、阵营 / 组织关系",
        "十、关系事件种子",
        "十一、角色退场与关系遗产",
        "十二、锁定项与可变项",
    ]
    result: list[str] = []
    total = 0
    for heading in priority:
        for bullet in characters_bullets(sections.get(heading, ""))[:2]:
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


def _extract_existing_heading_sections(text: str, headings: list[str]) -> dict[str, str]:
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


def _headings_for_mode(mode: str) -> list[str]:
    if mode == "full":
        return full_characters_headings()
    if mode == "compact":
        return compact_characters_headings()
    raise ValueError(f"Unsupported characters framework mode: {mode}")


def _heading_position(text: str, heading: str) -> int | None:
    pattern = re.compile(rf"^\s*#{{1,6}}\s*{re.escape(heading)}(?:\s|$)", re.MULTILINE)
    match = pattern.search(text or "")
    return match.start() if match else None
