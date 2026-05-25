"""Local file storage for novel projects."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

    def craft_dir(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "craft"

    def stage_craft_briefs_dir(self, project_id: str) -> Path:
        return self.craft_dir(project_id) / "stage_briefs"

    def stage_craft_sources_dir(self, project_id: str) -> Path:
        return self.craft_dir(project_id) / "stage_sources"

    def craft_similarity_reports_dir(self, project_id: str) -> Path:
        return self.craft_dir(project_id) / "similarity_reports"

    def project_craft_memory_path(self, project_id: str) -> Path:
        return self.craft_dir(project_id) / "project_craft_memory.json"

    def project_memory_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "project_memory.md"

    def outline_debug_dir(self, project_id: str) -> Path:
        return self.outline_dir(project_id) / "debug"

    def outline_role_reviews_path(self, project_id: str, stage: str) -> Path:
        return self.outline_debug_dir(project_id) / f"{stage}_role_reviews.md"

    def novel_bible_json_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "novel_bible.json"

    def novel_bible_markdown_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "novel_bible.md"

    def chapter_path(self, project_id: str, chapter: int) -> Path:
        return self.chapters_dir(project_id) / f"chapter_{chapter:03d}.md"

    def chapter_artifact_dir(self, project_id: str, chapter: int) -> Path:
        return self.chapters_dir(project_id) / f"chapter_{chapter:03d}"

    def chapter_card_path(self, project_id: str, chapter: int) -> Path:
        return self.chapter_artifact_dir(project_id, chapter) / "chapter_card.md"

    def scene_cards_path(self, project_id: str, chapter: int) -> Path:
        return self.chapter_artifact_dir(project_id, chapter) / "scene_cards.md"

    def chapter_draft_path(self, project_id: str, chapter: int, version: int = 1) -> Path:
        return self.chapter_artifact_dir(project_id, chapter) / f"draft_v{version}.md"

    def review_report_path(self, project_id: str, chapter: int, version: int = 1) -> Path:
        return self.chapter_artifact_dir(project_id, chapter) / f"review_v{version}.md"

    def review_json_path(self, project_id: str, chapter: int, version: int = 1) -> Path:
        return self.chapter_artifact_dir(project_id, chapter) / f"review_v{version}.json"

    def revision_plan_path(self, project_id: str, chapter: int, version: int = 1) -> Path:
        return self.chapter_artifact_dir(project_id, chapter) / f"revision_plan_v{version}.md"

    def final_chapter_path(self, project_id: str, chapter: int) -> Path:
        return self.chapter_artifact_dir(project_id, chapter) / "final.md"

    def chapter_summary_path(self, project_id: str, chapter: int) -> Path:
        return self.chapter_artifact_dir(project_id, chapter) / "summary.md"

    def pacing_report_path(self, project_id: str, chapter: int) -> Path:
        return self.chapter_artifact_dir(project_id, chapter) / "pacing_report.json"

    def exports_dir(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "exports"

    def manuscript_export_path(self, project_id: str) -> Path:
        return self.exports_dir(project_id) / "manuscript.md"

    def volume_export_path(self, project_id: str, volume: int = 1) -> Path:
        return self.exports_dir(project_id) / f"volume_{volume:03d}.md"

    def bible_export_path(self, project_id: str) -> Path:
        return self.exports_dir(project_id) / "novel_bible.md"

    def stage_craft_brief_relative_path(self, purpose: str, chapter: int | None, stage: str | None = None) -> str:
        return f"craft/stage_briefs/{craft_stage_filename(purpose, chapter, stage)}.md"

    def stage_craft_sources_relative_path(self, purpose: str, chapter: int | None, stage: str | None = None) -> str:
        return f"craft/stage_sources/{craft_stage_filename(purpose, chapter, stage)}.sources.json"

    def stage_craft_brief_path(self, project_id: str, purpose: str, chapter: int | None, stage: str | None = None) -> Path:
        return self.project_dir(project_id) / self.stage_craft_brief_relative_path(purpose, chapter, stage)

    def stage_craft_sources_path(self, project_id: str, purpose: str, chapter: int | None, stage: str | None = None) -> Path:
        return self.project_dir(project_id) / self.stage_craft_sources_relative_path(purpose, chapter, stage)

    def craft_similarity_report_relative_path(self, chapter: int, artifact: str) -> str:
        return f"craft/similarity_reports/chapter_{chapter:03d}_{safe_artifact_name(artifact)}.json"

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
        self.stage_craft_briefs_dir(state.project_id).mkdir(parents=True, exist_ok=True)
        self.stage_craft_sources_dir(state.project_id).mkdir(parents=True, exist_ok=True)
        self.craft_similarity_reports_dir(state.project_id).mkdir(parents=True, exist_ok=True)
        data = self._lightweight_state_dict(state)
        with self.state_path(state.project_id).open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        self.save_project_memory(state)

    def _lightweight_state_dict(self, state: NovelState) -> dict[str, Any]:
        data = deepcopy(state.to_dict())
        data["messages"] = compact_messages(data.get("messages", []), max_items=12, max_chars=500)
        summaries = dict(data.get("outline_stage_summaries") or {})
        artifacts = data.get("outline_stage_artifacts")
        if isinstance(artifacts, dict):
            slim_artifacts: dict[str, Any] = {}
            for stage, raw_item in artifacts.items():
                if not isinstance(raw_item, dict):
                    slim_artifacts[stage] = raw_item
                    continue
                item = dict(raw_item)
                synthesis = str(item.get("synthesis", "")).strip()
                if synthesis:
                    self._ensure_outline_artifact_files(state.project_id, str(stage), item, synthesis)
                summary = str(item.get("summary") or summaries.get(str(stage)) or summarize_text(synthesis)).strip()
                stage_memory = normalize_memory_lines(item.get("stage_memory") or summary or synthesis)
                if summary:
                    summaries[str(stage)] = summary
                slim = {
                    "stage": item.get("stage") or stage,
                    "label": item.get("label"),
                    "status": item.get("status", "options_ready"),
                    "path": item.get("path") or f"outline/{stage}.md",
                    "summary": summary,
                    "stage_memory": stage_memory,
                    "pending_questions": normalize_text_list(item.get("pending_questions", [])),
                    "updated_at": item.get("updated_at") or datetime.now(UTC).isoformat(timespec="seconds"),
                }
                if item.get("locked_at"):
                    slim["locked_at"] = item.get("locked_at")
                if item.get("default_discretion_summary"):
                    slim["default_discretion_summary"] = item.get("default_discretion_summary")
                if isinstance(item.get("metadata"), dict):
                    slim["metadata"] = item.get("metadata")
                slim_artifacts[str(stage)] = {k: v for k, v in slim.items() if v not in (None, "", [])}
            data["outline_stage_artifacts"] = slim_artifacts
            data["outline_stage_summaries"] = summaries
        self._compact_saved_large_fields(state, data)
        return data

    def _compact_saved_large_fields(self, state: NovelState, data: dict[str, Any]) -> None:
        chapter = state.active_chapter or state.current_chapter
        if data.get("chapter_draft") and self.chapter_draft_path(state.project_id, chapter, 2 if state.revision_count else 1).exists():
            data["chapter_draft"] = summarize_text(str(data["chapter_draft"]), max_chars=600)
        if data.get("current_review_report") and self.review_report_path(state.project_id, chapter, 1).exists():
            data["current_review_report"] = summarize_text(str(data["current_review_report"]), max_chars=600)
        if data.get("reference_brief") and self.reference_brief_path(state.project_id).exists():
            data["reference_brief"] = summarize_text(str(data["reference_brief"]), max_chars=800)

    def _ensure_outline_artifact_files(self, project_id: str, stage: str, item: dict[str, Any], synthesis: str) -> None:
        content = synthesis
        label = str(item.get("label") or stage).strip()
        stripped = content.lstrip()
        if not stripped.startswith("#") or stripped.startswith("##"):
            content = f"# {label}\n\n{content}"
        for path in (self.outline_artifact_path(project_id, stage), self.outline_stage_path(project_id, stage)):
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content.rstrip() + "\n", encoding="utf-8")

    def save_outline(self, state: NovelState) -> Path:
        return self._write_required(self.outline_path(state.project_id), state.outline, "outline")

    def save_outline_stage(self, state: NovelState, stage: str, content: str) -> Path:
        return self._write_required(self.outline_stage_path(state.project_id, stage), content, f"outline stage {stage}")

    def save_outline_artifact(self, state: NovelState, stage: str, content: str) -> Path:
        return self._write_required(self.outline_artifact_path(state.project_id, stage), content, f"outline artifact {stage}")

    def save_outline_role_reviews(self, state: NovelState, stage: str, reviews: list[dict[str, str]]) -> Path | None:
        if not reviews:
            return None
        lines = [f"# {stage} role reviews", ""]
        for item in reviews:
            role = str(item.get("role", "Agent")).strip() or "Agent"
            content = str(item.get("content", "")).strip()
            if content:
                lines.extend([f"## {role}", content, ""])
        return self._write_required(self.outline_role_reviews_path(state.project_id, stage), "\n".join(lines).strip(), f"outline role reviews {stage}")

    def load_outline_artifact(self, project_id: str, stage: str) -> str:
        path = self.outline_artifact_path(project_id, stage)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

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

    def load_project_memory(self, project_id: str) -> str:
        path = self.project_memory_path(project_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def save_project_memory(self, state: NovelState) -> Path:
        content = build_project_memory_markdown(state).rstrip() + "\n"
        path = self.project_memory_path(state.project_id)
        digest_path = path.with_suffix(path.suffix + ".sha256")
        digest = sha256_text(content)
        if path.exists() and digest_path.exists() and digest_path.read_text(encoding="utf-8").strip() == digest:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        digest_path.write_text(digest + "\n", encoding="utf-8")
        return path

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

    def save_chapter_card(self, state: NovelState) -> Path:
        return self._write_required(
            self.chapter_card_path(state.project_id, state.active_chapter or state.current_chapter),
            state.current_chapter_card,
            "chapter card",
        )

    def save_scene_cards(self, state: NovelState) -> Path:
        return self._write_required(
            self.scene_cards_path(state.project_id, state.active_chapter or state.current_chapter),
            state.current_scene_cards,
            "scene cards",
        )

    def save_chapter_draft(self, state: NovelState, version: int = 1) -> Path:
        return self._write_required(
            self.chapter_draft_path(state.project_id, state.active_chapter or state.current_chapter, version),
            state.chapter_draft,
            "chapter draft",
        )

    def save_review_report(self, state: NovelState, version: int = 1) -> Path:
        return self._write_required(
            self.review_report_path(state.project_id, state.active_chapter or state.current_chapter, version),
            state.current_review_report,
            "review report",
        )

    def save_revision_plan(self, state: NovelState, version: int = 1) -> Path:
        return self._write_required(
            self.revision_plan_path(state.project_id, state.active_chapter or state.current_chapter, version),
            state.current_revision_plan,
            "revision plan",
        )

    def save_final_chapter(self, state: NovelState) -> Path:
        return self._write_required(
            self.final_chapter_path(state.project_id, state.active_chapter or state.current_chapter),
            state.current_final_chapter,
            "final chapter",
        )

    def save_chapter_summary(self, state: NovelState) -> Path:
        return self._write_required(
            self.chapter_summary_path(state.project_id, state.active_chapter or state.current_chapter),
            state.chapter_summaries.get(str(state.active_chapter or state.current_chapter), ""),
            "chapter summary",
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


def compact_messages(messages: Any, max_items: int = 12, max_chars: int = 500) -> list[dict[str, str]]:
    if not isinstance(messages, list):
        return []
    compacted: list[dict[str, str]] = []
    for item in messages[-max_items:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if not role or not content:
            continue
        if len(content) > max_chars:
            content = content[:max_chars].rstrip() + "..."
        compacted.append({"role": role, "content": content})
    return compacted


def normalize_text_list(value: Any, limit: int = 12) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [str(item) for item in value]
    else:
        values = []
    return [item.strip() for item in values if item.strip()][:limit]


def summarize_text(text: str, max_chars: int = 420) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    return cleaned[:max_chars].rstrip() + ("..." if len(cleaned) > max_chars else "")


def normalize_memory_lines(value: Any, max_items: int = 12, max_chars: int = 1100) -> list[str]:
    if isinstance(value, list):
        lines = [str(item).strip(" -•\t") for item in value]
    else:
        text = str(value or "")
        lines = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            line = re.sub(r"^[-*+•\s]*", "", line)
            line = re.sub(r"^\d+[.、)]\s*", "", line).strip()
            if line and not line.startswith("#"):
                lines.append(line)
        if not lines and text.strip():
            lines = [summarize_text(text, max_chars=max_chars)]
    result: list[str] = []
    total = 0
    for line in lines:
        if not line or line in result:
            continue
        total += len(line)
        if total > max_chars and result:
            break
        result.append(line)
        if len(result) >= max_items:
            break
    return result


def build_project_memory_markdown(state: NovelState) -> str:
    lines = ["# Project Memory", "", "## 不可压缩种子设定"]
    seeds = []
    if state.idea.strip():
        seeds.append(f"原始创意：{state.idea.strip()}")
    seeds.extend(f"锁定约束：{item}" for item in state.locked_constraints if item.strip())
    seeds.extend(f"风格偏好：{item}" for item in state.style_preferences if item.strip())
    if seeds:
        lines.extend(f"- {item}" for item in dict.fromkeys(seeds))
    else:
        lines.append("- 暂无")
    lines.extend(["", "## 阶段记忆"])
    for stage, artifact in state.outline_stage_artifacts.items():
        if not isinstance(artifact, dict):
            continue
        label = artifact.get("label") or stage
        status = artifact.get("status") or "draft"
        memory = normalize_memory_lines(artifact.get("stage_memory") or artifact.get("summary") or artifact.get("synthesis", ""))
        if not memory:
            continue
        lines.append(f"### {label}（{status}）")
        lines.extend(f"- {item}" for item in memory[:12])
        lines.append("")
    lines.append("## 滚动对话摘要")
    if state.rolling_dialogue_summary.strip():
        lines.append(state.rolling_dialogue_summary.strip())
    else:
        recent = compact_messages(state.messages, max_items=8, max_chars=160)
        if recent:
            for item in recent:
                content = item["content"]
                if item["role"] == "assistant" and ("之前已确认" in content or ("还剩" in content and "尚未" in content)):
                    continue
                lines.append(f"- {item['role']}: {content}")
            if lines[-1] == "## 滚动对话摘要":
                lines.append("- 暂无")
        else:
            lines.append("- 暂无")
    return "\n".join(lines).rstrip() + "\n"

def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", value.strip()).strip("-")
    return slug[:64]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def craft_stage_filename(purpose: str, chapter: int | None, stage: str | None = None) -> str:
    prefix = f"chapter_{chapter:03d}_" if chapter is not None else ""
    suffix = f"_{safe_artifact_name(stage)}" if stage else ""
    return f"{prefix}{safe_artifact_name(purpose)}{suffix}"


def safe_artifact_name(value: str | None) -> str:
    text = str(value or "general").strip().lower()
    text = re.sub(r"[^a-z0-9_\-]+", "_", text)
    return text.strip("_") or "general"
