"""High-level Author Craft data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

CraftFacet = Literal[
    "premise",
    "conflict",
    "character_arc",
    "relationship",
    "scene_turn",
    "chapter_hook",
    "foreshadowing",
    "information_release",
    "pacing",
    "restraint",
    "narrative_distance",
    "dialogue",
    "atmosphere",
    "revision_strategy",
]
ProfileScope = Literal["work", "chapter", "scene", "genre", "project"]

ALLOWED_FACETS = {
    "premise",
    "conflict",
    "character_arc",
    "relationship",
    "scene_turn",
    "chapter_hook",
    "foreshadowing",
    "information_release",
    "pacing",
    "restraint",
    "narrative_distance",
    "dialogue",
    "atmosphere",
    "revision_strategy",
}
ALLOWED_SCOPES = {"work", "chapter", "scene", "genre", "project"}


@dataclass(frozen=True)
class CraftEvidence:
    source_id: str
    work_id: str
    chapter_id: str = ""
    scene_id: str = ""
    chunk_id: str = ""
    location_label: str = ""
    summary: str = ""
    short_quote: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CraftEvidence":
        quote = str(data.get("short_quote", ""))
        if len(quote) > 30:
            quote = quote[:30]
        return cls(
            source_id=str(data.get("source_id", "")),
            work_id=str(data.get("work_id", "")),
            chapter_id=str(data.get("chapter_id", "")),
            scene_id=str(data.get("scene_id", "")),
            chunk_id=str(data.get("chunk_id", "")),
            location_label=str(data.get("location_label", "")),
            summary=compact_text(str(data.get("summary", "")), 160),
            short_quote=quote,
        )


@dataclass(frozen=True)
class CraftNote:
    note_id: str
    scope: ProfileScope
    facet: CraftFacet
    title: str
    pattern: str
    why_it_works: str
    use_when: list[str]
    avoid_when: list[str]
    pacing_functions: list[str]
    intensity_range: tuple[int, int] = (1, 5)
    evidence: list[CraftEvidence] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["intensity_range"] = list(self.intensity_range)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CraftNote":
        raw_range = data.get("intensity_range", [1, 5])
        if not isinstance(raw_range, (list, tuple)) or len(raw_range) != 2:
            raw_range = [1, 5]
        facet = str(data.get("facet", "pacing"))
        scope = str(data.get("scope", "chapter"))
        return cls(
            note_id=str(data.get("note_id", "")),
            scope=scope if scope in ALLOWED_SCOPES else "chapter",  # type: ignore[arg-type]
            facet=facet if facet in ALLOWED_FACETS else "pacing",  # type: ignore[arg-type]
            title=compact_text(str(data.get("title", "")), 80),
            pattern=compact_text(str(data.get("pattern", "")), 160),
            why_it_works=compact_text(str(data.get("why_it_works", "")), 160),
            use_when=normalize_str_list(data.get("use_when", []), 8, 80),
            avoid_when=normalize_str_list(data.get("avoid_when", []), 8, 80),
            pacing_functions=normalize_str_list(data.get("pacing_functions", []), 8, 40),
            intensity_range=(max(1, int(raw_range[0])), min(5, int(raw_range[1]))),
            evidence=[CraftEvidence.from_dict(item) for item in data.get("evidence", []) if isinstance(item, dict)],
            tags=normalize_str_list(data.get("tags", []), 12, 40),
            score=float(data.get("score", 0.0) or 0.0),
        )


@dataclass(frozen=True)
class CraftProfile:
    profile_id: str
    scope: ProfileScope
    work_id: str = ""
    title: str = ""
    author: str = ""
    genre: list[str] = field(default_factory=list)
    notes: list[CraftNote] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "scope": self.scope,
            "work_id": self.work_id,
            "title": self.title,
            "author": self.author,
            "genre": self.genre,
            "notes": [note.to_dict() for note in self.notes],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CraftProfile":
        scope = str(data.get("scope", "chapter"))
        return cls(
            profile_id=str(data.get("profile_id", "")),
            scope=scope if scope in ALLOWED_SCOPES else "chapter",  # type: ignore[arg-type]
            work_id=str(data.get("work_id", "")),
            title=str(data.get("title", "")),
            author=str(data.get("author", "")),
            genre=normalize_str_list(data.get("genre", []), 8, 40),
            notes=[CraftNote.from_dict(item) for item in data.get("notes", []) if isinstance(item, dict)],
            metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata", {}), dict) else {},
        )


@dataclass(frozen=True)
class CraftContext:
    purpose: str
    chapter: int | None
    stage: str
    query_terms: list[str]
    selected_notes: list[CraftNote]
    sources: list[CraftEvidence]
    max_chars: int
    source_profile_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StageCraftBrief:
    project_id: str
    purpose: str
    chapter: int | None
    stage: str
    content: str
    source_profile_ids: list[str]
    source_note_ids: list[str]
    source_evidence: list[CraftEvidence]
    digest: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_sources_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "purpose": self.purpose,
            "chapter": self.chapter,
            "stage": self.stage,
            "digest": self.digest,
            "source_profile_ids": self.source_profile_ids,
            "source_note_ids": self.source_note_ids,
            "source_evidence": [item.to_dict() for item in self.source_evidence],
            "metadata": dict(self.metadata),
        }


def normalize_str_list(value: Any, limit: int = 20, max_chars: int = 120) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []
    result: list[str] = []
    for item in items:
        text = compact_text(str(item), max_chars)
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def compact_text(text: str, max_chars: int) -> str:
    cleaned = " ".join(text.split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max(1, max_chars - 1)].rstrip() + "…"
