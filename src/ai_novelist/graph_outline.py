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
    "show_outline",
    "run_outline_stage",
    "advance_outline_stage",
    "show_outline_stage",
    "stop",
}

OUTLINE_STAGES = ["direction", "worldbuilding", "characters", "story_flow", "outline_draft", "review_lock"]
STAGE_LABELS = {
    "direction": "方向定位",
    "worldbuilding": "世界观设定",
    "characters": "人物关系",
    "story_flow": "故事流程",
    "outline_draft": "总大纲草案",
    "review_lock": "审稿锁定",
    "done": "已锁定",
}
STAGE_ROLES = {
    "direction": ["类型定位 Agent", "主题卖点 Agent", "风险编辑 Agent"],
    "worldbuilding": ["规则架构 Agent", "冲突资源 Agent", "原作/检索一致性 Agent"],
    "characters": ["主角弧光 Agent", "关系冲突 Agent", "反派/势力 Agent"],
    "story_flow": ["主线结构 Agent", "节奏悬念 Agent", "伏笔代价 Agent"],
    "outline_draft": ["大纲策划 Agent", "连续性编辑 Agent", "章节可执行性 Agent"],
    "review_lock": ["总编辑 Agent", "约束审计 Agent", "章节准备 Agent"],
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
    graph.add_node("show_outline", lambda data: outline_show_outline_node(data, store))
    graph.add_node("run_outline_stage", lambda data: run_outline_stage_node(data, adapter, store))
    graph.add_node("advance_outline_stage", lambda data: advance_outline_stage_node(data, adapter, store))
    graph.add_node("show_outline_stage", lambda data: show_outline_stage_node(data, store))

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
            "show_outline": "show_outline",
            "run_outline_stage": "run_outline_stage",
            "advance_outline_stage": "advance_outline_stage",
            "show_outline_stage": "show_outline_stage",
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
    graph.add_edge("show_outline", END)
    graph.add_edge("run_outline_stage", END)
    graph.add_edge("advance_outline_stage", END)
    graph.add_edge("show_outline_stage", END)
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
        if route == "show_outline":
            return outline_show_outline_node(current, self.store)
        if route == "run_outline_stage":
            return run_outline_stage_node(current, self.adapter, self.store)
        if route == "advance_outline_stage":
            return advance_outline_stage_node(current, self.adapter, self.store)
        if route == "show_outline_stage":
            return show_outline_stage_node(current, self.store)
        return current


def outline_director_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    ensure_outline_stage(state)
    user_text = state.user_request.strip()

    if state.outline.strip() and is_final_outline_view_request(user_text):
        state.director_action = "show_outline"
        state.director_intent = "status"
        state.director_message = "我会展示当前已生成的大纲。"
    elif state.outline.strip() and is_final_outline_save_request(user_text):
        state.director_action = "persist_outline"
        state.director_intent = "save"
        state.director_message = "我会保存当前已生成的大纲。"
    elif is_lock_request(user_text):
        constraint = user_text.split("：", 1)[-1].split(":", 1)[-1].strip() or user_text
        add_unique_items(state.locked_constraints, [constraint])
        state.director_action = "run_outline_stage" if state.active_workflow == "outline" else "show_status"
        state.director_intent = "lock"
        state.director_message = "已记录锁定约束，后续阶段产物会遵守。"
    else:
        explicit_stage = detect_stage_reference(user_text)
        if explicit_stage and is_stage_switch_request(user_text):
            state.outline_stage = explicit_stage  # type: ignore[assignment]
            state.outline_stage_status = "collecting"
            record_stage_history(state, "switch", explicit_stage, user_text)
            state.director_action = "run_outline_stage"
            state.director_intent = "revise" if is_revision_request(user_text) else "create"
            state.director_message = f"已切换到第 {stage_number(explicit_stage)} 阶段：{STAGE_LABELS[explicit_stage]}。我会重新组织这一阶段的共创。"
        elif explicit_stage and is_stage_view_request(user_text):
            state.director_action = "show_outline_stage"
            state.director_intent = "status"
            state.director_task_args = {"stage": explicit_stage}
            state.director_message = f"我会展示{STAGE_LABELS[explicit_stage]}阶段产物。"
        elif is_stage_confirmation(user_text):
            state.director_action = "advance_outline_stage"
            state.director_intent = "approve"
            state.director_message = "我会锁定当前阶段，并进入下一阶段。"
        elif should_run_outline_stage(user_text, state):
            state.director_action = "run_outline_stage"
            state.director_intent = "revise" if is_revision_request(user_text) else "create"
            state.director_message = f"我会推进第 {stage_number(state.outline_stage)} 阶段：{STAGE_LABELS[state.outline_stage]}。"
        else:
            try:
                output = adapter.complete(build_outline_director_prompt(state), store.project_dir(state.project_id))
            except AgentAdapterError as exc:
                state.error = str(exc)
                state.review_status = "error"
                store.save_state(state)
                return state.to_dict()
            decision = parse_outline_director_output(output)
            action = stage_action_from_director(decision["action"], user_text, state)
            state.director_action = action
            state.director_intent = decision["intent"]
            state.director_message = decision["message"]
            state.revision_instruction = decision["instruction"] or infer_revision_instruction(state.user_request, state.director_intent)
            state.active_artifact = decision["target"]
            add_unique_items(state.locked_constraints, decision["locked_constraints"])
            add_unique_items(state.style_preferences, decision["style_preferences"])
            if decision["chapter"]:
                state.current_chapter = decision["chapter"]

    state.last_user_feedback = state.user_request
    state.active_artifact = state.active_artifact or "outline_stage"
    state.active_workflow = "outline" if state.director_action != "stop" else ""
    state.current_stage = state.outline_stage
    state.pending_question = state.director_message if state.director_action == "ask_user" else ""
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


def run_outline_stage_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    ensure_outline_stage(state)
    stage = state.outline_stage
    if stage == "done":
        state.director_message = "最终大纲已经锁定。可以进入章节细纲或正文写作。"
        state.next_action = "end"
        store.save_state(state)
        return state.to_dict()

    role_reviews: list[dict[str, str]] = []
    for role in STAGE_ROLES[stage]:
        try:
            output = adapter.complete(build_outline_stage_role_prompt(state, stage, role), store.project_dir(state.project_id))
        except AgentAdapterError as exc:
            state.error = str(exc)
            state.review_status = "error"
            store.save_state(state)
            return state.to_dict()
        role_reviews.append({"role": role, "content": output})

    try:
        synthesis = adapter.complete(build_outline_stage_synthesizer_prompt(state, stage, role_reviews), store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()

    artifact = {
        "stage": stage,
        "label": STAGE_LABELS[stage],
        "status": "options_ready",
        "role_reviews": role_reviews,
        "synthesis": synthesis,
        "user_feedback": state.user_request,
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    state.outline_stage_artifacts[stage] = artifact
    state.outline_stage_status = "options_ready"
    state.review_status = "draft"
    state.active_workflow = "outline"
    state.current_stage = stage
    state.active_artifact = "outline_stage"
    state.director_action = "run_outline_stage"
    questions = extract_stage_confirmation_questions(synthesis)
    state.director_message = stage_ready_message(stage, questions)
    if questions:
        state.pending_questions = questions
        state.pending_question = "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))
    else:
        state.pending_question = f"请确认是否锁定{STAGE_LABELS[stage]}并进入下一阶段，或继续提出修改。"
        state.pending_questions = [state.pending_question]
    record_stage_history(state, "run", stage, state.user_request)
    store.save_outline_stage(state, stage, format_stage_markdown(artifact))
    store.save_state(state)
    return state.to_dict()


def advance_outline_stage_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    ensure_outline_stage(state)
    stage = state.outline_stage
    hydrate_stage_artifact_from_legacy_fields(state, stage, store)
    lock_previous_stage_artifacts(state, stage)
    if stage == "done":
        state.director_message = "最终大纲已经锁定，无需再次推进。"
        store.save_state(state)
        return state.to_dict()
    if stage not in state.outline_stage_artifacts:
        state.director_action = "run_outline_stage"
        state.director_message = f"当前第 {stage_number(stage)} 阶段还没有可锁定产物，我先生成{STAGE_LABELS[stage]}。"
        store.save_state(state)
        return run_outline_stage_node(state.to_dict(), adapter, store)

    artifact = dict(state.outline_stage_artifacts[stage])
    artifact["status"] = "locked"
    artifact["locked_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    state.outline_stage_artifacts[stage] = artifact
    record_stage_history(state, "lock", stage, state.user_request)

    next_stage = next_outline_stage(stage)
    if next_stage is None:
        finalize_locked_outline(state, store)
        store.save_state(state)
        return state.to_dict()

    state.outline_stage = next_stage  # type: ignore[assignment]
    state.outline_stage_status = "collecting"
    state.current_stage = next_stage
    state.director_action = "run_outline_stage"
    state.director_message = f"已锁定{STAGE_LABELS[stage]}，进入第 {stage_number(next_stage)} 阶段：{STAGE_LABELS[next_stage]}。"
    state.pending_question = f"请确认是否锁定{STAGE_LABELS[next_stage]}并进入下一阶段，或继续提出修改。"
    state.pending_questions = [state.pending_question]
    store.save_state(state)
    return run_outline_stage_node(state.to_dict(), adapter, store)



def hydrate_stage_artifact_from_legacy_fields(state: NovelState, stage: str, store: LocalStore) -> None:
    if stage in state.outline_stage_artifacts:
        return
    if stage != "worldbuilding" or not state.worldbuilding.strip():
        return
    artifact = {
        "stage": "worldbuilding",
        "label": STAGE_LABELS["worldbuilding"],
        "status": "options_ready",
        "role_reviews": [],
        "synthesis": state.worldbuilding.strip(),
        "user_feedback": state.user_request,
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    state.outline_stage_artifacts["worldbuilding"] = artifact
    store.save_outline_stage(state, "worldbuilding", format_stage_markdown(artifact))


def lock_previous_stage_artifacts(state: NovelState, stage: str) -> None:
    if stage not in OUTLINE_STAGES:
        return
    for previous_stage in OUTLINE_STAGES[: OUTLINE_STAGES.index(stage)]:
        artifact = state.outline_stage_artifacts.get(previous_stage)
        if isinstance(artifact, dict) and artifact.get("status") != "locked":
            artifact = dict(artifact)
            artifact["status"] = "locked"
            artifact.setdefault("locked_at", datetime.now(UTC).isoformat(timespec="seconds"))
            state.outline_stage_artifacts[previous_stage] = artifact

def show_outline_stage_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    stage = str(state.director_task_args.get("stage") or detect_stage_reference(state.user_request) or state.outline_stage)
    artifact = state.outline_stage_artifacts.get(stage)
    if artifact:
        state.director_message = format_stage_markdown(artifact)
    else:
        saved = store.load_outline_stage(state.project_id, stage)
        if saved:
            state.director_message = saved
        elif stage == "worldbuilding" and state.worldbuilding.strip():
            state.director_message = "# 世界观设定\n\n" + state.worldbuilding.strip()
        else:
            state.director_message = f"{STAGE_LABELS.get(stage, stage)}阶段还没有产物。"
    store.save_state(state)
    return state.to_dict()


def ensure_outline_stage(state: NovelState) -> None:
    if state.outline_stage == "done":
        state.outline_stage_status = "done"
        return
    if state.outline_stage not in OUTLINE_STAGES:
        state.outline_stage = "direction"
    if not state.outline_stage_status:
        state.outline_stage_status = "collecting"


def should_run_outline_stage(text: str, state: NovelState) -> bool:
    if state.active_workflow == "outline":
        return True
    markers = ("生成大纲", "写大纲", "大纲", "方向", "世界观", "人物", "故事流程", "主线", "审稿", "锁定")
    return any(marker in text for marker in markers)


def is_final_outline_view_request(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"show outline", "查看大纲", "当前大纲"} or any(marker in text for marker in ("查看大纲", "当前大纲", "看一下大纲", "展示大纲"))


def is_final_outline_save_request(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"approve", "save outline", "保存大纲", "确认大纲"} or any(marker in text for marker in ("保存大纲", "确认大纲", "写入大纲"))


def is_lock_request(text: str) -> bool:
    return any(marker in text for marker in ("这个设定别改", "别改", "不要改", "保留"))


def is_stage_confirmation(text: str) -> bool:
    lowered = text.strip().lower()
    exact = {"确认", "下一阶段", "进入下一阶段", "确认进入下一阶段", "锁定", "锁定当前阶段", "ok", "yes", "approve", "confirm"}
    if lowered in exact:
        return True
    return any(marker in text for marker in ("确认进入下一阶段", "锁定并进入", "进入下一阶段", "推进到下一阶段"))


def is_revision_request(text: str) -> bool:
    return any(marker in text for marker in ("修改", "调整", "重做", "重新", "不要", "更", "太", "强化", "补充"))


def is_stage_view_request(text: str) -> bool:
    return any(marker in text for marker in ("查看", "看一下", "展示", "显示"))


def is_stage_switch_request(text: str) -> bool:
    return any(marker in text for marker in ("回到", "重做", "重新做", "切换到")) or is_revision_request(text)


def detect_stage_reference(text: str) -> str | None:
    mapping = [
        ("direction", ("方向", "定位", "类型", "卖点")),
        ("worldbuilding", ("世界观", "设定", "规则")),
        ("characters", ("人物", "人设", "关系", "反派", "势力")),
        ("story_flow", ("故事流程", "流程", "主线", "节奏", "伏笔")),
        ("outline_draft", ("总大纲", "大纲草案", "草案")),
        ("review_lock", ("审稿", "锁定", "终审")),
    ]
    for stage, markers in mapping:
        if any(marker in text for marker in markers):
            return stage
    return None


def stage_action_from_director(action: str, user_text: str, state: NovelState) -> str:
    if action in {"propose_directions", "worldbuild", "generate_outline", "review_outline", "revise_outline", "compare_versions"}:
        if action == "worldbuild":
            state.outline_stage = "worldbuilding"
        elif action == "review_outline":
            state.outline_stage = "review_lock"
        return "run_outline_stage"
    if action == "persist_outline":
        return "advance_outline_stage" if state.outline_stage != "done" else "persist_outline"
    if action == "show_outline":
        return "show_outline_stage" if state.active_workflow == "outline" and not state.outline.strip() else "show_outline"
    if is_stage_confirmation(user_text):
        return "advance_outline_stage"
    return action


def stage_number(stage: str) -> int:
    return OUTLINE_STAGES.index(stage) + 1 if stage in OUTLINE_STAGES else len(OUTLINE_STAGES)


def next_outline_stage(stage: str) -> str | None:
    if stage not in OUTLINE_STAGES:
        return "direction"
    index = OUTLINE_STAGES.index(stage)
    if index + 1 >= len(OUTLINE_STAGES):
        return None
    return OUTLINE_STAGES[index + 1]


def record_stage_history(state: NovelState, event: str, stage: str, user_text: str) -> None:
    state.outline_stage_history.append(
        {
            "event": event,
            "stage": stage,
            "user_text": user_text,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    state.outline_stage_history = state.outline_stage_history[-80:]


def build_outline_stage_role_prompt(state: NovelState, stage: str, role: str) -> str:
    return (
        "AGENT: outline_stage_role\n"
        f"ROLE: {role}\n"
        f"STAGE: {stage}\n"
        f"STAGE_LABEL: {STAGE_LABELS[stage]}\n\n"
        f"用户最新输入：{state.user_request}\n"
        f"创意：{state.idea or '暂无'}\n"
        f"检索上下文：\n{state.retrieval_context or state.reference_brief or '暂无'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, stage)}\n\n"
        f"当前阶段已有内容：\n{current_stage_context(state, stage)}\n\n"
        f"阶段连续性要求：\n{stage_continuity_requirement(stage)}\n\n"
        "请只输出该角色的短评：机会、风险、建议各 1-3 条。"
        "建议必须基于前序已保存阶段内容和当前阶段已有内容继续创作，"
        "不得把本阶段写成与前序设定割裂的新故事。"
    )


def build_outline_stage_synthesizer_prompt(state: NovelState, stage: str, role_reviews: list[dict[str, str]]) -> str:
    reviews = "\n\n".join(f"## {item['role']}\n{item['content']}" for item in role_reviews)
    if stage == "direction":
        output_rule = (
            "方向定位不是评审报告，而是后续世界观、人物和剧情都会继承的创作基准。"
            "必须把用户最新输入与当前阶段已有内容整合成一版新的方向定位稿；"
            "不要追加、罗列或保留历史修改记录，不要把用户意见单独堆成段落。"
            "若新意见与旧方向重复，合并去重；若冲突，以用户最新输入为准并改写旧方向。"
            "最终文本必须短、准、可执行，而不是资料汇编。"
            "请只输出一个 Markdown 小节：\n"
            "## 方向定位稿\n"
            "用 6-10 条短句同时确定故事类型、主角行动方式、核心冲突、情绪基调、关键关系、主要代价、全书开篇切入、中期升级、后期终局和禁止跑偏项；"
            "不能只写开篇局面，必须让后续世界观、人物关系和故事流程能看见中期与结尾方向；"
            "不要再拆成“一句话方向 / 方向命令 / 不许跑偏”。"
        )
    else:
        output_rule = (
            "请综合为用户可读的阶段产物，但不要输出让用户误以为必须逐项选择的“候选项 A/B/C”。"
            "如果有多个方案，请直接以“已采用设定”写明本轮建议采用哪一版，以及为什么适合当前故事；"
            "未采用方案只在必要时用一句话说明，不要展开成选择菜单。"
            "最后必须输出“仍需确认的问题”，只列真正需要用户补充或拍板的问题；"
            "如果没有必须确认的问题，写“暂无，当前阶段可继续修改或确认进入下一阶段”。"
            "请只输出以下 Markdown 结构：\n"
            "## Director 汇总\n"
            "整合本阶段的核心关系、规则或流程，不写机会/风险/建议。\n"
            "## 已采用设定\n"
            "列出本轮已经纳入阶段产物的明确设定。\n"
            "## 仍需确认的问题\n"
            "只列用户下一步真正需要回答的问题，不要伪装成候选菜单。"
        )
    return (
        "AGENT: outline_stage_synthesizer\n"
        f"STAGE: {stage}\n"
        f"STAGE_LABEL: {STAGE_LABELS[stage]}\n\n"
        f"创意：{state.idea or '暂无'}\n"
        f"用户最新输入：{state.user_request}\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, stage)}\n\n"
        f"当前阶段已有内容：\n{current_stage_context(state, stage)}\n\n"
        f"阶段连续性要求：\n{stage_continuity_requirement(stage)}\n\n"
        f"角色短评：\n{reviews}\n\n"
        f"{output_rule}"
    )


def previous_stage_context(state: NovelState, stage: str, max_chars_per_stage: int = 1800) -> str:
    if stage not in OUTLINE_STAGES:
        return "暂无"
    parts: list[str] = []
    for previous_stage in OUTLINE_STAGES[: OUTLINE_STAGES.index(stage)]:
        artifact = state.outline_stage_artifacts.get(previous_stage)
        if not isinstance(artifact, dict):
            continue
        synthesis = str(artifact.get("synthesis", "")).strip()
        if not synthesis:
            continue
        status = str(artifact.get("status") or "draft")
        if len(synthesis) > max_chars_per_stage:
            synthesis = synthesis[:max_chars_per_stage].rstrip() + "\n..."
        parts.append(f"## {STAGE_LABELS[previous_stage]}（{status}）\n{synthesis}")
    return "\n\n".join(parts) or "暂无"


def current_stage_context(state: NovelState, stage: str, max_chars: int = 2400) -> str:
    artifact = state.outline_stage_artifacts.get(stage)
    if not isinstance(artifact, dict):
        return "暂无"
    synthesis = str(artifact.get("synthesis", "")).strip()
    if not synthesis:
        return "暂无"
    status = str(artifact.get("status") or state.outline_stage_status or "draft")
    if len(synthesis) > max_chars:
        synthesis = synthesis[:max_chars].rstrip() + "\n..."
    return f"## {STAGE_LABELS.get(stage, stage)}（{status}）\n{synthesis}"


def stage_continuity_requirement(stage: str) -> str:
    requirements = {
        "direction": "方向定位是后续所有阶段的源头：输出必须成为世界观、人物关系和故事流程可执行的控制稿。",
        "worldbuilding": "世界观必须承接方向定位提出的类型、冲突、情绪和禁止项；每条规则都要服务这个故事方向。",
        "characters": "人物关系必须承接方向定位和世界观规则；人物欲望、关系张力和阵营冲突要由已保存设定自然生长。",
        "story_flow": "故事流程必须承接方向定位、世界观代价和人物关系冲突；转折不能脱离已建立的规则和人物动机。",
        "outline_draft": "总大纲草案必须整合方向、世界观、人物关系和故事流程，形成同一条连续故事骨架。",
        "review_lock": "审稿锁定必须检查六阶段是否互相承接，并指出任何方向、规则、人物、流程或章节草案的割裂点。",
    }
    return requirements.get(stage, "本阶段必须承接前序已保存阶段内容继续创作。")


def locked_stage_summary(state: NovelState) -> str:
    parts = []
    for stage in OUTLINE_STAGES:
        artifact = state.outline_stage_artifacts.get(stage)
        if artifact and artifact.get("status") == "locked":
            parts.append(f"## {STAGE_LABELS[stage]}\n{artifact.get('synthesis', '')}")
    return "\n\n".join(parts) or "暂无"


def format_stage_markdown(artifact: dict) -> str:
    if not artifact:
        return ""
    stage = str(artifact.get("stage", ""))
    lines = [f"# {artifact.get('label') or STAGE_LABELS.get(stage, '阶段产物')}", ""]
    user_feedback = str(artifact.get("user_feedback", "")).strip()
    if user_feedback and stage != "direction":
        lines.append("## 用户本轮反馈")
        lines.append(user_feedback)
        lines.append("")
    synthesis = str(artifact.get("synthesis", "")).strip()
    if synthesis:
        heading = "## 方向控制稿" if stage == "direction" else "## Director 汇总"
        lines.append(heading)
        lines.append(synthesis)
    if stage != "direction":
        role_reviews = artifact.get("role_reviews") if isinstance(artifact.get("role_reviews"), list) else []
        if role_reviews:
            lines.append("")
            lines.append("## 角色短评")
            for item in role_reviews:
                if isinstance(item, dict):
                    lines.append(f"### {item.get('role', 'Agent')}")
                    lines.append(str(item.get("content", "")).strip())
                    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def stage_ready_message(stage: str, questions: list[str] | None = None) -> str:
    message = f"第 {stage_number(stage)} 阶段「{STAGE_LABELS[stage]}」已完成本轮共创。"
    if questions:
        question_lines = "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))
        return (
            message
            + "\n\n本阶段还有这些需要你确认的问题：\n"
            + question_lines
            + "\n\n你可以直接逐条回答；如果认可当前设定，也可以说“确认进入下一阶段”。"
        )
    return message + "你可以继续反馈修改，或明确说“确认进入下一阶段”来锁定。"


def extract_stage_confirmation_questions(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    collecting = False
    questions: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if collecting and questions:
                continue
            continue
        if line.startswith("## ") or line.startswith("### "):
            title = line.lstrip("#").strip()
            collecting = title in {"仍需确认的问题", "待确认问题", "待确认的问题"}
            continue
        if not collecting:
            continue
        if line.startswith("#"):
            break
        if line in {"暂无", "暂无。", "无", "无。"} or "暂无" in line:
            continue
        cleaned = re.sub(r"^[-*+•\s]*", "", line)
        cleaned = re.sub(r"^\d+[.、)]\s*", "", cleaned).strip()
        cleaned = cleaned.strip(" ：:")
        if cleaned:
            questions.append(cleaned)
    return list(dict.fromkeys(questions))[:8]


def finalize_locked_outline(state: NovelState, store: LocalStore) -> None:
    sections = []
    for stage in OUTLINE_STAGES:
        artifact = state.outline_stage_artifacts.get(stage, {})
        synthesis = str(artifact.get("synthesis", "")).strip()
        if synthesis:
            sections.append(f"## {STAGE_LABELS[stage]}\n\n{synthesis}")
    state.outline = "# 最终锁定总大纲\n\n" + "\n\n".join(sections)
    state.outline_stage = "done"
    state.outline_stage_status = "done"
    state.review_status = "approved"
    state.editor_decision = "pass"
    state.active_workflow = ""
    state.current_stage = "chapter_plan"
    state.director_action = "advance_outline_stage"
    state.director_message = f"六阶段大纲已锁定，并保存为最终大纲：{store.outline_path(state.project_id)}"
    add_outline_version(state, "outline", state.outline, "六阶段锁定大纲")
    store.save_outline(state)


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
        state.active_workflow = ""
        state.current_stage = "chapter_plan"
        state.director_message = f"当前大纲已保存：{store.outline_path(state.project_id)}"
    else:
        state.director_message = "当前没有可保存的大纲。"
    store.save_state(state)
    return state.to_dict()


def outline_show_outline_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    if state.outline.strip():
        state.director_message = "当前大纲：\n" + state.outline
    else:
        state.director_message = "当前还没有大纲草案。你可以先说：给我几个方向，或生成大纲。"
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
        f"参考简报：{'已有' if state.reference_brief else '暂无'}\n"
        f"检索上下文：{'已有' if state.retrieval_context else '暂无'}\n"
        f"检索查询：{state.retrieval_query or '暂无'}\n"
        f"原作不确定点：{', '.join(state.research_uncertainties) or '暂无'}\n"
        f"修订要求：{state.revision_instruction or '暂无'}\n"
        f"编辑结论：{state.editor_decision}\n"
        f"质量分：{state.quality_score}\n"
        f"大纲阶段：{state.outline_stage} / {state.outline_stage_status}\n\n"
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
        f"参考简报：\n{state.reference_brief or '暂无'}\n\n"
        f"检索查询：{state.retrieval_query or '暂无'}\n"
        f"检索上下文：\n{state.retrieval_context or '暂无'}\n\n"
        f"检索来源：\n{format_retrieval_sources(state.retrieval_sources)}\n"
        f"原作事实：{', '.join(state.canon_facts) or '暂无'}\n"
        f"原作不确定点：{', '.join(state.research_uncertainties) or '暂无'}\n"
        "如果存在原作不确定点，必须要求用户确认，不得擅自补完原作设定。\n"
        f"编辑意见：\n{state.editor_notes or '暂无'}\n\n"
        f"最近大纲版本：\n{versions or '暂无'}\n"
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
