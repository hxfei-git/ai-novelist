"""Local file storage for novel projects."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ai_novelist.state import NovelState


class LocalStoreError(RuntimeError):
    """Raised when local project data is invalid."""


class LocalStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def create_project(self, title: str, project_id: str | None = None) -> NovelState:
        project_id = project_id or slugify(title)
        if not project_id:
            raise LocalStoreError("Project id cannot be empty")

        project_dir = self.project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        self.chapters_dir(project_id).mkdir(exist_ok=True)
        self.outline_stages_dir(project_id).mkdir(exist_ok=True)
        self.outline_dir(project_id).mkdir(exist_ok=True)

        state_path = self.state_path(project_id)
        if state_path.exists():
            return self.load_state(project_id)

        state = NovelState(project_id=project_id, title=title)
        self.save_state(state)
        return state

    def project_dir(self, project_id: str) -> Path:
        return self.root / project_id

    def chapters_dir(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "chapters"

    def outline_stages_dir(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "outline_stages"

    def outline_dir(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "outline"

    def state_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "state.json"

    def outline_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "outline.md"

    def outline_stage_path(self, project_id: str, stage: str) -> Path:
        return self.outline_stages_dir(project_id) / f"{stage}.md"

    def outline_artifact_path(self, project_id: str, stage: str) -> Path:
        return self.outline_dir(project_id) / f"{stage}.md"

    def worldbuilding_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "worldbuilding.md"

    def chapter_plan_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "chapter_plan.md"

    def reference_brief_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "reference_brief.md"

    def research_sources_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "research_sources.json"

    def project_context_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "project_context.md"

    def artifact_registry_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "artifacts.json"

    def novel_bible_json_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "novel_bible.json"

    def novel_bible_markdown_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "novel_bible.md"

    def chapter_path(self, project_id: str, chapter: int) -> Path:
        return self.chapters_dir(project_id) / f"chapter_{chapter:03d}.md"

    def editor_notes_path(self, project_id: str, chapter: int) -> Path:
        return self.chapters_dir(project_id) / f"chapter_{chapter:03d}_review.md"

    def load_state(self, project_id: str) -> NovelState:
        path = self.state_path(project_id)
        if not path.exists():
            raise LocalStoreError(f"Project does not exist: {project_id}")
        with path.open("r", encoding="utf-8") as file:
            return NovelState.from_dict(json.load(file))

    def save_state(self, state: NovelState) -> None:
        project_dir = self.project_dir(state.project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        self.chapters_dir(state.project_id).mkdir(exist_ok=True)
        self.outline_stages_dir(state.project_id).mkdir(exist_ok=True)
        self.outline_dir(state.project_id).mkdir(exist_ok=True)
        with self.state_path(state.project_id).open("w", encoding="utf-8") as file:
            json.dump(state.to_dict(), file, ensure_ascii=False, indent=2)
            file.write("\n")

    def save_outline(self, state: NovelState) -> Path:
        return self._write_required(self.outline_path(state.project_id), state.outline, "outline")

    def save_outline_stage(self, state: NovelState, stage: str, content: str) -> Path:
        return self._write_required(self.outline_stage_path(state.project_id, stage), content, f"outline stage {stage}")

    def save_outline_artifact(self, state: NovelState, stage: str, content: str) -> Path:
        return self._write_required(self.outline_artifact_path(state.project_id, stage), content, f"outline artifact {stage}")

    def load_outline_stage(self, project_id: str, stage: str) -> str:
        path = self.outline_stage_path(project_id, stage)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def save_worldbuilding(self, state: NovelState) -> Path:
        return self._write_required(self.worldbuilding_path(state.project_id), state.worldbuilding, "worldbuilding")

    def save_chapter_plan(self, state: NovelState) -> Path:
        return self._write_required(self.chapter_plan_path(state.project_id), state.chapter_plan, "chapter plan")

    def save_reference_brief(self, state: NovelState) -> Path:
        return self._write_required(self.reference_brief_path(state.project_id), state.reference_brief, "reference brief")

    def save_research_sources(self, state: NovelState) -> Path:
        path = self.research_sources_path(state.project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(state.research_sources, file, ensure_ascii=False, indent=2)
            file.write("\n")
        return path

    def load_project_context(self, project_id: str) -> str:
        path = self.project_context_path(project_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def save_project_context(self, project_id: str, content: str) -> Path:
        path = self.project_context_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return path

    def save_chapter(self, state: NovelState) -> Path:
        return self._write_required(
            self.chapter_path(state.project_id, state.current_chapter),
            state.chapter_draft,
            "chapter draft",
        )

    def save_editor_notes(self, state: NovelState) -> Path:
        return self._write_required(
            self.editor_notes_path(state.project_id, state.current_chapter),
            state.editor_notes,
            "editor notes",
        )

    def _write_required(self, path: Path, content: str, label: str) -> Path:
        if not content.strip():
            raise LocalStoreError(f"Cannot save empty {label}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            file.write(content.rstrip())
            file.write("\n")
        return path


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", value.strip()).strip("-")
    return slug[:64]
