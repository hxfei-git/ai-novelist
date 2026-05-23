"""Stage-aware Author Craft query planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


PURPOSE_TO_FACETS = {
    "outline_stage": ["premise", "conflict", "character_arc", "information_release", "pacing"],
    "chapter_planning": ["chapter_hook", "conflict", "character_arc", "information_release", "pacing", "restraint"],
    "scene_design": ["scene_turn", "conflict", "relationship", "information_release", "atmosphere"],
    "drafting": ["narrative_distance", "dialogue", "atmosphere", "information_release", "pacing"],
    "review": ["conflict", "character_arc", "chapter_hook", "pacing", "restraint"],
    "revision": ["revision_strategy", "character_arc", "information_release", "foreshadowing", "pacing"],
}
LOW_INTENSITY_FUNCTIONS = {"breather", "aftermath", "setup", "resolution"}
HIGH_INTENSITY_FUNCTIONS = {"twist", "climax", "reveal", "crisis"}


@dataclass(frozen=True)
class CraftQuery:
    purpose: str
    chapter: int | None = None
    stage: str = ""
    facets: list[str] = field(default_factory=list)
    query_terms: list[str] = field(default_factory=list)
    genre: list[str] = field(default_factory=list)
    pacing_target: dict[str, Any] = field(default_factory=dict)
    intensity: int = 3
    craft_mode: str = "off"
    index_dir: Path = Path("corpus_index")
    project_memory_path: str = ""
    profile_ids: list[str] = field(default_factory=list)
    exclude_work_ids: list[str] = field(default_factory=list)
    max_notes: int = 8


def plan_craft_query(
    state: NovelState,
    store: LocalStore | None,
    purpose: str,
    chapter: int | None = None,
    stage: str | None = None,
    pacing_target: dict[str, Any] | None = None,
) -> CraftQuery:
    options = dict(getattr(state, "craft_options", {}) or {})
    target = normalize_pacing_target(pacing_target or state.director_task_args.get("pacing_target"))
    facets = list(PURPOSE_TO_FACETS.get(purpose, ["pacing", "information_release"]))
    function = str(target.get("function", "unknown")).lower()
    intensity = int(target.get("intensity", 3) or 3)
    if function in LOW_INTENSITY_FUNCTIONS or intensity <= 2:
        boost_front(facets, ["restraint", "atmosphere", "relationship", "pacing"])
        facets = [facet for facet in facets if facet != "chapter_hook"] + (["chapter_hook"] if purpose == "chapter_planning" else [])
    if function in HIGH_INTENSITY_FUNCTIONS or intensity >= 4:
        boost_front(facets, ["chapter_hook", "conflict", "information_release", "scene_turn"])
    terms = build_query_terms(state, purpose, chapter, stage, target)
    index_dir = Path(str(options.get("corpus_index_dir") or "corpus_index")).expanduser()
    project_memory_path = ""
    if store is not None:
        project_memory_path = str(store.project_craft_memory_path(state.project_id))
    else:
        project_memory_path = str(options.get("project_craft_memory_path", ""))
    return CraftQuery(
        purpose=purpose,
        chapter=chapter,
        stage=stage or state.outline_stage or "",
        facets=dedupe(facets),
        query_terms=terms,
        genre=normalize_str_list(options.get("craft_genre") or state.director_task_args.get("craft_genre") or []),
        pacing_target=target,
        intensity=max(1, min(5, intensity)),
        craft_mode=str(getattr(state, "craft_mode", "off") or options.get("craft_mode") or "off"),
        index_dir=index_dir,
        project_memory_path=project_memory_path,
        profile_ids=normalize_str_list(options.get("craft_profile") or options.get("profile_ids") or []),
        exclude_work_ids=normalize_str_list(options.get("craft_exclude_work") or options.get("exclude_work_ids") or []),
        max_notes=int(options.get("craft_max_notes") or 8),
    )


def normalize_pacing_target(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    return {
        "function": str(value.get("function") or "unknown"),
        "intensity": max(1, min(5, int(value.get("intensity") or 3))),
        "hook_strength": str(value.get("hook_strength") or "medium"),
        "conflict_mode": str(value.get("conflict_mode") or value.get("tension_source") or "mixed"),
        "must_not": normalize_str_list(value.get("must_not") or []),
        "defer_to_later": normalize_str_list(value.get("defer_to_later") or []),
    }


def build_query_terms(
    state: NovelState,
    purpose: str,
    chapter: int | None,
    stage: str | None,
    pacing_target: dict[str, Any],
) -> list[str]:
    text = " ".join(
        item
        for item in [
            state.title,
            state.idea,
            state.user_request,
            state.outline[:800],
            state.current_chapter_card[:800],
            purpose,
            stage or "",
            str(chapter or ""),
            str(pacing_target.get("function", "")),
            str(pacing_target.get("hook_strength", "")),
        ]
        if item
    )
    terms = []
    for marker in ("悬疑", "科幻", "仙侠", "都市", "失忆", "月球", "案件", "成长", "余波", "反转", "对白", "氛围", "钩子"):
        if marker in text:
            terms.append(marker)
    terms.extend(str(text).replace("\n", " ").split()[:20])
    return dedupe([item.strip("，。,.：:") for item in terms if item.strip("，。,.：:")])[:30]


def boost_front(facets: list[str], boosted: list[str]) -> None:
    for facet in reversed(boosted):
        if facet in facets:
            facets.remove(facet)
        facets.insert(0, facet)


def normalize_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        if "," in value:
            items = value.split(",")
        else:
            items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
