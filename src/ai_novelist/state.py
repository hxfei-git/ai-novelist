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
    revision_instruction: str = ""
    locked_constraints: list[str] = field(default_factory=list)
    style_preferences: list[str] = field(default_factory=list)
    outline_versions: list[dict] = field(default_factory=list)
    selected_outline_version: int = -1
    pending_questions: list[str] = field(default_factory=list)
    open_decisions: list[str] = field(default_factory=list)
    last_user_feedback: str = ""
    active_artifact: str = ""
    active_workflow: str = ""
    current_stage: str = ""
    reference_brief: str = ""
    canon_facts: list[str] = field(default_factory=list)
    research_sources: list[dict] = field(default_factory=list)
    research_uncertainties: list[str] = field(default_factory=list)
    retrieval_context: str = ""
    retrieval_query: str = ""
    retrieval_sources: list[dict] = field(default_factory=list)
    director_intent: str = ""
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
            revision_instruction=str(data.get("revision_instruction", "")),
            locked_constraints=normalize_str_list(data.get("locked_constraints", [])),
            style_preferences=normalize_str_list(data.get("style_preferences", [])),
            outline_versions=normalize_outline_versions(data.get("outline_versions", [])),
            selected_outline_version=int(data.get("selected_outline_version", -1)),
            pending_questions=normalize_str_list(data.get("pending_questions", [])),
            open_decisions=normalize_str_list(data.get("open_decisions", [])),
            last_user_feedback=str(data.get("last_user_feedback", "")),
            active_artifact=str(data.get("active_artifact", "")),
            active_workflow=str(data.get("active_workflow", "")),
            current_stage=str(data.get("current_stage", "")),
            reference_brief=str(data.get("reference_brief", "")),
            canon_facts=normalize_str_list(data.get("canon_facts", [])),
            research_sources=normalize_dict_list(data.get("research_sources", [])),
            research_uncertainties=normalize_str_list(data.get("research_uncertainties", [])),
            retrieval_context=str(data.get("retrieval_context", "")),
            retrieval_query=str(data.get("retrieval_query", "")),
            retrieval_sources=normalize_dict_list(data.get("retrieval_sources", [])),
            director_intent=str(data.get("director_intent", "")),
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


def normalize_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_outline_versions(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    versions: list[dict] = []
    for item in value:
        if isinstance(item, dict):
            versions.append(dict(item))
    return versions


def normalize_dict_list(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]
