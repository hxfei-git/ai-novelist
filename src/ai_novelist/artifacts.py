"""Artifact registry helpers for generated novel assets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ArtifactRecord:
    id: str
    type: str
    path: str
    version: int = 1
    source_agent: str = ""
    graph: str = ""
    stage: str = ""
    chapter: int | None = None
    created_at: str = ""
    updated_at: str = ""
    summary: str = ""
    sha256: str = ""
    chars: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactRecord":
        chapter = data.get("chapter")
        return cls(
            id=str(data.get("id", "")),
            type=str(data.get("type", "")),
            path=str(data.get("path", "")),
            version=int(data.get("version", 1)),
            source_agent=str(data.get("source_agent", "")),
            graph=str(data.get("graph", "")),
            stage=str(data.get("stage", "")),
            chapter=int(chapter) if chapter is not None else None,
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            summary=str(data.get("summary", "")),
            sha256=str(data.get("sha256", "")),
            chars=int(data.get("chars", 0) or 0),
            metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata", {}), dict) else {},
        )


def artifact_registry_path(project_dir: Path) -> Path:
    return project_dir / "artifacts.json"


def load_artifacts(project_dir: Path) -> list[ArtifactRecord]:
    path = artifact_registry_path(project_dir)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        return []
    return [ArtifactRecord.from_dict(item) for item in data if isinstance(item, dict)]


def save_artifacts(project_dir: Path, records: list[ArtifactRecord]) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    with artifact_registry_path(project_dir).open("w", encoding="utf-8") as file:
        json.dump([record.to_dict() for record in records], file, ensure_ascii=False, indent=2)
        file.write("\n")


def register_artifact(project_dir: Path, record: ArtifactRecord) -> ArtifactRecord:
    records = load_artifacts(project_dir)
    now = utc_now()
    normalized_path = normalize_relative_path(project_dir, record.path)
    content_sha, content_chars = artifact_content_digest(project_dir, normalized_path)
    record_sha = record.sha256 or content_sha
    record_chars = record.chars or content_chars
    duplicate = next(
        (
            item
            for item in records
            if item.type == record.type
            and item.chapter == record.chapter
            and item.stage == record.stage
            and item.sha256
            and item.sha256 == record_sha
        ),
        None,
    )
    if duplicate is not None:
        return duplicate
    matching = [
        item
        for item in records
        if item.type == record.type
        and item.chapter == record.chapter
        and item.stage == record.stage
        and item.path == normalized_path
    ]
    version = max((item.version for item in matching), default=0) + 1
    created_at = record.created_at or now
    if matching and not record.created_at:
        created_at = matching[-1].created_at or now
    registered = ArtifactRecord(
        id=record.id or artifact_id(record.type, record.stage, record.chapter, version),
        type=record.type,
        path=normalized_path,
        version=version,
        source_agent=record.source_agent,
        graph=record.graph,
        stage=record.stage,
        chapter=record.chapter,
        created_at=created_at,
        updated_at=now,
        summary=record.summary,
        sha256=record_sha,
        chars=record_chars,
        metadata=dict(record.metadata),
    )
    records.append(registered)
    save_artifacts(project_dir, records)
    return registered


def get_latest_artifact(
    project_dir: Path,
    artifact_type: str,
    chapter: int | None = None,
    stage: str | None = None,
) -> ArtifactRecord | None:
    records = [
        item
        for item in load_artifacts(project_dir)
        if item.type == artifact_type
        and (chapter is None or item.chapter == chapter)
        and (stage is None or item.stage == stage)
    ]
    if not records:
        return None
    return sorted(records, key=lambda item: (item.version, item.updated_at, item.created_at))[-1]


def save_markdown_artifact(
    project_dir: Path,
    relative_path: str,
    content: str,
    artifact_type: str,
    **kwargs: Any,
) -> ArtifactRecord:
    path = write_text_artifact(project_dir, relative_path, content.rstrip() + "\n")
    return register_artifact(
        project_dir,
        ArtifactRecord(
            id="",
            type=artifact_type,
            path=path.relative_to(project_dir).as_posix(),
            **kwargs,
        ),
    )


def save_json_artifact(
    project_dir: Path,
    relative_path: str,
    data: dict[str, Any],
    artifact_type: str,
    **kwargs: Any,
) -> ArtifactRecord:
    path = project_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return register_artifact(
        project_dir,
        ArtifactRecord(
            id="",
            type=artifact_type,
            path=path.relative_to(project_dir).as_posix(),
            **kwargs,
        ),
    )


def load_artifact_text(project_dir: Path, record_or_path: ArtifactRecord | str) -> str:
    relative_path = record_or_path.path if isinstance(record_or_path, ArtifactRecord) else record_or_path
    path = project_dir / relative_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_text_artifact(project_dir: Path, relative_path: str, content: str) -> Path:
    path = project_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def artifact_id(artifact_type: str, stage: str, chapter: int | None, version: int) -> str:
    parts = [artifact_type]
    if stage:
        parts.append(stage)
    if chapter is not None:
        parts.append(f"chapter-{chapter:03d}")
    parts.append(f"v{version}")
    return "-".join(parts)


def normalize_relative_path(project_dir: Path, path: str) -> str:
    value = Path(path)
    if value.is_absolute():
        try:
            return value.relative_to(project_dir).as_posix()
        except ValueError:
            return value.as_posix()
    return value.as_posix()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def artifact_content_digest(project_dir: Path, relative_path: str) -> tuple[str, int]:
    path = project_dir / relative_path
    if not path.exists() or not path.is_file():
        return "", 0
    text = path.read_text(encoding="utf-8")
    return sha256_text(text), len(text)
