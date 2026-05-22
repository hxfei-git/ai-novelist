"""Director service shared by CLI and future chat channels."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any, Literal

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.graph_bible import build_bible_graph
from ai_novelist.graph_research import build_research_graph, extract_research_query
from ai_novelist.graph_writer import (
    DIRECTOR_ACTIONS,
    append_message,
    build_reference_summary,
    parse_director_decision,
    persist_available_outputs,
    run_selected_agent,
    show_outline_node,
    show_reference_node,
    show_status_node,
)
from ai_novelist.prompts import load_prompt
from ai_novelist.research import SearchBackend
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError

ProgressFunc = Callable[[str, str], None]
Channel = Literal["cli", "feishu", "test"] | str

CONFIRMATION_ACTIONS = {
    "research",
    "worldbuild",
    "generate_outline",
    "review_outline",
    "revise_outline",
    "compare_versions",
    "plan_chapters",
    "plan_chapter",
    "plan_scenes",
    "write_chapter",
    "review",
    "review_chapter",
    "revise_chapter",
    "finalize_chapter",
    "export_project",
    "persist_outputs",
}
DIRECT_ACTIONS = {"ask_user", "show_status", "show_outline", "show_reference", "show_bible", "stop"}


@dataclass
class DirectorDecision:
    action: str
    requires_confirmation: bool = False
    confidence: int = 0
    user_message: str = ""
    task_args: dict[str, Any] = field(default_factory=dict)
    next_steps: list[str] = field(default_factory=list)
    target: str = "unknown"
    intent: str = "answer"
    instruction: str = ""
    locked_constraints: list[str] = field(default_factory=list)
    style_preferences: list[str] = field(default_factory=list)
    chapter: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "requires_confirmation": self.requires_confirmation,
            "confidence": self.confidence,
            "user_message": self.user_message,
            "task_args": self.task_args,
            "next_steps": self.next_steps,
            "target": self.target,
            "intent": self.intent,
            "instruction": self.instruction,
            "locked_constraints": self.locked_constraints,
            "style_preferences": self.style_preferences,
            "chapter": self.chapter,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectorDecision":
        action = str(data.get("action", "ask_user")).strip().lower()
        if action == "persist_outline":
            action = "persist_outputs"
        if action == "plan_outline":
            action = "generate_outline"
        if action == "plan_chapters":
            action = "plan_chapter"
        if action == "review":
            action = "review_chapter"
        if action == "export":
            action = "export_project"
        if action in {"run_current_stage", "answer_pending_questions"}:
            action = "revise_outline"
        if action == "advance_current_stage":
            action = "persist_outputs"
        if action == "show_stage":
            action = "show_outline"
        if action not in DIRECTOR_ACTIONS:
            action = "ask_user"
        task_args = data.get("task_args") if isinstance(data.get("task_args"), dict) else {}
        chapter = normalize_chapter(data.get("chapter") or task_args.get("chapter"))
        return cls(
            action=action,
            requires_confirmation=normalize_bool(data.get("requires_confirmation"), action in CONFIRMATION_ACTIONS),
            confidence=normalize_confidence(data.get("confidence")),
            user_message=str(data.get("user_message") or data.get("message") or "我需要更多信息才能决定下一步。").strip(),
            task_args=dict(task_args),
            next_steps=normalize_str_list(data.get("next_steps", [])),
            target=str(data.get("target", "unknown")).strip().lower() or "unknown",
            intent=str(data.get("intent", "answer")).strip().lower() or "answer",
            instruction=str(data.get("instruction", "")).strip(),
            locked_constraints=normalize_str_list(data.get("locked_constraints", [])),
            style_preferences=normalize_str_list(data.get("style_preferences", [])),
            chapter=chapter,
        )


@dataclass
class DirectorChoice:
    id: str
    label: str
    value: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "value": self.value}


@dataclass
class DirectorTurnResult:
    immediate_message: str = ""
    started_task: str = ""
    final_message: str = ""
    artifact_paths: list[str] = field(default_factory=list)
    choices: list[DirectorChoice] = field(default_factory=list)
    requires_followup: bool = False
    state: NovelState | None = None
    decision: DirectorDecision | None = None


class DirectorService:
    def __init__(
        self,
        store: LocalStore,
        adapter: AgentAdapter,
        search_backend: SearchBackend,
        progress: ProgressFunc | None = None,
    ) -> None:
        self.store = store
        self.adapter = adapter
        self.search_backend = search_backend
        self.progress = progress

    def handle_turn(self, project_id: str, user_text: str, channel: Channel = "cli") -> DirectorTurnResult:
        state = load_or_create_project(self.store, project_id)
        text = user_text.strip()
        if not text:
            return DirectorTurnResult(immediate_message="请输入你的需求。", requires_followup=True, state=state)

        pending = DirectorDecision.from_dict(state.pending_director_decision) if state.pending_director_decision else None
        if pending and is_rejection(text):
            state.pending_director_decision = {}
            state.director_message = "已取消上一步计划。你可以重新说明想做什么。"
            append_message(state, "user", text)
            append_message(state, "assistant", state.director_message)
            self.store.save_state(state)
            return DirectorTurnResult(final_message=state.director_message, requires_followup=True, state=state)
        if pending and should_execute_pending_decision(text):
            state.pending_director_decision = {}
            state.user_request = merged_pending_user_request(pending, text, state.user_request)
            if not is_confirmation(text):
                pending.task_args["confirmation_reply"] = text
            append_message(state, "user", text)
            self.store.save_state(state)
            return self._execute_decision(state, pending, channel)

        state.user_request = text
        append_message(state, "user", text)
        if not state.idea and looks_like_story_idea(text):
            state.idea = text
        self.store.save_state(state)

        decision = self._decide(state, channel)
        decision.task_args.setdefault("original_user_text", text)
        hydrate_decision_args(decision, state)
        state.director_task_args = decision.task_args
        self._apply_decision_metadata(state, decision)

        if should_prompt_for_confirmation(decision, state):
            state.pending_director_decision = decision.to_dict()
            state.director_message = confirmation_message(decision)
            append_message(state, "assistant", state.director_message)
            self.store.save_state(state)
            return DirectorTurnResult(
                immediate_message=state.director_message,
                choices=confirmation_choices(),
                requires_followup=True,
                state=state,
                decision=decision,
            )

        state.pending_director_decision = {}
        self.store.save_state(state)
        return self._execute_decision(state, decision, channel)

    def _decide(self, state: NovelState, channel: Channel) -> DirectorDecision:
        direct = deterministic_bible_decision(state, self.store)
        if direct is not None:
            return direct
        direct = deterministic_chapter_pipeline_decision(state)
        if direct is not None:
            return direct
        direct = deterministic_outline_stage_decision(state)
        if direct is not None:
            return direct
        prompt = build_service_director_prompt(state, self.store, channel)
        if self.progress:
            self.progress("Director", "正在理解你的需求...")
        try:
            output = self.adapter.complete(prompt, self.store.project_dir(state.project_id))
        except AgentAdapterError:
            return fallback_decision(state)
        return parse_service_director_output(output, state)

    def _execute_decision(self, state: NovelState, decision: DirectorDecision, channel: Channel) -> DirectorTurnResult:
        self._apply_decision_metadata(state, decision)
        if self.progress:
            plan = execution_plan_message(decision)
            if plan:
                self.progress("Plan", plan)
        state.director_task_args = decision.task_args
        state.pending_director_decision = {}
        self.store.save_state(state)

        if decision.action == "research":
            result_state = self._run_research(state)
        elif decision.action == "persist_outputs":
            if state.active_workflow == "outline" and state.outline_stage != "done":
                from ai_novelist.graph_outline import OUTLINE_STAGES, advance_outline_stage_node

                requested_stage = str(decision.task_args.get("stage", "")).strip()
                if requested_stage in OUTLINE_STAGES:
                    state.outline_stage = requested_stage  # type: ignore[assignment]
                    state.current_stage = requested_stage
                result_state = NovelState.from_dict(advance_outline_stage_node(state.to_dict(), self.adapter, self.store, self.progress or noop_progress))
            else:
                result_state = NovelState.from_dict(persist_available_outputs(state.to_dict(), self.store))
        elif decision.action in {"init_bible", "update_bible"}:
            result_state = self._run_bible(state)
        elif decision.action == "plan_chapter":
            result_state = self._run_chapter_plan(state)
        elif decision.action == "plan_scenes":
            result_state = self._run_scene_plan(state)
        elif decision.action == "finalize_chapter":
            result_state = self._run_finalize(state)
        elif decision.action == "export_project":
            result_state = self._run_export(state)
        elif decision.action == "show_bible":
            result_state = show_bible_state(state, self.store)
        elif decision.action == "show_status":
            result_state = NovelState.from_dict(show_status_node(state.to_dict(), self.store))
        elif decision.action == "show_outline":
            result_state = NovelState.from_dict(show_outline_node(state.to_dict(), self.store))
        elif decision.action == "show_reference":
            result_state = NovelState.from_dict(show_reference_node(state.to_dict(), self.store))
        elif decision.action == "stop":
            state.review_status = "stopped"
            state.next_action = "stop"
            state.director_message = decision.user_message or "已结束本次创作对话。"
            append_message(state, "assistant", state.director_message)
            self.store.save_state(state)
            result_state = state
        elif decision.action == "ask_user":
            state.pending_question = decision.user_message
            state.director_message = decision.user_message
            append_message(state, "assistant", state.director_message)
            self.store.save_state(state)
            result_state = state
        else:
            result_state = NovelState.from_dict(run_selected_agent(state.to_dict(), self.adapter, self.store, self.progress or noop_progress))

        update_project_context(result_state, self.store, decision)
        return DirectorTurnResult(
            started_task=decision.action if decision.action not in DIRECT_ACTIONS else "",
            final_message=result_state.director_message,
            artifact_paths=artifact_paths(result_state, self.store),
            requires_followup=result_state.director_action != "stop",
            state=result_state,
            decision=decision,
        )

    def _run_bible(self, state: NovelState) -> NovelState:
        if not state.outline.strip() and not state.outline_stage_artifacts:
            state.director_message = "当前还没有可用于初始化小说圣经的大纲产物。请先完成大纲锁定。"
            state.director_action = "update_bible"
            self.store.save_state(state)
            return state
        if self.progress:
            self.progress("Bible", "正在更新小说圣经...")
        graph = build_bible_graph(self.adapter, self.store)
        return NovelState.from_dict(graph.invoke(state.to_dict()))

    def _run_chapter_plan(self, state: NovelState) -> NovelState:
        from ai_novelist.graph_chapter_plan import build_chapter_plan_graph

        graph = build_chapter_plan_graph(self.adapter, self.store, progress=self.progress)
        return NovelState.from_dict(graph.invoke(state.to_dict()))

    def _run_scene_plan(self, state: NovelState) -> NovelState:
        from ai_novelist.graph_scene import build_scene_graph

        graph = build_scene_graph(self.adapter, self.store, progress=self.progress)
        return NovelState.from_dict(graph.invoke(state.to_dict()))

    def _run_finalize(self, state: NovelState) -> NovelState:
        from ai_novelist.graph_finalize import build_finalize_graph

        graph = build_finalize_graph(self.adapter, self.store, progress=self.progress)
        return NovelState.from_dict(graph.invoke(state.to_dict()))

    def _run_export(self, state: NovelState) -> NovelState:
        from ai_novelist.graph_export import build_export_graph

        graph = build_export_graph(self.store, progress=self.progress)
        return NovelState.from_dict(graph.invoke(state.to_dict()))

    def _run_research(self, state: NovelState) -> NovelState:
        query = first_text(state.director_task_args, "research_query", "work_title", "author")
        if query:
            state.retrieval_query = query
            state.open_decisions = [item for item in state.open_decisions if not item.startswith("research_query:")]
            state.open_decisions.append(f"research_query:{query}")
        graph = build_research_graph(self.search_backend, self.store, adapter=self.adapter, progress=self.progress)
        return NovelState.from_dict(graph.invoke(state.to_dict()))

    def _apply_decision_metadata(self, state: NovelState, decision: DirectorDecision) -> None:
        state.director_action = decision.action
        state.director_intent = decision.intent
        state.active_artifact = decision.target
        state.director_message = decision.user_message
        state.active_task = decision.action
        state.next_action = decision.action
        if decision.instruction:
            state.revision_instruction = decision.instruction
        for item in decision.locked_constraints:
            if item not in state.locked_constraints:
                state.locked_constraints.append(item)
        for item in decision.style_preferences:
            if item not in state.style_preferences:
                state.style_preferences.append(item)
        chapter = decision.chapter or normalize_chapter(decision.task_args.get("chapter"))
        if chapter:
            state.current_chapter = chapter




def execution_plan_message(decision: DirectorDecision) -> str:
    chapter = decision.chapter or normalize_chapter(decision.task_args.get("chapter"))
    if decision.action == "write_chapter":
        return f"将生成第 {chapter or 1} 章正文；缺少章节卡或场景卡时会先自动补齐。"
    if decision.action == "review_chapter":
        return f"将审稿第 {chapter or 1} 章，包含连续性、结构、人物、风格和读者反馈。"
    if decision.action == "revise_chapter":
        return f"将按审稿任务修订第 {chapter or 1} 章，并保存新版草稿。"
    if decision.action == "finalize_chapter":
        return f"将定稿第 {chapter or 1} 章，生成摘要并更新小说圣经。"
    if decision.action == "export_project":
        return "将收集已定稿章节并导出 manuscript、volume 和 novel_bible。"
    if decision.action == "plan_chapter":
        return f"将把第 {chapter or 1} 章大纲细化为章节卡。"
    if decision.action == "plan_scenes":
        return f"将把第 {chapter or 1} 章章节卡拆成场景卡。"
    if decision.action in {"init_bible", "update_bible"}:
        return "将基于当前稳定产物更新小说圣经。"
    if decision.action == "research":
        return "将检索参考资料并整理参考简报。"
    return ""


def noop_progress(_stage: str, _message: str) -> None:
    return

def load_or_create_project(store: LocalStore, project_id: str) -> NovelState:
    try:
        return store.load_state(project_id)
    except LocalStoreError:
        return store.create_project(project_id, project_id)


def build_service_director_prompt(state: NovelState, store: LocalStore, channel: Channel) -> str:
    template = load_prompt("director")
    history = format_recent_dialogue_for_director(state)
    project_context = store.load_project_context(state.project_id)
    project_memory = store.load_project_memory(state.project_id)
    outline_stage_context = current_outline_stage_context(state)
    return (
        f"{template.rstrip()}\n\n"
        "## 输出格式\n"
        "优先输出一个 JSON 对象，不要包裹 Markdown 代码块。字段：action, requires_confirmation, confidence, user_message, task_args, next_steps, intent, instruction, locked_constraints。\n"
        "task_args 可包含 research_query, work_title, author, chapter, instruction, stage, default_discretion_summary。\n"
        "大纲共创阶段可用动作语义：run_current_stage（继续重写/补充当前阶段）、advance_current_stage（锁定当前阶段并进入下一阶段）、answer_pending_questions（吸收用户对待确认问题的回答后重跑当前阶段）、show_stage（查看当前或指定阶段）、ask_user（信息不足再追问）。输出时也可使用等价旧动作 revise_outline、persist_outputs、show_outline。\n"
        "判断大纲阶段意图时必须区分：用户提供新修改意见、用户回答问题、用户把剩余问题交给系统裁量并要求推进、用户只是查看状态。待确认问题不是必须逐项回答的阻塞项；只有用户明确要求进入/推进下一阶段，或明确锁定当前阶段并继续，才选择 advance_current_stage。不要因为句子里出现‘确定/确认/同意’就推进；如果用户是在确定某个设定、回答问题或补充细节，应留在当前阶段处理。若用户明确交给系统裁量并推进，请选择 advance_current_stage，并在 default_discretion_summary 中写一段简短裁量摘要。\n"
        "如果无法输出 JSON，才使用旧的 ACTION/MESSAGE 字段格式。\n\n"
        "## 当前通道\n"
        f"{channel}\n\n"
        "## project_context.md\n"
        f"{project_context.strip() or '暂无'}\n\n"
        "## project_memory.md\n"
        f"{project_memory.strip() or '暂无'}\n\n"
        "## state.json 摘要\n"
        f"项目：{state.project_id}\n"
        f"标题：{state.title}\n"
        f"创意：{state.idea or '暂无'}\n"
        f"当前章节：{state.current_chapter}\n"
        f"参考简报：{'已有' if state.reference_brief else '暂无'}\n"
        f"检索查询：{state.retrieval_query or '暂无'}\n"
        f"世界观：{'已有' if state.worldbuilding else '暂无'}\n"
        f"总大纲：{'已有' if state.outline else '暂无'}\n"
        f"章节细纲：{'已有' if state.chapter_plan else '暂无'}\n"
        f"章节正文：{'已有' if state.chapter_draft else '暂无'}\n"
        f"编辑意见：{'已有' if state.editor_notes else '暂无'}\n"
        f"小说圣经：{'已有' if store.novel_bible_markdown_path(state.project_id).exists() else '暂无'}\n"
        f"待确认决策：{'有' if state.pending_director_decision else '无'}\n"
        f"active_workflow：{state.active_workflow or 'none'}\n"
        f"outline_stage：{state.outline_stage}\n"
        f"outline_stage_status：{state.outline_stage_status}\n"
        f"pending_questions：{json.dumps(state.pending_questions, ensure_ascii=False)}\n"
        f"pending_question：{state.pending_question or '暂无'}\n\n"
        f"## 当前大纲阶段产物（优先于旧对话）\n{outline_stage_context}\n\n"
        f"## 已获取参考信息摘要\n{build_reference_summary(state, max_chars=1200) if state.reference_brief or state.retrieval_context or state.research_sources else '暂无'}\n\n"
        f"## 最近编辑意见和待确认项\n{state.editor_notes[-1800:] if state.editor_notes.strip() else '暂无'}\n\n"
        "## 最近对话（仅作口吻和上下文参考；若与当前阶段产物冲突，以当前阶段产物为准）\n"
        f"{history or '暂无'}\n\n"
        f"最新用户输入：{state.user_request}\n"
    )


def current_outline_stage_context(state: NovelState, max_chars: int = 1800) -> str:
    artifact = state.outline_stage_artifacts.get(state.outline_stage)
    if not artifact:
        return "暂无"
    memory = artifact.get("stage_memory")
    if isinstance(memory, list) and memory:
        synthesis = "\n".join(f"- {str(item).strip()}" for item in memory if str(item).strip())
    else:
        synthesis = str(artifact.get("summary") or artifact.get("synthesis", "")).strip()
    if not synthesis:
        return "暂无"
    label = artifact.get("label") or state.outline_stage
    content = f"# {label}\n\n{synthesis}"
    if len(content) > max_chars:
        return content[:max_chars].rstrip() + "\n..."
    return content


def format_recent_dialogue_for_director(state: NovelState, max_items: int = 8, max_chars_per_message: int = 260) -> str:
    lines: list[str] = []
    for msg in state.messages[-max_items:]:
        role = str(msg.get("role", "")).strip()
        content = str(msg.get("content", "")).strip()
        if not role or not content:
            continue
        if role == "assistant" and looks_like_stale_stage_summary(content, state):
            continue
        if len(content) > max_chars_per_message:
            content = content[:max_chars_per_message].rstrip() + "..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def looks_like_stale_stage_summary(content: str, state: NovelState) -> bool:
    if "之前已确认" in content or "还剩" in content and "尚未" in content:
        return True
    artifact = state.outline_stage_artifacts.get(state.outline_stage, {})
    synthesis = str(artifact.get("synthesis", ""))
    return bool(synthesis and "待确认" in content and content not in synthesis)


def parse_service_director_output(output: str, state: NovelState) -> DirectorDecision:
    parsed_json = parse_json_object(output)
    if parsed_json:
        decision = DirectorDecision.from_dict(parsed_json)
    else:
        legacy = parse_director_decision(output)
        legacy["user_message"] = legacy.pop("message")
        legacy["requires_confirmation"] = legacy["action"] in CONFIRMATION_ACTIONS
        legacy["confidence"] = 70 if legacy["action"] != "ask_user" else 35
        legacy["task_args"] = {}
        decision = DirectorDecision.from_dict(legacy)
    hydrate_decision_args(decision, state)
    apply_pending_confirmation_feedback(decision, state)
    return decision


def apply_pending_confirmation_feedback(decision: DirectorDecision, state: NovelState) -> None:
    questions = extract_confirmation_questions(state)
    if not questions or not has_confirmation_feedback(state.user_request):
        return

    constraints = confirmation_feedback_constraints(state.user_request, questions)
    if not constraints:
        return

    for item in constraints:
        if item not in decision.locked_constraints:
            decision.locked_constraints.append(item)

    feedback_instruction = "；".join(constraints)
    if decision.instruction:
        decision.instruction = f"{decision.instruction}；{feedback_instruction}"
    else:
        decision.instruction = feedback_instruction
    decision.task_args["instruction"] = decision.instruction

    if state.outline.strip() and state.editor_decision == "revise" and decision.action == "ask_user":
        decision.action = "revise_outline"
        decision.requires_confirmation = True
        decision.intent = "revise"
        decision.target = "outline"
        decision.user_message = "我会把这些确认项作为锁定约束纳入大纲修订。"


def extract_confirmation_questions(state: NovelState) -> list[str]:
    text = "\n".join(
        item
        for item in [
            state.editor_notes,
            state.pending_question,
            "\n".join(state.pending_questions),
        ]
        if item
    )
    questions: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*+•\d.、\s]+", "", line).strip()
        if not line:
            continue
        if "？" in line or "?" in line or line.startswith(("是否", "能否", "要不要")):
            questions.append(line)
    return list(dict.fromkeys(questions))[-6:]


def has_confirmation_feedback(text: str) -> bool:
    if any(word in text for word in ("接受", "接收", "同意", "认可", "采用")):
        return True
    return bool(re.search(r"\b(ok|yes|approve|confirm)\b", text, re.IGNORECASE))


def confirmation_feedback_constraints(text: str, questions: list[str]) -> list[str]:
    accept_pattern = re.compile(r"接受|接收|同意|认可|采用|\bok\b|\byes\b|\bapprove\b|\bconfirm\b", re.IGNORECASE)
    first_accept = accept_pattern.search(text)
    constraints: list[str] = []
    question_index = 0

    if first_accept:
        explicit_answer = text[: first_accept.start()].strip(" ：:，,。.!！?？；; \n\t")
        accept_count = len(accept_pattern.findall(text[first_accept.start() :]))
    else:
        explicit_answer = text.strip(" ：:，,。.!！?？；; \n\t")
        accept_count = 0

    if explicit_answer and questions:
        constraints.append(f"用户确认：{questions[0]} -> {explicit_answer}")
        question_index = 1

    if accept_count and not explicit_answer and accept_count >= len(questions):
        remaining = questions
    else:
        remaining = questions[question_index : question_index + accept_count]
    constraints.extend(f"用户接受：{question}" for question in remaining)
    return constraints


def parse_json_object(output: str) -> dict[str, Any]:
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



def deterministic_chapter_pipeline_decision(state: NovelState) -> DirectorDecision | None:
    text = state.user_request.strip()
    if not text:
        return None
    lowered = text.lower()
    chapter = extract_chapter_from_text(text) or state.current_chapter
    wants_export = any(marker in text for marker in ("导出小说", "导出全文", "导出手稿")) or any(marker in lowered for marker in ("export novel", "export manuscript", "export"))
    if wants_export:
        return DirectorDecision(
            "export_project",
            requires_confirmation=False,
            user_message="我会导出当前已定稿章节。",
            confidence=95,
            target="export",
            intent="export",
        )
    wants_finalize = (any(marker in text for marker in ("定稿", "最终稿")) and "章" in text) or "finalize chapter" in lowered
    if wants_finalize:
        return DirectorDecision(
            "finalize_chapter",
            requires_confirmation=False,
            user_message=f"我会定稿第 {chapter} 章并更新小说圣经。",
            confidence=95,
            task_args={"chapter": chapter, "explicit_finalize": True},
            target="final_chapter",
            intent="approve",
            chapter=chapter,
        )
    wants_scene = "章" in text and ("场景" in text or "scene" in lowered)
    if wants_scene:
        return DirectorDecision(
            "plan_scenes",
            requires_confirmation=False,
            user_message=f"我会为第 {chapter} 章生成场景卡。",
            confidence=95,
            task_args={"chapter": chapter},
            target="scene_cards",
            intent="create",
            chapter=chapter,
        )
    wants_chapter_card = "章节卡" in text or ("规划" in text and "章" in text and "场景" not in text) or "chapter card" in lowered
    if wants_chapter_card:
        return DirectorDecision(
            "plan_chapter",
            requires_confirmation=False,
            user_message=f"我会为第 {chapter} 章生成章节卡。",
            confidence=95,
            task_args={"chapter": chapter},
            target="chapter_card",
            intent="create",
            chapter=chapter,
        )
    wants_review = ("章" in text and any(marker in text for marker in ("审稿", "审查", "检查"))) or "review chapter" in lowered
    if wants_review:
        return DirectorDecision(
            "review_chapter",
            requires_confirmation=False,
            user_message=f"我会审稿第 {chapter} 章。",
            confidence=95,
            task_args={"chapter": chapter},
            target="chapter",
            intent="review",
            chapter=chapter,
        )
    wants_revise = ("章" in text and any(marker in text for marker in ("修订", "修改", "重写", "改写"))) or "revise chapter" in lowered
    if wants_revise:
        return DirectorDecision(
            "revise_chapter",
            requires_confirmation=False,
            user_message=f"我会修订第 {chapter} 章。",
            confidence=95,
            task_args={"chapter": chapter},
            target="chapter",
            intent="revise",
            chapter=chapter,
        )
    wants_write = ("章" in text and any(marker in text for marker in ("写", "生成正文", "正文"))) or "write chapter" in lowered
    if wants_write:
        return DirectorDecision(
            "write_chapter",
            requires_confirmation=False,
            user_message=f"我会生成第 {chapter} 章正文。",
            confidence=95,
            task_args={"chapter": chapter},
            target="chapter",
            intent="create",
            chapter=chapter,
        )
    return None


def extract_chapter_from_text(text: str) -> int | None:
    match = re.search(r"第\s*(\d+)\s*章", text)
    if match:
        return max(1, int(match.group(1)))
    match = re.search(r"chapter\s*(\d+)", text, re.IGNORECASE)
    if match:
        return max(1, int(match.group(1)))
    return None


def deterministic_bible_decision(state: NovelState, store: LocalStore) -> DirectorDecision | None:
    text = state.user_request.strip()
    lowered = text.lower()
    if not text:
        return None
    bible_markers = ("小说圣经", "novel bible", "bible")
    if any(marker in lowered for marker in ("show bible", "view bible")) or any(marker in text for marker in ("查看小说圣经", "展示小说圣经", "看一下小说圣经", "显示小说圣经")):
        return DirectorDecision("show_bible", user_message="我会展示当前小说圣经。", confidence=95, target="novel_bible", intent="status")
    if any(marker in text for marker in ("更新小说圣经", "初始化小说圣经", "生成小说圣经")) or any(marker in lowered for marker in ("update bible", "init bible", "generate bible")):
        action = "init_bible" if any(marker in text for marker in ("初始化小说圣经", "生成小说圣经")) or any(marker in lowered for marker in ("init bible", "generate bible")) else "update_bible"
        return DirectorDecision(action, user_message="我会基于当前稳定产物更新小说圣经。", confidence=95, target="novel_bible", intent="update")
    if any(marker in text for marker in bible_markers):
        return DirectorDecision("show_bible", user_message="我会展示当前小说圣经。", confidence=80, target="novel_bible", intent="status")
    return None


def deterministic_outline_stage_decision(state: NovelState) -> DirectorDecision | None:
    text = state.user_request.strip()
    if not text:
        return None
    view = deterministic_view_decision(state)
    if view is not None:
        return view

    if state.active_workflow != "outline" or state.outline_stage == "done":
        return None

    if state.outline_stage_status == "options_ready" and should_defer_outline_confirmation_to_director(text):
        return None

    if state.pending_questions and answers_pending_outline_questions(text):
        instruction = build_pending_answer_instruction(state, text)
        return DirectorDecision(
            "revise_outline",
            requires_confirmation=False,
            user_message="我会吸收你的补充回答，并重跑当前大纲阶段。",
            confidence=88,
            task_args={"instruction": instruction},
            target="outline",
            intent="answer_pending_questions",
            instruction=instruction,
            locked_constraints=[instruction],
        )

    if looks_like_outline_stage_feedback(text):
        return DirectorDecision(
            "revise_outline",
            requires_confirmation=False,
            user_message="我会把你的新意见合入当前阶段，并重跑阶段产物。",
            confidence=82,
            task_args={"instruction": text},
            target="outline",
            intent="run_current_stage",
            instruction=text,
        )

    return None



def negates_stage_advance(text: str) -> bool:
    return any(marker in text for marker in ("不要进入下一阶段", "不进入下一阶段", "先不进入下一阶段", "暂不进入下一阶段", "别进入下一阶段", "不要推进", "先不推进", "暂不推进"))


def should_defer_outline_confirmation_to_director(text: str) -> bool:
    """Let the Director model judge natural-language stage approval or delegation."""
    if parse_numbered_answers(text):
        return False
    if any(marker in text for marker in ("查看", "展示", "看一下", "看下", "显示")):
        return False
    if negates_stage_advance(text):
        return False
    transition_markers = ("下一阶段", "进入下一阶段", "推进到下一阶段", "进入后续阶段", "推进后续阶段")
    lock_and_continue = any(marker in text for marker in ("锁定当前阶段", "锁定本阶段", "通过当前阶段", "通过本阶段")) and any(marker in text for marker in ("继续", "进入", "推进", "下一阶段"))
    delegated_advance = any(marker in text for marker in ("你决定", "由你决定", "交给你", "默认处理", "你来定")) and any(marker in text for marker in ("继续", "进入", "推进", "下一阶段"))
    return any(marker in text for marker in transition_markers) or lock_and_continue or delegated_advance

def stage_display_name(stage: str) -> str:
    labels = {
        "direction": "方向定位",
        "concept": "故事概念",
        "worldbuilding": "世界观设定",
        "characters": "人物关系",
        "story_flow": "故事流程",
        "volume_outline": "分卷大纲",
        "chapter_outline": "章节大纲",
        "review_lock": "审稿锁定",
    }
    return labels.get(stage, stage)

def is_simple_outline_stage_confirmation(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {
        "下一阶段",
        "进入下一阶段",
        "确认进入下一阶段",
        "确定进入下一阶段",
        "推进到下一阶段",
        "advance",
    }


def delegates_outline_stage_decision(text: str) -> bool:
    markers = (
        "你决定",
        "由你决定",
        "交给你",
        "系统决定",
        "系统裁量",
        "按你建议",
        "按系统建议",
        "按当前建议",
        "默认处理",
        "你来定",
        "你看着办",
        "无需我确认",
    )
    wants_advance = any(marker in text for marker in ("下一阶段", "进入", "推进", "继续", "锁定", "确定"))
    return any(marker in text for marker in markers) and wants_advance


def answers_pending_outline_questions(text: str) -> bool:
    if is_simple_outline_stage_confirmation(text) or delegates_outline_stage_decision(text):
        return False
    if re.search(r"(^|[\s，,；;])\d+[.、)]", text):
        return True
    return any(marker in text for marker in ("回答", "补充", "选择", "选", "采用", "接受", "接收", "同意", "设为", "改成"))


def looks_like_outline_stage_feedback(text: str) -> bool:
    if is_simple_outline_stage_confirmation(text) or delegates_outline_stage_decision(text):
        return False
    if any(marker in text for marker in ("查看", "展示", "看一下", "看下", "显示")):
        return False
    return bool(text.strip())


def build_pending_answer_instruction(state: NovelState, text: str) -> str:
    questions = [item.strip() for item in state.pending_questions if item.strip()]
    if not questions:
        return text
    numbered_answers = parse_numbered_answers(text)
    if numbered_answers:
        parts = []
        for index, answer in numbered_answers.items():
            question = questions[index - 1] if 0 < index <= len(questions) else f"问题 {index}"
            parts.append(f"用户回答：{question} -> {answer}")
        return "；".join(parts)
    return "用户补充待确认问题：" + text


def parse_numbered_answers(text: str) -> dict[int, str]:
    matches = list(re.finditer(r"(?<!\d)(?P<index>\d+)(?:[.、)]\s*|(?=\D))", text))
    answers: dict[int, str] = {}
    for pos, match in enumerate(matches):
        start = match.end()
        end = matches[pos + 1].start() if pos + 1 < len(matches) else len(text)
        answer = text[start:end].strip(" ：:，,。；;\n\t")
        if answer:
            answers[int(match.group("index"))] = answer
    return answers


def build_default_discretion_summary(state: NovelState, text: str) -> str:
    questions = [item.strip() for item in state.pending_questions if item.strip()]
    if questions:
        joined = "；".join(questions[:4])
        return f"锁定当前阶段前，系统按当前阶段产物和连续性要求自行闭环未决问题并推进；待裁量问题：{joined}；用户原话：{text}"
    return f"用户认可当前阶段产物，并将细节交由系统按当前建议默认裁量后推进；用户原话：{text}"


def deterministic_view_decision(state: NovelState) -> DirectorDecision | None:
    text = state.user_request.strip()
    lowered = text.lower()
    wants_view = any(marker in text for marker in ("查看", "展示", "看一下", "看下", "看看", "显示")) or lowered.startswith("show ")
    stage = detect_outline_stage_request(text)
    if wants_view and stage:
        return DirectorDecision(
            "show_outline",
            user_message="我会展示当前大纲阶段内容。",
            confidence=95,
            task_args={"stage": stage},
            target="outline",
            intent="status",
        )
    if wants_view and any(marker in text for marker in ("当前阶段", "阶段内容", "阶段产物", "当前产物")):
        return DirectorDecision(
            "show_outline",
            user_message="我会展示当前大纲阶段内容。",
            confidence=90,
            target="outline",
            intent="status",
        )
    return None


def detect_outline_stage_request(text: str) -> str:
    stage_markers = {
        "direction": ("方向定位", "创作方向", "方向阶段"),
        "concept": ("故事概念", "概念阶段", "核心冲突", "反转机制"),
        "worldbuilding": ("世界观", "世界观设定", "世界观阶段"),
        "characters": ("人物关系", "人物阶段", "角色关系"),
        "story_flow": ("故事流程", "流程阶段", "剧情流程"),
        "volume_outline": ("分卷大纲", "分卷阶段", "总大纲草案", "大纲草案"),
        "chapter_outline": ("章节大纲", "章节阶段", "章节拆分", "章节钩子"),
        "review_lock": ("审稿锁定", "终审阶段"),
    }
    for stage, markers in stage_markers.items():
        if any(marker in text for marker in markers):
            return stage
    return ""


def fallback_decision(state: NovelState) -> DirectorDecision:
    direct = deterministic_outline_stage_decision(state)
    if direct is not None:
        return direct
    text = state.user_request
    if any(marker in text for marker in ("查看状态", "项目状态", "显示状态")) or text.lower() in {"status", "show status"}:
        return DirectorDecision("show_status", user_message="我会展示当前项目状态。", confidence=60)
    if any(marker in text for marker in ("查看小说圣经", "展示小说圣经", "更新小说圣经", "小说圣经")) or text.lower() in {"show bible", "update bible"}:
        action = "update_bible" if "更新" in text or "update" in text.lower() else "show_bible"
        return DirectorDecision(action, user_message="我会处理小说圣经。", confidence=70, target="novel_bible")
    if any(marker in text for marker in ("导出小说", "导出全文", "导出手稿")) or "export" in text.lower():
        return DirectorDecision("export_project", user_message="我会导出当前已定稿章节。", confidence=70, target="export", intent="export")
    if any(marker in text for marker in ("定稿", "最终稿")) and "章" in text:
        chapter = extract_chapter_from_text(text) or state.current_chapter
        return DirectorDecision("finalize_chapter", user_message=f"我会定稿第 {chapter} 章并更新小说圣经。", confidence=70, task_args={"chapter": chapter, "explicit_finalize": True}, target="final_chapter", intent="approve", chapter=chapter)
    if any(marker in text for marker in ("查看大纲", "当前大纲", "展示大纲")):
        return DirectorDecision("show_outline", user_message="我会展示当前大纲。", confidence=60)
    if any(marker in text for marker in ("参考简报", "参考信息", "检索信息", "调研信息", "当前获取的信息")):
        return DirectorDecision("show_reference", user_message="我会展示当前已获取的信息。", confidence=60)
    if any(marker in text for marker in ("同人", "原作", "查一下", "调研", "research", "苟在初圣")):
        return DirectorDecision("research", True, 45, "我建议先调研参考资料。", {"research_query": extract_research_query(text)})
    return DirectorDecision("ask_user", user_message="我需要更多信息才能决定下一步。", confidence=20)


def hydrate_decision_args(decision: DirectorDecision, state: NovelState) -> None:
    if decision.instruction:
        decision.task_args.setdefault("instruction", decision.instruction)
    if decision.chapter:
        decision.task_args.setdefault("chapter", decision.chapter)
    if decision.action == "research":
        query = first_text(decision.task_args, "research_query", "work_title", "author") or extract_research_query(state.user_request)
        if query:
            decision.task_args["research_query"] = query
    if decision.action in {"plan_chapter", "plan_scenes", "write_chapter", "review", "review_chapter", "revise_chapter", "finalize_chapter"} and not decision.task_args.get("chapter"):
        decision.task_args["chapter"] = state.current_chapter


def update_project_context(state: NovelState, store: LocalStore, decision: DirectorDecision) -> None:
    facts = "\n".join(f"- {item}" for item in state.canon_facts[:8]) or "- 暂无"
    uncertainties = "\n".join(f"- {item}" for item in state.research_uncertainties[:6]) or "- 暂无"
    pending = format_pending_context(state)
    next_steps = "\n".join(f"- {item}" for item in decision.next_steps[:6]) or default_next_steps(state)
    stage_context = format_current_stage_context(state)
    content = (
        f"# Project Context: {state.project_id}\n\n"
        "## 项目目标\n"
        f"- 标题：{state.title}\n"
        f"- 创意：{state.idea or '暂无'}\n"
        f"- 当前章节：{state.current_chapter}\n\n"
        "## 当前大纲阶段\n"
        f"{stage_context}\n\n"
        "## 已检索事实\n"
        f"- 最近查询：{state.retrieval_query or '暂无'}\n"
        f"{facts}\n\n"
        "## 不确定点\n"
        f"{uncertainties}\n\n"
        "## 产物状态\n"
        f"- 参考简报：{'已有' if state.reference_brief.strip() else '暂无'}\n"
        f"- 世界观：{'已有' if state.worldbuilding.strip() else '暂无'}\n"
        f"- 总大纲：{'已有' if state.outline.strip() else '暂无'}\n"
        f"- 章节细纲：{'已有' if state.chapter_plan.strip() else '暂无'}\n"
        f"- 章节卡：{'已有' if state.current_chapter_card.strip() else '暂无'}\n"
        f"- 场景卡：{'已有' if state.current_scene_cards.strip() else '暂无'}\n"
        f"- 章节正文：{'已有' if state.chapter_draft.strip() else '暂无'}\n"
        f"- 定稿章节：{'已有' if state.current_final_chapter.strip() else '暂无'}\n"
        f"- 编辑意见：{'已有' if state.editor_notes.strip() else '暂无'}\n"
        f"- 小说圣经：{'已有' if store.novel_bible_markdown_path(state.project_id).exists() else '暂无'}\n\n"
        "## 待确认事项\n"
        f"{pending}\n\n"
        "## 建议下一步\n"
        f"{next_steps}\n"
    )
    store.save_project_context(state.project_id, content)


def format_pending_context(state: NovelState) -> str:
    if state.pending_question.strip():
        return f"- {state.pending_question.strip()}"
    items = [item.strip() for item in state.pending_questions if item.strip()]
    return "\n".join(f"- {item}" for item in items[:6]) or "- 暂无"


def format_current_stage_context(state: NovelState, max_chars: int = 700) -> str:
    stage = state.outline_stage
    if not stage or stage == "done":
        return "- 阶段：已锁定最终大纲" if stage == "done" else "- 暂无"
    artifact = state.outline_stage_artifacts.get(stage, {})
    label = artifact.get("label") or stage
    status = artifact.get("status") or state.outline_stage_status or "unknown"
    synthesis = str(artifact.get("synthesis", "")).strip()
    lines = [f"- 阶段：{label} ({stage})", f"- 状态：{status}"]
    if synthesis:
        excerpt = synthesis[:max_chars].rstrip() + ("\n..." if len(synthesis) > max_chars else "")
        lines.append("- 当前控制稿/阶段摘要：")
        lines.append(excerpt)
    else:
        lines.append("- 当前控制稿/阶段摘要：暂无")
    return "\n".join(lines)


def default_next_steps(state: NovelState) -> str:
    if state.active_workflow == "outline" and state.outline_stage and state.outline_stage != "done":
        label = state.outline_stage_artifacts.get(state.outline_stage, {}).get("label") or state.outline_stage
        return (
            f"- 继续提出{label}修改意见，系统会合并成新版阶段产物。\n"
            "- 如果认可当前阶段，回复“确认进入下一阶段”。"
        )
    if state.reference_brief.strip() and not state.outline.strip():
        return "- 请用户确认参考事实后生成创作方向或大纲。"
    if state.outline.strip() and not state.chapter_plan.strip():
        return "- 生成章节细纲。"
    if state.chapter_plan.strip() and not state.chapter_draft.strip():
        return f"- 写第 {state.current_chapter} 章。"
    if state.chapter_draft.strip() and state.editor_decision != "pass":
        return f"- 审稿第 {state.current_chapter} 章。"
    if state.editor_decision == "pass" and not state.current_final_chapter.strip():
        return f"- 定稿第 {state.current_chapter} 章。"
    if state.current_final_chapter.strip():
        return "- 导出小说。"
    return "- 等待用户指定下一步。"


def artifact_paths(state: NovelState, store: LocalStore) -> list[str]:
    paths = []
    candidates = [
        (state.reference_brief, store.reference_brief_path(state.project_id)),
        (state.worldbuilding, store.worldbuilding_path(state.project_id)),
        (state.outline, store.outline_path(state.project_id)),
        (state.chapter_plan, store.chapter_plan_path(state.project_id)),
        (state.current_chapter_card, store.chapter_card_path(state.project_id, state.active_chapter or state.current_chapter)),
        (state.current_scene_cards, store.scene_cards_path(state.project_id, state.active_chapter or state.current_chapter)),
        (state.chapter_draft, store.chapter_path(state.project_id, state.current_chapter)),
        (state.current_final_chapter, store.final_chapter_path(state.project_id, state.active_chapter or state.current_chapter)),
        (state.chapter_summaries.get(str(state.active_chapter or state.current_chapter), ""), store.chapter_summary_path(state.project_id, state.active_chapter or state.current_chapter)),
        (state.editor_notes, store.editor_notes_path(state.project_id, state.current_chapter)),
    ]
    for content, path in candidates:
        if content.strip() and path.exists():
            paths.append(str(path))

    bible_path = store.novel_bible_markdown_path(state.project_id)
    if bible_path.exists():
        paths.append(str(bible_path))
    for export_path in (store.manuscript_export_path(state.project_id), store.volume_export_path(state.project_id), store.bible_export_path(state.project_id)):
        if export_path.exists():
            paths.append(str(export_path))
    context_path = store.project_context_path(state.project_id)
    if context_path.exists():
        paths.append(str(context_path))
    return paths


def show_bible_state(state: NovelState, store: LocalStore) -> NovelState:
    path = store.novel_bible_markdown_path(state.project_id)
    state.director_action = "show_bible"
    state.active_artifact = "novel_bible"
    if not path.exists():
        state.director_message = "当前还没有小说圣经。请先锁定大纲，或输入“更新小说圣经”进行初始化。"
    else:
        content = path.read_text(encoding="utf-8").strip()
        if len(content) > 3200:
            content = content[:3200].rstrip() + "\n...\n（已截断，完整内容见 novel_bible.md）"
        state.director_message = "当前小说圣经：\n" + content
    append_message(state, "assistant", state.director_message)
    store.save_state(state)
    return state


def confirmation_message(decision: DirectorDecision) -> str:
    return decision.user_message or f"我准备执行：{decision.action}。"


def confirmation_choices() -> list[DirectorChoice]:
    return [
        DirectorChoice(id="confirm", label="确认执行", value="1"),
        DirectorChoice(id="cancel", label="取消", value="2"),
    ]


def should_prompt_for_confirmation(decision: DirectorDecision, state: NovelState) -> bool:
    if not decision.requires_confirmation or decision.action in DIRECT_ACTIONS:
        return False
    if state.active_workflow == "outline" and state.outline_stage != "done" and decision.action in OUTLINE_STAGE_EDIT_ACTIONS:
        return False
    return True


OUTLINE_STAGE_EDIT_ACTIONS = {
    "propose_directions",
    "worldbuild",
    "generate_outline",
    "review_outline",
    "revise_outline",
    "compare_versions",
}


def should_execute_pending_decision(text: str) -> bool:
    return not is_rejection(text)


def merged_pending_user_request(pending: DirectorDecision, text: str, fallback: str) -> str:
    original = str(pending.task_args.get("original_user_text") or fallback or text).strip()
    if is_confirmation(text):
        return original
    reply = text.strip()
    if not reply or reply in original:
        return original
    return f"{original}\n补充确认：{reply}"


def is_confirmation(text: str) -> bool:
    return text.strip().lower() in {"1", "y", "yes", "ok", "okay", "confirm", "approve", "确认", "可以", "继续", "执行", "是", "接受", "接收", "同意", "认可"}


def is_rejection(text: str) -> bool:
    return text.strip().lower() in {"2", "n", "no", "cancel", "取消", "不用", "否", "停止"}


def normalize_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1", "确认", "是"}:
            return True
        if lowered in {"false", "no", "n", "0", "否"}:
            return False
    return bool(value)


def normalize_chapter(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return max(1, int(value))
    except (TypeError, ValueError):
        return None


def normalize_confidence(value: Any) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def normalize_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def first_text(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(data.get(key, "")).strip()
        if value:
            return value
    return ""


def looks_like_story_idea(text: str) -> bool:
    markers = ("想写", "小说", "故事", "主角", "世界", "城市", "科幻", "悬疑", "奇幻")
    return any(marker in text for marker in markers)
