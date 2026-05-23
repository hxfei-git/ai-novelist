"""JSONL corpus index build and load helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Iterator

from ai_novelist.corpus.chunker import chunk_scene, split_chapters, split_scenes
from ai_novelist.corpus.encoding import read_text_with_fallback
from ai_novelist.corpus.ingest import scan_corpus
from ai_novelist.corpus.models import CorpusChapter, CorpusScene, CorpusWork, RetrievalChunk
from ai_novelist.corpus.quality_report import render_quality_report


@dataclass(frozen=True)
class CorpusIndexResult:
    index_dir: Path
    works: int
    chapters: int
    scenes: int
    chunks: int
    skipped_files: int
    errors: int


def build_corpus_index(corpus_dir: str | Path, index_dir: str | Path, incremental: bool = True) -> CorpusIndexResult:
    del incremental
    corpus_root = Path(corpus_dir).expanduser()
    output_dir = Path(index_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    files = scan_corpus(corpus_root)
    previous_manifest = load_manifest(output_dir)
    works: list[CorpusWork] = []
    chapters: list[CorpusChapter] = []
    scenes: list[CorpusScene] = []
    chunks: list[RetrievalChunk] = []
    errors: list[dict] = []
    skipped_files = 0
    manifest_files: dict[str, dict] = {}

    for corpus_file in files:
        previous = previous_manifest.get("files", {}).get(corpus_file.relative_path, {})
        if previous.get("sha256") == corpus_file.sha256:
            skipped_files += 1
        try:
            text, encoding = read_text_with_fallback(corpus_file.path)
        except Exception as exc:
            errors.append({"path": corpus_file.relative_path, "error": str(exc)})
            manifest_files[corpus_file.relative_path] = file_manifest_entry(corpus_file, "error")
            continue
        work = CorpusWork(
            work_id=corpus_file.work_id,
            title=str(corpus_file.metadata.get("title") or corpus_file.path.stem),
            author=str(corpus_file.metadata.get("author", "")),
            genre=[str(item) for item in corpus_file.metadata.get("genre", []) if str(item).strip()],
            source_path=corpus_file.relative_path,
            sha256=corpus_file.sha256,
            char_count=len(text),
            encoding=encoding,
            metadata={k: v for k, v in corpus_file.metadata.items() if k not in {"title", "author", "genre"}},
        )
        works.append(work)
        build_work_units(text, work, chapters, scenes, chunks)
        manifest_files[corpus_file.relative_path] = file_manifest_entry(corpus_file, "indexed")

    manifest = {
        "version": 1,
        "created_at": previous_manifest.get("created_at") or utc_now(),
        "updated_at": utc_now(),
        "corpus_dir": str(corpus_root),
        "files": manifest_files,
    }
    write_json(output_dir / "manifest.json", manifest)
    write_jsonl(output_dir / "works.jsonl", (work.to_dict() for work in works))
    write_jsonl(output_dir / "chapters.jsonl", (chapter.to_dict() for chapter in chapters))
    write_jsonl(output_dir / "scenes.jsonl", (scene.to_dict() for scene in scenes))
    write_jsonl(output_dir / "chunks.jsonl", (chunk.to_dict() for chunk in chunks))
    write_jsonl(output_dir / "errors.jsonl", errors)
    (output_dir / "pending_jobs.jsonl").touch()
    (output_dir / "quality_report.md").write_text(render_quality_report(works, chapters, scenes, chunks, errors), encoding="utf-8")
    return CorpusIndexResult(output_dir, len(works), len(chapters), len(scenes), len(chunks), skipped_files, len(errors))


def build_work_units(
    text: str,
    work: CorpusWork,
    chapters: list[CorpusChapter],
    scenes: list[CorpusScene],
    chunks: list[RetrievalChunk],
) -> None:
    for chapter_index, chapter_span in enumerate(split_chapters(text), start=1):
        chapter_id = f"{work.work_id}_ch{chapter_index:04d}"
        chapter = CorpusChapter(
            chapter_id=chapter_id,
            work_id=work.work_id,
            chapter_index=chapter_index,
            title=chapter_span.title,
            char_start=chapter_span.start,
            char_end=chapter_span.end,
            role_hint=chapter_role_hint(chapter_index, len(text), chapter_span.start),
        )
        chapters.append(chapter)
        chapter_text = text[chapter_span.content_start : chapter_span.end]
        for scene_index, scene_span in enumerate(split_scenes(chapter_text), start=1):
            scene_id = f"{chapter_id}_sc{scene_index:03d}"
            scene_start = chapter_span.content_start + scene_span.start
            scene_end = chapter_span.content_start + scene_span.end
            scene = CorpusScene(
                scene_id=scene_id,
                work_id=work.work_id,
                chapter_id=chapter_id,
                scene_index=scene_index,
                char_start=scene_start,
                char_end=scene_end,
                position=scene_span.position,
            )
            scenes.append(scene)
            scene_text = text[scene_start:scene_end]
            for local_chunk_index, chunk in enumerate(chunk_scene(scene_text), start=1):
                chunk_index = len(chunks) + 1
                chunks.append(
                    RetrievalChunk(
                        chunk_id=f"{scene_id}_ck{local_chunk_index:03d}",
                        work_id=work.work_id,
                        chapter_id=chapter_id,
                        scene_id=scene_id,
                        chunk_index=chunk_index,
                        text=chunk.text,
                        char_start=scene_start + chunk.start,
                        char_end=scene_start + chunk.end,
                        chapter_index=chapter_index,
                        chapter_title=chapter.title,
                        position=scene.position,
                        tags=infer_chunk_tags(chunk.text, scene.position, chapter.role_hint),
                        metadata={"source_path": work.source_path},
                    )
                )


def load_works(index_dir: str | Path) -> Iterator[CorpusWork]:
    for item in read_jsonl(Path(index_dir) / "works.jsonl"):
        yield CorpusWork.from_dict(item)


def load_chapters(index_dir: str | Path) -> Iterator[CorpusChapter]:
    for item in read_jsonl(Path(index_dir) / "chapters.jsonl"):
        yield CorpusChapter.from_dict(item)


def load_scenes(index_dir: str | Path) -> Iterator[CorpusScene]:
    for item in read_jsonl(Path(index_dir) / "scenes.jsonl"):
        yield CorpusScene.from_dict(item)


def load_chunks(index_dir: str | Path) -> Iterator[RetrievalChunk]:
    for item in read_jsonl(Path(index_dir) / "chunks.jsonl"):
        yield RetrievalChunk.from_dict(item)


def load_profiles(index_dir: str | Path):
    from ai_novelist.corpus.craft_schema import CraftProfile

    root = Path(index_dir) / "craft_profiles"
    for path in sorted((root / "works").glob("*.json")):
        yield CraftProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    for path in sorted((root / "chapters").glob("*.jsonl")):
        for item in read_jsonl(path):
            yield CraftProfile.from_dict(item)
    for path in sorted((root / "scenes").glob("*.jsonl")):
        for item in read_jsonl(path):
            yield CraftProfile.from_dict(item)
    for path in sorted((root / "genres").glob("*.json")):
        yield CraftProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            file.write("\n")


def read_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                yield item


def load_manifest(index_dir: Path) -> dict:
    path = index_dir / "manifest.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def file_manifest_entry(corpus_file, status: str) -> dict:
    return {
        "work_id": corpus_file.work_id,
        "sha256": corpus_file.sha256,
        "mtime": corpus_file.mtime,
        "size": corpus_file.size,
        "status": status,
    }


def chapter_role_hint(chapter_index: int, text_len: int, start: int) -> str:
    if chapter_index == 1:
        return "opening"
    ratio = start / max(1, text_len)
    if ratio < 0.25:
        return "setup"
    if ratio < 0.55:
        return "escalation"
    if ratio < 0.8:
        return "climax"
    return "aftermath"


def infer_chunk_tags(text: str, position: str, role_hint: str) -> list[str]:
    tags = {position, role_hint}
    marker_map = {
        "但是": "turn",
        "然而": "turn",
        "忽然": "turn",
        "沉默": "restraint",
        "门": "threshold",
        "信": "information_release",
        "名单": "information_release",
        "秘密": "foreshadowing",
        "真相": "reveal",
        "雨": "atmosphere",
        "灯": "atmosphere",
        "说": "dialogue",
    }
    for marker, tag in marker_map.items():
        if marker in text:
            tags.add(tag)
    return sorted(tags)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
