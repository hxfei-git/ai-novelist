"""Project-level craft memory extracted from finalized chapters."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from ai_novelist.artifacts import save_json_artifact
from ai_novelist.corpus.craft_schema import CraftEvidence, CraftNote, CraftProfile
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def extract_project_craft_memory(state: NovelState, store: LocalStore, chapter: int, adapter=None) -> CraftProfile:
    del adapter
    final_path = store.final_chapter_path(state.project_id, chapter)
    summary_path = store.chapter_summary_path(state.project_id, chapter)
    final_text = final_path.read_text(encoding="utf-8") if final_path.exists() else state.current_final_chapter
    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else state.chapter_summaries.get(str(chapter), "")
    existing = load_project_craft_memory(state.project_id, store)
    notes = list(existing.notes) if existing else []
    evidence = CraftEvidence(
        source_id=f"project_chapter_{chapter:03d}",
        work_id=state.project_id,
        chapter_id=str(chapter),
        location_label=f"本项目第 {chapter} 章定稿",
        summary=(summary or first_sentence(final_text) or "本项目已定稿章节的结构经验。")[:160],
    )
    notes.append(
        CraftNote(
            note_id=f"{state.project_id}_chapter_{chapter:03d}_memory",
            scope="project",
            facet="pacing",
            title="本项目已确立的章节推进方式",
            pattern=project_pattern_from_text(final_text, summary),
            why_it_works="来自本项目已定稿章节，优先用于保持长篇内部一致性。",
            use_when=["后续章节需要延续本项目叙事方式", "需要避免外部作者方法压过本项目风格"],
            avoid_when=["用户明确要求改变写法", "当前章节奏目标完全相反"],
            pacing_functions=["setup", "escalation", "aftermath", "unknown"],
            intensity_range=(1, 4),
            evidence=[evidence],
            tags=["project_memory", "pacing"],
        )
    )
    profile = CraftProfile(
        profile_id=f"{state.project_id}_project_craft_memory",
        scope="project",
        work_id=state.project_id,
        title=f"{state.title} Project Craft Memory",
        notes=dedupe_notes(notes)[-20:],
        metadata={"updated_at": datetime.now(UTC).isoformat(timespec="seconds"), "latest_chapter": chapter},
    )
    path = store.project_craft_memory_path(state.project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record = save_json_artifact(
        store.project_dir(state.project_id),
        path.relative_to(store.project_dir(state.project_id)).as_posix(),
        profile.to_dict(),
        "project_craft_memory",
        chapter=chapter,
        stage="project_memory",
        source_agent="project_craft_memory",
        graph="finalize",
        summary=f"{len(profile.notes)} project craft notes",
    )
    state.project_craft_memory_path = record.path
    return profile


def load_project_craft_memory(project_id: str, store: LocalStore) -> CraftProfile | None:
    path = store.project_craft_memory_path(project_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return CraftProfile.from_dict(data) if isinstance(data, dict) else None


def project_pattern_from_text(final_text: str, summary: str) -> str:
    if any(marker in final_text for marker in ("沉默", "停顿", "没有回答")):
        return "用克制反应承接事件余波，再让一个可行动线索推动下一场。"
    if any(marker in final_text for marker in ("门", "权限", "倒计时", "名单")):
        return "把外部规则压力和身份疑问绑定，让角色在限制中推进信息。"
    if summary:
        return f"延续本项目已定稿章节的推进边界：{summary[:80]}"
    return "保持每章一个主要状态变化，并避免无依据扩大冲突。"


def first_sentence(text: str) -> str:
    for marker in ("。", "！", "？", "\n"):
        if marker in text:
            return text.split(marker, 1)[0].strip()
    return text.strip()[:80]


def dedupe_notes(notes: list[CraftNote]) -> list[CraftNote]:
    seen = set()
    result = []
    for note in notes:
        if note.note_id in seen:
            continue
        seen.add(note.note_id)
        result.append(note)
    return result
