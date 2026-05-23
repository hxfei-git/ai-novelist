"""Chinese novel chapter, scene, and chunk splitting."""

from __future__ import annotations

import re
from dataclasses import dataclass


CHAPTER_PATTERNS = [
    r"^\s*第[一二三四五六七八九十百千万零〇两\d]+[章节回卷部].*$",
    r"^\s*(序章|楔子|引子|尾声|终章|番外.*).*$",
    r"^\s*Chapter\s+\d+.*$",
]
CHAPTER_RE = re.compile("|".join(f"(?:{pattern})" for pattern in CHAPTER_PATTERNS), re.MULTILINE | re.IGNORECASE)
SCENE_RE = re.compile(r"^\s*(?:\*{3,}|-{3,}|—{2,}|[0-9]{1,2}[:：][0-9]{2}.*|[一二三四五六七八九十]+[、.].*)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ChapterSpan:
    title: str
    start: int
    end: int
    content_start: int


@dataclass(frozen=True)
class SceneSpan:
    start: int
    end: int
    position: str


@dataclass(frozen=True)
class ChunkSpan:
    start: int
    end: int
    text: str


def split_chapters(text: str) -> list[ChapterSpan]:
    matches = list(CHAPTER_RE.finditer(text))
    if not matches:
        return [ChapterSpan(title="全文", start=0, end=len(text), content_start=0)] if text else []
    chapters: list[ChapterSpan] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = match.group(0).strip() or f"第 {index + 1} 章"
        chapters.append(ChapterSpan(title=title, start=match.start(), end=end, content_start=match.end()))
    return chapters


def split_scenes(chapter_text: str) -> list[SceneSpan]:
    matches = list(SCENE_RE.finditer(chapter_text))
    if not matches:
        return [SceneSpan(0, len(chapter_text), "scene_full")] if chapter_text else []
    boundaries = [0]
    for match in matches:
        if match.start() > 0:
            boundaries.append(match.end())
    boundaries.append(len(chapter_text))
    spans: list[SceneSpan] = []
    for index, start in enumerate(boundaries[:-1]):
        end = boundaries[index + 1]
        if end <= start:
            continue
        spans.append(SceneSpan(start=start, end=end, position=scene_position(index, len(boundaries) - 1)))
    return spans or [SceneSpan(0, len(chapter_text), "scene_full")]


def chunk_scene(
    scene_text: str,
    target_chars: int = 2400,
    overlap_chars: int = 300,
    min_chunk_chars: int = 800,
    max_chunk_chars: int = 3600,
) -> list[ChunkSpan]:
    if not scene_text:
        return []
    if len(scene_text) <= max_chunk_chars:
        return [ChunkSpan(0, len(scene_text), scene_text)]
    spans: list[ChunkSpan] = []
    start = 0
    while start < len(scene_text):
        hard_end = min(len(scene_text), start + target_chars)
        end = choose_chunk_end(scene_text, start, hard_end, max_chunk_chars=max_chunk_chars)
        if end - start < min_chunk_chars and end < len(scene_text):
            end = min(len(scene_text), start + min_chunk_chars)
        spans.append(ChunkSpan(start, end, scene_text[start:end]))
        if end >= len(scene_text):
            break
        start = max(0, end - overlap_chars)
        if spans and start <= spans[-1].start:
            start = end
    return spans


def choose_chunk_end(text: str, start: int, preferred_end: int, max_chunk_chars: int) -> int:
    search_end = min(len(text), start + max_chunk_chars)
    window = text[start:search_end]
    relative = preferred_end - start
    candidates = [window.rfind(mark, 0, relative + 1) for mark in ("\n\n", "\n", "。", "！", "？")]
    best = max(candidates)
    if best > 0:
        return start + best + 1
    return min(preferred_end, len(text))


def scene_position(index: int, total: int) -> str:
    if total <= 1:
        return "scene_full"
    if index == 0:
        return "scene_opening"
    if index == total - 1:
        return "scene_ending"
    return "scene_middle"
