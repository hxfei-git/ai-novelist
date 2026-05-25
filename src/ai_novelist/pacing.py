"""Pacing helpers for chapter planning and downstream guardrails."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ChapterFunction = Literal["setup", "breather", "aftermath", "build", "twist", "climax", "transition", "unknown"]
HookStrength = Literal["none", "soft", "hard"]


@dataclass
class PacingTarget:
    chapter: int
    function: ChapterFunction = "unknown"
    intensity: int = 3
    tension_source: str = ""
    ending_mode: str = ""
    hook_strength: HookStrength = "soft"
    must_not: list[str] | None = None
    defer_to_later: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "function": self.function,
            "intensity": self.intensity,
            "tension_source": self.tension_source,
            "ending_mode": self.ending_mode,
            "hook_strength": self.hook_strength,
            "must_not": list(self.must_not or []),
            "defer_to_later": list(self.defer_to_later or []),
        }


def clamp_intensity(value: int) -> int:
    return max(1, min(5, int(value)))


def infer_function(text: str) -> ChapterFunction:
    raw = text.lower()
    mapping = {
        "余波": "aftermath",
        "收束章": "aftermath",
        "aftermath": "aftermath",
        "低谷": "breather",
        "日常章": "breather",
        "breather": "breather",
        "过渡": "transition",
        "过渡章": "transition",
        "transition": "transition",
        "开篇章": "setup",
        "铺垫": "setup",
        "铺垫章": "setup",
        "setup": "setup",
        "蓄势": "build",
        "冲突章": "build",
        "爽点章": "build",
        "感情推进章": "build",
        "世界观释放章": "build",
        "战斗章": "build",
        "谋略章": "build",
        "钩子章": "build",
        "build": "build",
        "转折": "twist",
        "反转章": "twist",
        "揭秘章": "twist",
        "twist": "twist",
        "高潮": "climax",
        "高潮章": "climax",
        "climax": "climax",
    }
    for key, value in mapping.items():
        if key in raw:
            return value  # type: ignore[return-value]
    return "unknown"


def infer_hook_strength(ending_mode: str, function: ChapterFunction, intensity: int) -> HookStrength:
    text = ending_mode.lower()
    if any(item in text for item in ("无钩子", "none", "软收束", "余波", "过渡")):
        return "none"
    if any(item in text for item in ("软钩子", "soft", "余韵", "回响")):
        return "soft"
    if any(item in text for item in ("硬钩子", "hard", "悬崖", "爆点")):
        return "hard"
    if function in {"aftermath", "breather", "transition"} and intensity <= 2:
        return "none"
    if intensity >= 4:
        return "hard"
    return "soft"


def split_items(text: str) -> list[str]:
    if not text.strip():
        return []
    items: list[str] = []
    for part in re.split(r"[；;。\n]", text):
        value = part.strip(" -:\t")
        if value:
            items.append(value)
    return items


def extract_section(markdown: str, heading: str) -> str:
    pattern = rf"^##\s*{re.escape(heading)}\s*$"
    lines = markdown.splitlines()
    start = -1
    for idx, line in enumerate(lines):
        if re.match(pattern, line.strip()):
            start = idx + 1
            break
    if start < 0:
        return ""
    end = len(lines)
    for idx in range(start, len(lines)):
        if lines[idx].strip().startswith("## "):
            end = idx
            break
    return "\n".join(lines[start:end]).strip()


def parse_pacing_target_from_card(chapter: int, chapter_card: str) -> PacingTarget:
    function_text = extract_section(chapter_card, "本章功能")
    intensity_text = extract_section(chapter_card, "目标强度")
    tension = extract_section(chapter_card, "张力来源")
    ending_mode = extract_section(chapter_card, "结尾方式")
    must_not_text = extract_section(chapter_card, "禁止升级项")
    defer_text = extract_section(chapter_card, "延后信息")
    found = re.search(r"([1-5])", intensity_text)
    intensity = clamp_intensity(int(found.group(1))) if found else 3
    function = infer_function(function_text)
    hook_strength = infer_hook_strength(ending_mode, function, intensity)
    return PacingTarget(
        chapter=chapter,
        function=function,
        intensity=intensity,
        tension_source=tension.strip(),
        ending_mode=ending_mode.strip(),
        hook_strength=hook_strength,
        must_not=split_items(must_not_text),
        defer_to_later=split_items(defer_text),
    )


def infer_pacing_target_from_outline(chapter: int, outline: str) -> PacingTarget:
    function = infer_function(outline)
    intensity = 3
    if function in {"aftermath", "breather", "transition"}:
        intensity = 2
    elif function == "climax":
        intensity = 5
    elif function == "twist":
        intensity = 4
    return PacingTarget(
        chapter=chapter,
        function=function,
        intensity=intensity,
        tension_source="待章节卡细化",
        ending_mode="待章节卡细化",
        hook_strength=infer_hook_strength("", function, intensity),
        must_not=[],
        defer_to_later=[],
    )


def select_chapter_agent_specs(pacing: PacingTarget) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = [
        ("chapter_pacing_report", "chapter_pacing_agent"),
        ("chapter_goal_report", "chapter_goal_agent"),
    ]
    if pacing.intensity <= 2:
        specs.append(("chapter_conflict_report", "restraint_agent"))
    else:
        specs.append(("chapter_conflict_report", "chapter_conflict_agent"))

    if pacing.hook_strength in {"none", "soft"}:
        specs.append(("chapter_hook_report", "ending_resonance_agent"))
    else:
        specs.append(("chapter_hook_report", "chapter_hook_agent"))
    return specs


def required_chapter_card_sections(pacing: PacingTarget) -> list[str]:
    required = [
        "本章功能",
        "目标强度",
        "张力来源",
        "结尾方式",
        "禁止升级项",
        "延后信息",
        "章节目标",
        "场景列表",
        "人物变化",
        "连续性约束",
        "本章写作输入",
        "自检",
    ]
    if pacing.intensity >= 3:
        required.append("关键冲突")
    if pacing.hook_strength == "hard":
        required.append("结尾钩子")
    return required


def allow_hook_enhance(pacing: PacingTarget) -> bool:
    return pacing.hook_strength == "hard" or pacing.intensity >= 4


def scene_required_fields(pacing: PacingTarget) -> list[str]:
    fields = ["地点", "出场人物", "场景目的", "人物目标", "关键信息", "情绪变化", "退出状态"]
    if pacing.intensity >= 3:
        fields.extend(["冲突对象", "场景转折"])
    return fields
