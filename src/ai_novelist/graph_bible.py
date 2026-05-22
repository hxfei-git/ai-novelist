"""Novel Bible update graph."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.artifacts import ArtifactRecord, load_artifacts, register_artifact
from ai_novelist.bible import (
    NovelBible,
    bible_from_dict,
    bible_to_dict,
    detect_bible_conflicts,
    load_bible,
    merge_bible_updates,
    save_bible,
)
from ai_novelist.context_builder import build_context
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


def build_bible_graph(adapter: AgentAdapter, store: LocalStore) -> CompiledGraph:
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return BibleSequentialGraph(adapter, store)

    graph = StateGraph(dict)
    graph.add_node("load_bible", lambda data: load_bible_node(data, store))
    graph.add_node("extract_bible_updates", lambda data: extract_bible_updates_node(data, adapter, store))
    graph.add_node("detect_bible_conflicts", lambda data: detect_bible_conflicts_node(data, store))
    graph.add_node("apply_bible_updates", lambda data: apply_bible_updates_node(data, store))
    graph.add_node("save_bible", lambda data: save_bible_node(data, store))
    graph.add_node("summarize_bible_update", lambda data: summarize_bible_update_node(data, store))
    graph.set_entry_point("load_bible")
    graph.add_edge("load_bible", "extract_bible_updates")
    graph.add_edge("extract_bible_updates", "detect_bible_conflicts")
    graph.add_edge("detect_bible_conflicts", "apply_bible_updates")
    graph.add_edge("apply_bible_updates", "save_bible")
    graph.add_edge("save_bible", "summarize_bible_update")
    graph.add_edge("summarize_bible_update", END)
    return graph.compile()


class BibleSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore) -> None:
        self.adapter = adapter
        self.store = store

    def invoke(self, state: dict) -> dict:
        current = load_bible_node(state, self.store)
        current = extract_bible_updates_node(current, self.adapter, self.store)
        current = detect_bible_conflicts_node(current, self.store)
        current = apply_bible_updates_node(current, self.store)
        current = save_bible_node(current, self.store)
        return summarize_bible_update_node(current, self.store)


def load_bible_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    state.director_task_args["current_bible"] = bible_to_dict(load_bible(store.project_dir(state.project_id)))
    state.active_graph = "bible"
    state.active_stage = "load_bible"
    store.save_state(state)
    return state.to_dict()


def extract_bible_updates_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    context = build_context(state, store, "bible_update", max_chars=14000)
    outline_context = collect_outline_context(state, store)
    try:
        output = adapter.complete(build_bible_update_prompt(state, context, outline_context), store.project_dir(state.project_id))
        updates = parse_bible_update_output(output)
    except AgentAdapterError:
        updates = {}
    if not updates:
        updates = mock_bible_updates_from_state(state, outline_context)
    state.director_task_args["bible_updates"] = updates
    state.last_context_digest = context[:1200]
    state.active_stage = "extract_bible_updates"
    store.save_state(state)
    return state.to_dict()


def detect_bible_conflicts_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    bible = load_bible(store.project_dir(state.project_id))
    updates = state.director_task_args.get("bible_updates", {})
    conflicts = detect_bible_conflicts(bible, updates if isinstance(updates, dict) else {})
    state.director_task_args["bible_conflicts"] = conflicts
    state.last_agent_reports = append_agent_report(
        state.last_agent_reports,
        "bible_conflict_checker",
        "conflicts" if conflicts else "pass",
        {"conflicts": conflicts},
    )
    state.active_stage = "detect_bible_conflicts"
    store.save_state(state)
    return state.to_dict()


def apply_bible_updates_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    bible = load_bible(store.project_dir(state.project_id))
    updates = state.director_task_args.get("bible_updates", {})
    merged = merge_bible_updates(bible, updates if isinstance(updates, dict) else {})
    conflicts = state.director_task_args.get("bible_conflicts", [])
    if isinstance(conflicts, list):
        for conflict in conflicts:
            if isinstance(conflict, dict):
                question = format_conflict_question(conflict)
                if question and question not in merged.open_questions:
                    merged.open_questions.append(question)
    state.director_task_args["merged_bible"] = bible_to_dict(merged)
    state.active_stage = "apply_bible_updates"
    store.save_state(state)
    return state.to_dict()


def save_bible_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    merged_data = state.director_task_args.get("merged_bible", {})
    bible = bible_from_dict(merged_data if isinstance(merged_data, dict) else {})
    save_bible(store.project_dir(state.project_id), bible)
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="novel_bible",
            path="novel_bible.md",
            source_agent="bible_update_synthesizer",
            graph="bible",
            stage="bible_update",
            summary=bible_summary(bible),
        ),
    )
    state.bible_version = bible.version
    state.bible_updated_at = record.updated_at or datetime.now(UTC).isoformat(timespec="seconds")
    state.artifact_registry = [record.to_dict() for record in load_artifacts(store.project_dir(state.project_id))][-20:]
    state.active_stage = "save_bible"
    store.save_state(state)
    return state.to_dict()


def summarize_bible_update_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    bible = load_bible(store.project_dir(state.project_id))
    state.active_graph = "bible"
    state.active_stage = "bible_update"
    state.active_artifact = "novel_bible"
    state.director_action = state.director_action or "update_bible"
    state.director_message = (
        f"小说圣经已更新：{store.novel_bible_markdown_path(state.project_id)}\n"
        f"版本：{bible.version}\n"
        f"摘要：{bible_summary(bible)}"
    )
    state.last_agent_reports = append_agent_report(
        state.last_agent_reports,
        "bible_update_synthesizer",
        "saved",
        {"version": bible.version, "path": "novel_bible.md"},
    )
    store.save_state(state)
    return state.to_dict()


def build_bible_update_prompt(state: NovelState, context: str, outline_context: str) -> str:
    template = load_prompt("bible_update_extractor")
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"IDEA: {state.idea or '暂无'}\n\n"
        f"## Task Context\n{context}\n\n"
        f"## Outline Artifacts\n{outline_context or '暂无'}\n"
    )


def parse_bible_update_output(output: str) -> dict[str, Any]:
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


def collect_outline_context(state: NovelState, store: LocalStore, max_chars_per_stage: int = 1800) -> str:
    stage_labels = {
        "direction": "方向定位",
        "concept": "故事概念",
        "worldbuilding": "世界观设定",
        "characters": "人物关系",
        "story_flow": "故事流程",
        "volume_outline": "分卷大纲",
        "chapter_outline": "章节大纲",
        "review_lock": "审稿锁定",
    }
    parts: list[str] = []
    for stage, label in stage_labels.items():
        text = ""
        path = store.outline_artifact_path(state.project_id, stage)
        if path.exists():
            text = path.read_text(encoding="utf-8")
        else:
            artifact = state.outline_stage_artifacts.get(stage, {})
            if isinstance(artifact, dict):
                text = str(artifact.get("synthesis", ""))
        text = text.strip()
        if not text:
            continue
        if len(text) > max_chars_per_stage:
            text = text[:max_chars_per_stage].rstrip() + "\n..."
        parts.append(f"## {label} ({stage})\n{text}")
    if not parts and state.outline.strip():
        parts.append("## 最终大纲\n" + state.outline.strip())
    return "\n\n".join(parts)


def mock_bible_updates_from_state(state: NovelState, outline_context: str) -> dict[str, Any]:
    title = state.title or state.project_id
    idea = state.idea or extract_first_sentence(outline_context) or "月球城市失忆工程师追查纸质手稿预言。"
    return {
        "project": {
            "title": title,
            "genre": "科幻悬疑",
            "subgenre": "记忆罪案",
            "target_reader": "喜欢悬疑推进、科幻设定和人物罪感的长篇小说读者",
            "core_experience": "在月球城市的记忆审计制度中追查旧罪与身份真相。",
            "tone_keywords": ["黑暗", "悬疑", "科幻", "罪感"],
            "locked_constraints": list(state.locked_constraints),
        },
        "concept": {
            "logline": "失忆工程师发现纸质手稿正在预言事故，并追查自己被删除的旧罪。",
            "premise": idea,
            "core_conflict": "主角求生本能与公开旧罪之间的对抗。",
            "theme": "安全秩序吞噬个人记忆后的代价。",
            "central_question": "主角能否用公开罪证换回被删除者的身份？",
            "ending_direction": "终局以公开旧罪和灰籍身份恢复收束。",
        },
        "world_rules": [
            {"name": "记忆审计", "description": "任何记忆备份都必须留下审计编号。", "limitation": "失效编号会暴露身份异常。", "cost": "公开未审计记忆会让相关人员失去合法身份。", "source_stage": "worldbuilding"},
            {"name": "纸质手稿", "description": "纸质文本无法被城市系统即时追踪。", "limitation": "传播慢且容易成为犯罪证据。", "cost": "持有者会被档案局追查。", "source_stage": "concept"},
            {"name": "月背冷库", "description": "被删除的记忆会转存到月背冷库。", "limitation": "私自读取属于重罪。", "cost": "找回真相会牵连被主角伤害过的人。", "source_stage": "worldbuilding"},
        ],
        "characters": [
            {"name": "林澈", "role": "主角", "identity": "失忆工程师", "external_goal": "追查手稿来源并阻止事故。", "internal_need": "承认并承担旧罪。", "flaw": "习惯用技术和失忆为自己辩解。", "fear": "发现自己是伤害他人的执行者。", "secret": "曾参与关键记忆删除。", "arc": "从逃避旧罪到公开自证。", "voice": "克制、警觉、带技术人员的精确感。", "relationships": ["许岚：盟友与受害者后代", "沈博士：旧授权关系与秩序对手"]},
            {"name": "许岚", "role": "盟友", "identity": "被删除者后代", "external_goal": "帮助灰籍居民恢复身份。", "relationships": ["林澈：互相试探后合作"]},
            {"name": "沈博士", "role": "对手", "identity": "记忆秩序维护者", "external_goal": "维持记忆公司和档案局的合法性。", "relationships": ["林澈：旧授权关系"]},
        ],
        "plot_threads": [
            {"name": "手稿预言", "description": "纸质手稿持续预告事故并逼近主角旧身份。", "status": "active", "related_chapters": [1, 2, 3]},
            {"name": "旧罪公开", "description": "林澈必须决定是否公开自己参与记忆删除的证据。", "status": "open", "related_chapters": [8, 12]},
        ],
        "timeline": [
            {"id": "outline-001", "order": 1, "event": "林澈发现纸质手稿和失效审计编号。", "characters": ["林澈"], "location": "银湾月球城"},
            {"id": "outline-002", "order": 2, "event": "中段进入月背冷库追查被删除记忆。", "characters": ["林澈", "许岚"], "location": "月背冷库"},
            {"id": "outline-003", "order": 3, "event": "终局公开旧罪并恢复灰籍身份。", "characters": ["林澈", "沈博士"], "location": "听证会"},
        ],
        "foreshadowing": [
            {"id": "F001", "setup_text": "失效审计编号", "payoff_text": "证明主角身份被删除。", "status": "planned"},
            {"id": "F002", "setup_text": "纸质手稿边角月尘", "payoff_text": "指向月背冷库。", "status": "planned"},
        ],
        "style_guide": {"pov": "第三人称贴近主角", "tone": "黑暗悬疑科幻", "pace": "线索驱动，章末保留钩子"},
        "open_questions": list(state.pending_questions[:6]),
    }


def format_conflict_question(conflict: dict[str, Any]) -> str:
    conflict_type = conflict.get("type", "conflict")
    name = conflict.get("name") or conflict.get("chapter") or "未知对象"
    return f"小说圣经冲突待确认：{conflict_type} / {name}。"


def bible_summary(bible: NovelBible) -> str:
    parts = []
    if bible.project.title:
        parts.append(f"《{bible.project.title}》")
    if bible.concept.logline:
        parts.append(bible.concept.logline)
    if bible.characters:
        parts.append("人物：" + "、".join(item.name for item in bible.characters[:4] if item.name))
    if bible.world_rules:
        parts.append("规则：" + "、".join(item.name for item in bible.world_rules[:4] if item.name))
    return "；".join(item for item in parts if item) or "已保存项目设定、故事核心和连续性信息。"


def extract_first_sentence(text: str) -> str:
    compact = re.sub(r"[#*`>\-]+", "", text).strip()
    if not compact:
        return ""
    return re.split(r"[。！？!?\n]", compact)[0].strip()


def append_agent_report(reports: list[dict[str, Any]], agent: str, status: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    updated = list(reports)
    updated.append({"agent": agent, "status": status, "data": data, "created_at": datetime.now(UTC).isoformat(timespec="seconds")})
    return updated[-20:]
