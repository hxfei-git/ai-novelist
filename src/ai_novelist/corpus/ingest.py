"""Corpus file scanning for Author Craft indexing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_SUFFIXES = {".txt", ".md"}
SKIP_DIR_NAMES = {".git", "__MACOSX", "corpus_index", "projects", ".venv", ".pytest_cache"}


@dataclass(frozen=True)
class CorpusFile:
    path: Path
    relative_path: str
    work_id: str
    sha256: str
    size: int
    mtime: float
    metadata: dict[str, Any] = field(default_factory=dict)


def scan_corpus(corpus_dir: Path) -> list[CorpusFile]:
    root = corpus_dir.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return []
    files: list[CorpusFile] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if should_skip(path, root):
            continue
        relative_path = path.relative_to(root).as_posix()
        metadata = load_sidecar_metadata(path)
        sha = sha256_file(path)
        files.append(
            CorpusFile(
                path=path,
                relative_path=relative_path,
                work_id=stable_work_id(relative_path, metadata),
                sha256=sha,
                size=path.stat().st_size,
                mtime=path.stat().st_mtime,
                metadata=metadata,
            )
        )
    return files


def should_skip(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts[:-1]
    except ValueError:
        return True
    return any(part.startswith(".") or part in SKIP_DIR_NAMES for part in parts)


def load_sidecar_metadata(path: Path) -> dict[str, Any]:
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    if not meta_path.exists():
        meta_path = path.with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_work_id(relative_path: str, metadata: dict[str, Any] | None = None) -> str:
    basis = relative_path
    if metadata:
        basis = f"{metadata.get('title', '')}|{metadata.get('author', '')}|{relative_path}"
    return "work_" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
