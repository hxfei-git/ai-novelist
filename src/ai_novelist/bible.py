"""Novel bible data model and persistence helpers."""

from __future__ import annotations

import json
from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal, TypeVar, get_args, get_origin


@dataclass
class ProjectBrief:
    title: str = ""
    genre: str = ""
    subgenre: str = ""
    target_reader: str = ""
    core_experience: str = ""
    tone_keywords: list[str] = field(default_factory=list)
    locked_constraints: list[str] = field(default_factory=list)


@dataclass
class StoryConcept:
    logline: str = ""
    premise: str = ""
    core_conflict: str = ""
    theme: str = ""
    central_question: str = ""
    ending_direction: str = ""


@dataclass
class WorldRule:
    name: str = ""
    description: str = ""
    limitation: str = ""
    cost: str = ""
    source_stage: str = ""


@dataclass
class CharacterCard:
    name: str = ""
    role: str = ""
    identity: str = ""
    external_goal: str = ""
    internal_need: str = ""
    flaw: str = ""
    fear: str = ""
    secret: str = ""
    arc: str = ""
    voice: str = ""
    relationships: list[str] = field(default_factory=list)
    status: str = "active"


@dataclass
class PlotThread:
    name: str = ""
    description: str = ""
    status: Literal["open", "active", "resolved"] = "open"
    related_chapters: list[int] = field(default_factory=list)


@dataclass
class ForeshadowingItem:
    id: str = ""
    setup_chapter: int | None = None
    setup_text: str = ""
    payoff_chapter: int | None = None
    payoff_text: str = ""
    status: Literal["planned", "setup", "paid_off", "dropped"] = "planned"


@dataclass
class TimelineEvent:
    id: str = ""
    order: int = 0
    chapter: int | None = None
    event: str = ""
    characters: list[str] = field(default_factory=list)
    location: str = ""


@dataclass
class NovelBible:
    project: ProjectBrief = field(default_factory=ProjectBrief)
    concept: StoryConcept = field(default_factory=StoryConcept)
    world_rules: list[WorldRule] = field(default_factory=list)
    factions: list[dict[str, Any]] = field(default_factory=list)
    characters: list[CharacterCard] = field(default_factory=list)
    plot_threads: list[PlotThread] = field(default_factory=list)
    timeline: list[TimelineEvent] = field(default_factory=list)
    foreshadowing: list[ForeshadowingItem] = field(default_factory=list)
    style_guide: dict[str, Any] = field(default_factory=dict)
    chapter_summaries: dict[str, str] = field(default_factory=dict)
    open_questions: list[str] = field(default_factory=list)
    version: int = 1


T = TypeVar("T")


def bible_to_dict(bible: NovelBible) -> dict[str, Any]:
    return asdict(bible)


def bible_from_dict(data: dict[str, Any]) -> NovelBible:
    return NovelBible(
        project=dataclass_from_dict(ProjectBrief, data.get("project", {})),
        concept=dataclass_from_dict(StoryConcept, data.get("concept", {})),
        world_rules=dataclass_list_from_dict(WorldRule, data.get("world_rules", [])),
        factions=normalize_dict_list(data.get("factions", [])),
        characters=dataclass_list_from_dict(CharacterCard, data.get("characters", [])),
        plot_threads=dataclass_list_from_dict(PlotThread, data.get("plot_threads", [])),
        timeline=dataclass_list_from_dict(TimelineEvent, data.get("timeline", [])),
        foreshadowing=dataclass_list_from_dict(ForeshadowingItem, data.get("foreshadowing", [])),
        style_guide=dict(data.get("style_guide", {})) if isinstance(data.get("style_guide", {}), dict) else {},
        chapter_summaries={str(key): str(value) for key, value in data.get("chapter_summaries", {}).items()}
        if isinstance(data.get("chapter_summaries", {}), dict)
        else {},
        open_questions=normalize_str_list(data.get("open_questions", [])),
        version=int(data.get("version", 1)),
    )


def load_bible(project_dir: Path) -> NovelBible:
    path = novel_bible_json_path(project_dir)
    if not path.exists():
        return NovelBible()
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return bible_from_dict(data if isinstance(data, dict) else {})


def save_bible(project_dir: Path, bible: NovelBible) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    with novel_bible_json_path(project_dir).open("w", encoding="utf-8") as file:
        json.dump(bible_to_dict(bible), file, ensure_ascii=False, indent=2)
        file.write("\n")
    novel_bible_markdown_path(project_dir).write_text(render_bible_markdown(bible), encoding="utf-8")


def render_bible_markdown(bible: NovelBible) -> str:
    lines = ["# 小说圣经", "", "## 项目简报"]
    lines.extend(render_object_lines(bible.project))
    lines.extend(["", "## 故事核心"])
    lines.extend(render_object_lines(bible.concept))
    lines.extend(["", "## 世界规则"])
    lines.extend(render_named_items(bible.world_rules, "name", "description"))
    lines.extend(["", "## 人物卡"])
    lines.extend(render_named_items(bible.characters, "name", "role"))
    lines.extend(["", "## 情节线"])
    lines.extend(render_named_items(bible.plot_threads, "name", "description"))
    lines.extend(["", "## 时间线"])
    if bible.timeline:
        for item in sorted(bible.timeline, key=lambda event: event.order):
            chapter = f"第 {item.chapter} 章" if item.chapter is not None else "未定章节"
            lines.append(f"- {item.order}. {chapter}：{item.event}")
    else:
        lines.append("- 暂无")
    lines.extend(["", "## 伏笔表"])
    lines.extend(render_named_items(bible.foreshadowing, "id", "setup_text"))
    lines.extend(["", "## 风格指南"])
    lines.extend(render_mapping_lines(bible.style_guide))
    lines.extend(["", "## 章节摘要"])
    if bible.chapter_summaries:
        for chapter, summary in sorted(bible.chapter_summaries.items(), key=lambda item: int(item[0]) if item[0].isdigit() else item[0]):
            lines.append(f"- 第 {chapter} 章：{summary}")
    else:
        lines.append("- 暂无")
    lines.extend(["", "## 开放问题"])
    lines.extend(f"- {item}" for item in bible.open_questions) if bible.open_questions else lines.append("- 暂无")
    lines.extend(["", f"版本：{bible.version}"])
    return "\n".join(lines).rstrip() + "\n"


def merge_bible_updates(bible: NovelBible, updates: dict[str, Any]) -> NovelBible:
    merged = bible_from_dict(bible_to_dict(bible))
    if not isinstance(updates, dict):
        return merged
    merge_dataclass_non_empty(merged.project, updates.get("project", {}))
    merge_dataclass_non_empty(merged.concept, updates.get("concept", {}))
    merged.style_guide.update({key: value for key, value in normalize_dict(updates.get("style_guide", {})).items() if value not in ("", None, [], {})})
    merged.world_rules = merge_dataclass_list(merged.world_rules, dataclass_list_from_dict(WorldRule, updates.get("world_rules", [])), "name")
    merged.characters = merge_dataclass_list(merged.characters, dataclass_list_from_dict(CharacterCard, updates.get("characters", [])), "name")
    merged.plot_threads = merge_dataclass_list(merged.plot_threads, dataclass_list_from_dict(PlotThread, updates.get("plot_threads", [])), "name")
    merged.timeline = merge_dataclass_list(merged.timeline, dataclass_list_from_dict(TimelineEvent, updates.get("timeline", [])), "id")
    merged.foreshadowing = merge_dataclass_list(merged.foreshadowing, dataclass_list_from_dict(ForeshadowingItem, updates.get("foreshadowing", [])), "id")
    merged.factions = merge_dict_list(merged.factions, normalize_dict_list(updates.get("factions", [])), "name")
    chapter_summaries = normalize_dict(updates.get("chapter_summaries", {}))
    for key, value in chapter_summaries.items():
        if str(value).strip():
            merged.chapter_summaries[str(key)] = str(value).strip()
    for question in normalize_str_list(updates.get("open_questions", [])):
        if question not in merged.open_questions:
            merged.open_questions.append(question)
    if updates:
        merged.version = max(1, merged.version + 1)
    return merged


def detect_bible_conflicts(bible: NovelBible, updates: dict[str, Any]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    update_characters = dataclass_list_from_dict(CharacterCard, updates.get("characters", [])) if isinstance(updates, dict) else []
    current_characters = {item.name: item for item in bible.characters if item.name}
    for item in update_characters:
        current = current_characters.get(item.name)
        if current and item.role and current.role and current.role != item.role:
            conflicts.append({"type": "character_role", "name": item.name, "current": current.role, "incoming": item.role})
    update_rules = dataclass_list_from_dict(WorldRule, updates.get("world_rules", [])) if isinstance(updates, dict) else []
    current_rules = {item.name: item for item in bible.world_rules if item.name}
    for item in update_rules:
        current = current_rules.get(item.name)
        if current and item.description and current.description and current.description != item.description:
            conflicts.append({"type": "world_rule", "name": item.name, "current": current.description, "incoming": item.description})
    summaries = normalize_dict(updates.get("chapter_summaries", {})) if isinstance(updates, dict) else {}
    for key, value in summaries.items():
        old = bible.chapter_summaries.get(str(key))
        if old and str(value).strip() and old != str(value).strip():
            conflicts.append({"type": "chapter_summary", "chapter": str(key), "current": old, "incoming": str(value).strip()})
    return conflicts


def novel_bible_json_path(project_dir: Path) -> Path:
    return project_dir / "novel_bible.json"


def novel_bible_markdown_path(project_dir: Path) -> Path:
    return project_dir / "novel_bible.md"


def dataclass_from_dict(cls: type[T], data: Any) -> T:
    if not isinstance(data, dict):
        data = {}
    values: dict[str, Any] = {}
    for item in fields(cls):
        value = data.get(item.name)
        default = field_default(item)
        values[item.name] = normalize_field_value(item.type, value, default)
    return cls(**values)


def field_default(item: Any) -> Any:
    if item.default is not MISSING:
        return item.default
    if item.default_factory is not MISSING:  # type: ignore[attr-defined]
        return item.default_factory()  # type: ignore[misc]
    return None


def dataclass_list_from_dict(cls: type[T], data: Any) -> list[T]:
    if not isinstance(data, list):
        return []
    return [dataclass_from_dict(cls, item) for item in data if isinstance(item, dict)]


def normalize_field_value(field_type: Any, value: Any, default: Any) -> Any:
    origin = get_origin(field_type)
    args = get_args(field_type)
    if value is None:
        return default if default is not None else None
    if origin is list:
        subtype = args[0] if args else str
        if not isinstance(value, list):
            return []
        if subtype is int:
            return [int(item) for item in value if str(item).strip().isdigit()]
        return [str(item) for item in value if str(item).strip()]
    if field_type is int:
        return int(value or 0)
    if field_type is dict[str, Any] or origin is dict:
        return dict(value) if isinstance(value, dict) else {}
    return value if not isinstance(value, str) else value.strip()


def merge_dataclass_non_empty(target: Any, updates: Any) -> None:
    if not is_dataclass(target) or not isinstance(updates, dict):
        return
    for item in fields(target):
        value = updates.get(item.name)
        if value not in ("", None, [], {}):
            setattr(target, item.name, normalize_field_value(item.type, value, getattr(target, item.name)))


def merge_dataclass_list(current: list[T], incoming: list[T], key: str) -> list[T]:
    result = list(current)
    index = {str(getattr(item, key, "")): pos for pos, item in enumerate(result) if str(getattr(item, key, ""))}
    for item in incoming:
        item_key = str(getattr(item, key, ""))
        if not item_key or item_key not in index:
            result.append(item)
            if item_key:
                index[item_key] = len(result) - 1
            continue
        existing = result[index[item_key]]
        merge_dataclass_non_empty(existing, asdict(item))
    return result


def merge_dict_list(current: list[dict[str, Any]], incoming: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result = [dict(item) for item in current]
    index = {str(item.get(key, "")): pos for pos, item in enumerate(result) if str(item.get(key, ""))}
    for item in incoming:
        item_key = str(item.get(key, ""))
        if item_key and item_key in index:
            result[index[item_key]].update({k: v for k, v in item.items() if v not in ("", None, [], {})})
        else:
            result.append(dict(item))
    return result


def render_object_lines(value: Any) -> list[str]:
    data = asdict(value) if is_dataclass(value) else normalize_dict(value)
    return render_mapping_lines(data)


def render_mapping_lines(data: dict[str, Any]) -> list[str]:
    if not data:
        return ["- 暂无"]
    lines = []
    for key, value in data.items():
        if value in ("", None, [], {}):
            continue
        if isinstance(value, list):
            value = "，".join(str(item) for item in value)
        lines.append(f"- {key}: {value}")
    return lines or ["- 暂无"]


def render_named_items(items: list[Any], name_field: str, detail_field: str) -> list[str]:
    if not items:
        return ["- 暂无"]
    lines = []
    for item in items:
        name = str(getattr(item, name_field, "") if is_dataclass(item) else item.get(name_field, "")).strip()
        detail = str(getattr(item, detail_field, "") if is_dataclass(item) else item.get(detail_field, "")).strip()
        lines.append(f"- {name or '未命名'}：{detail or '暂无'}")
    return lines


def normalize_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def normalize_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def normalize_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
