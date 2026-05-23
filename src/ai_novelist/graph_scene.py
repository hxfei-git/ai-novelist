"""Scene card design graph."""

from __future__ import annotations

from typing import Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.artifacts import ArtifactRecord, get_latest_artifact, load_artifact_text, load_artifacts, register_artifact
from ai_novelist.context_builder import build_context
from ai_novelist.pacing import parse_pacing_target_from_card, scene_required_fields
from ai_novelist.progress import ProgressFunc, emit_progress, noop_progress, run_with_progress, run_with_progress, with_agent_metadata
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


SCENE_FIELDS = [
    "地点",
    "出场人物",
    "场景目的",
    "人物目标",
    "冲突对象",
    "关键信息",
    "情绪变化",
    "场景转折",
    "退出状态",
]


class SceneSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> None:
        self.adapter = adapter
        self.store = store
        self.progress = progress

    def invoke(self, state: dict) -> dict:
        emit_progress(self.progress, "SceneDesign 1/6", "正在读取章节卡...")
        current = load_chapter_card_node(state, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        emit_progress(self.progress, "SceneDesign 2/6", with_agent_metadata("正在拆分章节场景...", self.adapter, "scene_breakdown_agent"))
        current = scene_breakdown_agent_node(current, self.adapter, self.store)
        emit_progress(self.progress, "SceneDesign 3/6", with_agent_metadata("正在检查场景冲突和连续性...", self.adapter, "scene_conflict_check_agent"))
        current = conflict_check_agent_node(current, self.adapter, self.store)
        emit_progress(self.progress, "SceneDesign 4/6", with_agent_metadata("正在汇总场景卡...", self.adapter, "scene_synthesizer"))
        current = scene_synthesizer_node(current, self.adapter, self.store)
        emit_progress(self.progress, "SceneDesign 5/6", "正在校验场景卡字段...")
        current = validate_scene_cards_node(current, self.store)
        emit_progress(self.progress, "SceneDesign 6/6", "正在保存场景卡...")
        current = save_scene_cards_node(current, self.store)
        return current


def build_scene_graph(adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc | None = None) -> CompiledGraph:
    progress_func = progress or noop_progress
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return SceneSequentialGraph(adapter, store, progress_func)

    graph = StateGraph(dict)
    graph.add_node("load_chapter_card", lambda data: progress_node(progress_func, "SceneDesign 1/6", "正在读取章节卡...", lambda: load_chapter_card_node(data, store)))
    graph.add_node("scene_breakdown_agent", lambda data: progress_node(progress_func, "SceneDesign 2/6", with_agent_metadata("正在拆分章节场景...", adapter, "scene_breakdown_agent"), lambda: scene_breakdown_agent_node(data, adapter, store)))
    graph.add_node("conflict_check_agent", lambda data: progress_node(progress_func, "SceneDesign 3/6", with_agent_metadata("正在检查场景冲突和连续性...", adapter, "scene_conflict_check_agent"), lambda: conflict_check_agent_node(data, adapter, store)))
    graph.add_node("scene_synthesizer", lambda data: progress_node(progress_func, "SceneDesign 4/6", with_agent_metadata("正在汇总场景卡...", adapter, "scene_synthesizer"), lambda: scene_synthesizer_node(data, adapter, store)))
    graph.add_node("validate_scene_cards", lambda data: progress_node(progress_func, "SceneDesign 5/6", "正在校验场景卡字段...", lambda: validate_scene_cards_node(data, store)))
    graph.add_node("save_scene_cards", lambda data: progress_node(progress_func, "SceneDesign 6/6", "正在保存场景卡...", lambda: save_scene_cards_node(data, store)))
    graph.set_entry_point("load_chapter_card")
    graph.add_conditional_edges("load_chapter_card", route_after_load, {"continue": "scene_breakdown_agent", "end": END})
    graph.add_edge("scene_breakdown_agent", "conflict_check_agent")
    graph.add_edge("conflict_check_agent", "scene_synthesizer")
    graph.add_edge("scene_synthesizer", "validate_scene_cards")
    graph.add_edge("validate_scene_cards", "save_scene_cards")
    graph.add_edge("save_scene_cards", END)
    return graph.compile()


def progress_node(progress: ProgressFunc, stage: str, message: str, fn) -> dict:
    return run_with_progress(progress, stage, message, fn)


def route_after_load(data: dict) -> str:
    return "end" if data.get("review_status") == "error" else "continue"


def load_chapter_card_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    chapter = int(state.director_task_args.get("chapter") or state.active_chapter or state.current_chapter or 1)
    state.active_chapter = max(1, chapter)
    state.current_chapter = state.active_chapter
    state.active_graph = "scene"
    state.active_stage = "load_chapter_card"
    state.active_artifact = "scene_cards"
    chapter_card = load_current_chapter_card(state, store)
    if not chapter_card.strip():
        state.review_status = "error"
        state.error = "缺少当前章节卡"
        state.director_action = state.director_action or "plan_scenes"
        state.director_message = f"缺少第 {state.active_chapter} 章章节卡。请先运行章节卡规划，再规划场景卡。"
        store.save_state(state)
        return state.to_dict()
    state.current_chapter_card = chapter_card
    context = build_context(state, store, "scene_design", chapter=state.active_chapter, max_chars=14000)
    state.director_task_args["scene_design_context"] = context
    state.last_context_digest = context[:1200]
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def scene_breakdown_agent_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    return run_report_agent(data, adapter, store, "scene_breakdown_agent", "scene_breakdown_report")


def conflict_check_agent_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    return run_report_agent(data, adapter, store, "scene_conflict_check_agent", "scene_conflict_report")


def scene_synthesizer_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_agent_prompt(state, "scene_synthesizer")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    state.current_scene_cards = output.strip()
    state.active_stage = "scene_synthesizer"
    state.review_status = "draft"
    state.error = ""
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "scene_synthesizer", "draft", {"chars": len(output)})
    store.save_state(state)
    return state.to_dict()


def validate_scene_cards_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    scene_count = count_scenes(state.current_scene_cards)
    pacing = parse_pacing_target_from_card(state.active_chapter or state.current_chapter or 1, state.current_chapter_card or "")
    required_fields = scene_required_fields(pacing)
    missing = [field for field in required_fields if field not in state.current_scene_cards]
    state.director_task_args["scene_cards_validation"] = {
        "missing_fields": missing,
        "required_fields": required_fields,
        "scene_count": scene_count,
        "pacing_target": pacing.to_dict(),
    }
    if scene_count < 2 or missing:
        state.current_scene_cards = add_missing_scene_validation(state.current_scene_cards, missing, scene_count)
    state.active_stage = "validate_scene_cards"
    store.save_state(state)
    return state.to_dict()


def save_scene_cards_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    path = store.save_scene_cards(state)
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="scene_cards",
            path=path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="scene_synthesizer",
            graph="scene",
            stage="scene_cards",
            chapter=state.active_chapter,
            summary=scene_cards_summary(state.current_scene_cards),
        ),
    )
    state.active_graph = "scene"
    state.active_stage = "scene_cards"
    state.active_artifact = "scene_cards"
    state.director_action = state.director_action or "plan_scenes"
    state.director_message = f"第 {state.active_chapter} 章场景卡已生成：{path}"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "scene_synthesizer", "saved", {"artifact_id": record.id, "path": record.path})
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
    context = str(state.director_task_args.get("scene_design_context", ""))
    reports = format_reports(state)
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"CHAPTER: {state.active_chapter or state.current_chapter}\n\n"
        f"## Chapter Card\n{state.current_chapter_card or '暂无'}\n\n"
        f"## Task Context\n{context or '暂无'}\n\n"
        f"## Agent Reports\n{reports or '暂无'}\n"
    )


def load_current_chapter_card(state: NovelState, store: LocalStore) -> str:
    path = store.chapter_card_path(state.project_id, state.active_chapter)
    if path.exists():
        return path.read_text(encoding="utf-8")
    record = get_latest_artifact(store.project_dir(state.project_id), "chapter_card", chapter=state.active_chapter)
    if record:
        return load_artifact_text(store.project_dir(state.project_id), record)
    if state.current_chapter_card.strip() and state.active_chapter == state.current_chapter:
        return state.current_chapter_card
    return ""


def format_reports(state: NovelState) -> str:
    fields = [
        ("scene_breakdown_report", "场景拆分报告"),
        ("scene_conflict_report", "冲突检查报告"),
    ]
    parts = []
    for key, label in fields:
        text = str(state.director_task_args.get(key, "")).strip()
        if text:
            parts.append(f"### {label}\n{text}")
    return "\n\n".join(parts)


def count_scenes(content: str) -> int:
    return sum(1 for line in content.splitlines() if line.strip().startswith(("## 场景", "### 场景", "## Scene", "### Scene")))


def add_missing_scene_validation(content: str, missing: list[str], scene_count: int) -> str:
    text = content.rstrip()
    if scene_count < 2:
        text += "\n\n## 场景 2：待补充\n"
        for field in SCENE_FIELDS:
            text += f"- {field}：待补充。\n"
    if missing:
        text += "\n## 场景卡自检补项\n" + "\n".join(f"- {field}：待补充。" for field in missing)
    return text + "\n"


def scene_cards_summary(content: str, max_chars: int = 160) -> str:
    for line in content.splitlines():
        stripped = line.strip("#：: ")
        if stripped:
            return stripped[:max_chars]
    return content.strip()[:max_chars]


def append_agent_report(reports: list[dict], agent: str, status: str, data: dict) -> list[dict]:
    updated = list(reports)
    updated.append({"agent": agent, "status": status, **data})
    return updated[-20:]
