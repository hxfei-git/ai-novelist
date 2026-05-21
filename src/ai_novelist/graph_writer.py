"""Multi-agent writer graphs for phase 2."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Literal, Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore

AgentTask = Literal["worldbuild", "plan_outline", "plan_chapters", "write_chapter", "review"]
ReviewFunc = Callable[[NovelState, AgentTask], str]
ComposerReviewFunc = Callable[[NovelState], str]
ProgressFunc = Callable[[str, str], None]


def noop_progress(_stage: str, _message: str) -> None:
    return


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


class SequentialGraph:
    def __init__(self, nodes: list[Callable[[dict], dict]]) -> None:
        self.nodes = nodes

    def invoke(self, state: dict) -> dict:
        current = dict(state)
        for node in self.nodes:
            update = node(current)
            current.update(update)
            if current.get("review_status") in {"revision_requested", "stopped", "error"}:
                break
        return current


class ComposerSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore, review_func: ComposerReviewFunc) -> None:
        self.adapter = adapter
        self.store = store
        self.review_func = review_func

    def invoke(self, state: dict) -> dict:
        current = dict(state)
        for task in ("worldbuild", "plan_outline", "plan_chapters", "write_chapter"):
            current.update(run_agent_task(current, self.adapter, self.store, task))
            if current.get("review_status") == "error":
                return current

        while True:
            current.update(editor_review_node(current, self.adapter, self.store))
            if current.get("review_status") == "error":
                return current
            if current.get("next_action") == "rewrite_chapter":
                current.update(rewrite_chapter_node(current, self.adapter, self.store))
                if current.get("review_status") == "error":
                    return current
                continue
            if current.get("next_action") == "stop":
                return current
            break

        current.update(human_review_compose(current, self.review_func))
        if current.get("review_status") == "approved":
            current.update(persist_outputs(current, self.store))
        return current


@dataclass(frozen=True)
class TaskSpec:
    prompt_name: str
    output_field: str
    display_name: str


TASKS: dict[AgentTask, TaskSpec] = {
    "worldbuild": TaskSpec("world_builder", "worldbuilding", "世界观设定"),
    "plan_outline": TaskSpec("outline_planner", "outline", "总大纲"),
    "plan_chapters": TaskSpec("chapter_planner", "chapter_plan", "章节细纲"),
    "write_chapter": TaskSpec("chapter_writer", "chapter_draft", "章节正文"),
    "review": TaskSpec("editor", "editor_notes", "编辑审稿意见"),
}


def build_writer_graph(
    adapter: AgentAdapter,
    store: LocalStore,
    task: AgentTask,
    review_func: ReviewFunc,
) -> CompiledGraph:
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return SequentialGraph(
            [
                lambda data: run_agent_task(data, adapter, store, task),
                lambda data: human_review_task(data, task, review_func),
                lambda data: persist_task_output(data, store, task),
            ]
        )

    graph = StateGraph(dict)
    graph.add_node("run_agent", lambda data: run_agent_task(data, adapter, store, task))
    graph.add_node("human_review", lambda data: human_review_task(data, task, review_func))
    graph.add_node("persist", lambda data: persist_task_output(data, store, task))
    graph.set_entry_point("run_agent")
    graph.add_edge("run_agent", "human_review")
    graph.add_conditional_edges("human_review", route_after_review, {"persist": "persist", "end": END})
    graph.add_edge("persist", END)
    return graph.compile()


def build_composer_graph(
    adapter: AgentAdapter,
    store: LocalStore,
    review_func: ComposerReviewFunc,
) -> CompiledGraph:
    """Build the full phase-2 multi-agent composer workflow."""
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return ComposerSequentialGraph(adapter, store, review_func)

    graph = StateGraph(dict)
    graph.add_node("worldbuild", lambda data: run_agent_task(data, adapter, store, "worldbuild"))
    graph.add_node("plan_outline", lambda data: run_agent_task(data, adapter, store, "plan_outline"))
    graph.add_node("plan_chapters", lambda data: run_agent_task(data, adapter, store, "plan_chapters"))
    graph.add_node("write_chapter", lambda data: run_agent_task(data, adapter, store, "write_chapter"))
    graph.add_node("editor_review", lambda data: editor_review_node(data, adapter, store))
    graph.add_node("rewrite_chapter", lambda data: rewrite_chapter_node(data, adapter, store))
    graph.add_node("human_review", lambda data: human_review_compose(data, review_func))
    graph.add_node("persist_outputs", lambda data: persist_outputs(data, store))

    graph.set_entry_point("worldbuild")
    graph.add_edge("worldbuild", "plan_outline")
    graph.add_edge("plan_outline", "plan_chapters")
    graph.add_edge("plan_chapters", "write_chapter")
    graph.add_edge("write_chapter", "editor_review")
    graph.add_conditional_edges(
        "editor_review",
        route_after_editor_review,
        {"rewrite_chapter": "rewrite_chapter", "human_review": "human_review", "end": END},
    )
    graph.add_edge("rewrite_chapter", "editor_review")
    graph.add_conditional_edges("human_review", route_after_review, {"persist": "persist_outputs", "end": END})
    graph.add_edge("persist_outputs", END)
    return graph.compile()


def route_after_review(data: dict) -> str:
    return "persist" if data.get("review_status") == "approved" else "end"


def route_after_editor_review(data: dict) -> str:
    state = NovelState.from_dict(data)
    if state.review_status == "error":
        return "end"
    if state.next_action == "rewrite_chapter":
        return "rewrite_chapter"
    if state.next_action == "human_review":
        return "human_review"
    return "end"


def run_agent_task(data: dict, adapter: AgentAdapter, store: LocalStore, task: AgentTask) -> dict:
    state = NovelState.from_dict(data)
    spec = TASKS[task]
    prompt = build_task_prompt(state, spec.prompt_name)
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()

    setattr(state, spec.output_field, output)
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def editor_review_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(run_agent_task(data, adapter, store, "review"))
    if state.review_status == "error":
        return state.to_dict()

    decision, score = parse_editor_review(state.editor_notes)
    state.editor_decision = decision
    state.quality_score = score
    if decision == "pass":
        state.next_action = "human_review"
    elif decision == "revise" and state.revision_count < state.max_revisions:
        state.next_action = "rewrite_chapter"
        state.review_status = "revision_requested"
    else:
        state.next_action = "stop"
        state.review_status = "stopped"
    store.save_state(state)
    return state.to_dict()


def rewrite_chapter_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    state.revision_count += 1
    state.next_action = "continue"
    state.review_status = "draft"
    store.save_state(state)
    return run_agent_task(state.to_dict(), adapter, store, "write_chapter")


def human_review_task(data: dict, task: AgentTask, review_func: ReviewFunc) -> dict:
    state = NovelState.from_dict(data)
    if state.review_status == "error":
        return state.to_dict()

    decision = review_func(state, task).strip().lower()
    apply_human_decision(state, decision)
    return state.to_dict()


def human_review_compose(data: dict, review_func: ComposerReviewFunc) -> dict:
    state = NovelState.from_dict(data)
    if state.review_status in {"error", "stopped"}:
        return state.to_dict()

    decision = review_func(state).strip().lower()
    apply_human_decision(state, decision)
    return state.to_dict()


def apply_human_decision(state: NovelState, decision: str) -> None:
    if decision in {"approve", "approved", "y", "yes", "确认", "通过"}:
        state.review_status = "approved"
        state.next_action = "persist"
    elif decision in {"revise", "revision", "r", "修改", "重写"}:
        state.review_status = "revision_requested"
        state.next_action = "rewrite_chapter"
    elif decision in {"stop", "s", "停止", "终止"}:
        state.review_status = "stopped"
        state.next_action = "stop"
    elif decision in {"reject", "rejected", "n", "no", "驳回", "拒绝"}:
        state.review_status = "rejected"
        state.next_action = "stop"
    else:
        state.review_status = "rejected"
        state.next_action = "stop"
        state.error = f"Unknown review decision: {decision}"


def persist_task_output(data: dict, store: LocalStore, task: AgentTask) -> dict:
    state = NovelState.from_dict(data)
    if state.review_status != "approved":
        store.save_state(state)
        return state.to_dict()

    if task == "worldbuild":
        store.save_worldbuilding(state)
    elif task == "plan_outline":
        store.save_outline(state)
    elif task == "plan_chapters":
        store.save_chapter_plan(state)
    elif task == "write_chapter":
        store.save_chapter(state)
    elif task == "review":
        store.save_editor_notes(state)
    store.save_state(state)
    return state.to_dict()


def persist_outputs(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if state.review_status != "approved":
        store.save_state(state)
        return state.to_dict()

    store.save_worldbuilding(state)
    store.save_outline(state)
    store.save_chapter_plan(state)
    store.save_chapter(state)
    store.save_editor_notes(state)
    store.save_state(state)
    return state.to_dict()


def build_task_prompt(state: NovelState, prompt_name: str) -> str:
    template = load_prompt(prompt_name)
    return (
        f"{template.rstrip()}\n\n"
        "## 当前项目上下文\n"
        f"小说标题：{state.title}\n"
        f"用户创意：{state.idea}\n"
        f"当前章节：{state.current_chapter}\n"
        f"修订次数：{state.revision_count}\n"
        f"最大修订次数：{state.max_revisions}\n"
        f"编辑结论：{state.editor_decision}\n"
        f"质量分：{state.quality_score}\n\n"
        f"## 检索上下文\n查询：{state.retrieval_query or '暂无'}\n\n{state.retrieval_context or '暂无'}\n\n来源：\n{format_retrieval_sources(state.retrieval_sources)}\n\n"
        f"## 已有世界观\n{state.worldbuilding or '暂无'}\n\n"
        f"## 已有总大纲\n{state.outline or '暂无'}\n\n"
        f"## 已有章节细纲\n{state.chapter_plan or '暂无'}\n\n"
        f"## 当前章节草稿\n{state.chapter_draft or '暂无'}\n\n"
        f"## 最近编辑意见\n{state.editor_notes or '暂无'}\n"
    )


def format_retrieval_sources(sources: list[dict]) -> str:
    if not sources:
        return "暂无"
    lines = []
    for item in sources[:5]:
        title = str(item.get("title", "无标题"))
        url = str(item.get("url", ""))
        source = str(item.get("source", "search"))
        lines.append(f"- {title} ({source}): {url}")
    return "\n".join(lines)


def parse_editor_review(editor_notes: str) -> tuple[str, int]:
    status_match = re.search(r"^STATUS:\s*(pass|revise|stop)\s*$", editor_notes, re.IGNORECASE | re.MULTILINE)
    score_match = re.search(r"^QUALITY_SCORE:\s*(\d{1,3})\s*$", editor_notes, re.IGNORECASE | re.MULTILINE)
    decision = status_match.group(1).lower() if status_match else "revise"
    score = int(score_match.group(1)) if score_match else 0
    return decision, max(0, min(score, 100))


def task_output(state: NovelState, task: AgentTask) -> str:
    return str(getattr(state, TASKS[task].output_field))


def task_display_name(task: AgentTask) -> str:
    return TASKS[task].display_name


DIRECTOR_ACTIONS = {
    "ask_user",
    "research",
    "worldbuild",
    "propose_directions",
    "generate_outline",
    "review_outline",
    "revise_outline",
    "compare_versions",
    "plan_outline",
    "plan_chapters",
    "write_chapter",
    "review",
    "revise_chapter",
    "persist_outputs",
    "show_status",
    "show_outline",
    "stop",
}

AGENT_ACTION_TO_TASK: dict[str, AgentTask] = {
    "worldbuild": "worldbuild",
    "plan_outline": "plan_outline",
    "plan_chapters": "plan_chapters",
    "write_chapter": "write_chapter",
    "review": "review",
}

OUTLINE_WORKFLOW_ACTIONS = {
    "propose_directions",
    "generate_outline",
    "review_outline",
    "revise_outline",
    "compare_versions",
    "show_outline",
}


class ChatSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc | None = None) -> None:
        self.adapter = adapter
        self.store = store
        self.progress = progress or noop_progress

    def invoke(self, state: dict) -> dict:
        current = director_node(state, self.adapter, self.store, self.progress)
        route = route_after_director(current)
        if route == "run_selected_agent":
            current.update(run_selected_agent(current, self.adapter, self.store, self.progress))
        elif route == "persist_outputs":
            current.update(persist_available_outputs(current, self.store))
        elif route == "show_status":
            current.update(show_status_node(current, self.store))
        elif route == "show_outline":
            current.update(show_outline_node(current, self.store))
        return current


def build_chat_graph(adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc | None = None) -> CompiledGraph:
    """Build a one-turn Director Agent chat workflow."""
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return ChatSequentialGraph(adapter, store, progress)

    progress_func = progress or noop_progress
    graph = StateGraph(dict)
    graph.add_node("director", lambda data: director_node(data, adapter, store, progress_func))
    graph.add_node("run_selected_agent", lambda data: run_selected_agent(data, adapter, store, progress_func))
    graph.add_node("persist_outputs", lambda data: persist_available_outputs(data, store))
    graph.add_node("show_status", lambda data: show_status_node(data, store))
    graph.add_node("show_outline", lambda data: show_outline_node(data, store))
    graph.set_entry_point("director")
    graph.add_conditional_edges(
        "director",
        route_after_director,
        {
            "run_selected_agent": "run_selected_agent",
            "persist_outputs": "persist_outputs",
            "show_status": "show_status",
            "show_outline": "show_outline",
            "end": END,
        },
    )
    graph.add_edge("run_selected_agent", END)
    graph.add_edge("persist_outputs", END)
    graph.add_edge("show_status", END)
    graph.add_edge("show_outline", END)
    return graph.compile()


def director_node(data: dict, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_director_prompt(state)
    progress("Director", "正在理解你的需求...")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()

    decision = parse_director_decision(output)
    action = decision["action"]
    message = decision["message"]
    state.director_action = action
    state.director_intent = decision["intent"]
    state.active_artifact = decision["target"]
    state.director_message = message
    state.pending_question = message if action == "ask_user" else ""
    state.active_task = action
    if action in OUTLINE_WORKFLOW_ACTIONS:
        state.active_workflow = "outline"
        state.current_stage = action
    if decision["instruction"]:
        state.revision_instruction = decision["instruction"]
    elif state.director_intent in {"revise", "lock"}:
        state.revision_instruction = state.user_request
    add_unique_texts(state.locked_constraints, decision["locked_constraints"])
    add_unique_texts(state.style_preferences, decision["style_preferences"])
    if decision["chapter"]:
        state.current_chapter = decision["chapter"]
    if action == "stop":
        state.next_action = "stop"
        state.review_status = "stopped"
    else:
        state.next_action = action
        if action in AGENT_ACTION_TO_TASK or action == "revise_chapter":
            state.review_status = "draft"
    append_message(state, "assistant", message)
    store.save_state(state)
    return state.to_dict()


def route_after_director(data: dict) -> str:
    action = data.get("director_action", "")
    if action in AGENT_ACTION_TO_TASK or action == "revise_chapter" or action in (OUTLINE_WORKFLOW_ACTIONS - {"show_outline"}):
        return "run_selected_agent"
    if action == "persist_outputs":
        return "persist_outputs"
    if action == "show_status":
        return "show_status"
    if action == "show_outline":
        return "show_outline"
    return "end"


def run_selected_agent(data: dict, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> dict:
    state = NovelState.from_dict(data)
    action = state.director_action
    if action in (OUTLINE_WORKFLOW_ACTIONS - {"show_outline"}):
        return run_selected_outline_agent(state, adapter, store, action, progress)
    if action == "revise_chapter":
        state.revision_count += 1
        state.active_task = "write_chapter"
        store.save_state(state)
        progress("ChapterWriter", "正在按反馈修订章节...")
        result = run_agent_task(state.to_dict(), adapter, store, "write_chapter")
        state = NovelState.from_dict(result)
        if state.error:
            state.director_message = summarize_agent_error(state, "write_chapter")
        else:
            state.director_message = summarize_agent_result(state, "write_chapter", revised=True)
    else:
        task = AGENT_ACTION_TO_TASK.get(action)
        if not task:
            state.director_message = "我还不能处理这个动作，请换一种说法。"
            store.save_state(state)
            return state.to_dict()
        state.active_task = task
        progress(*task_progress_message(task))
        result = run_agent_task(state.to_dict(), adapter, store, task)
        state = NovelState.from_dict(result)
        if state.error:
            state.director_message = summarize_agent_error(state, task)
        elif task == "review":
            decision, score = parse_editor_review(state.editor_notes)
            state.editor_decision = decision
            state.quality_score = score
            state.director_message = summarize_agent_result(state, task)
        else:
            state.director_message = summarize_agent_result(state, task)

    progress("Done", outline_done_message(action))
    append_message(state, "assistant", state.director_message)
    store.save_state(state)
    return state.to_dict()


def run_selected_outline_agent(state: NovelState, adapter: AgentAdapter, store: LocalStore, action: str, progress: ProgressFunc = noop_progress) -> dict:
    from ai_novelist.graph_outline import (
        compare_outline_versions_node,
        generate_outline_node,
        propose_directions_node,
        review_outline_node,
        revise_outline_node,
    )

    current = state.to_dict()
    if action == "propose_directions":
        progress("DirectionProposer", "正在生成多个创作方向...")
        current = propose_directions_node(current, adapter, store)
        state = NovelState.from_dict(current)
        state.director_message = "已生成三个大纲/创意方向，请选择一个或继续提出修改。"
    elif action == "generate_outline":
        progress("OutlinePlanner", "正在生成大纲草案...")
        current = generate_outline_node(current, adapter, store)
        progress("OutlineEditor", "正在审查大纲...")
        current = review_outline_node(current, adapter, store)
        state = NovelState.from_dict(current)
        state.director_message = f"已生成并审查大纲：{state.editor_decision}，质量分 {state.quality_score}。"
    elif action == "review_outline":
        progress("OutlineEditor", "正在审查大纲...")
        current = review_outline_node(current, adapter, store)
        state = NovelState.from_dict(current)
        state.director_message = f"大纲审查完成：{state.editor_decision}，质量分 {state.quality_score}。"
    elif action == "revise_outline":
        progress("OutlineReviser", "正在按反馈修订大纲...")
        current = revise_outline_node(current, adapter, store)
        progress("VersionComparator", "正在比较大纲版本...")
        current = compare_outline_versions_node(current, adapter, store)
        progress("OutlineEditor", "正在审查大纲...")
        current = review_outline_node(current, adapter, store)
        state = NovelState.from_dict(current)
        state.director_message = f"已按反馈修订大纲并复审：{state.editor_decision}，质量分 {state.quality_score}。"
    elif action == "compare_versions":
        progress("VersionComparator", "正在比较大纲版本...")
        current = compare_outline_versions_node(current, adapter, store)
        state = NovelState.from_dict(current)
        state.director_message = "已比较最近的大纲版本，差异摘要已写入编辑意见。"
    progress("Done", outline_done_message(action))
    append_message(state, "assistant", state.director_message)
    store.save_state(state)
    return state.to_dict()


def persist_available_outputs(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    saved: list[str] = []
    if state.worldbuilding.strip():
        saved.append(str(store.save_worldbuilding(state)))
    if state.outline.strip():
        saved.append(str(store.save_outline(state)))
    if state.chapter_plan.strip():
        saved.append(str(store.save_chapter_plan(state)))
    if state.chapter_draft.strip():
        saved.append(str(store.save_chapter(state)))
    if state.editor_notes.strip():
        saved.append(str(store.save_editor_notes(state)))
    state.review_status = "approved" if saved else "draft"
    state.director_message = "已保存当前产物：\n" + "\n".join(saved) if saved else "当前还没有可保存的产物。"
    append_message(state, "assistant", state.director_message)
    store.save_state(state)
    return state.to_dict()


def show_status_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    lines = [
        f"项目：{state.project_id}",
        f"标题：{state.title}",
        f"创意：{state.idea or '暂无'}",
        f"当前章节：{state.current_chapter}",
        f"审核状态：{state.review_status}",
        f"编辑结论：{state.editor_decision}",
        f"质量分：{state.quality_score}",
        f"修订次数：{state.revision_count}/{state.max_revisions}",
        artifact_status("世界观", state.worldbuilding, store.worldbuilding_path(state.project_id)),
        artifact_status("参考简报", state.reference_brief, store.reference_brief_path(state.project_id)),
        artifact_status("总大纲", state.outline, store.outline_path(state.project_id)),
        artifact_status("章节细纲", state.chapter_plan, store.chapter_plan_path(state.project_id)),
        artifact_status("章节正文", state.chapter_draft, store.chapter_path(state.project_id, state.current_chapter)),
        artifact_status("编辑意见", state.editor_notes, store.editor_notes_path(state.project_id, state.current_chapter)),
    ]
    state.director_message = "\n".join(lines)
    append_message(state, "assistant", state.director_message)
    store.save_state(state)
    return state.to_dict()


def show_outline_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if state.outline.strip():
        state.director_message = "当前大纲：\n" + state.outline
    else:
        state.director_message = "当前还没有大纲草案。你可以先说：生成大纲。"
    append_message(state, "assistant", state.director_message)
    store.save_state(state)
    return state.to_dict()


def task_progress_message(task: AgentTask) -> tuple[str, str]:
    if task == "worldbuild":
        return "WorldBuilder", "正在设计世界观..."
    if task == "plan_outline":
        return "OutlinePlanner", "正在生成大纲草案..."
    if task == "plan_chapters":
        return "ChapterPlanner", "正在生成章节细纲..."
    if task == "write_chapter":
        return "ChapterWriter", "正在生成章节正文..."
    if task == "review":
        return "Editor", "正在审查章节..."
    return "Agent", "正在执行任务..."


def outline_done_message(action: str) -> str:
    if action in {"generate_outline", "plan_outline"}:
        return "大纲草案已生成，等待你查看、修改或保存。"
    if action == "revise_outline":
        return "大纲已修订并复审，等待你查看、继续修改或保存。"
    if action == "review_outline":
        return "大纲审查已完成。"
    if action == "propose_directions":
        return "创作方向已生成，等待你选择或继续修改。"
    if action == "compare_versions":
        return "大纲版本比较已完成。"
    return "当前任务已完成。"


def artifact_status(label: str, content: str, path) -> str:
    if not content.strip():
        return f"{label}：暂无"
    if path.exists():
        return f"{label}：已保存 -> {path}"
    if label == "总大纲":
        return f"{label}：草案已生成，尚未确认保存。输入‘查看大纲’查看正文，输入‘保存大纲’写入 {path}"
    return f"{label}：草案已生成，尚未确认保存。保存后写入 {path}"


def build_director_prompt(state: NovelState) -> str:
    template = load_prompt("director")
    history = "\n".join(f"{msg['role']}: {msg['content']}" for msg in state.messages[-12:])
    return (
        f"{template.rstrip()}\n\n"
        "## 当前项目状态\n"
        f"项目：{state.project_id}\n"
        f"标题：{state.title}\n"
        f"创意：{state.idea or '暂无'}\n"
        f"当前章节：{state.current_chapter}\n"
        f"世界观：{'已有' if state.worldbuilding else '暂无'}\n"
        f"总大纲：{'已有' if state.outline else '暂无'}\n"
        f"章节细纲：{'已有' if state.chapter_plan else '暂无'}\n"
        f"章节正文：{'已有' if state.chapter_draft else '暂无'}\n"
        f"编辑意见：{'已有' if state.editor_notes else '暂无'}\n"
        f"编辑结论：{state.editor_decision}\n"
        f"质量分：{state.quality_score}\n\n"
        f"## 最近对话\n{history or '暂无'}\n\n"
        f"最新用户输入：{state.user_request}\n"
    )


def parse_director_output(output: str) -> tuple[str, str, int | None]:
    decision = parse_director_decision(output)
    return decision["action"], decision["message"], decision["chapter"]


def parse_director_decision(output: str) -> dict:
    action = extract_director_field(output, "ACTION").strip().lower()
    if action == "persist_outline":
        action = "persist_outputs"
    if action == "plan_outline":
        action = "generate_outline"
    message = extract_director_field(output, "MESSAGE").strip()
    chapter_text = extract_director_field(output, "CHAPTER").strip()
    if action not in DIRECTOR_ACTIONS:
        action = "ask_user"
    if not message:
        message = "我需要更多信息才能决定下一步。"
    chapter = None
    if chapter_text:
        match = re.search(r"\d+", chapter_text)
        if match:
            chapter = max(1, int(match.group(0)))
    return {
        "action": action,
        "target": extract_director_field(output, "TARGET").strip().lower() or "unknown",
        "intent": extract_director_field(output, "INTENT").strip().lower() or "answer",
        "message": message,
        "instruction": extract_director_field(output, "INSTRUCTION").strip(),
        "locked_constraints": split_director_list(extract_director_field(output, "LOCKED_CONSTRAINTS")),
        "style_preferences": split_director_list(extract_director_field(output, "STYLE_PREFERENCES")),
        "chapter": chapter,
    }


def split_director_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，]", value) if item.strip()]


def add_unique_texts(target: list[str], values: list[str]) -> None:
    for value in values:
        if value and value not in target:
            target.append(value)


def extract_director_field(output: str, field: str) -> str:
    pattern = rf"^{field}:[ \t]*(.*)$"
    match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
    return match.group(1) if match else ""


def append_message(state: NovelState, role: str, content: str) -> None:
    if not content:
        return
    state.messages.append({"role": role, "content": content})
    state.messages = state.messages[-40:]


def summarize_agent_result(state: NovelState, task: AgentTask, revised: bool = False) -> str:
    if task == "worldbuild":
        return "世界观 Agent 已完成设定草案，包含世界规则、冲突来源和可持续写作素材。"
    if task == "plan_outline":
        return "大纲 Agent 已完成总大纲草案，包含主线、人物弧光、章节钩子和伏笔回收。"
    if task == "plan_chapters":
        return "章节细纲 Agent 已完成章节规划，包含场景列表、冲突递进和连续性约束。"
    if task == "write_chapter":
        return "章节写手已根据编辑意见重写当前章节。" if revised else f"章节写手已完成第 {state.current_chapter} 章草稿。"
    if task == "review":
        return f"编辑 Agent 已完成审稿：{state.editor_decision}，质量分 {state.quality_score}。"
    return "子 Agent 已完成当前任务。"


def summarize_agent_error(state: NovelState, task: AgentTask) -> str:
    return f"{task_display_name(task)} Agent 执行失败：{state.error}"
