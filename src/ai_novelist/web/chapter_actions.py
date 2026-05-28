"""Chapter generation and chapter payload actions for the Web API."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_novelist.adapters.base import AgentAdapter
from ai_novelist.graph_volume_write import build_volume_write_graph, parse_chapter_override
from ai_novelist.outline.chapter_outline_structure import (
    chinese_number_to_int,
    current_volume_spec,
    volume_label,
)
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError, summarize_text
from ai_novelist.web.chapter_outline_actions import chapter_outline_workspace_payload
from ai_novelist.web.outline_actions import strip_markdown_heading
from ai_novelist.workflow_payloads import set_chapter_batch_payload

ProgressFunc = Callable[[str, str], None]


@dataclass(frozen=True)
class WebChapter:
    chapter: int
    title: str
    path: str
    source: str
    version: int | None
    updated_at: str
    summary: str


def generate_chapter_batch(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    *,
    volume: int = 1,
    requested_count: int | None = None,
    chapters: str | Iterable[int] | None = None,
    max_workers: int = 3,
    progress: ProgressFunc | None = None,
) -> NovelState:
    import os

    if volume < 1:
        raise LocalStoreError("Volume must be greater than 0")
    state = store.load_state(project_id)
    state.director_action = "write_volume"
    state.director_task_args = {}
    set_chapter_batch_payload(state, volume=volume)
    if requested_count is not None:
        workspace = chapter_batch_workspace_payload(store, project_id, volume)
        remaining_numbers = list(workspace.get("remaining_chapter_numbers") or [])
        requested_total = max(1, min(int(requested_count or 1), len(remaining_numbers)))
        selected_numbers = remaining_numbers[:requested_total]
        if not selected_numbers:
            raise LocalStoreError(f"第 {volume} 卷没有剩余章节可生成")
        os.environ["AI_NOVELIST_PARALLEL_AGENTS"] = "1"
        os.environ["AI_NOVELIST_MAX_PARALLEL_AGENTS"] = str(max(1, requested_total))
        set_chapter_batch_payload(state, volume=volume, requested_count=requested_total, chapters=selected_numbers)
        state.user_request = f"批量生成第 {volume} 卷 {requested_total} 章"
    else:
        os.environ["AI_NOVELIST_PARALLEL_AGENTS"] = "1"
        os.environ["AI_NOVELIST_MAX_PARALLEL_AGENTS"] = str(max(1, min(int(max_workers or 3), 8)))
        chapter_text = normalize_chapter_selector(chapters)
        if chapter_text:
            set_chapter_batch_payload(state, volume=volume, chapters=chapter_text)
        state.user_request = f"批量生成第 {volume} 卷"
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    result = build_volume_write_graph(adapter, store, progress=progress).invoke(state.to_dict())
    return NovelState.from_dict(result)


def latest_volume_batch_manifest(store: LocalStore, project_id: str, volume: int) -> dict[str, Any]:
    root = store.project_dir(project_id) / "chapters" / "batches" / f"volume_{volume:03d}"
    if not root.exists():
        return {}
    candidates = sorted((path for path in root.glob('*/manifest.json') if path.is_file()), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    return {}


def extract_volume_chapter_numbers(volume_outline: str, spec: Any | None = None) -> list[int]:
    content = str(volume_outline or "").strip()
    if not content:
        return []
    numbers: list[int] = []
    seen: set[int] = set()
    for match in re.finditer(r"第\s*([一二两三四五六七八九十\d]+)\s*章", content):
        number = chinese_number_to_int(match.group(1))
        if number and number not in seen:
            seen.add(number)
            numbers.append(number)
    if numbers:
        return numbers
    chapter_range = str(getattr(spec, "chapter_range", "") or "").strip()
    if chapter_range:
        return parse_chapter_override(chapter_range)
    return []


def chapter_batch_workspace_payload(store: LocalStore, project_id: str, volume: int) -> dict[str, Any]:
    workspace = chapter_outline_workspace_payload(store, project_id, selected_volume_index=volume)
    selected_volume = workspace["selected_volume"]
    selected_index = int(selected_volume.get("index") or volume)
    spec = current_volume_spec(
        {
            "current_volume_index": selected_index,
            "volume_specs": list(workspace.get("volume_specs") or []),
        }
    )
    volume_outline = str(selected_volume.get("content") or "")
    planned_chapter_numbers = extract_volume_chapter_numbers(volume_outline, spec)
    generated_items = list_chapters(store, project_id, volume=selected_index)
    if planned_chapter_numbers and not generated_items:
        planned_set = set(planned_chapter_numbers)
        generated_items = [item for item in list_chapters(store, project_id) if int(item.get("chapter") or 0) in planned_set]
    generated_set: set[int] = set()
    normalized_generated_items: list[dict[str, Any]] = []
    for item in generated_items:
        chapter = int(item.get("chapter") or 0)
        if chapter in generated_set:
            continue
        generated_set.add(chapter)
        normalized_generated_items.append(item)
    remaining_chapter_numbers = [chapter for chapter in planned_chapter_numbers if chapter not in generated_set]
    selected_name = str(selected_volume.get("name") or "").strip()
    return {
        "volume_index": selected_index,
        "volume_label": str(selected_volume.get("label") or spec.label or volume_label(selected_index)),
        "volume_name": selected_name,
        "total_chapters": len(planned_chapter_numbers),
        "generated_chapters": len(normalized_generated_items),
        "remaining_chapters": len(remaining_chapter_numbers),
        "next_chapter_number": remaining_chapter_numbers[0] if remaining_chapter_numbers else None,
        "planned_chapter_numbers": planned_chapter_numbers,
        "remaining_chapter_numbers": remaining_chapter_numbers,
        "chapters": normalized_generated_items,
    }


def list_chapters(store: LocalStore, project_id: str, volume: int | None = None) -> list[dict[str, Any]]:
    store.load_state(project_id)
    if volume is None:
        return [
            chapter_payload(store, project_id, chapter, path, content, include_content=False)
            for chapter, path, content in collect_latest_chapters(store, project_id)
        ]
    manifest = latest_volume_batch_manifest(store, project_id, volume)
    latest = manifest.get('chapters') if isinstance(manifest.get('chapters'), dict) else {}
    chapter_items: list[dict[str, Any]] = []
    for raw_chapter, raw_item in sorted(latest.items(), key=lambda item: int(item[0])):
        try:
            chapter = int(raw_chapter)
        except (TypeError, ValueError):
            continue
        path_value = str(raw_item.get('path') or '').strip() if isinstance(raw_item, dict) else ''
        path = store.project_dir(project_id) / path_value if path_value else latest_chapter_path(store, project_id, chapter)
        if not path or not path.exists():
            continue
        chapter_items.append(chapter_payload(store, project_id, chapter, path, path.read_text(encoding='utf-8'), include_content=False))
    return chapter_items


def load_chapter_payload(store: LocalStore, project_id: str, chapter: int) -> dict[str, Any]:
    if chapter < 1:
        raise LocalStoreError("Chapter must be greater than 0")
    store.load_state(project_id)
    path = latest_chapter_path(store, project_id, chapter)
    if not path:
        raise LocalStoreError(f"Chapter does not exist: {chapter}")
    return chapter_payload(store, project_id, chapter, path, path.read_text(encoding="utf-8"), include_content=True)


def normalize_chapter_selector(chapters: str | Iterable[int] | None) -> str:
    if chapters is None:
        return ""
    if isinstance(chapters, str):
        return chapters.strip()
    values = sorted({int(item) for item in chapters if int(item) > 0})
    return ",".join(str(item) for item in values)


def collect_latest_chapters(store: LocalStore, project_id: str) -> list[tuple[int, Path, str]]:
    chapters: list[tuple[int, Path, str]] = []
    root = store.chapters_dir(project_id)
    if not root.exists():
        return chapters
    chapter_numbers = set()
    for path in root.glob("chapter_*.md"):
        match = re.fullmatch(r"chapter_(\d{3})\.md", path.name)
        if match:
            chapter_numbers.add(int(match.group(1)))
    for path in root.glob("chapter_*"):
        if path.is_dir():
            match = re.fullmatch(r"chapter_(\d{3})", path.name)
            if match:
                chapter_numbers.add(int(match.group(1)))
    for chapter in sorted(chapter_numbers):
        path = latest_chapter_path(store, project_id, chapter)
        if path and path.exists():
            chapters.append((chapter, path, path.read_text(encoding="utf-8")))
    return chapters


def chapter_payload(store: LocalStore, project_id: str, chapter: int, path: Path, content: str, *, include_content: bool) -> dict[str, Any]:
    source, version = chapter_source(store, project_id, chapter, path)
    relative = path.relative_to(store.project_dir(project_id)).as_posix()
    payload = WebChapter(
        chapter=chapter,
        title=chapter_title(chapter, content),
        path=relative,
        source=source,
        version=version,
        updated_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(timespec="seconds"),
        summary=summarize_text(strip_markdown_heading(content), max_chars=180),
    ).__dict__
    if include_content:
        payload["content"] = content
    return payload


def chapter_source(store: LocalStore, project_id: str, chapter: int, path: Path) -> tuple[str, int | None]:
    if path == store.final_chapter_path(project_id, chapter):
        return "final", None
    match = re.fullmatch(r"draft_v(\d+)\.md", path.name)
    if match:
        return "draft", int(match.group(1))
    return "legacy", None


def chapter_title(chapter: int, content: str) -> str:
    for line in content.splitlines():
        match = re.match(r"^\s*#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return f"第 {chapter} 章"


def latest_chapter_path(store: LocalStore, project_id: str, chapter: int) -> Path | None:
    final = store.final_chapter_path(project_id, chapter)
    if final.exists():
        return final
    drafts: list[tuple[int, Path]] = []
    chapter_dir = store.chapter_artifact_dir(project_id, chapter)
    if chapter_dir.exists():
        for path in chapter_dir.glob("draft_v*.md"):
            match = re.fullmatch(r"draft_v(\d+)\.md", path.name)
            if match:
                drafts.append((int(match.group(1)), path))
    if drafts:
        return max(drafts, key=lambda item: item[0])[1]
    legacy = store.chapter_path(project_id, chapter)
    return legacy if legacy.exists() else None


def load_latest_chapter_text(store: LocalStore, project_id: str, chapter: int) -> str:
    path = latest_chapter_path(store, project_id, chapter)
    return path.read_text(encoding="utf-8") if path else ""


def next_draft_version(store: LocalStore, project_id: str, chapter: int) -> int:
    for version in range(50, 0, -1):
        if store.chapter_draft_path(project_id, chapter, version).exists():
            return version + 1
    return 1


def fallback_repair_text(chapter: int, draft: str, issue: str) -> str:
    base = draft.strip() or f"# 第 {chapter} 章\n\n"
    return f"{base}\n\n<!-- global consistency repair: {issue} -->\n"
