"""Craft profile extraction entry points."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ai_novelist.adapters.base import AgentAdapter
from ai_novelist.corpus.craft_schema import CraftProfile
from ai_novelist.corpus.index import load_chunks, load_works, write_jsonl
from ai_novelist.corpus.mock import build_mock_profiles


@dataclass(frozen=True)
class CraftExtractionResult:
    index_dir: Path
    work_profiles: int
    chapter_profiles: int
    scene_profiles: int
    genre_profiles: int
    dry_run: bool = False


def extract_craft_profiles(
    index_dir: str | Path,
    adapter: AgentAdapter | None = None,
    mock: bool = True,
    limit_files: int | None = None,
    limit_chunks: int | None = None,
    work_id: str = "",
    dry_run: bool = False,
    resume: bool = True,
) -> CraftExtractionResult:
    del adapter, resume
    root = Path(index_dir).expanduser()
    works = list(load_works(root))
    chunks = list(load_chunks(root))
    if work_id:
        works = [item for item in works if item.work_id == work_id]
        chunks = [item for item in chunks if item.work_id == work_id]
    if limit_files is not None:
        allowed = {item.work_id for item in works[: max(0, limit_files)]}
        works = [item for item in works if item.work_id in allowed]
        chunks = [item for item in chunks if item.work_id in allowed]
    if limit_chunks is not None:
        chunks = chunks[: max(0, limit_chunks)]
    # v1 intentionally uses deterministic rules for both mock and fallback real mode.
    work_profiles, chapter_profiles, scene_profiles, genre_profiles = build_mock_profiles(works, chunks)
    if dry_run:
        return CraftExtractionResult(root, len(work_profiles), len(chapter_profiles), len(scene_profiles), len(genre_profiles), True)
    write_profiles(root, work_profiles, chapter_profiles, scene_profiles, genre_profiles)
    return CraftExtractionResult(root, len(work_profiles), len(chapter_profiles), len(scene_profiles), len(genre_profiles), False)


def write_profiles(
    index_dir: Path,
    work_profiles: list[CraftProfile],
    chapter_profiles: list[CraftProfile],
    scene_profiles: list[CraftProfile],
    genre_profiles: list[CraftProfile],
) -> None:
    root = index_dir / "craft_profiles"
    for path in (root / "works", root / "chapters", root / "scenes", root / "genres"):
        path.mkdir(parents=True, exist_ok=True)
    for profile in work_profiles:
        (root / "works" / f"{profile.work_id}.json").write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    by_work: dict[str, list[dict]] = {}
    for profile in chapter_profiles:
        by_work.setdefault(profile.work_id, []).append(profile.to_dict())
    for work_id, rows in by_work.items():
        write_jsonl(root / "chapters" / f"{work_id}.jsonl", rows)
    by_work = {}
    for profile in scene_profiles:
        by_work.setdefault(profile.work_id, []).append(profile.to_dict())
    for work_id, rows in by_work.items():
        write_jsonl(root / "scenes" / f"{work_id}.jsonl", rows)
    for profile in genre_profiles:
        name = (profile.genre[0] if profile.genre else profile.profile_id).replace("/", "_")
        (root / "genres" / f"{name}.json").write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
