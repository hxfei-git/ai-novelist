"""Project and progress-log services used by the Web API."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError

ProgressItem = str | dict[str, str]
MAX_WEB_PROGRESS_LOG_ITEMS = 10


@dataclass(frozen=True)
class WebProject:
    project_id: str
    title: str
    path: str


def list_projects(store: LocalStore) -> list[WebProject]:
    if not store.root.exists():
        return []
    projects: list[WebProject] = []
    for path in sorted(store.root.iterdir()):
        if not path.is_dir() or not (path / "state.json").exists():
            continue
        try:
            state = store.load_state(path.name)
        except LocalStoreError:
            continue
        projects.append(WebProject(project_id=state.project_id, title=state.title, path=str(path)))
    return projects


def create_project(store: LocalStore, title: str, project_id: str | None = None, idea: str = "") -> NovelState:
    state = store.create_project(title.strip() or project_id or "untitled", project_id)
    if idea.strip() and state.idea != idea.strip():
        state.idea = idea.strip()
        store.save_state(state)
    return state


def project_needs_onboarding(state: NovelState) -> bool:
    if state.idea.strip():
        return False
    if state.outline.strip() or state.worldbuilding.strip() or state.chapter_plan.strip():
        return False
    if any(str(summary or "").strip() for summary in state.outline_stage_summaries.values()):
        return False
    for raw_artifact in state.outline_stage_artifacts.values():
        if not isinstance(raw_artifact, dict):
            continue
        status = str(raw_artifact.get("status") or "")
        if status in {"options_ready", "locked", "revision_requested", "done"}:
            return False
        for key in ("summary", "synthesis", "stage_memory", "path"):
            value = raw_artifact.get(key)
            if isinstance(value, list) and any(str(item).strip() for item in value):
                return False
            if isinstance(value, str) and value.strip():
                return False
    return True


def save_project_idea(store: LocalStore, project_id: str, idea: str) -> NovelState:
    text = idea.strip()
    if not text:
        raise LocalStoreError("Novel idea cannot be empty")
    state = store.load_state(project_id)
    state.idea = text
    state.user_request = text
    state.revision_instruction = text
    store.save_state(state)
    return state


def project_progress_log_path(store: LocalStore, project_id: str) -> Path:
    return store.project_dir(project_id) / "web_progress_log.json"


def normalize_progress_log_items(items: Iterable[Any]) -> list[ProgressItem]:
    normalized: list[ProgressItem] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                normalized.append(text)
        elif isinstance(item, dict):
            event = {
                key: str(item.get(key) or "").strip()
                for key in ("label", "model", "elapsed", "tokens", "context", "status")
            }
            key = str(item.get("key") or "").strip()
            if key:
                event["key"] = key
            if event["label"]:
                normalized.append(event)
        if len(normalized) >= MAX_WEB_PROGRESS_LOG_ITEMS:
            break
    return normalized


def build_progress_event(stage: str, message: str) -> dict[str, str]:
    body = str(message or "").strip()
    label = body.split("（", 1)[0].strip() or str(stage or "").strip() or "Progress"
    label = re.sub(r"^(已完成[:：]?)", "", label).strip()
    label = re.sub(r"^(执行失败[:：]?)", "", label).strip()
    metadata = ""
    if "（" in body and body.endswith("）"):
        metadata = body.rsplit("（", 1)[1][:-1]
    metadata_parts = [part.strip() for part in re.split(r"\s*\|\s*|/", metadata) if part.strip()]
    elapsed_value = next((part for part in metadata_parts if re.fullmatch(r"\d+(?:\.\d+)?s", part)), "")
    if not elapsed_value:
        elapsed = re.search(r"(?:^|[/（])(\d+(?:\.\d+)?s)(?:[/）]|$)", body)
        elapsed_value = elapsed.group(1) if elapsed else ""
    model_value = ""
    if metadata_parts:
        first_metadata_part = metadata_parts[0]
        if (
            not re.fullmatch(r"\d+(?:\.\d+)?s", first_metadata_part)
            and not first_metadata_part.startswith("ctx=")
            and not first_metadata_part.startswith("tok≈")
        ):
            model_value = first_metadata_part
    tokens = re.search(r"(tok≈[^/）\s]+)", body)
    context = re.search(r"(ctx=[^/）\s]+(?:/[^/）\s]+)?)", body)
    status = "failed" if "失败" in body else "completed" if body.startswith("已完成") else "running"
    return {
        "key": str(stage or "").strip() or label,
        "label": label,
        "model": model_value,
        "elapsed": elapsed_value,
        "tokens": tokens.group(1) if tokens else "",
        "context": context.group(1) if context else "",
        "status": status,
    }


def load_project_progress_log(store: LocalStore, project_id: str) -> list[ProgressItem]:
    store.load_state(project_id)
    path = project_progress_log_path(store, project_id)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = raw.get("items") if isinstance(raw, dict) else raw
    return normalize_progress_log_items(items if isinstance(items, list) else [])


def save_project_progress_log(store: LocalStore, project_id: str, items: Iterable[Any]) -> list[ProgressItem]:
    store.load_state(project_id)
    normalized = normalize_progress_log_items(items)
    path = project_progress_log_path(store, project_id)
    path.write_text(json.dumps({"items": normalized}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized
