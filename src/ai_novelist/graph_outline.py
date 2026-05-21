"""Interactive outline collaboration graph."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


OUTLINE_ACTIONS = {
    "ask_user",
    "propose_directions",
    "worldbuild",
    "generate_outline",
    "review_outline",
    "revise_outline",
    "compare_versions",
    "persist_outline",
    "show_status",
    "stop",
}


def build_outline_collaboration_graph(adapter: AgentAdapter, store: LocalStore) -> CompiledGraph:
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return OutlineSequentialGraph(adapter, store)

    graph = StateGraph(dict)
    graph.add_node("director", lambda data: outline_director_node(data, adapter, store))
    graph.add_node("ask_user", lambda data: ask_user_node(data, store))
    graph.add_node("propose_directions", lambda data: propose_directions_node(data, adapter, store))
    graph.add_node("worldbuild", lambda data: outline_worldbuild_node(data, adapter, store))
    graph.add_node("generate_outline", lambda data: generate_outline_node(data, adapter, store))
    graph.add_node("review_outline", lambda data: review_outline_node(data, adapter, store))
    graph.add_node("revise_outline", lambda data: revise_outline_node(data, adapter, store))
    graph.add_node("compare_versions", lambda data: compare_outline_versions_node(data, adapter, store))
    graph.add_node("human_feedback", lambda data: human_feedback_node(data, store))
    graph.add_node("persist_outline", lambda data: persist_outline_node(data, store))
    graph.add_node("show_status", lambda data: outline_show_status_node(data, store))

    graph.set_entry_point("director")
    graph.add_conditional_edges(
        "director",
        route_after_outline_director,
        {
            "ask_user": "ask_user",
            "propose_directions": "propose_directions",
            "worldbuild": "worldbuild",
            "generate_outline": "generate_outline",
            "review_outline": "review_outline",
            "revise_outline": "revise_outline",
            "compare_versions": "compare_versions",
            "persist_outline": "persist_outline",
            "show_status": "show_status",
            "end": END,
        },
    )
    graph.add_edge("ask_user", END)
    graph.add_edge("propose_directions", "human_feedback")
    graph.add_edge("worldbuild", "generate_outline")
    graph.add_edge("generate_outline", "review_outline")
    graph.add_edge("review_outline", "human_feedback")
    graph.add_edge("revise_outline", "compare_versions")
    graph.add_edge("compare_versions", "review_outline")
    graph.add_conditional_edges(
        "human_feedback",
        route_after_human_feedback,
        {
            "persist_outline": "persist_outline",
            "revise_outline": "revise_outline",
            "propose_directions": "propose_directions",
            "review_outline": "review_outline",
            "end": END,
        },
    )
    graph.add_edge("persist_outline", END)
    graph.add_edge("show_status", END)
    return graph.compile()


class OutlineSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore) -> None:
        self.adapter = adapter
        self.store = store

    def invoke(self, state: dict) -> dict:
        current = outline_director_node(state, self.adapter, self.store)
        route = route_after_outline_director(current)
        if route == "ask_user":
            return ask_user_node(current, self.store)
        if route == "propose_directions":
            current = propose_directions_node(current, self.adapter, self.store)
            return human_feedback_node(current, self.store)
        if route == "worldbuild":
            current = outline_worldbuild_node(current, self.adapter, self.store)
            current = generate_outline_node(current, self.adapter, self.store)
            current = review_outline_node(current, self.adapter, self.store)
            return human_feedback_node(current, self.store)
        if route == "generate_outline":
            current = generate_outline_node(current, self.adapter, self.store)
            current = review_outline_node(current, self.adapter, self.store)
            return human_feedback_node(current, self.store)
        if route == "review_outline":
            current = review_outline_node(current, self.adapter, self.store)
            return human_feedback_node(current, self.store)
        if route == "revise_outline":
            current = revise_outline_node(current, self.adapter, self.store)
            current = compare_outline_versions_node(current, self.adapter, self.store)
            current = review_outline_node(current, self.adapter, self.store)
            return human_feedback_node(current, self.store)
        if route == "compare_versions":
            return compare_outline_versions_node(current, self.adapter, self.store)
        if route == "persist_outline":
            return persist_outline_node(current, self.store)
        if route == "show_status":
            return outline_show_status_node(current, self.store)
        return current


def outline_director_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    try:
        output = adapter.complete(build_outline_director_prompt(state), store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()

    decision = parse_outline_director_output(output)
    state.director_action = decision["action"]
    state.director_intent = decision["intent"]
    state.director_message = decision["message"]
    state.revision_instruction = decision["instruction"] or infer_revision_instruction(state.user_request, state.director_intent)
    state.last_user_feedback = state.user_request
    state.active_artifact = decision["target"]
    state.pending_question = decision["message"] if decision["action"] == "ask_user" else ""
    add_unique_items(state.locked_constraints, decision["locked_constraints"])
    add_unique_items(state.style_preferences, decision["style_preferences"])
    if decision["chapter"]:
        state.current_chapter = decision["chapter"]
    if state.director_action == "stop":
        state.review_status = "stopped"
        state.next_action = "stop"
    else:
        state.next_action = state.director_action
    append_message(state, "assistant", state.director_message)
    store.save_state(state)
    return state.to_dict()


def ask_user_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    question = state.director_message or "请告诉我你想修改大纲、生成多个方向、审稿还是保存。"
    add_unique_items(state.pending_questions, [question])
    state.next_action = "stop"
    store.save_state(state)
    return state.to_dict()


def propose_directions_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    try:
        directions = adapter.complete(build_outline_prompt(state, "direction_proposer"), store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    add_outline_version(state, "directions", directions, "方向提案")
    state.active_artifact = "outline"
    state.director_message = "已生成 3 个创作方向。你可以选择一个方向，或继续提出修改。"
    state.next_action = "wait_feedback"
    store.save_state(state)
    return state.to_dict()


def outline_worldbuild_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    try:
        state.worldbuilding = adapter.complete(build_outline_prompt(state, "world_builder"), store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
    else:
        state.director_message = "已补充世界观，接下来生成大纲。"
    store.save_state(state)
    return state.to_dict()


def generate_outline_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    try:
        state.outline = adapter.complete(build_outline_prompt(state, "outline_planner"), store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    add_outline_version(state, "outline", state.outline, "生成大纲")
    state.active_artifact = "outline"
    state.review_status = "draft"
    state.director_message = "已生成大纲草案，并准备进入审稿。"
    store.save_state(state)
    return state.to_dict()


def review_outline_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    try:
        state.editor_notes = adapter.complete(build_outline_prompt(state, "outline_editor"), store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    decision, score = parse_status_score(state.editor_notes)
    state.editor_decision = decision
    state.quality_score = score
    if decision == "revise":
        state.revision_instruction = state.revision_instruction or extract_outline_editor_advice(state.editor_notes)
        state.review_status = "revision_requested"
    elif decision == "pass":
        state.review_status = "draft"
    else:
        state.review_status = "stopped"
    state.director_message = f"大纲审稿完成：{decision}，质量分 {score}。"
    store.save_state(state)
    return state.to_dict()


def revise_outline_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    previous = state.outline
    try:
        revised = adapter.complete(build_outline_prompt(state, "outline_reviser"), store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    if previous.strip():
        add_outline_version(state, "outline_previous", previous, "修订前大纲")
    state.outline = revised
    state.revision_count += 1
    add_outline_version(state, "outline", state.outline, f"修订版 {state.revision_count}")
    state.review_status = "draft"
    state.director_message = "已根据反馈修订大纲，并准备比较版本和再次审稿。"
    store.save_state(state)
    return state.to_dict()


def compare_outline_versions_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    try:
        comparison = adapter.complete(build_outline_prompt(state, "version_comparator"), store.project_dir(state.project_id))
    except AgentAdapterError:
        comparison = simple_outline_comparison(state)
    state.editor_notes = (state.editor_notes + "\n\n" if state.editor_notes else "") + comparison
    state.director_message = "已比较新旧大纲版本，差异摘要已写入编辑意见。"
    store.save_state(state)
    return state.to_dict()


def human_feedback_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    intent = state.director_intent
    action = state.director_action
    if intent in {"approve", "save"} or action == "persist_outline":
        state.review_status = "approved"
        state.next_action = "persist_outline"
    elif intent == "variant" or action == "propose_directions":
        state.review_status = "draft"
        state.next_action = "end"
    elif intent == "lock":
        state.next_action = "end"
        state.director_message = "已记录锁定约束，后续修订会保留这些内容。"
    elif intent == "stop" or action == "stop":
        state.review_status = "stopped"
        state.next_action = "end"
    else:
        # Agent 节点已经完成本轮生成、审稿或修订；等待下一轮用户反馈再继续路由。
        state.next_action = "end"
    store.save_state(state)
    return state.to_dict()


def persist_outline_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if state.outline.strip():
        store.save_outline(state)
        state.review_status = "approved"
        state.director_message = f"当前大纲已保存：{store.outline_path(state.project_id)}"
    else:
        state.director_message = "当前没有可保存的大纲。"
    store.save_state(state)
    return state.to_dict()


def outline_show_status_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    state.director_message = (
        f"项目：{state.project_id}\n"
        f"创意：{state.idea or '暂无'}\n"
        f"大纲版本数：{len(state.outline_versions)}\n"
        f"锁定约束：{', '.join(state.locked_constraints) or '暂无'}\n"
        f"风格偏好：{', '.join(state.style_preferences) or '暂无'}\n"
        f"当前审稿：{state.editor_decision} / {state.quality_score}\n"
        f"大纲：{'已有' if state.outline else '暂无'} -> {store.outline_path(state.project_id)}"
    )
    store.save_state(state)
    return state.to_dict()


def route_after_outline_director(data: dict) -> str:
    action = data.get("director_action", "")
    if action in OUTLINE_ACTIONS:
        return action if action != "stop" else "end"
    if action in {"plan_outline", "generate_outline"}:
        return "generate_outline"
    return "ask_user"


def route_after_human_feedback(data: dict) -> str:
    action = data.get("next_action", "end")
    if action in {"persist_outline", "revise_outline", "propose_directions", "review_outline"}:
        return action
    return "end"


def build_outline_director_prompt(state: NovelState) -> str:
    template = load_prompt("director")
    history = "\n".join(f"{msg['role']}: {msg['content']}" for msg in state.messages[-12:])
    return (
        f"{template.rstrip()}\n\n"
        "## 当前大纲共创状态\n"
        f"项目：{state.project_id}\n"
        f"标题：{state.title}\n"
        f"创意：{state.idea or '暂无'}\n"
        f"当前大纲：{'已有' if state.outline else '暂无'}\n"
        f"大纲版本数：{len(state.outline_versions)}\n"
        f"锁定约束：{', '.join(state.locked_constraints) or '暂无'}\n"
        f"风格偏好：{', '.join(state.style_preferences) or '暂无'}\n"
        f"修订要求：{state.revision_instruction or '暂无'}\n"
        f"编辑结论：{state.editor_decision}\n"
        f"质量分：{state.quality_score}\n\n"
        f"## 最近对话\n{history or '暂无'}\n\n"
        f"最新用户输入：{state.user_request}\n"
    )


def build_outline_prompt(state: NovelState, prompt_name: str) -> str:
    template = load_prompt(prompt_name)
    versions = "\n\n".join(
        f"版本 {idx}: {item.get('label', '')}\n{item.get('content', '')}"
        for idx, item in enumerate(state.outline_versions[-3:])
    )
    return (
        f"{template.rstrip()}\n\n"
        "## 项目上下文\n"
        f"标题：{state.title}\n"
        f"创意：{state.idea}\n"
        f"世界观：\n{state.worldbuilding or '暂无'}\n\n"
        f"当前大纲：\n{state.outline or '暂无'}\n\n"
        f"修订要求：{state.revision_instruction or '暂无'}\n"
        f"锁定约束：{', '.join(state.locked_constraints) or '暂无'}\n"
        f"风格偏好：{', '.join(state.style_preferences) or '暂无'}\n"
        f"编辑意见：\n{state.editor_notes or '暂无'}\n\n"
        f"最近大纲版本：\n{versions or '暂无'}\n"
    )


def parse_outline_director_output(output: str) -> dict:
    action = field_value(output, "ACTION").lower() or "ask_user"
    if action == "plan_outline":
        action = "generate_outline"
    if action not in OUTLINE_ACTIONS:
        action = "ask_user"
    intent = field_value(output, "INTENT").lower() or "answer"
    target = field_value(output, "TARGET").lower() or "unknown"
    chapter = None
    chapter_text = field_value(output, "CHAPTER")
    if chapter_text:
        match = re.search(r"\d+", chapter_text)
        if match:
            chapter = max(1, int(match.group(0)))
    return {
        "action": action,
        "target": target,
        "intent": intent,
        "message": field_value(output, "MESSAGE") or "我会继续推进大纲共创。",
        "instruction": field_value(output, "INSTRUCTION"),
        "locked_constraints": split_csv(field_value(output, "LOCKED_CONSTRAINTS")),
        "style_preferences": split_csv(field_value(output, "STYLE_PREFERENCES")),
        "chapter": chapter,
    }


def field_value(output: str, name: str) -> str:
    match = re.search(rf"^{name}:[ \t]*(.*)$", output, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，]", value) if item.strip()]


def add_unique_items(target: list[str], items: list[str]) -> None:
    for item in items:
        if item and item not in target:
            target.append(item)


def add_outline_version(state: NovelState, kind: str, content: str, label: str) -> None:
    state.outline_versions.append(
        {
            "kind": kind,
            "label": label,
            "content": content,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    state.selected_outline_version = len(state.outline_versions) - 1


def parse_status_score(text: str) -> tuple[str, int]:
    status = field_value(text, "STATUS").lower() or "revise"
    if status not in {"pass", "revise", "stop"}:
        status = "revise"
    score_text = field_value(text, "QUALITY_SCORE")
    score = int(score_text) if score_text.isdigit() else 0
    return status, max(0, min(score, 100))


def infer_revision_instruction(user_request: str, intent: str) -> str:
    if intent in {"revise", "lock"}:
        return user_request
    return ""


def extract_outline_editor_advice(notes: str) -> str:
    lines = [line.strip() for line in notes.splitlines() if line.strip()]
    return "；".join(lines[:6])


def simple_outline_comparison(state: NovelState) -> str:
    return "# 大纲版本比较\n\n已生成新版大纲。请重点检查人物弧光、冲突强度和锁定约束是否符合预期。"


def append_message(state: NovelState, role: str, content: str) -> None:
    if content:
        state.messages.append({"role": role, "content": content})
        state.messages = state.messages[-40:]
