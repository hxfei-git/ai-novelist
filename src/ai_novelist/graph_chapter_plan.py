"""Chapter card planning graph."""

from __future__ import annotations

from typing import Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.artifacts import ArtifactRecord, load_artifacts, register_artifact
from ai_novelist.context_builder import build_context
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


CHAPTER_CARD_SECTIONS = [
    "章节目标",
    "场景列表",
    "关键冲突",
    "人物变化",
    "结尾钩子",
    "连续性约束",
    "本章写作输入",
    "自检",
]


class ChapterPlanSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore) -> None:
        self.adapter = adapter
        self.store = store

    def invoke(self, state: dict) -> dict:
        current = select_chapter_node(state, self.store)
        current = load_chapter_context_node(current, self.store)
        current = chapter_goal_agent_node(current, self.adapter, self.store)
        current = chapter_conflict_agent_node(current, self.adapter, self.store)
        current = chapter_hook_agent_node(current, self.adapter, self.store)
        current = chapter_card_synthesizer_node(current, self.adapter, self.store)
        current = validate_chapter_card_node(current, self.store)
        current = save_chapter_card_node(current, self.store)
        return current


def build_chapter_plan_graph(adapter: AgentAdapter, store: LocalStore) -> CompiledGraph:
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return ChapterPlanSequentialGraph(adapter, store)

    graph = StateGraph(dict)
    graph.add_node("select_chapter", lambda data: select_chapter_node(data, store))
    graph.add_node("load_chapter_context", lambda data: load_chapter_context_node(data, store))
    graph.add_node("chapter_goal_agent", lambda data: chapter_goal_agent_node(data, adapter, store))
    graph.add_node("chapter_conflict_agent", lambda data: chapter_conflict_agent_node(data, adapter, store))
    graph.add_node("chapter_hook_agent", lambda data: chapter_hook_agent_node(data, adapter, store))
    graph.add_node("chapter_card_synthesizer", lambda data: chapter_card_synthesizer_node(data, adapter, store))
    graph.add_node("validate_chapter_card", lambda data: validate_chapter_card_node(data, store))
    graph.add_node("save_chapter_card", lambda data: save_chapter_card_node(data, store))
    graph.set_entry_point("select_chapter")
    graph.add_edge("select_chapter", "load_chapter_context")
    graph.add_edge("load_chapter_context", "chapter_goal_agent")
    graph.add_edge("chapter_goal_agent", "chapter_conflict_agent")
    graph.add_edge("chapter_conflict_agent", "chapter_hook_agent")
    graph.add_edge("chapter_hook_agent", "chapter_card_synthesizer")
    graph.add_edge("chapter_card_synthesizer", "validate_chapter_card")
    graph.add_edge("validate_chapter_card", "save_chapter_card")
    graph.add_edge("save_chapter_card", END)
    return graph.compile()


def select_chapter_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    chapter = int(state.director_task_args.get("chapter") or state.current_chapter or state.active_chapter or 1)
    state.current_chapter = max(1, chapter)
    state.active_chapter = state.current_chapter
    state.active_graph = "chapter_plan"
    state.active_stage = "select_chapter"
    state.active_artifact = "chapter_card"
    store.save_state(state)
    return state.to_dict()


def load_chapter_context_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    context = build_context(state, store, "chapter_planning", chapter=state.active_chapter, max_chars=14000)
    chapter_outline = collect_chapter_outline(state)
    state.director_task_args["chapter_planning_context"] = context
    state.director_task_args["selected_chapter_outline"] = chapter_outline
    state.last_context_digest = context[:1200]
    state.active_stage = "load_chapter_context"
    store.save_state(state)
    return state.to_dict()


def chapter_goal_agent_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    return run_report_agent(data, adapter, store, "chapter_goal_agent", "chapter_goal_report")


def chapter_conflict_agent_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    return run_report_agent(data, adapter, store, "chapter_conflict_agent", "chapter_conflict_report")


def chapter_hook_agent_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    return run_report_agent(data, adapter, store, "chapter_hook_agent", "chapter_hook_report")


def chapter_card_synthesizer_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_agent_prompt(state, "chapter_card_synthesizer")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.current_chapter_card = output.strip()
    state.review_status = "draft"
    state.error = ""
    state.active_graph = "chapter_plan"
    state.active_stage = "chapter_card_synthesizer"
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "chapter_card_synthesizer", "draft", {"chars": len(output)})
    store.save_state(state)
    return state.to_dict()


def validate_chapter_card_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    missing = [section for section in CHAPTER_CARD_SECTIONS if section not in state.current_chapter_card]
    state.director_task_args["chapter_card_validation"] = {"missing_sections": missing}
    state.active_stage = "validate_chapter_card"
    if missing:
        state.current_chapter_card = add_missing_sections(state.current_chapter_card, missing)
    store.save_state(state)
    return state.to_dict()


def save_chapter_card_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    path = store.save_chapter_card(state)
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="chapter_card",
            path=path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="chapter_card_synthesizer",
            graph="chapter_plan",
            stage="chapter_card",
            chapter=state.active_chapter,
            summary=chapter_card_summary(state.current_chapter_card),
        ),
    )
    state.active_graph = "chapter_plan"
    state.active_stage = "chapter_card"
    state.active_artifact = "chapter_card"
    state.director_action = state.director_action or "plan_chapter"
    state.director_message = f"第 {state.active_chapter} 章章节卡已生成：{path}"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "chapter_card_synthesizer", "saved", {"artifact_id": record.id, "path": record.path})
    store.save_state(state)
    return state.to_dict()


def run_report_agent(data: dict, adapter: AgentAdapter, store: LocalStore, prompt_name: str, field: str) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_agent_prompt(state, prompt_name)
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.director_task_args[field] = output.strip()
    state.active_stage = prompt_name
    state.last_agent_reports = append_agent_report(state.last_agent_reports, prompt_name, "ok", {"chars": len(output)})
    store.save_state(state)
    return state.to_dict()


def build_agent_prompt(state: NovelState, prompt_name: str) -> str:
    template = load_prompt(prompt_name)
    context = str(state.director_task_args.get("chapter_planning_context", ""))
    reports = format_reports(state)
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"CHAPTER: {state.active_chapter or state.current_chapter}\n\n"
        f"## Task Context\n{context or '暂无'}\n\n"
        f"## Selected Chapter Outline\n{state.director_task_args.get('selected_chapter_outline') or '暂无'}\n\n"
        f"## Agent Reports\n{reports or '暂无'}\n"
    )


def format_reports(state: NovelState) -> str:
    fields = [
        ("chapter_goal_report", "章节目标报告"),
        ("chapter_conflict_report", "冲突报告"),
        ("chapter_hook_report", "钩子报告"),
    ]
    parts = []
    for key, label in fields:
        text = str(state.director_task_args.get(key, "")).strip()
        if text:
            parts.append(f"### {label}\n{text}")
    return "\n\n".join(parts)


def collect_chapter_outline(state: NovelState) -> str:
    artifact = state.outline_stage_artifacts.get("chapter_outline", {})
    if isinstance(artifact, dict) and str(artifact.get("synthesis", "")).strip():
        return str(artifact.get("synthesis", "")).strip()
    if state.chapter_plan.strip():
        return state.chapter_plan.strip()
    if state.outline.strip():
        return state.outline.strip()
    return "暂无"


def add_missing_sections(content: str, missing: list[str]) -> str:
    text = content.rstrip()
    for section in missing:
        text += f"\n\n## {section}\n待补充。"
    return text + "\n"


def chapter_card_summary(content: str, max_chars: int = 160) -> str:
    for line in content.splitlines():
        stripped = line.strip("#：: ")
        if stripped and stripped not in CHAPTER_CARD_SECTIONS:
            return stripped[:max_chars]
    return content.strip()[:max_chars]


def append_agent_report(reports: list[dict], agent: str, status: str, data: dict) -> list[dict]:
    updated = list(reports)
    updated.append({"agent": agent, "status": status, **data})
    return updated[-20:]
