"""Interactive outline collaboration graph."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.agent_metrics import complete_with_metrics, estimate_tokens
from ai_novelist.agent_parallel import AgentJob, run_agent_jobs
from ai_novelist.artifacts import ArtifactRecord, register_artifact, sha256_text
from ai_novelist.corpus.craft_resolver import resolve_author_craft
from ai_novelist.outline.legacy_migration import ensure_outline_stage, normalize_legacy_outline_artifacts
from ai_novelist.outline.chapter_outline_structure import (
    build_chapter_outline_target_context,
    chapter_outline_metadata_from_artifact,
    extract_chapter_outline_volume,
    merge_chapter_outline_volumes,
    normalize_generated_volume_outline,
)
from ai_novelist.outline.question_filter import filter_stage_confirmation_questions
from ai_novelist.outline.renderers import build_stage_output_rule, render_direction_stage_markdown
from ai_novelist.outline.stage_contracts import (
    LEGACY_OUTLINE_STAGES,
    OUTLINE_STAGES,
    STAGE_LABELS,
    get_stage_contract,
)
from ai_novelist.outline.stage_guard import guard_stage_output
from ai_novelist.outline_graph.review_lock import (
    extract_review_lock_issue_buckets,
    filter_review_lock_issue_buckets_by_history,
    review_lock_blocking_issues,
    review_lock_blocking_message,
    review_lock_detail_issues,
    review_lock_issue_buckets_from_artifact,
    review_lock_issue_lines,
    review_lock_pending_question_text,
)
from ai_novelist.outline_graph.routing import (
    OUTLINE_ACTIONS,
    answers_stage_pending_questions,
    delegates_stage_decision,
    detect_stage_reference,
    is_final_outline_save_request,
    is_final_outline_view_request,
    is_lock_request,
    is_revision_request,
    is_short_stage_confirmation,
    is_stage_confirmation,
    is_stage_switch_request,
    is_stage_view_request,
    negates_stage_advance,
    next_outline_stage,
    route_after_human_feedback,
    route_after_outline_director,
    should_defer_stage_confirmation_to_director,
    should_run_outline_stage,
    stage_action_from_director,
    stage_number,
)
from ai_novelist.outline_graph.artifact_io import (
    add_outline_version,
    build_final_outline_text,
    current_stage_context,
    extract_outline_stage_memory_for_artifact,
    finalize_locked_outline,
    format_stage_markdown,
    previous_stage_context,
    stage_full_text,
    summarize_outline_stage_for_artifact,
)
from ai_novelist.outline_graph.prompts import (
    CHAPTER_OUTLINE_FORCE_FULL_KEY,
    CHAPTER_OUTLINE_INTERNAL_REQUEST_KEY,
    build_outline_stage_role_prompt,
    build_outline_stage_synthesizer_prompt,
    chapter_outline_forced_full_generation,
    locked_stage_summary,
    outline_stage_boundary_prompt,
    stage_continuity_requirement,
)
from ai_novelist.outline_graph.repair import (
    chapter_outline_has_next_volume,
    confirm_current_chapter_outline_volume,
    ensure_chapter_outline_structure,
    ensure_characters_outline_structure,
    ensure_story_flow_outline_structure,
    ensure_volume_outline_structure,
    ensure_worldbuilding_outline_structure,
    sanitize_direction_stage_output,
)
from ai_novelist.progress import ProgressFunc, emit_progress, noop_progress, run_with_progress, with_agent_metadata
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""



STAGE_ROLES = {
    "direction": ["类型定位 Agent", "主题卖点 Agent"],
    "worldbuilding": ["世界架构 Agent", "规则力量 Agent", "社会权力 Agent", "剧情服务 Agent"],
    "characters": ["主角弧光 Agent", "关系冲突 Agent", "反派/势力 Agent"],
    "story_flow": ["主线结构 Agent", "冲突升级 Agent", "人物弧光 Agent", "悬念伏笔 Agent", "爽点情绪 Agent", "终局回收 Agent"],
    "volume_outline": ["分卷架构 Agent", "卷内推进 Agent", "人物推进 Agent", "世界观释放 Agent", "爽点悬念 Agent", "衔接约束 Agent"],
    "chapter_outline": ["章节拆分 Agent", "章节钩子 Agent", "连续性编辑 Agent"],
    "review_lock": ["总编辑 Agent", "约束审计 Agent", "章节准备 Agent"],
}



MAX_STAGE_QUESTION_ROUNDS = 3


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
    if stage == "chapter_outline":
        prepare_chapter_outline_metadata(state, store)

    existing_artifact = state.outline_stage_artifacts.get(stage)
    if should_lightly_revise_outline_stage(state, stage, existing_artifact, store):
        return revise_outline_stage_from_existing(
            state=state,
            stage=stage,
            adapter=adapter,
            store=store,
            progress=progress,
            author_craft=author_craft,
        )

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
    elif stage == "characters":
        synthesis = ensure_characters_outline_structure(
            synthesis=synthesis,
            state=state,
            adapter=adapter,
            store=store,
            author_craft=author_craft,
        )
    elif stage == "story_flow":
        synthesis = ensure_story_flow_outline_structure(
            synthesis=synthesis,
            state=state,
            adapter=adapter,
            store=store,
            author_craft=author_craft,
            role_reviews=role_reviews,
        )
    elif stage == "volume_outline":
        synthesis = ensure_volume_outline_structure(
            synthesis=synthesis,
            state=state,
            adapter=adapter,
            store=store,
            author_craft=author_craft,
            role_reviews=role_reviews,
        )
    elif stage == "chapter_outline":
        synthesis, chapter_metadata = ensure_chapter_outline_structure(
            synthesis=synthesis,
            state=state,
            adapter=adapter,
            store=store,
            author_craft=author_craft,
            role_reviews=role_reviews,
        )
        state.director_task_args["chapter_outline_metadata"] = chapter_metadata
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

    if stage == "review_lock":
        issue_buckets = extract_review_lock_issue_buckets(synthesis)
        issue_buckets = filter_review_lock_issue_buckets_by_history(existing_artifact, issue_buckets)
        combined_issues = review_lock_issue_lines(issue_buckets)
        question_round = stage_question_round(state, stage, bool(combined_issues))
        artifact = {
            "stage": stage,
            "label": STAGE_LABELS[stage],
            "status": "options_ready",
            "path": f"outline/{stage}.md",
            "role_reviews": role_reviews,
            "synthesis": synthesis,
            "summary": summarize_outline_stage_for_artifact(stage, synthesis),
            "stage_memory": extract_outline_stage_memory_for_artifact(stage, synthesis),
            "pending_questions": [],
            "review_lock_issues": issue_buckets,
            "question_round": question_round,
            "max_question_rounds": MAX_STAGE_QUESTION_ROUNDS,
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
        update_stage_revision_metadata(
            artifact=artifact,
            previous_artifact=existing_artifact,
            mode="full",
            state=state,
            visible_questions=combined_issues,
            question_round=question_round,
        )
        state.outline_stage_artifacts[stage] = artifact
        state.outline_stage_status = "options_ready"
        state.review_status = "revision_requested" if issue_buckets["blocking"] else "draft"
        state.active_workflow = "outline"
        state.current_stage = stage
        state.active_artifact = "outline_stage"
        state.director_action = "run_outline_stage"
        state.outline_stage_summaries[stage] = artifact["summary"]
        state.pending_questions = combined_issues
        state.pending_question = review_lock_pending_question_text(issue_buckets)
        state.director_message = stage_ready_message(stage, combined_issues, artifact)
        record_stage_history(state, "run", stage, state.user_request)

        def save_stage_outputs() -> None:
            save_outline_stage_outputs(state, stage, format_stage_markdown(artifact), store)
            store.save_state(state)

        run_with_progress(progress, "OutlineStage", f"正在保存「{label}」阶段产物...", save_stage_outputs)
        return state.to_dict()

    questions = extract_stage_confirmation_questions(synthesis)
    questions = filter_stage_confirmation_questions(stage, questions, state, synthesis)
    questions = filter_stage_questions_by_history(existing_artifact, questions)
    question_round = stage_question_round(state, stage, bool(questions))
    artifact = {
        "stage": stage,
        "label": STAGE_LABELS[stage],
        "status": "options_ready",
        "path": f"outline/{stage}.md",
        "role_reviews": role_reviews,
        "synthesis": synthesis,
        "summary": summarize_outline_stage_for_artifact(stage, synthesis),
        "stage_memory": extract_outline_stage_memory_for_artifact(stage, synthesis),
        "pending_questions": questions,
        "question_round": question_round,
        "max_question_rounds": MAX_STAGE_QUESTION_ROUNDS,
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
    update_stage_revision_metadata(
        artifact=artifact,
        previous_artifact=existing_artifact,
        mode="full",
        state=state,
        visible_questions=questions,
        question_round=question_round,
    )
    if stage == "chapter_outline":
        artifact["metadata"] = state.director_task_args.get("chapter_outline_metadata") or chapter_outline_metadata_from_artifact(None)
        clear_chapter_outline_generation_directives(state)
    if questions and question_round > MAX_STAGE_QUESTION_ROUNDS:
        answer = answer_stage_unresolved_questions(
            state=state,
            stage=stage,
            artifact=artifact,
            questions=questions,
            user_text=f"当前阶段已达到最多 {MAX_STAGE_QUESTION_ROUNDS} 轮追问，系统自动闭环。",
            adapter=adapter,
            store=store,
            progress=progress,
        )
        artifact["default_discretion_summary"] = answer
        artifact["default_discretion_answers"] = answer
        artifact["question_round_limit_reached"] = True
        append_artifact_memory(artifact, answer)
        questions = []
        artifact["pending_questions"] = []
    state.outline_stage_artifacts[stage] = artifact
    state.outline_stage_status = "options_ready"
    state.review_status = "draft"
    state.active_workflow = "outline"
    state.current_stage = stage
    state.active_artifact = "outline_stage"
    state.director_action = "run_outline_stage"
    state.outline_stage_summaries[stage] = artifact["summary"]
    state.director_message = stage_ready_message(stage, questions, artifact)
    if questions:
        state.pending_questions = questions
        state.pending_question = "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))
    else:
        state.pending_question = f"请确认是否锁定{STAGE_LABELS[stage]}并进入下一阶段，或继续提出修改。"
        state.pending_questions = [state.pending_question]
    record_stage_history(state, "run", stage, state.user_request)

    def save_stage_outputs() -> None:
        save_outline_stage_outputs(state, stage, format_stage_markdown(artifact), store)
        if stage == "worldbuilding":
            store.save_worldbuilding(state)
        store.save_state(state)

    run_with_progress(progress, "OutlineStage", f"正在保存「{label}」阶段产物...", save_stage_outputs)
    return state.to_dict()


def revise_outline_stage_from_existing(
    state: NovelState,
    stage: str,
    adapter: AgentAdapter,
    store: LocalStore,
    progress: ProgressFunc = noop_progress,
    author_craft: str = "",
) -> dict:
    existing_artifact = dict(state.outline_stage_artifacts.get(stage) or {})
    current_markdown = current_stage_markdown_for_revision(state, store, stage, existing_artifact)
    if stage == "chapter_outline":
        metadata = state.director_task_args.get("chapter_outline_metadata")
        if not isinstance(metadata, dict):
            metadata = chapter_outline_metadata_from_artifact(
                existing_artifact,
                stage_full_text(state, store, "volume_outline"),
            )
        current_index = int(metadata.get("current_volume_index") or 1)
        contents = metadata.get("volume_contents") if isinstance(metadata.get("volume_contents"), dict) else {}
        current_volume_text = str(contents.get(str(current_index)) or "").strip()
        if not current_volume_text:
            current_volume_text = extract_chapter_outline_volume(current_markdown, current_index)
        if current_volume_text:
            current_markdown = current_volume_text
    if not current_markdown.strip():
        return run_outline_stage_node(state.to_dict(), adapter, store, progress)

    label = STAGE_LABELS[stage]
    emit_progress(progress, "OutlineStage", f"正在轻修订第 {stage_number(stage)} 阶段「{label}」...")
    prompt = build_outline_stage_revision_prompt(
        state=state,
        stage=stage,
        current_markdown=current_markdown,
        author_craft=author_craft,
        artifact=existing_artifact,
    )
    try:
        revised = complete_with_metrics(
            adapter=adapter,
            prompt=prompt,
            project_dir=store.project_dir(state.project_id),
            project_id=state.project_id,
            graph="outline",
            node="outline_stage_reviser",
            agent="outline_stage_reviser",
            prompt_profile="outline_stage_reviser",
        ).strip()
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()

    if not revised:
        revised = current_markdown

    guarded = guard_stage_output(revised, stage, state)
    revised = guarded.text.strip() or revised
    if stage == "worldbuilding":
        state.worldbuilding = revised
    elif stage == "chapter_outline":
        metadata = state.director_task_args.get("chapter_outline_metadata")
        if not isinstance(metadata, dict):
            metadata = chapter_outline_metadata_from_artifact(
                existing_artifact,
                stage_full_text(state, store, "volume_outline"),
            )
        current_index = int(metadata.get("current_volume_index") or 1)
        current_key = str(current_index)
        revised_current_volume = extract_chapter_outline_volume(revised, current_index) or revised
        volume_text = normalize_generated_volume_outline(revised_current_volume, metadata)
        contents = dict(metadata.get("volume_contents") or {})
        contents[current_key] = volume_text.strip()
        metadata["volume_contents"] = contents
        statuses = dict(metadata.get("volume_statuses") or {})
        statuses[current_key] = "options_ready"
        metadata["volume_statuses"] = statuses
        state.director_task_args["chapter_outline_metadata"] = metadata
        revised = merge_chapter_outline_volumes(metadata)

    artifact = dict(existing_artifact)
    artifact.update(
        {
            "stage": stage,
            "label": STAGE_LABELS[stage],
            "status": "options_ready",
            "path": f"outline/{stage}.md",
            "synthesis": revised,
            "summary": summarize_outline_stage_for_artifact(stage, revised),
            "stage_memory": extract_outline_stage_memory_for_artifact(stage, revised),
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
    )

    if stage == "chapter_outline":
        artifact["metadata"] = state.director_task_args.get("chapter_outline_metadata") or chapter_outline_metadata_from_artifact(artifact)

    if stage == "review_lock":
        issue_buckets = extract_review_lock_issue_buckets(revised)
        issue_buckets = filter_review_lock_issue_buckets_by_history(existing_artifact, issue_buckets)
        combined_issues = review_lock_issue_lines(issue_buckets)
        question_round = stage_question_round(state, stage, bool(combined_issues))
        artifact["review_lock_issues"] = issue_buckets
        artifact["pending_questions"] = combined_issues
        artifact["question_round"] = question_round
        artifact["max_question_rounds"] = MAX_STAGE_QUESTION_ROUNDS
        state.review_status = "revision_requested" if review_lock_blocking_issues(issue_buckets) else "draft"
        update_stage_revision_metadata(
            artifact=artifact,
            previous_artifact=existing_artifact,
            mode="light",
            state=state,
            visible_questions=combined_issues,
            question_round=question_round,
        )
        state.pending_questions = combined_issues
        state.pending_question = review_lock_pending_question_text(issue_buckets)
        state.director_message = stage_ready_message(stage, combined_issues, artifact)
    else:
        questions = extract_stage_confirmation_questions(revised)
        questions = filter_stage_confirmation_questions(stage, questions, state, revised)
        questions = filter_stage_questions_by_history(existing_artifact, questions)
        question_round = stage_question_round(state, stage, bool(questions))
        artifact["pending_questions"] = questions
        artifact["question_round"] = question_round
        artifact["max_question_rounds"] = MAX_STAGE_QUESTION_ROUNDS
        state.review_status = "draft"
        update_stage_revision_metadata(
            artifact=artifact,
            previous_artifact=existing_artifact,
            mode="light",
            state=state,
            visible_questions=questions,
            question_round=question_round,
        )
        if questions and question_round > MAX_STAGE_QUESTION_ROUNDS:
            answer = answer_stage_unresolved_questions(
                state=state,
                stage=stage,
                artifact=artifact,
                questions=questions,
                user_text=f"当前阶段已达到最多 {MAX_STAGE_QUESTION_ROUNDS} 轮追问，系统自动闭环。",
                adapter=adapter,
                store=store,
                progress=progress,
            )
            artifact["default_discretion_summary"] = answer
            artifact["default_discretion_answers"] = answer
            artifact["question_round_limit_reached"] = True
            append_artifact_memory(artifact, answer)
            questions = []
            artifact["pending_questions"] = []
        state.director_message = stage_ready_message(stage, questions, artifact)
        if questions:
            state.pending_questions = questions
            state.pending_question = "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))
        else:
            state.pending_question = f"请确认是否锁定{STAGE_LABELS[stage]}并进入下一阶段，或继续提出修改。"
            state.pending_questions = [state.pending_question]

    state.outline_stage_artifacts[stage] = artifact
    state.outline_stage_status = "options_ready"
    state.active_workflow = "outline"
    state.current_stage = stage
    state.active_artifact = "outline_stage"
    state.director_action = "run_outline_stage"
    state.outline_stage_summaries[stage] = artifact["summary"]
    record_stage_history(state, "light_revise", stage, state.user_request)

    def save_stage_outputs() -> None:
        save_outline_stage_outputs(state, stage, format_stage_markdown(artifact), store, source_agent="outline_stage_reviser")
        if stage == "worldbuilding":
            store.save_worldbuilding(state)
        store.save_state(state)

    run_with_progress(progress, "OutlineStage", f"正在保存「{label}」轻修订产物...", save_stage_outputs)
    return state.to_dict()


def should_lightly_revise_outline_stage(state: NovelState, stage: str, artifact: object, store: LocalStore) -> bool:
    if stage not in OUTLINE_STAGES:
        return False
    if state.director_intent == "create":
        return False
    if chapter_outline_forced_full_generation(state, stage):
        return False
    if force_full_outline_stage_rerun(state.user_request):
        return False
    if not isinstance(artifact, dict):
        return False
    current_text = str(artifact.get("synthesis") or artifact.get("summary") or "").strip()
    if not current_text and not (store.load_outline_artifact(state.project_id, stage) or store.load_outline_stage(state.project_id, stage)).strip():
        return False
    revision_intents = {"revise", "run_current_stage", "answer_pending_questions", "revise_previous_stage", "lock"}
    if state.director_intent in revision_intents:
        return True
    if state.revision_instruction.strip() and state.user_request.strip():
        return True
    return bool(state.user_request.strip() and is_revision_request(state.user_request))


def force_full_outline_stage_rerun(text: str) -> bool:
    markers = (
        "完整重做",
        "完整重写",
        "全部重做",
        "全部重写",
        "全量重做",
        "全量重写",
        "推翻重来",
        "整个阶段重做",
        "重跑整个阶段",
        "从头重做",
        "从零重做",
    )
    return any(marker in text for marker in markers)


def current_stage_markdown_for_revision(state: NovelState, store: LocalStore, stage: str, artifact: dict) -> str:
    saved = store.load_outline_artifact(state.project_id, stage).strip() or store.load_outline_stage(state.project_id, stage).strip()
    if saved:
        return saved
    formatted = format_stage_markdown(artifact).strip()
    if formatted:
        return formatted
    return str(artifact.get("synthesis") or artifact.get("summary") or "").strip()


def build_outline_stage_revision_prompt(
    state: NovelState,
    stage: str,
    current_markdown: str,
    author_craft: str = "",
    artifact: dict | None = None,
) -> str:
    template = load_prompt("outline_stage_reviser")
    metadata = stage_revision_metadata(artifact or {})
    return (
        f"{template.rstrip()}\n\n"
        "## 当前任务\n"
        f"STAGE: {stage}\n"
        f"STAGE_LABEL: {STAGE_LABELS[stage]}\n"
        f"用户最新输入：{state.user_request or '暂无'}\n"
        f"Director intent：{state.director_intent or 'unknown'}\n"
        f"修订要求：{state.revision_instruction or state.user_request or '暂无'}\n"
        f"锁定约束：{', '.join(state.locked_constraints) or '暂无'}\n"
        f"风格偏好：{', '.join(state.style_preferences) or '暂无'}\n\n"
        "## 阶段边界\n"
        f"{stage_continuity_requirement(stage)}\n\n"
        f"{outline_stage_boundary_prompt(stage)}\n\n"
        "## 修订策略\n"
        f"{outline_stage_revision_focus(stage)}\n\n"
        "## 前序已保存阶段内容\n"
        f"{previous_stage_context(state, stage)}\n\n"
        "## 作者构思参考\n"
        f"{author_craft or '暂无'}\n\n"
        "## 该阶段问题历史\n"
        f"{format_stage_revision_metadata_for_prompt(metadata)}\n\n"
        "## 当前阶段 Markdown（在此基础上做最小补丁）\n"
        f"{current_markdown or '暂无'}\n\n"
        "## 输出结构参考\n"
        f"{build_stage_output_rule(stage, state)}\n"
    )


def outline_stage_revision_focus(stage: str) -> str:
    common = "只改用户反馈、修订要求或待确认回答直接覆盖的区块；未覆盖的设定、顺序、标题和已锁定来源保持原意。"
    focuses = {
        "direction": "保留方向定位的十项结构，只调整宏观方向、卖点、基调、篇幅或主角方向中被点名的部分。",
        "worldbuilding": "保留现有世界组成部分和来源关系，只补丁受影响的世界规则、势力、资源、历史或剧情服务条目。",
        "characters": "保留既有人物池、关系卡、秘密与读者认知进度，只调整用户点名的人物关系或信息差。",
        "story_flow": "保留全书主线骨架和阶段顺序，只修正被点名的目标升级、失败代价、反转、伏笔或终局选择。",
        "volume_outline": "保留分卷数量、卷序和卷间承接，只修正受影响卷的卷级目标、关键节点或悬念释放。",
        "chapter_outline": "保留已确认卷和当前卷章节表，只修正用户点名的卷、章节、profile、钩子或连续性项。",
        "review_lock": "继续审计锁定链，但采用增量更新：保留已锁定来源，只回改阻塞项；非阻塞项只作为补齐提示，不把全部细节重新铺一遍。",
    }
    return common + "\n" + focuses.get(stage, "")


def format_stage_revision_metadata_for_prompt(metadata: dict) -> str:
    history = metadata.get("question_history") if isinstance(metadata.get("question_history"), list) else []
    lines = [
        f"- 最近修订模式：{metadata.get('last_revision_mode') or 'none'}",
        f"- 最近问题轮次：{metadata.get('last_question_round') or metadata.get('question_round') or 0}",
        f"- 已见问题指纹数：{len(metadata.get('seen_question_fingerprints') or [])}",
    ]
    if history:
        lines.append("- 已展示问题：")
        for batch in history[-4:]:
            questions = batch.get("questions") if isinstance(batch, dict) else []
            question_text = "；".join(str(item).strip() for item in questions if str(item).strip())
            if question_text:
                lines.append(f"  - 第 {batch.get('round', '?')} 轮：{question_text}")
    else:
        lines.append("- 已展示问题：暂无")
    return "\n".join(lines)


def stage_revision_metadata(artifact: dict) -> dict:
    raw = artifact.get("revision_meta") if isinstance(artifact, dict) else {}
    metadata = dict(raw) if isinstance(raw, dict) else {}
    metadata["revision_count"] = int_value(metadata.get("revision_count"), int_value(artifact.get("revision_count"), 0))
    metadata["last_revision_mode"] = str(metadata.get("last_revision_mode") or artifact.get("last_revision_mode") or "")
    metadata["last_revision_at"] = str(metadata.get("last_revision_at") or artifact.get("last_revision_at") or "")
    metadata["last_revision_intent"] = str(metadata.get("last_revision_intent") or artifact.get("last_revision_intent") or "")
    metadata["last_revision_instruction"] = str(metadata.get("last_revision_instruction") or artifact.get("last_revision_instruction") or "")
    metadata["last_revision_user_text"] = str(metadata.get("last_revision_user_text") or artifact.get("last_revision_user_text") or "")
    metadata["question_round"] = int_value(metadata.get("question_round"), int_value(artifact.get("question_round"), 0))
    metadata["last_question_round"] = int_value(metadata.get("last_question_round"), int_value(artifact.get("question_round"), 0))
    metadata["last_question_fingerprints"] = normalize_meta_str_list(metadata.get("last_question_fingerprints") or artifact.get("last_question_fingerprints"))
    metadata["seen_question_fingerprints"] = normalize_meta_str_list(metadata.get("seen_question_fingerprints") or artifact.get("seen_question_fingerprints"))
    metadata["question_history"] = normalize_meta_dict_list(metadata.get("question_history") or artifact.get("question_history"))
    return metadata


def update_stage_revision_metadata(
    artifact: dict,
    previous_artifact: object,
    mode: str,
    state: NovelState,
    visible_questions: list[str],
    question_round: int,
) -> None:
    previous = previous_artifact if isinstance(previous_artifact, dict) else {}
    metadata = stage_revision_metadata(previous)
    fingerprints = [stage_question_fingerprint(question) for question in visible_questions if question.strip()]
    metadata["revision_count"] = int_value(metadata.get("revision_count"), 0) + 1
    metadata["last_revision_mode"] = mode
    metadata["last_revision_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    metadata["last_revision_intent"] = state.director_intent
    metadata["last_revision_instruction"] = state.revision_instruction or state.user_request
    metadata["last_revision_user_text"] = state.user_request
    metadata["question_round"] = question_round
    metadata["last_question_round"] = question_round
    metadata["last_question_fingerprints"] = fingerprints
    seen = normalize_meta_str_list(metadata.get("seen_question_fingerprints"))
    metadata["seen_question_fingerprints"] = list(dict.fromkeys([*seen, *fingerprints]))[-120:]
    if visible_questions:
        history = normalize_meta_dict_list(metadata.get("question_history"))
        history.append(
            {
                "round": question_round,
                "questions": list(visible_questions),
                "fingerprints": fingerprints,
                "mode": mode,
                "created_at": metadata["last_revision_at"],
            }
        )
        metadata["question_history"] = history[-12:]
    artifact["revision_meta"] = metadata


def filter_stage_questions_by_history(artifact: object, questions: list[str]) -> list[str]:
    if not isinstance(artifact, dict):
        return questions
    metadata = stage_revision_metadata(artifact)
    seen = set(normalize_meta_str_list(metadata.get("seen_question_fingerprints")))
    filtered: list[str] = []
    fingerprints: set[str] = set()
    for question in questions:
        cleaned = str(question).strip()
        if not cleaned:
            continue
        fingerprint = stage_question_fingerprint(cleaned)
        if fingerprint in seen or fingerprint in fingerprints:
            continue
        filtered.append(cleaned)
        fingerprints.add(fingerprint)
    return filtered




def stage_question_fingerprint(question: str) -> str:
    normalized = normalize_stage_question_text(question)
    return sha256_text(normalized) if normalized else ""


def normalize_stage_question_text(question: str) -> str:
    text = str(question or "").strip()
    text = re.sub(r"^[-*+•\s]*", "", text)
    text = re.sub(r"^\d+[.、)]\s*", "", text)
    text = re.sub(r"[`*_#>\[\]【】()（）{}]+", "", text)
    text = re.sub(r"\s+", "", text)
    text = text.strip(" ：:，,。.!！?？；;、-/\\")
    return text.lower()


def int_value(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_meta_str_list(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_meta_dict_list(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def stage_question_round(state: NovelState, stage: str, has_questions: bool) -> int:
    artifact = state.outline_stage_artifacts.get(stage)
    previous = 0
    if isinstance(artifact, dict):
        metadata = stage_revision_metadata(artifact)
        previous = int_value(metadata.get("question_round"), int_value(artifact.get("question_round"), 0))
    return previous + 1 if has_questions else previous


def append_artifact_memory(artifact: dict, item: str) -> None:
    text = str(item).strip()
    if not text:
        return
    memory = artifact.get("stage_memory") if isinstance(artifact.get("stage_memory"), list) else []
    artifact["stage_memory"] = [*memory, text]


def answer_stage_unresolved_questions(
    state: NovelState,
    stage: str,
    artifact: dict,
    questions: list[str],
    user_text: str,
    adapter: AgentAdapter,
    store: LocalStore,
    progress: ProgressFunc = noop_progress,
) -> str:
    cleaned_questions = [item.strip() for item in questions if item.strip()]
    if not cleaned_questions:
        return ""
    label = STAGE_LABELS.get(stage, stage)
    emit_progress(progress, "大纲汇总 Agent", with_agent_metadata(f"正在回答「{label}」未决问题...", adapter, "outline_question_answerer"))
    question_lines = "\n".join(f"{index}. {question}" for index, question in enumerate(cleaned_questions, start=1))
    stage_text = str(artifact.get("synthesis") or "").strip() or stage_full_text(state, store, stage)
    prompt = (
        "AGENT: outline_question_answerer\n"
        f"STAGE: {stage}\n"
        f"阶段：{label}\n"
        "任务：用户准备锁定当前大纲阶段或当前阶段已达到最多 3 轮追问。请根据当前阶段产物和前序上下文，逐项回答所有未决问题，并给出可写入阶段记忆的锁定摘要。\n"
        "要求：\n"
        "- 必须回答下面列出的每一个问题，不要跳过。\n"
        "- 不要新增与当前阶段产物或前序阶段冲突的 canon。\n"
        "- 信息不足时选择最稳妥、最利于后续写作连续性的默认方案，并标注为系统默认裁量。\n"
        "- 只输出 Markdown，包含 `## 未决问题默认回答` 和 `## 锁定摘要` 两节。\n\n"
        f"用户确认/触发语：{user_text or '未提供'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, stage)}\n\n"
        f"当前阶段产物：\n{stage_text or stage_memory_context(artifact, 2400) or '暂无'}\n\n"
        f"待回答问题：\n{question_lines}\n"
    )
    try:
        answer = complete_with_metrics(
            adapter=adapter,
            prompt=prompt,
            project_dir=store.project_dir(state.project_id),
            project_id=state.project_id,
            graph="outline",
            node="outline_question_answerer",
            agent="outline_question_answerer",
            prompt_profile="outline_question_answerer",
        ).strip()
    except AgentAdapterError:
        answer = build_stage_closure_summary(stage, cleaned_questions, user_text)
    if not answer:
        answer = build_stage_closure_summary(stage, cleaned_questions, user_text)
    return answer


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
    if stage == "review_lock":
        issue_buckets = review_lock_issue_buckets_from_artifact(artifact)
        blocking_issues = review_lock_blocking_issues(issue_buckets)
        detail_issues = review_lock_detail_issues(issue_buckets)
        combined_issues = review_lock_issue_lines(issue_buckets)
        artifact["review_lock_issues"] = issue_buckets
        if blocking_issues:
            artifact["pending_questions"] = []
            artifact["status"] = "options_ready"
            state.outline_stage_artifacts[stage] = artifact
            state.outline_stage_status = "options_ready"
            state.review_status = "revision_requested"
            state.active_workflow = "outline"
            state.current_stage = stage
            state.active_artifact = "outline_stage"
            state.director_action = "revise_outline"
            state.outline_stage_summaries[stage] = artifact["summary"]
            state.pending_questions = combined_issues
            state.pending_question = review_lock_pending_question_text(issue_buckets)
            state.director_message = review_lock_blocking_message(issue_buckets)
            record_stage_history(state, "review_lock_blocked", stage, state.user_request)
            store.save_state(state)
            return state.to_dict()
        default_summary = ""
        if detail_issues:
            default_summary = answer_stage_unresolved_questions(
                state=state,
                stage=stage,
                artifact=artifact,
                questions=detail_issues,
                user_text=state.user_request,
                adapter=adapter,
                store=store,
                progress=progress,
            )
            artifact["default_discretion_answers"] = default_summary
            artifact["default_discretion_summary"] = default_summary
            append_artifact_memory(artifact, default_summary)
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

        state.outline_stage = stage  # type: ignore[assignment]
        state.outline_stage_status = "locked"
        state.current_stage = stage
        state.director_action = "advance_outline_stage"
        state.director_message = f"已锁定{STAGE_LABELS[stage]}。如需继续，请手动进入{STAGE_LABELS[next_stage]}并点击生成。"
        store.save_state(state)
        return state.to_dict()

    unresolved = stage_unresolved_questions(state, artifact)
    director_summary = str(state.director_task_args.get("default_discretion_summary") or "").strip()
    default_summary = ""
    if unresolved:
        answer_trigger = state.user_request
        if director_summary:
            answer_trigger = f"{state.user_request}；Director 裁量提示：{director_summary}"
        default_summary = answer_stage_unresolved_questions(
            state=state,
            stage=stage,
            artifact=artifact,
            questions=unresolved,
            user_text=answer_trigger,
            adapter=adapter,
            store=store,
            progress=progress,
        )
        artifact["default_discretion_answers"] = default_summary
    elif director_summary:
        default_summary = director_summary
    if default_summary:
        artifact["default_discretion_summary"] = default_summary
        append_artifact_memory(artifact, default_summary)

    if stage == "chapter_outline":
        artifact, _next_volume_index = confirm_current_chapter_outline_volume(artifact, state, store)
        metadata = dict(artifact.get("metadata") or {})
        total_volumes = int(metadata.get("total_volumes") or 1)
        completed_volumes = {int(item) for item in metadata.get("completed_volumes", []) if str(item).isdigit()}
        artifact["pending_questions"] = []
        artifact["status"] = "locked" if len(completed_volumes) >= total_volumes else "options_ready"
        state.outline_stage_artifacts[stage] = artifact
        state.pending_question = ""
        state.pending_questions = []
        state.outline_stage = "chapter_outline"
        state.outline_stage_status = str(artifact["status"])
        state.current_stage = "chapter_outline"
        state.director_action = "advance_outline_stage"
        state.director_message = "已锁定当前卷章节大纲。如需继续，请在章节大纲导航中手动选择下一卷并点击生成。"
        record_stage_history(state, "lock_volume", stage, default_summary or state.user_request)
        save_outline_stage_outputs(state, stage, format_stage_markdown(artifact), store)
        store.save_state(state)
        return state.to_dict()

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

    state.outline_stage = stage  # type: ignore[assignment]
    state.outline_stage_status = "locked"
    state.current_stage = stage
    state.director_action = "advance_outline_stage"
    state.director_message = f"已锁定{STAGE_LABELS[stage]}。如需继续，请手动进入{STAGE_LABELS[next_stage]}并点击生成。"
    store.save_state(state)
    return state.to_dict()




def stage_unresolved_questions(state: NovelState, artifact: dict) -> list[str]:
    questions = []
    raw_artifact_questions = artifact.get("pending_questions")
    if isinstance(raw_artifact_questions, list):
        questions.extend(str(item).strip() for item in raw_artifact_questions if str(item).strip())
    questions.extend(item.strip() for item in state.pending_questions if item.strip())
    generic = f"请确认是否锁定{STAGE_LABELS.get(state.outline_stage, state.outline_stage)}并进入下一阶段，或继续提出修改。"
    return [item for item in dict.fromkeys(questions) if item != generic][:10]


def build_stage_closure_summary(stage: str, questions: list[str], user_text: str) -> str:
    joined = "；".join(questions[:10])
    return (
        f"锁定{STAGE_LABELS.get(stage, stage)}前，模型按当前阶段产物和连续性要求逐项回答未决问题；"
        f"已由本阶段 Agent 默认回答：{joined}；用户确认语：{user_text}"
    )

def save_outline_stage_outputs(state: NovelState, stage: str, content: str, store: LocalStore, source_agent: str = "outline_stage_synthesizer") -> None:
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
            source_agent=source_agent,
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
        return f"用户将待确认问题交由模型按当前阶段产物逐项回答并推进；待裁量问题：{'；'.join(questions[:10])}；用户原话：{text}"
    return f"用户认可当前阶段产物，并将细节交由系统按当前建议由模型回答后推进；用户原话：{text}"



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


def prepare_chapter_outline_metadata(state: NovelState, store: LocalStore) -> dict:
    volume_outline_text = stage_full_text(state, store, "volume_outline")
    artifact = state.outline_stage_artifacts.get("chapter_outline")
    metadata = chapter_outline_metadata_from_artifact(artifact if isinstance(artifact, dict) else None, volume_outline_text)
    state.director_task_args["chapter_outline_metadata"] = metadata
    state.director_task_args["chapter_outline_target_context"] = build_chapter_outline_target_context(metadata)
    return metadata




















def clear_chapter_outline_generation_directives(state: NovelState) -> None:
    state.director_task_args.pop(CHAPTER_OUTLINE_FORCE_FULL_KEY, None)
    state.director_task_args.pop(CHAPTER_OUTLINE_INTERNAL_REQUEST_KEY, None)


def set_next_chapter_outline_volume_generation_directive(state: NovelState, next_volume_index: int) -> None:
    state.director_task_args[CHAPTER_OUTLINE_FORCE_FULL_KEY] = True
    state.director_task_args[CHAPTER_OUTLINE_INTERNAL_REQUEST_KEY] = (
        f"完整生成第 {next_volume_index} 卷章节大纲，不要轻修订已确认卷，"
        "不要只回复确认状态。"
    )








































































def stage_ready_message(stage: str, questions: list[str] | None = None, artifact: dict | None = None) -> str:
    message = f"第 {stage_number(stage)} 阶段「{STAGE_LABELS[stage]}」已完成本轮共创。"
    if stage == "review_lock":
        issue_buckets = review_lock_issue_buckets_from_artifact(artifact or {})
        blocking = review_lock_blocking_issues(issue_buckets)
        detail = review_lock_detail_issues(issue_buckets)
        if blocking or detail:
            message += "\n\n本阶段分为阻塞型结构问题和非阻塞细节问题。"
            if blocking:
                message += f"\n- 阻塞型结构问题：{len(blocking)} 项。"
            if detail:
                message += f"\n- 非阻塞细节问题：{len(detail)} 项。"
            message += "\n\n你可以先回改阻塞项；细节项可以在锁定前补齐，或明确接受当前风险后继续。"
        else:
            message += "\n\n暂未发现阻塞型结构问题；你可以确认锁定并进入章节卡。"
        return message
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
    return list(dict.fromkeys(questions))[:10]





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

def review_outline_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_outline_prompt(state, "outline_editor")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    decision, score = parse_status_score(output)
    state.editor_notes = output.strip()
    state.editor_decision = decision  # type: ignore[assignment]
    state.quality_score = score
    state.revision_instruction = extract_outline_editor_advice(output)
    state.review_status = {
        "pass": "approved",
        "revise": "revision_requested",
        "stop": "stopped",
    }[decision]
    state.next_action = {
        "pass": "human_review",
        "revise": "rewrite_chapter",
        "stop": "stop",
    }[decision]
    state.director_message = state.revision_instruction or state.editor_notes
    store.save_state(state)
    return state.to_dict()


def revise_outline_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_outline_prompt(state, "outline_reviser")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    revised = output.strip()
    if revised:
        state.outline = revised
    add_outline_version(state, "outline", state.outline, "修订后大纲")
    state.editor_decision = "revise"
    state.review_status = "draft"
    state.next_action = "human_review"
    state.director_message = "已生成大纲修订稿。"
    store.save_state(state)
    return state.to_dict()


def compare_outline_versions_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    del adapter
    state = NovelState.from_dict(data)
    if state.outline_versions:
        latest = state.outline_versions[-1]
        if isinstance(latest, dict) and str(latest.get("content") or "").strip():
            state.outline = str(latest.get("content") or "")
    state.director_message = simple_outline_comparison(state)
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
