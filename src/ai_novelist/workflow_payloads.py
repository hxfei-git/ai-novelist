"""Typed helpers for workflow payloads stored in director_task_args."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from ai_novelist.state import NovelState


def set_task_arg(state: NovelState, key: str, value: Any) -> None:
    state.director_task_args[str(key)] = value


def get_task_arg_str(state: NovelState, key: str, default: str = "") -> str:
    value = state.director_task_args.get(key, default)
    return str(value or default).strip()


def get_task_arg_int(state: NovelState, key: str, default: int = 0) -> int:
    value = state.director_task_args.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_task_arg_dict(state: NovelState, key: str) -> dict[str, Any]:
    value = state.director_task_args.get(key)
    return dict(value) if isinstance(value, dict) else {}


def get_task_arg_list(state: NovelState, key: str) -> list[Any]:
    value = state.director_task_args.get(key)
    return list(value) if isinstance(value, list) else []


@dataclass(frozen=True)
class ChapterBatchPayload:
    volume: int
    requested_count: int | None
    chapters: list[int]
    run_id: str


def set_chapter_batch_payload(
    state: NovelState,
    *,
    volume: int,
    requested_count: int | None = None,
    chapters: Iterable[int] | str | None = None,
    run_id: str = "",
) -> None:
    state.director_task_args["volume"] = int(volume)
    if requested_count is not None:
        state.director_task_args["requested_count"] = int(requested_count)
    if chapters is not None:
        if isinstance(chapters, str):
            chapter_text = chapters
        else:
            chapter_text = ",".join(str(int(item)) for item in chapters)
        if chapter_text.strip():
            state.director_task_args["chapters"] = chapter_text.strip()
    if run_id:
        state.director_task_args["batch_run_id"] = run_id


def chapter_batch_payload(state: NovelState) -> ChapterBatchPayload:
    requested = state.director_task_args.get("requested_count")
    try:
        requested_count = int(requested) if requested is not None else None
    except (TypeError, ValueError):
        requested_count = None
    return ChapterBatchPayload(
        volume=get_task_arg_int(state, "volume", 1),
        requested_count=requested_count,
        chapters=parse_chapter_selector(state.director_task_args.get("chapters")),
        run_id=get_task_arg_str(state, "batch_run_id"),
    )


def parse_chapter_selector(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        chapters = {int(item) for item in value if str(item).strip().isdigit()}
        return sorted(chapter for chapter in chapters if chapter > 0)
    text = str(value or "").strip()
    if not text:
        return []
    chapters: set[int] = set()
    for part in re.split(r"[,，\s]+", text):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start_raw, end_raw = item.split("-", 1)
            if start_raw.strip().isdigit() and end_raw.strip().isdigit():
                start = int(start_raw)
                end = int(end_raw)
                chapters.update(range(min(start, end), max(start, end) + 1))
        elif item.isdigit():
            chapters.add(int(item))
    return sorted(chapter for chapter in chapters if chapter > 0)
