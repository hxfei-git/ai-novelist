"""Local Feishu session to project mapping."""

from __future__ import annotations

import json
from hashlib import sha1

from ai_novelist.storage.local_store import LocalStore, slugify


class FeishuSessionStore:
    def __init__(self, store: LocalStore) -> None:
        self.store = store
        self.path = store.root / ".feishu_sessions.json"

    def current_project(self, open_id: str) -> str:
        sessions = self._load()
        project_id = str(sessions.get(open_id, "")).strip()
        if project_id:
            return project_id
        project_id = default_project_id(open_id)
        self.set_current_project(open_id, project_id)
        return project_id

    def set_current_project(self, open_id: str, project_id: str) -> None:
        sessions = self._load()
        sessions[open_id] = normalize_project_id(project_id)
        self._save(sessions)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items() if str(key).strip() and str(value).strip()}

    def _save(self, sessions: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sessions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def default_project_id(open_id: str) -> str:
    normalized = slugify(open_id)[:48]
    if normalized:
        return f"feishu-{normalized}"
    digest = sha1(open_id.encode("utf-8")).hexdigest()[:12]
    return f"feishu-{digest}"


def normalize_project_id(project_id: str) -> str:
    normalized = slugify(project_id)
    if not normalized:
        raise ValueError("项目 ID 不能为空")
    return normalized
