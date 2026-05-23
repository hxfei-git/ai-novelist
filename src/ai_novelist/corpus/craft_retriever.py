"""Keyword-based Author Craft retrieval."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ai_novelist.corpus.craft_query_planner import CraftQuery
from ai_novelist.corpus.craft_schema import CraftContext, CraftEvidence, CraftNote, CraftProfile
from ai_novelist.corpus.index import load_profiles


def retrieve_craft_context(index_dir: str | Path, query: CraftQuery, max_notes: int = 8) -> CraftContext:
    if query.craft_mode == "off":
        return CraftContext(query.purpose, query.chapter, query.stage, query.query_terms, [], [], 0, [])
    profiles = list(load_profiles(index_dir))
    project_profile = load_project_memory_profile(query.project_memory_path)
    if project_profile is not None:
        profiles.insert(0, project_profile)
    scored: list[tuple[float, int, CraftProfile, CraftNote]] = []
    for profile_index, profile in enumerate(profiles):
        if query.profile_ids and profile.profile_id not in query.profile_ids:
            continue
        if profile.work_id and profile.work_id in query.exclude_work_ids:
            continue
        for note in profile.notes:
            score = score_note(profile, note, query)
            if score <= 0:
                continue
            priority = 0 if profile.scope == "project" else profile_index + 1
            scored.append((score, -priority, profile, note))
    scored.sort(key=lambda item: (item[0], item[1], item[3].note_id), reverse=True)
    selected = diversify_notes(scored, max_notes=max_notes or query.max_notes)
    notes = [note for _profile, note in selected]
    evidence = flatten_evidence(notes)
    profile_ids = [profile.profile_id for profile, _note in selected]
    return CraftContext(
        purpose=query.purpose,
        chapter=query.chapter,
        stage=query.stage,
        query_terms=query.query_terms,
        selected_notes=notes,
        sources=evidence,
        max_chars=0,
        source_profile_ids=profile_ids,
    )


def score_note(profile: CraftProfile, note: CraftNote, query: CraftQuery) -> float:
    score = 0.0
    if note.facet in query.facets:
        score += 3.0
    if profile.scope == "project":
        score += 5.0
    if profile.genre and set(profile.genre) & set(query.genre):
        score += 2.0
    if query.purpose in note.tags or query.stage in note.tags:
        score += 2.0
    function = str(query.pacing_target.get("function", "unknown"))
    if function in note.pacing_functions or "unknown" in note.pacing_functions:
        score += 2.0
    if note.intensity_range[0] <= query.intensity <= note.intensity_range[1]:
        score += 2.0
    else:
        if query.intensity <= 2 and note.intensity_range[0] > 2:
            return 0.0
        score -= 1.0
    score += keyword_score(note, query.query_terms)
    if profile.scope in {"work", "chapter", "scene"}:
        score += {"work": 0.3, "chapter": 0.2, "scene": 0.1}[profile.scope]
    if note.facet == "chapter_hook" and query.intensity <= 2 and str(query.pacing_target.get("hook_strength")) in {"none", "soft"}:
        score -= 3.0
    return score + note.score


def keyword_score(note: CraftNote, terms: list[str]) -> float:
    haystack = " ".join([note.title, note.pattern, note.why_it_works, " ".join(note.tags), " ".join(note.use_when)])
    score = 0.0
    for term in terms:
        if len(term) < 2:
            continue
        if term in haystack:
            score += 0.8
    return min(score, 5.0)


def diversify_notes(scored: list[tuple[float, int, CraftProfile, CraftNote]], max_notes: int) -> list[tuple[CraftProfile, CraftNote]]:
    selected: list[tuple[CraftProfile, CraftNote]] = []
    per_work: dict[str, int] = defaultdict(int)
    per_chapter: dict[str, int] = defaultdict(int)
    seen_note_shapes: set[tuple[str, str]] = set()
    scopes = set()
    for _score, _priority, profile, note in scored:
        work_id = profile.work_id or "project"
        chapter_id = ""
        if note.evidence:
            chapter_id = note.evidence[0].chapter_id
        shape = (note.title, note.pattern)
        if shape in seen_note_shapes and profile.scope != "project":
            continue
        if per_work[work_id] >= 3 and profile.scope != "project":
            continue
        if chapter_id and per_chapter[chapter_id] >= 2:
            continue
        selected.append((profile, note))
        seen_note_shapes.add(shape)
        per_work[work_id] += 1
        if chapter_id:
            per_chapter[chapter_id] += 1
        scopes.add(profile.scope)
        if len(selected) >= max_notes:
            break
    if len(scopes) < 2:
        for _score, _priority, profile, note in scored:
            if profile.scope in scopes:
                continue
            if all(existing.note_id != note.note_id for _p, existing in selected):
                selected.append((profile, note))
                scopes.add(profile.scope)
            if len(selected) >= max_notes or len(scopes) >= 3:
                break
    return selected[:max_notes]


def flatten_evidence(notes: list[CraftNote]) -> list[CraftEvidence]:
    seen = set()
    evidence: list[CraftEvidence] = []
    for note in notes:
        for item in note.evidence:
            key = item.source_id or item.chunk_id
            if key in seen:
                continue
            seen.add(key)
            evidence.append(item)
    return evidence


def load_project_memory_profile(path: str) -> CraftProfile | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    profile = CraftProfile.from_dict(data)
    return profile if profile.notes else None
