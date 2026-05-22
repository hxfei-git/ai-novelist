"""State models used by the graph."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ReviewStatus = Literal["draft", "approved", "rejected", "revision_requested", "stopped", "error"]
EditorDecision = Literal["unknown", "pass", "revise", "stop"]
NextAction = Literal["continue", "rewrite_chapter", "human_review", "persist", "stop"]
OutlineStage = Literal[
    "direction",
    "concept",
    "worldbuilding",
    "characters",
    "story_flow",
    "volume_outline",
    "chapter_outline",
    "review_lock",
    "done",
]
OutlineStageStatus = Literal["collecting", "options_ready", "locked", "revision_requested", "done"]


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
    director_task_args: dict[str, Any] = field(default_factory=dict)
    bible_version: int = 0
    bible_updated_at: str = ""
    active_graph: str = ""
    active_stage: str = ""
    active_chapter: int = 1
    active_scene: str = ""
    current_chapter_card: str = ""
    current_scene_cards: str = ""
    current_review_report: str = ""
    current_revision_plan: str = ""
    current_final_chapter: str = ""
    chapter_summaries: dict[str, str] = field(default_factory=dict)
    artifact_registry: list[dict[str, Any]] = field(default_factory=list)
    last_context_digest: str = ""
    last_agent_reports: list[dict[str, Any]] = field(default_factory=list)
    pending_director_decision: dict[str, Any] = field(default_factory=dict)
    pending_question: str = ""
    active_task: str = ""
    project_memory_version: int = 1
    rolling_dialogue_summary: str = ""
    outline_stage_summaries: dict[str, str] = field(default_factory=dict)
    outline_stage: OutlineStage = "direction"
    outline_stage_status: OutlineStageStatus = "collecting"
    outline_stage_artifacts: dict[str, Any] = field(default_factory=dict)
    outline_stage_history: list[dict[str, Any]] = field(default_factory=list)
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
            director_task_args=normalize_dict(data.get("director_task_args", {})),
            bible_version=int(data.get("bible_version", 0)),
            bible_updated_at=str(data.get("bible_updated_at", "")),
            active_graph=str(data.get("active_graph", "")),
            active_stage=str(data.get("active_stage", "")),
            active_chapter=int(data.get("active_chapter", data.get("current_chapter", 1))),
            active_scene=str(data.get("active_scene", "")),
            current_chapter_card=str(data.get("current_chapter_card", "")),
            current_scene_cards=str(data.get("current_scene_cards", "")),
            current_review_report=str(data.get("current_review_report", "")),
            current_revision_plan=str(data.get("current_revision_plan", "")),
            current_final_chapter=str(data.get("current_final_chapter", "")),
            chapter_summaries=normalize_str_dict(data.get("chapter_summaries", {})),
            artifact_registry=normalize_dict_list(data.get("artifact_registry", [])),
            last_context_digest=str(data.get("last_context_digest", "")),
            last_agent_reports=normalize_dict_list(data.get("last_agent_reports", [])),
            pending_director_decision=normalize_dict(data.get("pending_director_decision", {})),
            pending_question=str(data.get("pending_question", "")),
            active_task=str(data.get("active_task", "")),
            project_memory_version=int(data.get("project_memory_version", 1)),
            rolling_dialogue_summary=str(data.get("rolling_dialogue_summary", "")),
            outline_stage_summaries=normalize_str_dict(data.get("outline_stage_summaries", {})),
            outline_stage=normalize_outline_stage(data.get("outline_stage", "direction")),
            outline_stage_status=normalize_outline_stage_status(data.get("outline_stage_status", "collecting")),
            outline_stage_artifacts=normalize_outline_stage_artifacts(data.get("outline_stage_artifacts", {})),
            outline_stage_history=normalize_dict_list(data.get("outline_stage_history", [])),
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


def normalize_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def normalize_outline_stage(value: Any) -> OutlineStage:
    stage = str(value or "direction").strip()
    if stage == "outline_draft":
        stage = "volume_outline"
    allowed = {
        "direction",
        "concept",
        "worldbuilding",
        "characters",
        "story_flow",
        "volume_outline",
        "chapter_outline",
        "review_lock",
        "done",
    }
    return stage if stage in allowed else "direction"  # type: ignore[return-value]


def normalize_outline_stage_status(value: Any) -> OutlineStageStatus:
    status = str(value or "collecting").strip()
    allowed = {"collecting", "options_ready", "locked", "revision_requested", "done"}
    return status if status in allowed else "collecting"  # type: ignore[return-value]


def normalize_str_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def normalize_outline_stage_artifacts(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    artifacts: dict[str, Any] = {}
    for raw_key, raw_item in value.items():
        key = normalize_outline_stage(raw_key)
        item = dict(raw_item) if isinstance(raw_item, dict) else raw_item
        if isinstance(item, dict):
            item["stage"] = key
            if item.get("label") == "总大纲草案":
                item["label"] = "分卷大纲"
        artifacts[key] = item
    return artifacts
