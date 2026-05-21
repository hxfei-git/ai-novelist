"""State models used by the graph."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ReviewStatus = Literal["draft", "approved", "rejected", "revision_requested", "stopped", "error"]
EditorDecision = Literal["unknown", "pass", "revise", "stop"]
NextAction = Literal["continue", "rewrite_chapter", "human_review", "persist", "stop"]


@dataclass
class NovelState:
    project_id: str
    title: str
    idea: str = ""
    outline: str = ""
    worldbuilding: str = ""
    chapter_plan: str = ""
    current_chapter: int = 1
    chapter_draft: str = ""
    editor_notes: str = ""
    editor_decision: EditorDecision = "unknown"
    revision_count: int = 0
    max_revisions: int = 1
    quality_score: int = 0
    next_action: NextAction = "continue"
    messages: list[dict[str, str]] = field(default_factory=list)
    user_request: str = ""
    director_action: str = ""
    director_message: str = ""
    pending_question: str = ""
    active_task: str = ""
    review_status: ReviewStatus = "draft"
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NovelState":
        return cls(
            project_id=str(data["project_id"]),
            title=str(data["title"]),
            idea=str(data.get("idea", "")),
            outline=str(data.get("outline", "")),
            worldbuilding=str(data.get("worldbuilding", "")),
            chapter_plan=str(data.get("chapter_plan", "")),
            current_chapter=int(data.get("current_chapter", 1)),
            chapter_draft=str(data.get("chapter_draft", "")),
            editor_notes=str(data.get("editor_notes", "")),
            editor_decision=data.get("editor_decision", "unknown"),
            revision_count=int(data.get("revision_count", 0)),
            max_revisions=int(data.get("max_revisions", 1)),
            quality_score=int(data.get("quality_score", 0)),
            next_action=data.get("next_action", "continue"),
            messages=normalize_messages(data.get("messages", [])),
            user_request=str(data.get("user_request", "")),
            director_action=str(data.get("director_action", "")),
            director_message=str(data.get("director_message", "")),
            pending_question=str(data.get("pending_question", "")),
            active_task=str(data.get("active_task", "")),
            review_status=data.get("review_status", "draft"),
            error=str(data.get("error", "")),
        )


def normalize_messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    messages: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        content = str(item.get("content", ""))
        if role and content:
            messages.append({"role": role, "content": content})
    return messages
