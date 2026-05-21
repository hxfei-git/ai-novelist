"""Director service shared by CLI and future chat channels."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any, Literal

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
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
    "write_chapter",
    "review",
    "revise_chapter",
    "persist_outputs",
}
DIRECT_ACTIONS = {"ask_user", "show_status", "show_outline", "show_reference", "stop"}


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
        if pending and is_confirmation(text):
            state.pending_director_decision = {}
            state.user_request = str(pending.task_args.get("original_user_text") or state.user_request or text)
            append_message(state, "user", text)
            self.store.save_state(state)
            return self._execute_decision(state, pending, channel)
        if pending and is_rejection(text):
            state.pending_director_decision = {}
            state.director_message = "已取消上一步计划。你可以重新说明想做什么。"
            append_message(state, "user", text)
            append_message(state, "assistant", state.director_message)
            self.store.save_state(state)
            return DirectorTurnResult(final_message=state.director_message, requires_followup=True, state=state)

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

        if decision.requires_confirmation and decision.action not in DIRECT_ACTIONS:
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
        prompt = build_service_director_prompt(state, self.store, channel)
        try:
            output = self.adapter.complete(prompt, self.store.project_dir(state.project_id))
        except AgentAdapterError:
            return fallback_decision(state)
        return parse_service_director_output(output, state)

    def _execute_decision(self, state: NovelState, decision: DirectorDecision, channel: Channel) -> DirectorTurnResult:
        self._apply_decision_metadata(state, decision)
        state.director_task_args = decision.task_args
        state.pending_director_decision = {}
        self.store.save_state(state)

        if decision.action == "research":
            result_state = self._run_research(state)
        elif decision.action == "persist_outputs":
            result_state = NovelState.from_dict(persist_available_outputs(state.to_dict(), self.store))
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
            result_state = NovelState.from_dict(run_selected_agent(state.to_dict(), self.adapter, self.store, self.progress))

        update_project_context(result_state, self.store, decision)
        return DirectorTurnResult(
            started_task=decision.action if decision.action not in DIRECT_ACTIONS else "",
            final_message=result_state.director_message,
            artifact_paths=artifact_paths(result_state, self.store),
            requires_followup=result_state.director_action != "stop",
            state=result_state,
            decision=decision,
        )

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


def load_or_create_project(store: LocalStore, project_id: str) -> NovelState:
    try:
        return store.load_state(project_id)
    except LocalStoreError:
        return store.create_project(project_id, project_id)


def build_service_director_prompt(state: NovelState, store: LocalStore, channel: Channel) -> str:
    template = load_prompt("director")
    history = "\n".join(f"{msg['role']}: {msg['content']}" for msg in state.messages[-12:])
    project_context = store.load_project_context(state.project_id)
    return (
        f"{template.rstrip()}\n\n"
        "## 输出格式\n"
        "优先输出一个 JSON 对象，不要包裹 Markdown 代码块。字段：action, requires_confirmation, confidence, user_message, task_args, next_steps。\n"
        "task_args 可包含 research_query, work_title, author, chapter, instruction。\n"
        "如果无法输出 JSON，才使用旧的 ACTION/MESSAGE 字段格式。\n\n"
        "## 当前通道\n"
        f"{channel}\n\n"
        "## project_context.md\n"
        f"{project_context.strip() or '暂无'}\n\n"
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
        f"待确认决策：{'有' if state.pending_director_decision else '无'}\n\n"
        f"## 已获取参考信息摘要\n{build_reference_summary(state, max_chars=1200) if state.reference_brief or state.retrieval_context or state.research_sources else '暂无'}\n\n"
        f"## 最近对话\n{history or '暂无'}\n\n"
        f"最新用户输入：{state.user_request}\n"
    )


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
    return decision


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


def fallback_decision(state: NovelState) -> DirectorDecision:
    text = state.user_request
    if any(marker in text for marker in ("查看状态", "项目状态", "显示状态")) or text.lower() in {"status", "show status"}:
        return DirectorDecision("show_status", user_message="我会展示当前项目状态。", confidence=60)
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
    if decision.action in {"write_chapter", "review", "revise_chapter"} and not decision.task_args.get("chapter"):
        decision.task_args["chapter"] = state.current_chapter


def update_project_context(state: NovelState, store: LocalStore, decision: DirectorDecision) -> None:
    facts = "\n".join(f"- {item}" for item in state.canon_facts[:8]) or "- 暂无"
    uncertainties = "\n".join(f"- {item}" for item in state.research_uncertainties[:6]) or "- 暂无"
    pending = "\n".join(f"- {item}" for item in state.pending_questions[:6]) or "- 暂无"
    next_steps = "\n".join(f"- {item}" for item in decision.next_steps[:6]) or default_next_steps(state)
    content = (
        f"# Project Context: {state.project_id}\n\n"
        "## 项目目标\n"
        f"- 标题：{state.title}\n"
        f"- 创意：{state.idea or '暂无'}\n"
        f"- 当前章节：{state.current_chapter}\n\n"
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
        f"- 章节正文：{'已有' if state.chapter_draft.strip() else '暂无'}\n"
        f"- 编辑意见：{'已有' if state.editor_notes.strip() else '暂无'}\n\n"
        "## 待确认事项\n"
        f"{pending}\n\n"
        "## 建议下一步\n"
        f"{next_steps}\n"
    )
    store.save_project_context(state.project_id, content)


def default_next_steps(state: NovelState) -> str:
    if state.reference_brief.strip() and not state.outline.strip():
        return "- 请用户确认参考事实后生成创作方向或大纲。"
    if state.outline.strip() and not state.chapter_plan.strip():
        return "- 生成章节细纲。"
    if state.chapter_plan.strip() and not state.chapter_draft.strip():
        return f"- 写第 {state.current_chapter} 章。"
    return "- 等待用户指定下一步。"


def artifact_paths(state: NovelState, store: LocalStore) -> list[str]:
    paths = []
    candidates = [
        (state.reference_brief, store.reference_brief_path(state.project_id)),
        (state.worldbuilding, store.worldbuilding_path(state.project_id)),
        (state.outline, store.outline_path(state.project_id)),
        (state.chapter_plan, store.chapter_plan_path(state.project_id)),
        (state.chapter_draft, store.chapter_path(state.project_id, state.current_chapter)),
        (state.editor_notes, store.editor_notes_path(state.project_id, state.current_chapter)),
    ]
    for content, path in candidates:
        if content.strip() and path.exists():
            paths.append(str(path))
    context_path = store.project_context_path(state.project_id)
    if context_path.exists():
        paths.append(str(context_path))
    return paths


def confirmation_message(decision: DirectorDecision) -> str:
    return decision.user_message or f"我准备执行：{decision.action}。"


def confirmation_choices() -> list[DirectorChoice]:
    return [
        DirectorChoice(id="confirm", label="确认执行", value="1"),
        DirectorChoice(id="cancel", label="取消", value="2"),
    ]


def is_confirmation(text: str) -> bool:
    return text.strip().lower() in {"1", "y", "yes", "ok", "okay", "confirm", "approve", "确认", "可以", "继续", "执行", "是"}


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
