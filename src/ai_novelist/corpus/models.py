"""Low-level corpus models for the Author Craft Layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CorpusWork:
    work_id: str
    title: str
    author: str = ""
    genre: list[str] = field(default_factory=list)
    source_path: str = ""
    sha256: str = ""
    char_count: int = 0
    encoding: str = "utf-8"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CorpusWork":
        return cls(
            work_id=str(data.get("work_id", "")),
            title=str(data.get("title", "")),
            author=str(data.get("author", "")),
            genre=[str(item) for item in data.get("genre", []) if str(item).strip()],
            source_path=str(data.get("source_path", "")),
            sha256=str(data.get("sha256", "")),
            char_count=int(data.get("char_count", 0) or 0),
            encoding=str(data.get("encoding", "utf-8")),
            metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata", {}), dict) else {},
        )


@dataclass(frozen=True)
class CorpusChapter:
    chapter_id: str
    work_id: str
    chapter_index: int
    title: str
    char_start: int
    char_end: int
    role_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CorpusChapter":
        return cls(
            chapter_id=str(data.get("chapter_id", "")),
            work_id=str(data.get("work_id", "")),
            chapter_index=int(data.get("chapter_index", 0) or 0),
            title=str(data.get("title", "")),
            char_start=int(data.get("char_start", 0) or 0),
            char_end=int(data.get("char_end", 0) or 0),
            role_hint=str(data.get("role_hint", "")),
        )


@dataclass(frozen=True)
class CorpusScene:
    scene_id: str
    work_id: str
    chapter_id: str
    scene_index: int
    char_start: int
    char_end: int
    position: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CorpusScene":
        return cls(
            scene_id=str(data.get("scene_id", "")),
            work_id=str(data.get("work_id", "")),
            chapter_id=str(data.get("chapter_id", "")),
            scene_index=int(data.get("scene_index", 0) or 0),
            char_start=int(data.get("char_start", 0) or 0),
            char_end=int(data.get("char_end", 0) or 0),
            position=str(data.get("position", "")),
        )


@dataclass(frozen=True)
class RetrievalChunk:
    chunk_id: str
    work_id: str
    chapter_id: str
    scene_id: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    chapter_index: int
    chapter_title: str
    position: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrievalChunk":
        return cls(
            chunk_id=str(data.get("chunk_id", "")),
            work_id=str(data.get("work_id", "")),
            chapter_id=str(data.get("chapter_id", "")),
            scene_id=str(data.get("scene_id", "")),
            chunk_index=int(data.get("chunk_index", 0) or 0),
            text=str(data.get("text", "")),
            char_start=int(data.get("char_start", 0) or 0),
            char_end=int(data.get("char_end", 0) or 0),
            chapter_index=int(data.get("chapter_index", 0) or 0),
            chapter_title=str(data.get("chapter_title", "")),
            position=str(data.get("position", "")),
            tags=[str(item) for item in data.get("tags", []) if str(item).strip()],
            metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata", {}), dict) else {},
        )
