"""Structural helpers for the progressive chapter_outline stage."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ai_novelist.chapter_outline_framework import (
    CHAPTER_OUTLINE_MODULES,
    CHAPTER_OUTLINE_STATUSES,
    chapter_profile_definition,
    chapter_profile_labels,
    profile_hook_strength,
    profile_intensity,
    profile_required_points,
    profile_to_pacing_function,
)


CHAPTER_OUTLINE_TITLE = "章节大纲稿"
VOLUME_PLAN_HEADING = "卷内章节总体规划"
CHAPTER_TABLE_HEADING = "章节列表总表"


@dataclass(frozen=True)
class VolumeSpec:
    index: int
    label: str
    name: str = ""
    chapter_range: str = ""
    function: str = ""

    @property
    def display_name(self) -> str:
        if self.name and self.name != self.label:
            return f"{self.label}：{self.name}"
        return self.label


def chinese_number_to_int(value: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if text == "十":
        return 10
    if "十" in text:
        left, right = text.split("十", 1)
        tens = digits.get(left, 1) if left else 1
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones
    return digits.get(text)


def volume_label(index: int) -> str:
    numerals = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
    if 0 <= index < len(numerals):
        return f"第{numerals[index]}卷"
    return f"第{index}卷"


def extract_volume_specs(volume_outline: str) -> list[VolumeSpec]:
    text = str(volume_outline or "")
    found: dict[int, VolumeSpec] = {}

    for match in re.finditer(r"第\s*(?P<num>[一二两三四五六七八九十\d]+)\s*卷[：:\s]*(?P<body>[^\n|。；;]*)", text):
        number = chinese_number_to_int(match.group("num"))
        if not number:
            continue
        body = match.group("body").strip(" -：:。")
        name = body.split("，", 1)[0].split(",", 1)[0].strip()
        found.setdefault(number, VolumeSpec(index=number, label=volume_label(number), name=name, function=body))

    for row in re.finditer(r"\|\s*第\s*(?P<num>[一二两三四五六七八九十\d]+)\s*卷\s*\|\s*(?P<function>[^|\n]+)\|", text):
        number = chinese_number_to_int(row.group("num"))
        if not number:
            continue
        function = row.group("function").strip()
        existing = found.get(number)
        if existing is None:
            found[number] = VolumeSpec(index=number, label=volume_label(number), function=function)
        elif not existing.function:
            found[number] = VolumeSpec(existing.index, existing.label, existing.name, existing.chapter_range, function)

    if not found:
        match = re.search(r"全书暂定\s*(?P<count>[一二两三四五六七八九十\d]+)\s*卷", text)
        count = chinese_number_to_int(match.group("count")) if match else None
        if count:
            found = {index: VolumeSpec(index=index, label=volume_label(index)) for index in range(1, count + 1)}

    if not found:
        return [VolumeSpec(index=1, label="第一卷", function="卷级章节拆分")]

    return [found[index] for index in sorted(found)]


def chapter_outline_metadata_from_artifact(artifact: dict[str, Any] | None, volume_outline: str = "") -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if isinstance(artifact, dict) and isinstance(artifact.get("metadata"), dict):
        metadata.update(artifact["metadata"])
    specs = extract_volume_specs(volume_outline)
    total = int(metadata.get("total_volumes") or len(specs) or 1)
    current = int(metadata.get("current_volume_index") or 1)
    completed = sorted({int(item) for item in metadata.get("completed_volumes", []) if str(item).isdigit()})
    statuses = metadata.get("volume_statuses") if isinstance(metadata.get("volume_statuses"), dict) else {}
    contents = metadata.get("volume_contents") if isinstance(metadata.get("volume_contents"), dict) else {}
    return {
        "current_volume_index": max(1, min(current, total)),
        "completed_volumes": [item for item in completed if 1 <= item <= total],
        "total_volumes": total,
        "volume_statuses": {str(key): str(value) for key, value in statuses.items()},
        "volume_contents": {str(key): str(value) for key, value in contents.items() if str(value).strip()},
        "volume_specs": [spec.__dict__ for spec in specs],
    }


def current_volume_spec(metadata: dict[str, Any]) -> VolumeSpec:
    current = int(metadata.get("current_volume_index") or 1)
    specs = metadata.get("volume_specs") if isinstance(metadata.get("volume_specs"), list) else []
    for raw in specs:
        if isinstance(raw, dict) and int(raw.get("index") or 0) == current:
            return VolumeSpec(
                index=current,
                label=str(raw.get("label") or volume_label(current)),
                name=str(raw.get("name") or ""),
                chapter_range=str(raw.get("chapter_range") or ""),
                function=str(raw.get("function") or ""),
            )
    return VolumeSpec(index=current, label=volume_label(current))


def completed_volume_briefs(metadata: dict[str, Any], max_chars: int = 1000) -> str:
    completed = metadata.get("completed_volumes") if isinstance(metadata.get("completed_volumes"), list) else []
    contents = metadata.get("volume_contents") if isinstance(metadata.get("volume_contents"), dict) else {}
    specs = metadata.get("volume_specs") if isinstance(metadata.get("volume_specs"), list) else []
    spec_map = {
        int(raw.get("index") or 0): raw
        for raw in specs
        if isinstance(raw, dict) and str(raw.get("index") or "").isdigit()
    }

    def brief_text(content: str) -> str:
        summary = chapter_outline_summary(content, max_chars=min(380, max_chars))
        bullets: list[str] = []
        capture = False
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("## 卷内章节总体规划"):
                capture = True
                continue
            if capture and line.startswith("-"):
                cleaned = re.sub(r"^[-*+•\s]*", "", line).strip()
                if cleaned:
                    bullets.append(cleaned)
                if len(bullets) >= 2:
                    break
        if bullets:
            bullet_text = "；".join(bullets)
            return f"{summary}；{bullet_text}" if summary else bullet_text
        return summary

    lines: list[str] = []
    total = 0
    for raw_index in completed:
        if not str(raw_index).isdigit():
            continue
        index = int(raw_index)
        content = str(contents.get(str(index)) or "").strip()
        if not content:
            continue
        raw_spec = spec_map.get(index, {})
        label = str(raw_spec.get("label") or volume_label(index))
        name = str(raw_spec.get("name") or "").strip()
        heading = f"{label}《{name}》" if name else label
        brief = brief_text(content)
        item = f"- {heading}摘要：{brief}" if brief else f"- {heading}摘要：暂无"
        if total + len(item) > max_chars and lines:
            break
        lines.append(item)
        total += len(item)
    return "\n".join(lines) if lines else "暂无"

def build_chapter_outline_target_context(metadata: dict[str, Any]) -> str:
    spec = current_volume_spec(metadata)
    completed = metadata.get("completed_volumes") if isinstance(metadata.get("completed_volumes"), list) else []
    completed_briefs = completed_volume_briefs(metadata)
    lines = [
        f"- current_volume_index: {spec.index}",
        f"- total_volumes: {metadata.get('total_volumes') or 1}",
        f"- target_volume: {spec.display_name}",
        f"- target_chapter_range: {spec.chapter_range or '优先从分卷大纲判断，缺失时由模型暂定并标注来源'}",
        f"- target_volume_function: {spec.function or '承接分卷大纲的卷级功能'}",
        f"- completed_volumes: {', '.join(str(item) for item in completed) if completed else '暂无'}",
        f"- 已完成卷摘要：{completed_briefs}",
        "- rule: 本轮只生成 target_volume 的整卷章节大纲，不重写已完成卷。",
    ]
    return "\n".join(lines)


def merge_chapter_outline_volumes(metadata: dict[str, Any]) -> str:
    contents = metadata.get("volume_contents") if isinstance(metadata.get("volume_contents"), dict) else {}
    total = int(metadata.get("total_volumes") or len(contents) or 1)
    lines = [f"## {CHAPTER_OUTLINE_TITLE}", ""]
    for index in range(1, total + 1):
        content = str(contents.get(str(index)) or "").strip()
        if not content:
            continue
        if re.search(rf"^\s*#{{2,6}}\s*{re.escape(volume_label(index))}", content, re.MULTILINE):
            lines.append(content)
        else:
            lines.append(f"### {volume_label(index)}")
            lines.append(content)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def normalize_generated_volume_outline(text: str, metadata: dict[str, Any]) -> str:
    spec = current_volume_spec(metadata)
    content = str(text or "").strip()
    content = re.sub(r"^\s*#{1,2}\s*章节大纲稿\s*", "", content).strip()
    if not re.search(rf"^\s*#{{2,6}}\s*{re.escape(spec.label)}", content, re.MULTILINE):
        content = f"### {spec.display_name}\n\n{content}"
    return content.rstrip() + "\n"


def validate_chapter_outline_volume(text: str, metadata: dict[str, Any]) -> tuple[bool, list[str]]:
    content = str(text or "").strip()
    issues: list[str] = []
    spec = current_volume_spec(metadata)
    if spec.label not in content and spec.name not in content:
        issues.append("目标卷标题")
    for heading in (VOLUME_PLAN_HEADING, CHAPTER_TABLE_HEADING):
        if heading not in content:
            issues.append(heading)
    if not re.search(r"第\s*\d+\s*章|第\s*[一二两三四五六七八九十]+\s*章", content):
        issues.append("单章条目")
    if not any(label in content for label in chapter_profile_labels()):
        issues.append("章级功能 profile")
    if "PacingTarget" not in content and "pacing" not in content.lower():
        issues.append("PacingTarget")
    if not any(module.heading in content for module in CHAPTER_OUTLINE_MODULES):
        issues.append("单章稳定结构")
    if not any(status in content for status in CHAPTER_OUTLINE_STATUSES):
        issues.append("模块状态")
    if "连续性" not in content:
        issues.append("连续性字段")
    issues.extend(profile_minimum_issues(content))
    if len(content) < 600:
        issues.append("内容过短")
    return not issues, list(dict.fromkeys(issues))


def profile_minimum_issues(text: str) -> list[str]:
    issues: list[str] = []
    for label in chapter_profile_labels():
        if label not in text:
            continue
        required = profile_required_points(label)
        missing = [item for item in required if item not in text]
        if missing:
            issues.append(f"{label}最低必填项缺失：{'、'.join(missing)}")
    return issues


def append_missing_chapter_outline_volume_sections(text: str, metadata: dict[str, Any], issues: list[str] | None = None) -> str:
    spec = current_volume_spec(metadata)
    content = normalize_generated_volume_outline(text, metadata).rstrip()
    lines = [content, ""]
    if VOLUME_PLAN_HEADING not in content:
        lines.extend(
            [
                f"#### {VOLUME_PLAN_HEADING}",
                "- 待补充：结构兜底占位。请结合分卷大纲明确本卷章节总数、区间任务、高潮/反转/信息揭示/钩子分布。",
                "",
            ]
        )
    if CHAPTER_TABLE_HEADING not in content:
        profile = chapter_profile_definition("铺垫章")
        lines.extend(
            [
                f"#### {CHAPTER_TABLE_HEADING}",
                f"| 章节 | 标题 | profile | PacingTarget | 一句话概括 | 结尾状态 |",
                "| --- | --- | --- | --- | --- | --- |",
                f"| 第 1 章 | 待定 | {profile.label} | function={profile.pacing_function}, intensity={profile.intensity}, hook={profile.hook_strength} | 承接本卷开端并建立章节任务。 | 留下轻钩子。 |",
                "",
            ]
        )
    if not any(module.heading in content for module in CHAPTER_OUTLINE_MODULES):
        lines.append("#### 第 1 章：结构兜底章纲")
        lines.append("- profile：铺垫章")
        lines.append("- PacingTarget：function=setup, intensity=3, hook=soft")
        for module in CHAPTER_OUTLINE_MODULES:
            status = "详写" if module.key in {"positioning", "plot_execution", "world_continuity", "execution_review"} else "简写"
            lines.append(f"- {module.heading}：状态：{status}。待补充：结构兜底占位，按本章 profile 选择能力池字段。")
        lines.append("- 连续性提醒：承接上一章或本卷开端状态，不提前暴露后续真相。")
        lines.append("- 审稿检查：本章必须有明确叙事功能，删除后会影响本卷推进。")
    if issues:
        lines.extend(["", "#### 结构修复备注", "- 已补齐：" + "、".join(issues)])
    return "\n".join(lines).rstrip() + "\n"


def chapter_outline_summary(text: str, max_chars: int = 2200) -> str:
    lines = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("| ---"):
            continue
        if line.startswith("#") or "profile" in line or "PacingTarget" in line or "结尾" in line or "卷内章节总体规划" in line:
            lines.append(line.strip("# "))
        if len("；".join(lines)) > max_chars:
            break
    summary = "；".join(dict.fromkeys(lines))
    return summary[:max_chars].rstrip() + ("..." if len(summary) > max_chars else "")


def extract_chapter_outline_memory(text: str, max_items: int = 28, max_chars: int = 2400) -> list[str]:
    result: list[str] = []
    total = 0
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("| ---"):
            continue
        if any(marker in line for marker in ("profile", "PacingTarget", "一句话概括", "结尾", "连续性", "审稿")):
            cleaned = re.sub(r"^[-*+•\s]*", "", line).strip()
            if cleaned and cleaned not in result:
                if total + len(cleaned) > max_chars and result:
                    break
                result.append(cleaned)
                total += len(cleaned)
        if len(result) >= max_items:
            break
    if result:
        return result
    fallback = chapter_outline_summary(text, max_chars=max_chars)
    return [fallback] if fallback else []


def extract_chapter_outline_volume(text: str, volume_index: int) -> str:
    content = str(text or "").strip()
    if not content or volume_index < 1:
        return ""
    headings = list(
        re.finditer(
            r"^\s*#{2,6}\s*第\s*(?P<num>[一二两三四五六七八九十\d]+)\s*卷[^\n]*$",
            content,
            re.MULTILINE,
        )
    )
    for position, match in enumerate(headings):
        if chinese_number_to_int(match.group("num")) != volume_index:
            continue
        end = headings[position + 1].start() if position + 1 < len(headings) else len(content)
        return content[match.start() : end].strip()
    return ""


def extract_chapter_outline_slice(text: str, chapter: int) -> str:
    content = str(text or "").strip()
    if not content or chapter < 1:
        return content
    chapter_pattern = re.compile(
        r"^\s*(?P<heading>#{1,6}\s*)?第\s*(?P<heading_num>[一二两三四五六七八九十\d]+)\s*章[：:\s].*$|"
        r"^\s*\|\s*第\s*(?P<row_num>[一二两三四五六七八九十\d]+)\s*章\s*\|.*$",
        re.MULTILINE,
    )
    match = None
    for candidate in chapter_pattern.finditer(content):
        raw_number = candidate.group("heading_num") or candidate.group("row_num")
        if chinese_number_to_int(raw_number) == chapter:
            match = candidate
            break
    if not match:
        return legacy_chapter_outline_slice(content, chapter)
    start = match.start()
    heading_level = None
    if match.group("heading"):
        heading_level = len(match.group("heading").strip())
    end = len(content)
    if heading_level:
        next_heading = re.compile(
            rf"^\s*#{{1,{heading_level}}}\s+第\s*(?P<num>[一二两三四五六七八九十\d]+)\s*章",
            re.MULTILINE,
        )
        for next_match in next_heading.finditer(content, match.end()):
            if chinese_number_to_int(next_match.group("num")) != chapter:
                end = next_match.start()
                break
    else:
        next_row = re.compile(
            r"^\s*\|\s*第\s*(?P<num>[一二两三四五六七八九十\d]+)\s*章\s*\|",
            re.MULTILINE,
        )
        for next_match in next_row.finditer(content, match.end()):
            if chinese_number_to_int(next_match.group("num")) != chapter:
                end = next_match.start()
                break
    volume_context = nearest_volume_context(content, start)
    chapter_text = content[start:end].strip()
    return "\n\n".join(part for part in (volume_context, chapter_text) if part).strip()


def nearest_volume_context(content: str, position: int) -> str:
    headings = list(re.finditer(r"^\s*#{2,6}\s*(第[一二两三四五六七八九十\d]+卷[^\n]*)$", content, re.MULTILINE))
    previous = [match for match in headings if match.start() <= position]
    if not previous:
        return ""
    volume = previous[-1]
    plan_heading = re.search(rf"^\s*#{{3,6}}\s*{re.escape(VOLUME_PLAN_HEADING)}\s*$", content[volume.end() : position], re.MULTILINE)
    if not plan_heading:
        return volume.group(0).strip()
    start = volume.end() + plan_heading.end()
    next_heading = re.search(r"^\s*#{3,6}\s+", content[start:position], re.MULTILINE)
    end = start + next_heading.start() if next_heading else min(position, start + 1000)
    return (volume.group(0).strip() + "\n" + content[start:end].strip()).strip()


def legacy_chapter_outline_slice(content: str, chapter: int) -> str:
    patterns = [
        rf"第\s*{chapter}\s*章[：:\s][\s\S]*?(?=第\s*{chapter + 1}\s*章[：:\s]|$)",
        rf"chapter\s*{chapter}\b[\s\S]*?(?=chapter\s*{chapter + 1}\b|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return content


def pacing_target_from_profile(profile: str, chapter: int) -> dict[str, Any]:
    return {
        "chapter": chapter,
        "function": profile_to_pacing_function(profile),
        "intensity": profile_intensity(profile),
        "hook_strength": profile_hook_strength(profile),
    }

