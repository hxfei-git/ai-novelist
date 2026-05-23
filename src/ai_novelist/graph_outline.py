"""Interactive outline collaboration graph."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.agent_metrics import complete_with_metrics, estimate_tokens
from ai_novelist.agent_parallel import AgentJob, run_agent_jobs
from ai_novelist.artifacts import ArtifactRecord, register_artifact
from ai_novelist.corpus.craft_resolver import resolve_author_craft
from ai_novelist.outline.legacy_migration import ensure_outline_stage, normalize_legacy_outline_artifacts
from ai_novelist.outline.question_filter import filter_stage_confirmation_questions
from ai_novelist.outline.renderers import build_stage_output_rule
from ai_novelist.outline.stage_contracts import (
    LEGACY_OUTLINE_STAGES,
    OUTLINE_STAGES,
    STAGE_LABELS,
    get_stage_contract,
)
from ai_novelist.outline.stage_guard import guard_stage_output
from ai_novelist.progress import ProgressFunc, emit_progress, noop_progress, with_agent_metadata
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

STAGE_ROLES = {
    "direction": ["类型定位 Agent", "主题卖点 Agent"],
    "worldbuilding": ["世界架构 Agent", "规则力量 Agent", "社会权力 Agent", "剧情服务 Agent"],
    "characters": ["主角弧光 Agent", "关系冲突 Agent", "反派/势力 Agent"],
    "story_flow": ["主线结构 Agent", "节奏悬念 Agent", "伏笔 Agent"],
    "volume_outline": ["分卷策划 Agent", "卷内高潮 Agent", "卷间钩子 Agent"],
    "chapter_outline": ["章节拆分 Agent", "章节钩子 Agent", "连续性编辑 Agent"],
    "review_lock": ["总编辑 Agent", "约束审计 Agent", "章节准备 Agent"],
}


def build_outline_collaboration_graph(adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc | None = None, search_backend=None) -> CompiledGraph:
    """Build an outline workflow whose natural-language routing goes through DirectorService."""
    return DirectorBackedOutlineGraph(adapter, store, progress or noop_progress, search_backend)


class DirectorBackedOutlineGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress, search_backend=None) -> None:
        self.adapter = adapter
        self.store = store
        self.progress = progress
        self.search_backend = search_backend

    def invoke(self, state: dict) -> dict:
        current = NovelState.from_dict(state)
        ensure_outline_stage(current)
        current.active_workflow = "outline" if current.director_action != "stop" else current.active_workflow
        current.current_stage = current.outline_stage
        artifact = current.outline_stage_artifacts.get(current.outline_stage, {})
        artifact_status = str(artifact.get("status", "")).strip()
        if artifact_status and current.outline_stage_status in {"", "collecting"}:
            current.outline_stage_status = artifact_status  # type: ignore[assignment]
        self.store.save_state(current)
        user_text = current.user_request.strip()
        if not user_text:
            return current.to_dict()

        from ai_novelist.director_service import DirectorService
        from ai_novelist.research import MockSearchBackend

        service = DirectorService(
            self.store,
            self.adapter,
            self.search_backend or MockSearchBackend(),
            progress=self.progress,
        )
        turn = service.handle_turn(current.project_id, user_text, channel="outline")
        return (turn.state or self.store.load_state(current.project_id)).to_dict()


class OutlineSequentialGraph(DirectorBackedOutlineGraph):
    pass


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
        elif is_stage_view_request(user_text) and any(marker in user_text for marker in ("当前阶段", "阶段内容", "阶段产物", "当前产物")):
            state.director_action = "show_outline_stage"
            state.director_intent = "status"
            state.director_task_args = {"stage": state.outline_stage}
            state.director_message = f"我会展示{STAGE_LABELS[state.outline_stage]}阶段产物。"
        elif state.pending_questions and answers_stage_pending_questions(user_text):
            instruction = build_stage_pending_answer_instruction(state, user_text)
            state.revision_instruction = instruction
            add_unique_items(state.locked_constraints, [instruction])
            state.director_action = "run_outline_stage"
            state.director_intent = "answer_pending_questions"
            state.director_message = "我会吸收你的补充回答，并重跑当前大纲阶段。"
        elif should_run_outline_stage(user_text, state) and not should_defer_stage_confirmation_to_director(user_text, state):
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


def run_outline_stage_node(data: dict, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> dict:
    state = NovelState.from_dict(data)
    ensure_outline_stage(state)
    stage = state.outline_stage
    if stage == "done":
        state.director_message = "最终大纲已经锁定。可以进入章节细纲或正文写作。"
        state.next_action = "end"
        store.save_state(state)
        return state.to_dict()

    label = STAGE_LABELS[stage]
    emit_progress(progress, "OutlineStage", f"正在准备第 {stage_number(stage)} 阶段「{label}」上下文...")
    state = resolve_author_craft(state, store, "outline_stage", stage=stage)
    author_craft = load_outline_stage_craft_brief(state, store)
    role_jobs = [
        AgentJob(
            key=role,
            agent="outline_stage_role",
            prompt=build_outline_stage_role_prompt(state, stage, role, author_craft=author_craft),
            graph="outline",
            node="outline_stage_role",
            prompt_profile="outline_role",
        )
        for role in STAGE_ROLES[stage]
    ]
    emit_progress(progress, "OutlineStage", with_agent_metadata(f"正在执行「{label}」角色短评 Agent...", adapter, "outline_stage_role"))
    try:
        role_results = run_agent_jobs(
            adapter=adapter,
            project_dir=store.project_dir(state.project_id),
            project_id=state.project_id,
            jobs=role_jobs,
        )
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    role_reviews: list[dict[str, str]] = []
    for result in role_results:
        emit_progress(
            progress,
            result.key,
            with_agent_metadata(
                f"已完成「{label}」角色短评",
                adapter,
                "outline_stage_role",
                (result.elapsed_ms or 0) / 1000,
                result.prompt_chars,
                result.estimated_total_tokens,
            ),
        )
        role_reviews.append({"role": result.key, "content": result.output})


    emit_progress(progress, "大纲汇总 Agent", with_agent_metadata(f"正在汇总「{label}」阶段产物...", adapter, "outline_stage_synthesizer"))
    synthesizer_prompt = build_outline_stage_synthesizer_prompt(state, stage, role_reviews, author_craft=author_craft)
    try:
        start = datetime.now(UTC)
        synthesis = complete_with_metrics(
            adapter=adapter,
            prompt=synthesizer_prompt,
            project_dir=store.project_dir(state.project_id),
            project_id=state.project_id,
            graph="outline",
            node="outline_stage_synthesizer",
            agent="outline_stage_synthesizer",
            prompt_profile="outline_synthesizer",
        )
        elapsed = (datetime.now(UTC) - start).total_seconds()
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    if stage == "worldbuilding":
        synthesis = ensure_worldbuilding_outline_structure(
            synthesis=synthesis,
            state=state,
            adapter=adapter,
            store=store,
            author_craft=author_craft,
        )
    emit_progress(
        progress,
        "大纲汇总 Agent",
        with_agent_metadata(
            f"已完成「{label}」阶段产物汇总",
            adapter,
            "outline_stage_synthesizer",
            elapsed,
            len(synthesizer_prompt),
            estimate_tokens(synthesizer_prompt) + estimate_tokens(synthesis),
        ),
    )

    guarded = guard_stage_output(synthesis, stage, state)
    synthesis = guarded.text
    if stage == "worldbuilding":
        state.worldbuilding = synthesis
    questions = extract_stage_confirmation_questions(synthesis)
    questions = filter_stage_confirmation_questions(stage, questions, state, synthesis)
    artifact = {
        "stage": stage,
        "label": STAGE_LABELS[stage],
        "status": "options_ready",
        "path": f"outline/{stage}.md",
        "role_reviews": role_reviews,
        "synthesis": synthesis,
        "summary": summarize_worldbuilding_outline(synthesis) if stage == "worldbuilding" else summarize_stage_text(synthesis),
        "stage_memory": extract_worldbuilding_memory(synthesis) if stage == "worldbuilding" else extract_stage_memory(synthesis),
        "pending_questions": questions,
        "guard_issues": [
            {
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "excerpt": issue.excerpt,
            }
            for issue in guarded.issues
        ],
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
    state.outline_stage_summaries[stage] = artifact["summary"]
    state.director_message = stage_ready_message(stage, questions)
    if questions:
        state.pending_questions = questions
        state.pending_question = "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))
    else:
        state.pending_question = f"请确认是否锁定{STAGE_LABELS[stage]}并进入下一阶段，或继续提出修改。"
        state.pending_questions = [state.pending_question]
    record_stage_history(state, "run", stage, state.user_request)
    emit_progress(progress, "OutlineStage", f"正在保存「{label}」阶段产物...")
    save_outline_stage_outputs(state, stage, format_stage_markdown(artifact), store)
    if stage == "worldbuilding":
        store.save_worldbuilding(state)
    store.save_state(state)
    return state.to_dict()


def advance_outline_stage_node(data: dict, adapter: AgentAdapter, store: LocalStore, progress: ProgressFunc = noop_progress) -> dict:
    state = NovelState.from_dict(data)
    ensure_outline_stage(state)
    stage = state.outline_stage
    emit_progress(progress, "OutlineStage", f"正在锁定第 {stage_number(stage)} 阶段「{STAGE_LABELS.get(stage, stage)}」...")
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
        return run_outline_stage_node(state.to_dict(), adapter, store, progress)

    artifact = dict(state.outline_stage_artifacts[stage])
    default_summary = str(state.director_task_args.get("default_discretion_summary") or "").strip()
    if not default_summary:
        unresolved = stage_unresolved_questions(state, artifact)
        if unresolved:
            default_summary = build_stage_closure_summary(stage, unresolved, state.user_request)
    if default_summary:
        artifact["default_discretion_summary"] = default_summary
        memory = artifact.get("stage_memory") if isinstance(artifact.get("stage_memory"), list) else []
        artifact["stage_memory"] = [*memory, default_summary]
    artifact["pending_questions"] = []
    artifact["status"] = "locked"
    artifact["locked_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    state.outline_stage_artifacts[stage] = artifact
    state.pending_question = ""
    state.pending_questions = []
    record_stage_history(state, "lock", stage, default_summary or state.user_request)

    next_stage = next_outline_stage(stage)
    if next_stage is None:
        emit_progress(progress, "OutlineStage", "正在合并七阶段产物并保存最终大纲...")
        finalize_locked_outline(state, store)
        store.save_state(state)
        outline_message = state.director_message
        try:
            from ai_novelist.graph_bible import build_bible_graph

            emit_progress(progress, "Bible", "正在基于锁定大纲更新小说圣经...")
            bible_state = NovelState.from_dict(build_bible_graph(adapter, store).invoke(state.to_dict()))
            bible_state.director_action = "advance_outline_stage"
            bible_state.director_message = outline_message + "\n" + bible_state.director_message
            store.save_state(bible_state)
            return bible_state.to_dict()
        except Exception as exc:  # pragma: no cover - defensive fallback keeps outline locking usable.
            state.last_agent_reports.append({"agent": "graph_bible", "status": "error", "error": str(exc)})
            state.last_agent_reports = state.last_agent_reports[-20:]
            store.save_state(state)
            return state.to_dict()

    emit_progress(progress, "OutlineStage", f"正在进入第 {stage_number(next_stage)} 阶段「{STAGE_LABELS[next_stage]}」...")
    state.outline_stage = next_stage  # type: ignore[assignment]
    state.outline_stage_status = "collecting"
    state.current_stage = next_stage
    state.director_action = "run_outline_stage"
    state.director_message = f"已锁定{STAGE_LABELS[stage]}，进入第 {stage_number(next_stage)} 阶段：{STAGE_LABELS[next_stage]}。"
    state.pending_question = f"请确认是否锁定{STAGE_LABELS[next_stage]}并进入下一阶段，或继续提出修改。"
    state.pending_questions = [state.pending_question]
    store.save_state(state)
    return run_outline_stage_node(state.to_dict(), adapter, store, progress)




def stage_unresolved_questions(state: NovelState, artifact: dict) -> list[str]:
    questions = []
    raw_artifact_questions = artifact.get("pending_questions")
    if isinstance(raw_artifact_questions, list):
        questions.extend(str(item).strip() for item in raw_artifact_questions if str(item).strip())
    questions.extend(item.strip() for item in state.pending_questions if item.strip())
    generic = f"请确认是否锁定{STAGE_LABELS.get(state.outline_stage, state.outline_stage)}并进入下一阶段，或继续提出修改。"
    return [item for item in dict.fromkeys(questions) if item != generic][:8]


def build_stage_closure_summary(stage: str, questions: list[str], user_text: str) -> str:
    joined = "；".join(questions[:6])
    return (
        f"锁定{STAGE_LABELS.get(stage, stage)}前，系统按当前阶段产物和连续性要求自行闭环未决问题；"
        f"已由本阶段 Agent 默认裁量：{joined}；用户确认语：{user_text}"
    )

def save_outline_stage_outputs(state: NovelState, stage: str, content: str, store: LocalStore) -> None:
    store.save_outline_stage(state, stage, content)
    artifact_path = store.save_outline_artifact(state, stage, content)
    artifact = state.outline_stage_artifacts.get(stage)
    role_reviews_path = None
    if isinstance(artifact, dict):
        role_reviews_path = store.save_outline_role_reviews(
            state,
            stage,
            artifact.get("role_reviews") if isinstance(artifact.get("role_reviews"), list) else [],
        )
    register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type=stage,
            path=artifact_path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="outline_stage_synthesizer",
            graph="outline",
            stage=stage,
        ),
    )
    if role_reviews_path is not None:
        register_artifact(
            store.project_dir(state.project_id),
            ArtifactRecord(
                id="",
                type=f"{stage}_role_reviews",
                path=role_reviews_path.relative_to(store.project_dir(state.project_id)).as_posix(),
                source_agent="outline_stage_roles",
                graph="outline",
                stage=stage,
            ),
        )


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
        "summary": summarize_worldbuilding_outline(state.worldbuilding),
        "stage_memory": extract_worldbuilding_memory(state.worldbuilding),
        "user_feedback": state.user_request,
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    state.outline_stage_artifacts["worldbuilding"] = artifact
    save_outline_stage_outputs(state, "worldbuilding", format_stage_markdown(artifact), store)


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
    if artifact and str(artifact.get("synthesis", "")).strip():
        state.director_message = format_stage_markdown(artifact)
    else:
        saved = store.load_outline_artifact(state.project_id, stage) or store.load_outline_stage(state.project_id, stage)
        if saved:
            state.director_message = saved
        elif stage == "worldbuilding" and state.worldbuilding.strip():
            state.director_message = "# 世界观设定\n\n" + state.worldbuilding.strip()
        else:
            state.director_message = f"{STAGE_LABELS.get(stage, stage)}阶段还没有产物。"
    store.save_state(state)
    return state.to_dict()



def negates_stage_advance(text: str) -> bool:
    return any(marker in text for marker in ("不要进入下一阶段", "不进入下一阶段", "先不进入下一阶段", "暂不进入下一阶段", "别进入下一阶段", "不要推进", "先不推进", "暂不推进"))


def should_defer_stage_confirmation_to_director(text: str, state: NovelState) -> bool:
    if state.active_workflow != "outline" or state.outline_stage_status != "options_ready":
        return False
    if parse_compact_numbered_answers(text):
        return False
    if any(marker in text for marker in ("查看", "展示", "看一下", "看下", "显示")):
        return False
    if negates_stage_advance(text):
        return False
    transition_markers = ("下一阶段", "进入下一阶段", "推进到下一阶段", "进入后续阶段", "推进后续阶段")
    lock_and_continue = any(marker in text for marker in ("锁定当前阶段", "锁定本阶段", "通过当前阶段", "通过本阶段")) and any(marker in text for marker in ("继续", "进入", "推进", "下一阶段"))
    delegated_advance = any(marker in text for marker in ("你决定", "由你决定", "交给你", "默认处理", "你来定")) and any(marker in text for marker in ("继续", "进入", "推进", "下一阶段"))
    return any(marker in text for marker in transition_markers) or lock_and_continue or delegated_advance

def should_run_outline_stage(text: str, state: NovelState) -> bool:
    if state.active_workflow == "outline":
        return True
    markers = ("生成大纲", "写大纲", "大纲", "方向", "概念", "核心冲突", "反转", "世界观", "人物", "故事流程", "主线", "分卷", "章节", "审稿", "锁定")
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
    exact = {"确认", "确定", "继续", "下一阶段", "进入下一阶段", "确认进入下一阶段", "确定进入下一阶段", "锁定", "锁定当前阶段", "通过", "认可", "同意", "ok", "yes", "approve", "confirm"}
    if lowered in exact:
        return True
    return any(marker in text for marker in ("确认进入下一阶段", "确定进入下一阶段", "锁定并进入", "进入下一阶段", "推进到下一阶段"))



def is_short_stage_confirmation(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {
        "下一阶段",
        "进入下一阶段",
        "确认进入下一阶段",
        "确定进入下一阶段",
        "推进到下一阶段",
        "advance",
    }


def delegates_stage_decision(text: str) -> bool:
    markers = ("你决定", "由你决定", "交给你", "系统决定", "系统裁量", "按你建议", "按系统建议", "按当前建议", "默认处理", "你来定", "你看着办")
    wants_advance = any(marker in text for marker in ("下一阶段", "进入", "推进", "继续", "锁定", "确定"))
    return any(marker in text for marker in markers) and wants_advance


def answers_stage_pending_questions(text: str) -> bool:
    if is_short_stage_confirmation(text) or delegates_stage_decision(text):
        return False
    if parse_compact_numbered_answers(text):
        return True
    if re.search(r"(^|[\s，,；;])\d+[.、)]", text):
        return True
    return any(marker in text for marker in ("回答", "补充", "选择", "选", "采用", "接受", "接收", "同意", "设为", "改成"))


def build_stage_pending_answer_instruction(state: NovelState, text: str) -> str:
    questions = [item.strip() for item in state.pending_questions if item.strip()]
    numbered_answers = parse_compact_numbered_answers(text)
    if questions and numbered_answers:
        parts = []
        for index, answer in numbered_answers.items():
            question = questions[index - 1] if 0 < index <= len(questions) else f"问题 {index}"
            parts.append(f"用户回答：{question} -> {answer}")
        return "；".join(parts)
    return "用户补充待确认问题：" + text


def parse_compact_numbered_answers(text: str) -> dict[int, str]:
    matches = list(re.finditer(r"(?<!\d)(?P<index>\d+)(?:[.、)]\s*|(?=\D))", text))
    answers: dict[int, str] = {}
    for pos, match in enumerate(matches):
        start = match.end()
        end = matches[pos + 1].start() if pos + 1 < len(matches) else len(text)
        answer = text[start:end].strip(" ：:，,。；;\n\t")
        if answer:
            answers[int(match.group("index"))] = answer
    return answers

def build_stage_default_discretion_summary(state: NovelState, text: str) -> str:
    questions = [item.strip() for item in state.pending_questions if item.strip()]
    if questions:
        return f"用户将待确认问题交由系统按当前阶段产物默认裁量并推进；待裁量问题：{'；'.join(questions[:4])}；用户原话：{text}"
    return f"用户认可当前阶段产物，并将细节交由系统按当前建议默认裁量后推进；用户原话：{text}"

def is_revision_request(text: str) -> bool:
    return any(marker in text for marker in ("修改", "调整", "重做", "重新", "不要", "更", "太", "强化", "补充"))


def is_stage_view_request(text: str) -> bool:
    return any(marker in text for marker in ("查看", "看一下", "展示", "显示"))


def is_stage_switch_request(text: str) -> bool:
    return any(marker in text for marker in ("回到", "重做", "重新做", "切换到")) or is_revision_request(text)


def detect_stage_reference(text: str) -> str | None:
    mapping = [
        ("direction", ("方向", "定位", "类型", "卖点", "故事概念", "概念", "一句话故事", "核心概念")),
        ("worldbuilding", ("世界观", "设定", "规则")),
        ("characters", ("人物", "人设", "关系", "反派", "势力")),
        ("story_flow", ("故事流程", "流程", "主线", "节奏", "伏笔")),
        ("volume_outline", ("分卷", "卷纲", "卷内", "卷间", "总大纲", "大纲草案", "草案")),
        ("chapter_outline", ("章节大纲", "章节拆分", "章节钩子", "章节", "细纲")),
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
    if is_short_stage_confirmation(user_text) or delegates_stage_decision(user_text):
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


def load_outline_stage_craft_brief(state: NovelState, store: LocalStore) -> str:
    if state.craft_mode == "off" or not state.active_craft_brief_path:
        return ""
    path = store.project_dir(state.project_id) / state.active_craft_brief_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def worldbuilding_framework_prompt(stage: str) -> str:
    if stage != "worldbuilding":
        return ""
    from ai_novelist.worldbuilding_framework import render_worldbuilding_framework

    return (
        "\nWORLD_OUTLINE_FRAMEWORK:\n"
        "你必须按下面的通用世界大纲框架生成，不要按题材分类。"
        "题材只影响每项如何填写。每项都要服务主角生存、冲突制造和后续剧情。\n"
        f"{render_worldbuilding_framework(mode='full')}\n"
    )


def build_outline_stage_role_prompt(state: NovelState, stage: str, role: str, author_craft: str = "") -> str:
    contract = get_stage_contract(stage)
    return (
        "AGENT: outline_stage_role\n"
        f"ROLE: {role}\n"
        f"STAGE: {stage}\n"
        f"STAGE_LABEL: {STAGE_LABELS[stage]}\n\n"
        "STAGE_CONTRACT:\n"
        f"- 本阶段目的：{contract.purpose}\n"
        f"- 允许新增：{', '.join(contract.allowed_intents)}\n"
        f"- 禁止越权：{', '.join(contract.forbidden_intents)}\n"
        f"- Canon policy：{contract.canon_policy}\n"
        "- 所有具体设定必须说明来源，不能把自造机制写成已锁定事实。\n\n"
        "LANGUAGE_QUALITY:\n"
        "- 不写公式化绝对因果句。\n"
        "- 不写产品规则、游戏机制、编剧理论语言。\n"
        "- 世界观阶段多写角色能看见、听见、触碰、承受的事物。\n\n"
        f"角色专属关注点：\n{role_focus_instruction(stage, role)}\n\n"
        f"用户最新输入：{state.user_request}\n"
        f"创意：{state.idea or '暂无'}\n"
        f"检索上下文：\n{state.retrieval_context or state.reference_brief or '暂无'}\n\n"
        f"作者构思参考：\n{author_craft or '暂无'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, stage)}\n\n"
        f"当前阶段已有内容：\n{current_stage_context(state, stage)}\n\n"
        f"阶段连续性要求：\n{stage_continuity_requirement(stage)}\n\n"
        f"{worldbuilding_framework_prompt(stage)}\n"
        f"{outline_stage_boundary_prompt(stage)}\n\n"
        "OUTPUT_BUDGET:\n"
        "- 只输出短 JSON：{role, opportunities, risks, suggestions}。\n"
        "- opportunities/risks/suggestions 各最多 2 条，每条不超过 80 中文字符。\n"
        "- 总输出不超过 500 中文字符。\n"
        "- 不要复述上下文，不要输出分析过程。\n"
        "建议必须基于前序已保存阶段内容和当前阶段已有内容继续创作，"
        "不得把本阶段写成与前序设定割裂的新故事。"
    )


def build_outline_stage_synthesizer_prompt(state: NovelState, stage: str, role_reviews: list[dict[str, str]], author_craft: str = "") -> str:
    contract = get_stage_contract(stage)
    reviews = "\n\n".join(f"## {item['role']}\n{item['content']}" for item in role_reviews)
    return (
        "AGENT: outline_stage_synthesizer\n"
        f"STAGE: {stage}\n"
        f"STAGE_LABEL: {STAGE_LABELS[stage]}\n\n"
        "STAGE_CONTRACT:\n"
        f"- 本阶段目的：{contract.purpose}\n"
        f"- 允许新增：{', '.join(contract.allowed_intents)}\n"
        f"- 禁止越权：{', '.join(contract.forbidden_intents)}\n"
        f"- Canon policy：{contract.canon_policy}\n"
        "- 所有具体设定必须说明来源，不能把自造机制写成已锁定事实。\n\n"
        "LANGUAGE_QUALITY:\n"
        "- 不写公式化绝对因果句。\n"
        "- 不写产品规则、游戏机制、编剧理论语言。\n"
        "- 世界观阶段多写角色能看见、听见、触碰、承受的事物。\n\n"
        f"创意：{state.idea or '暂无'}\n"
        f"用户最新输入：{state.user_request}\n"
        f"作者构思参考：\n{author_craft or '暂无'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, stage)}\n\n"
        f"当前阶段已有内容：\n{current_stage_context(state, stage)}\n\n"
        f"阶段连续性要求：\n{stage_continuity_requirement(stage)}\n\n"
        f"{worldbuilding_framework_prompt(stage)}\n"
        f"{outline_stage_boundary_prompt(stage)}\n\n"
        f"角色短评：\n{reviews}\n\n"
        f"{outline_stage_synthesizer_output_rule(stage, state)}"
    )


OUTLINE_STAGE_BOUNDARIES = {
    "direction": {
        "allowed": "类型定位、主角行动原则、核心爽点、核心冲突方向、情绪基调、主题边界、反转原则、禁区",
        "forbidden": "具体世界观规则、宗门/组织流程、制度条款、申请表、审批、考评、备案、绩效、KPI、具体人物关系细则、具体剧情桥段、章节安排、专有名词清单",
    },
    "concept": {
        "allowed": "故事钩子、一句话概念、主角欲望、核心冲突、主要悬念、叙事承诺、主题问题、反转原则、待后续阶段展开的确认点",
        "forbidden": "具体世界规则、世界规则清单、组织流程、人物关系细则、人物亲密机制、章节列表、第1章/第 1 章、分卷结构、第一卷、专有名词堆砌、行政或制度化细则、申请表、审批、备案、绩效、KPI",
    },
    "worldbuilding": {
        "allowed": "完整小说世界大纲：世界核心设定、世界格局、地理与环境、历史背景、时代背景、世界规则、力量体系、成长体系、能力分类体系、职业与身份体系、资源体系、经济体系、政治与权力体系、势力体系、社会结构、文化体系、宗教信仰神话、科技工艺生产力、交通通讯、法律秩序、军事战争、种族族群生灵、重要地点、危险体系、知识教育、日常生活、信息舆论、核心矛盾、主角与世界关系、主要人物群体、主线时间线、隐藏真相、结局后世界格局",
        "forbidden": "按题材分类替代世界组成部分、只输出世界运行原则/关键边界/冲突资源/代价红线四段摘要、只写抽象口号、只写专有名词清单、空标题模板、过细行政流程、申请表、审批、备案、考评、绩效、KPI、无代价万能规则、完整人物小传、章节正文、分卷章节安排、与主线无关的猎奇机制",
    },
    "characters": {
        "allowed": "主角缺陷与欲望、关键人物目标、动机、关系张力、成人亲密张力、情色/福利关系功能、阵营位置、阵营冲突、背叛/信任风险、成长矛盾、人物弧光",
        "forbidden": "未成年性化、非自愿亲密、无主线功能成人内容、把亲密关系写成行政审批/绩效表格、世界规则清单、章节列表、完整剧情梗概、无主线功能的人设细节、与主线无关的角色堆砌",
    },
    "story_flow": {
        "allowed": "叙事流程中的主线阶段、阶段目标、关键转折、信息释放节奏、伏笔布置与回收方向、失败代价、高潮方向",
        "forbidden": "完整章节正文、细场景动作、未在前序确立的新世界规则、新增世界观 canon、突然新增人物关系、人物长期关系机制、无依据专有名词、行政流程、办理、审批、备案、绩效、申请表、逐章正文、世界百科、分卷篇幅表",
    },
    "volume_outline": {
        "allowed": "卷名、卷目标、卷内主要矛盾、卷级高潮事件、失败/胜利代价、主角能力或认知变化、卷间钩子",
        "forbidden": "逐章细纲、第1章、第2章、章节列表、场景列表、细场景动作、正文片段、新世界观规则、新世界规则、新人物系统、过细制度机制、临时改写世界规则、脱离主线的新人物群",
    },
    "chapter_outline": {
        "allowed": "章节编号、章节目标、主要冲突、信息增量、人物状态变化、结尾钩子、连续性提醒",
        "forbidden": "正式正文、正文段落、对白、中文引号对白、完整场景卡、场景卡、细场景调度、细场景动作、未确立的新规则、新人物关系、额外世界观机制、审批、制度、亲密机制、临时改写已锁定设定、无关支线扩写",
    },
    "review_lock": {
        "allowed": "一致性问题、阶段承接检查、锁定约束、待确认问题、风险标注、进入章节卡前的准备条件、锁定建议",
        "forbidden": "新增世界规则、新增 canon、重写人物关系、重写剧情流程、重写前序阶段、生成章节卡、生成正文、章节正文、未标记来源的新 canon、候选菜单、二次创作",
    },
}


def outline_stage_boundary_prompt(stage: str) -> str:
    boundary = OUTLINE_STAGE_BOUNDARIES.get(stage)
    if boundary:
        allowed = str(boundary.get("allowed") or "").strip()
        forbidden = str(boundary.get("forbidden") or "").strip()
    else:
        contract = get_stage_contract(stage)
        allowed = ", ".join(contract.allowed_intents)
        forbidden = ", ".join(contract.forbidden_intents)
    return (
        "STAGE_BOUNDARY:\n"
        f"- 允许输出：{allowed}。\n"
        f"- 禁止输出：{forbidden}。\n"
        "- 只给本阶段短评或产物，不越权生成其他阶段内容，不新增无依据 canon。"
    )


def worldbuilding_overfine_terms_guard(state: NovelState, stage: str) -> str:
    if stage != "worldbuilding":
        return ""
    controlled_terms = ("申请表", "申请", "审批", "备案", "考评", "绩效", "KPI")
    explicit_sources = [state.user_request, state.idea]
    for artifact in state.outline_stage_artifacts.values():
        if not isinstance(artifact, dict) or artifact.get("status") != "locked":
            continue
        explicit_sources.append(str(artifact.get("synthesis") or ""))
        memory = artifact.get("stage_memory")
        if isinstance(memory, list):
            explicit_sources.extend(str(item) for item in memory)
    source_text = "\n".join(item for item in explicit_sources if item)
    explicit_terms = [term for term in controlled_terms if term in source_text]
    if explicit_terms:
        return (
            "\nWORLDBUILDING_OVERFINE_TERMS:\n"
            f"- 用户原始输入或锁定产物已明确包含：{'、'.join(explicit_terms)}。\n"
            "- 可以保留这些词，但只能改写为服务主线冲突的世界运行原则；不得扩写成申请/审批/备案/考评流程或表格制度。"
        )
    return (
        "\nWORLDBUILDING_OVERFINE_TERMS:\n"
        "- 默认不要生成申请表、申请、审批、备案、考评、绩效或 KPI 等行政化机制。\n"
        "- 如果角色短评出现这些词，必须改写为资源压力、代价或阵营冲突原则。"
    )


def characters_relationship_guard(state: NovelState, stage: str) -> str:
    if stage != "characters":
        return ""
    controlled_terms = ("亲密行为", "双修", "道侣", "福利场景", "擦边", "暧昧", "恋爱", "色情", "情色")
    explicit_sources = [state.user_request, state.idea]
    for artifact in state.outline_stage_artifacts.values():
        if not isinstance(artifact, dict) or artifact.get("status") != "locked":
            continue
        explicit_sources.append(str(artifact.get("synthesis") or ""))
        memory = artifact.get("stage_memory")
        if isinstance(memory, list):
            explicit_sources.extend(str(item) for item in memory)
    source_text = "\n".join(item for item in explicit_sources if item)
    explicit_terms = [term for term in controlled_terms if term in source_text]
    if explicit_terms:
        return (
            "\nCHARACTER_RELATIONSHIP_TERMS:\n"
            f"- 用户原始输入或锁定产物已明确包含：{'、'.join(explicit_terms)}。\n"
            "- 可以保留并展开这些成人亲密方向；必须服务目标、动机、权力关系、诱惑、背叛、占有欲或主线冲突，不要改写成行政审批/绩效表格。"
        )
    return (
        "\nCHARACTER_RELATIONSHIP_TERMS:\n"
        "- 默认允许成人角色之间的暧昧、色情、福利、双修和亲密张力；但必须服务人物关系或主线冲突，不要写成无功能卖点清单。\n"
        "- 禁止未成年性化、非自愿亲密、剥削性内容，禁止把亲密关系写成审批/绩效/流程表格。\n"
        "- 每个角色必须有明确主线功能、冲突功能或情欲张力功能；无功能的人设细节一律删除。"
    )


def outline_stage_synthesizer_output_rule(stage: str, state: NovelState | None = None) -> str:
    return build_stage_output_rule(stage, state)


def ensure_worldbuilding_outline_structure(
    synthesis: str,
    state: NovelState,
    adapter: AgentAdapter,
    store: LocalStore,
    author_craft: str = "",
) -> str:
    from ai_novelist.worldbuilding_framework import (
        append_missing_worldbuilding_sections,
        render_worldbuilding_framework,
        validate_worldbuilding_outline,
    )

    ok, missing = validate_worldbuilding_outline(synthesis, mode="full")
    if ok:
        return synthesis

    repair_prompt = (
        "AGENT: worldbuilding_structure_repair\n"
        "你要修复世界观阶段输出结构。不要分析，不要解释，只输出完整 Markdown。\n"
        f"缺失或顺序异常标题：{missing}\n\n"
        "必须使用完整 33 项世界大纲标题，且继承原文内容。\n"
        "不要按题材分类，不得只输出世界运行原则/关键边界/冲突资源/代价红线四段摘要。\n"
        "每个小节写 2-5 条当前小说的具体 bullet；信息不足时给出合理默认建议。\n\n"
        f"框架：\n{render_worldbuilding_framework(mode='full')}\n\n"
        f"作者构思参考：\n{author_craft or '暂无'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, 'worldbuilding')}\n\n"
        f"原始世界观草稿：\n{synthesis}\n"
    )
    try:
        repaired = complete_with_metrics(
            adapter=adapter,
            prompt=repair_prompt,
            project_dir=store.project_dir(state.project_id),
            project_id=state.project_id,
            graph="outline",
            node="worldbuilding_structure_repair",
            agent="worldbuilding_structure_repair",
            prompt_profile="outline_worldbuilding_repair",
        )
    except AgentAdapterError:
        repaired = synthesis

    ok, missing = validate_worldbuilding_outline(repaired, mode="full")
    if ok:
        return repaired
    return append_missing_worldbuilding_sections(repaired, missing)


def summarize_worldbuilding_outline(text: str, max_chars: int = 1800) -> str:
    sections = split_worldbuilding_sections(text)
    key_headings = [
        "一、世界核心设定",
        "二、世界格局",
        "六、世界规则",
        "七、力量体系",
        "八、成长体系",
        "十四、势力体系",
        "二十八、核心矛盾",
        "二十九、主角与世界的关系",
        "三十一、主线时间线",
        "三十二、隐藏真相",
        "三十三、结局后的世界格局",
    ]
    lines: list[str] = []
    for heading in key_headings:
        bullet = first_worldbuilding_bullet(sections.get(heading, ""))
        if bullet:
            lines.append(f"{heading}：{bullet}")
    if not lines:
        return summarize_stage_text(text, max_chars=420)
    summary = "；".join(lines)
    return summary[:max_chars].rstrip() + ("..." if len(summary) > max_chars else "")


def extract_worldbuilding_memory(text: str, max_items: int = 18, max_chars: int = 1800) -> list[str]:
    sections = split_worldbuilding_sections(text)
    priority = [
        "一、世界核心设定",
        "二、世界格局",
        "六、世界规则",
        "七、力量体系",
        "八、成长体系",
        "十一、资源体系",
        "十四、势力体系",
        "二十、法律与秩序体系",
        "二十三、重要地点体系",
        "二十八、核心矛盾",
        "二十九、主角与世界的关系",
        "三十、主要人物群体",
        "三十一、主线时间线",
        "三十二、隐藏真相",
        "三十三、结局后的世界格局",
    ]
    result: list[str] = []
    total = 0
    for heading in priority:
        for bullet in worldbuilding_bullets(sections.get(heading, ""))[:2]:
            item = f"{heading}：{bullet}"
            if item in result:
                continue
            if total + len(item) > max_chars and result:
                return result
            result.append(item)
            total += len(item)
            if len(result) >= max_items:
                return result
    if result:
        return result
    return extract_stage_memory(text, max_items=12, max_chars=1100)


def split_worldbuilding_sections(text: str) -> dict[str, str]:
    from ai_novelist.worldbuilding_framework import full_worldbuilding_headings

    headings = full_worldbuilding_headings()
    matches: list[tuple[str, int, int]] = []
    for heading in headings:
        pattern = re.compile(rf"^\s*#{{1,6}}\s*{re.escape(heading)}(?:\s|$)", re.MULTILINE)
        match = pattern.search(text or "")
        if match:
            matches.append((heading, match.start(), match.end()))
    matches.sort(key=lambda item: item[1])
    sections: dict[str, str] = {}
    for index, (heading, _start, end) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(text)
        sections[heading] = text[end:next_start].strip()
    return sections


def worldbuilding_bullets(section_text: str) -> list[str]:
    bullets: list[str] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "仍需确认" in line:
            continue
        line = re.sub(r"^[-*+•\s]*", "", line)
        line = re.sub(r"^\d+[.、)]\s*", "", line).strip()
        if not line or line in {"暂无", "暂无。"}:
            continue
        if line.startswith("待补充：结构兜底占位"):
            continue
        bullets.append(line)
    return bullets


def first_worldbuilding_bullet(section_text: str) -> str:
    bullets = worldbuilding_bullets(section_text)
    return bullets[0] if bullets else ""


def summarize_stage_text(text: str, max_chars: int = 420) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    return cleaned[:max_chars].rstrip() + ("..." if len(cleaned) > max_chars else "")


def extract_stage_memory(text: str, max_items: int = 12, max_chars: int = 1100) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        line = re.sub(r"^[-*+•\s]*", "", line)
        line = re.sub(r"^\d+[.、)]\s*", "", line).strip()
        if not line or line.startswith("#") or "仍需确认" in line or "暂无" == line:
            continue
        lines.append(line)
    if not lines and text.strip():
        lines = [summarize_stage_text(text, max_chars=max_chars)]
    result: list[str] = []
    total = 0
    for line in lines:
        if line in result:
            continue
        total += len(line)
        if total > max_chars and result:
            break
        result.append(line)
        if len(result) >= max_items:
            break
    return result


def stage_memory_context(artifact: dict, max_chars: int) -> str:
    memory = artifact.get("stage_memory")
    if isinstance(memory, list) and memory:
        context = "\n".join(f"- {str(item).strip()}" for item in memory if str(item).strip())
    else:
        context = str(artifact.get("summary") or artifact.get("synthesis", "")).strip()
    if len(context) > max_chars:
        context = context[:max_chars].rstrip() + "\n..."
    return context


def stage_full_text(state: NovelState, store: LocalStore, stage: str) -> str:
    saved = store.load_outline_artifact(state.project_id, stage).strip()
    if saved:
        return saved
    artifact = state.outline_stage_artifacts.get(stage, {})
    if isinstance(artifact, dict):
        return str(artifact.get("synthesis") or artifact.get("summary") or "").strip()
    return ""


def previous_stage_context(state: NovelState, stage: str, max_chars_per_stage: int = 1800) -> str:
    if stage not in OUTLINE_STAGES:
        return "暂无"
    parts: list[str] = []
    for previous_stage in OUTLINE_STAGES[: OUTLINE_STAGES.index(stage)]:
        artifact = state.outline_stage_artifacts.get(previous_stage)
        if not isinstance(artifact, dict):
            continue
        context = stage_memory_context(artifact, max_chars_per_stage)
        if not context:
            continue
        status = str(artifact.get("status") or "draft")
        parts.append(f"## {STAGE_LABELS[previous_stage]}（{status}）\n{context}")
    return "\n\n".join(parts) or "暂无"


def current_stage_context(state: NovelState, stage: str, max_chars: int = 2400) -> str:
    artifact = state.outline_stage_artifacts.get(stage)
    if not isinstance(artifact, dict):
        return "暂无"
    context = stage_memory_context(artifact, max_chars)
    if not context:
        return "暂无"
    status = str(artifact.get("status") or state.outline_stage_status or "draft")
    return f"## {STAGE_LABELS.get(stage, stage)}（{status}）\n{context}"


def role_focus_instruction(stage: str, role: str) -> str:
    focus_map = {
        "类型定位 Agent": "从类型承诺、读者预期和市场识别度判断方向是否清晰；重点检查开篇钩子、中段升级、终局承诺是否属于同一种故事体验，避免只给出氛围标签。",
        "主题卖点 Agent": "从主题表达、情绪卖点和主角核心欲望判断方向是否有长线吸引力；重点提炼一句能驱动后续概念、人物和流程的核心卖点。",
        "故事概念 Agent": "专注故事概念本身：主角在什么异常局面中采取什么行动，故事以什么长期问题牵引读者。必须把方向定位转成可连续展开的故事发动机。",
        "世界架构 Agent": "负责世界核心设定、世界格局、地理环境、历史背景和时代背景；必须把主舞台、空间边界、历史遗留问题和时代压力写成后续剧情可复用的世界基座。",
        "规则力量 Agent": "负责世界规则、力量体系、成长体系、能力分类体系和危险体系；必须说明力量来源、获得条件、代价、克制、寿命影响和强者尺度，避免无代价万能规则。",
        "社会权力 Agent": "负责职业身份、资源、经济、政治权力、势力、社会结构、法律秩序、军事战争、文化信仰、科技生产力、交通通讯、信息舆论、知识教育和日常生活；必须写清普通人与强者如何被制度和资源压迫。",
        "剧情服务 Agent": "负责核心矛盾、主角与世界关系、主要人物群体、主线时间线、隐藏真相和结局后的世界格局；必须检查每项设定是否服务后续人物、主线、分卷和章节。",
        "规则架构 Agent": "专注世界规则的因果链：力量、资源、限制和代价如何运转。每条规则都必须能制造剧情选择，而不是只做背景百科。",
        "原作/检索一致性 Agent": "专注参考资料边界：区分已确认事实、用户自创延展和不确定点；不得把缺证据的内容当成原作设定。",
        "主角弧光 Agent": "专注主角欲望、缺陷、代价和阶段性变化；人物弧光必须从已有方向、概念和世界规则中自然生长。",
        "关系冲突 Agent": "专注关键关系的互相利用、误解、利益交换和情感压力；每条关系都要能反向推动主线冲突。",
        "反派/势力 Agent": "专注对手和势力结构：反派目标、组织利益和压迫方式必须具体，并能长期制造升级压力。",
        "主线结构 Agent": "专注主线推进链：开端事件、中段升级、低谷反击和终局兑现必须互相因果连接。",
        "节奏悬念 Agent": "专注信息释放、章节钩子和阶段悬念；避免连续解释设定，确保每个阶段都有新的问题和压力。",
        "伏笔 Agent": "专注伏笔埋设、回收路径和线索可追踪性；每个重大转折都应有前文依据，并为后续章节留下可验证线索。",
        "分卷策划 Agent": "专注分卷目标和卷间递进；每卷必须有独立高潮，同时推动全书核心谜团或主题更进一步。",
        "卷内高潮 Agent": "专注单卷内部高潮、失败点和反击点；高潮必须来自前文积累，而不是外部硬插事件。",
        "卷间钩子 Agent": "专注卷末悬念和下一卷启动条件；钩子要改变角色处境或认知，而不是只抛新名词。",
        "章节拆分 Agent": "专注章节颗粒度和执行顺序；章节必须能被写手直接转成场景任务。",
        "章节钩子 Agent": "专注章末钩子、信息差和读者追读动力；钩子要服务主线推进，不制造无关悬念。",
        "连续性编辑 Agent": "专注章节之间的因果、时间线和设定一致性；发现割裂点时优先提出低成本修补方式。",
        "总编辑 Agent": "专注七阶段整体一致性和可写性；判断当前大纲是否已经足够进入章节卡和正文生产。",
        "约束审计 Agent": "专注锁定约束、未决问题和设定边界；检查是否存在互相冲突或尚未闭环的约束。",
        "章节准备 Agent": "专注下一步章节生产准备度；指出章节卡、场景卡和正文写作前还缺哪些最小信息。",
    }
    if role in focus_map:
        return focus_map[role]
    return f"围绕{STAGE_LABELS.get(stage, stage)}阶段，以{role}的专业职责提出短评；必须只处理本角色负责的问题，不复述其他角色的判断。"


def stage_continuity_requirement(stage: str) -> str:
    requirements = {
        "direction": "方向定位是后续所有阶段的源头：只锁定宏观创作原则，具体规则、人物细则和剧情桥段留到后续阶段展开。",
        "concept": "故事概念为旧版兼容阶段，新流程不再主动进入。",
        "worldbuilding": "世界观必须承接方向定位提出的类型、冲突和情绪边界；按世界组成部分建立完整基座，每项都要影响主角生存、制造冲突或服务后续剧情。",
        "characters": "人物关系必须承接方向定位和世界观规则；人物欲望、关系张力和阵营冲突要由已保存设定自然生长。",
        "story_flow": "故事流程必须承接方向定位、世界观代价和人物关系冲突；这里的流程只表示叙事流程，转折不能脱离已建立的规则和人物动机。",
        "volume_outline": "分卷大纲必须整合方向、世界观、人物关系和故事流程，只做卷级目标、卷内高潮、代价和卷间钩子，不拆逐章细纲。",
        "chapter_outline": "章节大纲必须承接分卷大纲，只做章节目标、冲突、信息增量、人物变化、钩子和连续性提醒，不写场景卡或正文。",
        "review_lock": "审稿锁定只做一致性检查、风险标注、锁定建议和章节卡准备度判断；不得新增 canon、重写人物关系、重写剧情流程或生成章节卡/正文。",
    }
    return requirements.get(stage, "本阶段必须承接前序已保存阶段内容继续创作。")


def locked_stage_summary(state: NovelState) -> str:
    parts = []
    for stage in OUTLINE_STAGES:
        artifact = state.outline_stage_artifacts.get(stage)
        if artifact and artifact.get("status") == "locked":
            context = stage_memory_context(artifact, 1800)
            if context:
                parts.append(f"## {STAGE_LABELS[stage]}\n{context}")
    return "\n\n".join(parts) or "暂无"


def format_stage_markdown(artifact: dict) -> str:
    if not artifact:
        return ""
    stage = str(artifact.get("stage", ""))
    if stage == "direction":
        synthesis = sanitize_direction_stage_output(
            str(artifact.get("synthesis", "")).strip(),
            str(artifact.get("user_feedback", "")).strip(),
        )
        return synthesis.rstrip() + "\n" if synthesis else ""
    lines = [f"# {artifact.get('label') or STAGE_LABELS.get(stage, '阶段产物')}", ""]
    user_feedback = str(artifact.get("user_feedback", "")).strip()
    if user_feedback and stage != "direction":
        lines.append("## 用户本轮反馈")
        lines.append(user_feedback)
        lines.append("")
    synthesis = str(artifact.get("synthesis", "")).strip()
    if synthesis:
        if re.match(r"^#{1,6}\s+", synthesis):
            lines.append(synthesis)
        else:
            lines.append("## Director 汇总")
            lines.append(synthesis)
    return "\n".join(lines).rstrip() + "\n"


DIRECTION_FORBIDDEN_REPLACEMENTS = {
    "项目审批": "关键选择必须服务核心冲突",
    "申请表": "关系把柄",
    "审批": "关键选择必须服务核心冲突",
    "考评": "关系压力必须服务主线推进",
    "备案": "关系登记或把柄压力",
    "绩效": "权力评价压力",
    "制度条款": "抽象规则边界",
    "规则清单": "原则边界",
    "KPI": "外部压力",
    "宗门流程": "主角优先利用既有规则求生，具体规则留到世界观阶段展开",
    "组织流程": "主角优先利用既有规则求生，具体规则留到世界观阶段展开",
    "流程": "推进原则",
}


def sanitize_direction_stage_output(markdown: str, user_text: str = "") -> str:
    state = NovelState(project_id="sanitize", title="sanitize", idea=user_text, user_request=user_text)
    result = guard_stage_output(markdown or "", "direction", state)
    text = result.text.strip()
    if not text:
        return "## 方向定位稿\n"

    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^#{1,6}\s*方向定位\s*$", line):
            continue
        if re.match(r"^#{1,6}\s*方向控制稿\s*$", line):
            continue
        if line == "## 方向定位稿":
            continue
        for forbidden, replacement in DIRECTION_FORBIDDEN_REPLACEMENTS.items():
            if forbidden in user_text:
                continue
            line = line.replace(forbidden, replacement)
        cleaned_lines.append(line)

    if not cleaned_lines:
        return "## 方向定位稿\n"
    body = "\n".join(cleaned_lines)
    return "## 方向定位稿\n" + body


def stage_ready_message(stage: str, questions: list[str] | None = None) -> str:
    message = f"第 {stage_number(stage)} 阶段「{STAGE_LABELS[stage]}」已完成本轮共创。"
    if questions:
        question_lines = "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))
        return (
            message
            + "\n\n本阶段有这些可补充确认的问题：\n"
            + question_lines
            + "\n\n你可以逐条补充；也可以明确说按当前建议处理并进入下一阶段。"
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
        synthesis = stage_full_text(state, store, stage).strip()
        if synthesis:
            sections.append(f"## {STAGE_LABELS[stage]}\n\n{synthesis}")
    concept_artifact = state.outline_stage_artifacts.get("concept")
    if isinstance(concept_artifact, dict):
        concept_text = str(concept_artifact.get("synthesis") or concept_artifact.get("summary") or "").strip()
        if concept_text:
            sections.append("## 旧版故事概念参考\n\n" + concept_text)
    state.outline = "# 最终锁定总大纲\n\n" + "\n\n".join(sections)
    state.outline_stage = "done"
    state.outline_stage_status = "done"
    state.review_status = "approved"
    state.editor_decision = "pass"
    state.active_workflow = ""
    state.current_stage = "chapter_plan"
    state.director_action = "advance_outline_stage"
    state.director_message = f"七阶段大纲已锁定，并保存为最终大纲：{store.outline_path(state.project_id)}"
    add_outline_version(state, "outline", state.outline, "七阶段锁定大纲")
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
        "## 输出格式\n"
        "优先输出 JSON：action, intent, target, user_message, instruction, task_args, locked_constraints。大纲阶段动作可用 run_current_stage、advance_current_stage、answer_pending_questions、show_stage、ask_user。\n"
        "请明确区分：新增修改意见、回答待确认问题、把剩余问题交给系统裁量并推进、仅查看状态。待确认问题不是必须逐项回答的阻塞项。只有用户明确要求进入/推进下一阶段，或明确锁定当前阶段并继续，才选择 advance_current_stage；不要因为句子里出现‘确定/确认/同意’就推进。\n\n"
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
        f"active_workflow：{state.active_workflow or 'none'}\n"
        f"outline_stage：{state.outline_stage}\n"
        f"outline_stage_status：{state.outline_stage_status}\n"
        f"pending_questions：{json.dumps(state.pending_questions, ensure_ascii=False)}\n"
        f"pending_question：{state.pending_question or '暂无'}\n\n"
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
    parsed = parse_outline_json_object(output)
    if parsed:
        action = str(parsed.get("action") or "ask_user").strip().lower()
        action = normalize_outline_director_action(action)
        task_args = parsed.get("task_args") if isinstance(parsed.get("task_args"), dict) else {}
        return {
            "action": action,
            "target": str(parsed.get("target") or "outline").strip().lower(),
            "intent": str(parsed.get("intent") or "answer").strip().lower(),
            "message": str(parsed.get("user_message") or parsed.get("message") or "我会继续推进大纲共创。").strip(),
            "instruction": str(parsed.get("instruction") or task_args.get("instruction") or "").strip(),
            "locked_constraints": normalize_outline_str_list(parsed.get("locked_constraints", [])),
            "style_preferences": normalize_outline_str_list(parsed.get("style_preferences", [])),
            "chapter": None,
        }

    action = field_value(output, "ACTION").lower() or "ask_user"
    action = normalize_outline_director_action(action)
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


def normalize_outline_director_action(action: str) -> str:
    if action == "plan_outline":
        action = "generate_outline"
    if action in {"run_current_stage", "answer_pending_questions"}:
        action = "revise_outline"
    if action == "advance_current_stage":
        action = "advance_outline_stage"
    if action == "show_stage":
        action = "show_outline_stage"
    return action if action in OUTLINE_ACTIONS else "ask_user"


def parse_outline_json_object(output: str) -> dict:
    text = output.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def normalize_outline_str_list(value) -> list[str]:
    if isinstance(value, str):
        return split_csv(value)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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
        compact = re.sub(r"\s+", " ", content).strip()
        if len(compact) > 500:
            compact = compact[:500].rstrip() + "..."
        state.messages.append({"role": role, "content": compact})
        state.messages = state.messages[-12:]
