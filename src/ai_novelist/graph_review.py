"""Review graph for multi-editor chapter assessment."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.artifacts import ArtifactRecord, get_latest_artifact, load_artifact_text, load_artifacts, register_artifact
from ai_novelist.context_builder import build_context
from ai_novelist.graph_writer import parse_editor_review
from ai_novelist.prompts import load_prompt
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class CompiledGraph(Protocol):
    def invoke(self, state: dict) -> dict:
        """Invoke the graph with a dict state."""


REVIEW_FIELDS = ("decision", "score", "blocking_issues", "issues", "rewrite_tasks")


class ReviewSequentialGraph:
    def __init__(self, adapter: AgentAdapter, store: LocalStore) -> None:
        self.adapter = adapter
        self.store = store

    def invoke(self, state: dict) -> dict:
        current = load_review_context_node(state, self.store)
        if NovelState.from_dict(current).review_status == "error":
            return current
        for prompt_name, field in [
            ("continuity_editor", "continuity_review"),
            ("structure_editor", "structure_review"),
            ("character_arc_editor", "character_arc_review"),
            ("style_editor", "style_review"),
            ("simulated_reader", "simulated_reader_review"),
        ]:
            current = run_review_agent(current, self.adapter, self.store, prompt_name, field)
            if NovelState.from_dict(current).review_status == "error":
                return current
        current = review_synthesizer_node(current, self.adapter, self.store)
        current = decide_pass_or_revise_node(current, self.store)
        current = save_review_report_node(current, self.store)
        return current


def build_review_graph(adapter: AgentAdapter, store: LocalStore) -> CompiledGraph:
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return ReviewSequentialGraph(adapter, store)

    graph = StateGraph(dict)
    graph.add_node("load_review_context", lambda data: load_review_context_node(data, store))
    graph.add_node("continuity_review_agent", lambda data: run_review_agent(data, adapter, store, "continuity_editor", "continuity_review"))
    graph.add_node("structure_review_agent", lambda data: run_review_agent(data, adapter, store, "structure_editor", "structure_review"))
    graph.add_node("character_arc_review_agent", lambda data: run_review_agent(data, adapter, store, "character_arc_editor", "character_arc_review"))
    graph.add_node("style_review_agent", lambda data: run_review_agent(data, adapter, store, "style_editor", "style_review"))
    graph.add_node("simulated_reader_agent", lambda data: run_review_agent(data, adapter, store, "simulated_reader", "simulated_reader_review"))
    graph.add_node("review_synthesizer", lambda data: review_synthesizer_node(data, adapter, store))
    graph.add_node("decide_pass_or_revise", lambda data: decide_pass_or_revise_node(data, store))
    graph.add_node("save_review_report", lambda data: save_review_report_node(data, store))
    graph.set_entry_point("load_review_context")
    graph.add_conditional_edges("load_review_context", route_after_load, {"continue": "continuity_review_agent", "end": END})
    graph.add_edge("continuity_review_agent", "structure_review_agent")
    graph.add_edge("structure_review_agent", "character_arc_review_agent")
    graph.add_edge("character_arc_review_agent", "style_review_agent")
    graph.add_edge("style_review_agent", "simulated_reader_agent")
    graph.add_edge("simulated_reader_agent", "review_synthesizer")
    graph.add_edge("review_synthesizer", "decide_pass_or_revise")
    graph.add_edge("decide_pass_or_revise", "save_review_report")
    graph.add_edge("save_review_report", END)
    return graph.compile()


def route_after_load(data: dict) -> str:
    return "end" if data.get("review_status") == "error" else "continue"


def load_review_context_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    chapter = int(state.director_task_args.get("chapter") or state.current_chapter or state.active_chapter or 1)
    state.active_chapter = max(1, chapter)
    state.current_chapter = state.active_chapter
    state.active_graph = "review"
    state.active_stage = "load_review_context"
    state.active_artifact = "review_report"
    draft = load_current_draft(state, store)
    if not draft.strip():
        state.review_status = "error"
        state.error = f"缺少第 {state.active_chapter} 章草稿，无法审稿。"
        state.director_message = state.error
        store.save_state(state)
        return state.to_dict()
    state.chapter_draft = draft
    context = build_context(state, store, "review", chapter=state.active_chapter, max_chars=18000)
    state.director_task_args["review_context"] = context
    state.last_context_digest = context[:1200]
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)
    return state.to_dict()


def run_review_agent(data: dict, adapter: AgentAdapter, store: LocalStore, prompt_name: str, field: str) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_review_prompt(state, prompt_name)
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


def review_synthesizer_node(data: dict, adapter: AgentAdapter, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    prompt = build_review_prompt(state, "review_synthesizer")
    try:
        output = adapter.complete(prompt, store.project_dir(state.project_id))
    except AgentAdapterError as exc:
        state.error = str(exc)
        state.review_status = "error"
        store.save_state(state)
        return state.to_dict()
    report = normalize_review_report(parse_review_json(output), output)
    state.director_task_args["review_json"] = report
    state.current_review_report = render_review_markdown(report)
    state.editor_notes = legacy_editor_notes(report, state.current_review_report)
    state.active_stage = "review_synthesizer"
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "review_synthesizer", "ok", {"decision": report["decision"], "score": report["score"]})
    store.save_state(state)
    return state.to_dict()


def decide_pass_or_revise_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    report = normalize_review_report(state.director_task_args.get("review_json", {}), state.current_review_report)
    decision = str(report["decision"])
    score = int(report["score"])
    state.editor_decision = decision if decision in {"pass", "revise", "stop"} else "revise"  # type: ignore[assignment]
    state.quality_score = max(0, min(score, 100))
    if state.editor_decision == "pass":
        state.review_status = "draft"
        state.next_action = "human_review"
    elif state.editor_decision == "revise" and state.revision_count < state.max_revisions:
        state.review_status = "revision_requested"
        state.next_action = "rewrite_chapter"
    else:
        state.review_status = "stopped"
        state.next_action = "stop"
    state.active_stage = "decide_pass_or_revise"
    store.save_state(state)
    return state.to_dict()


def save_review_report_node(data: dict, store: LocalStore) -> dict:
    state = NovelState.from_dict(data)
    report = normalize_review_report(state.director_task_args.get("review_json", {}), state.current_review_report)
    path = store.save_review_report(state, version=1)
    json_path = store.review_json_path(state.project_id, state.active_chapter, 1)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    legacy = store.save_editor_notes(state)
    record = register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="review_report",
            path=path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="review_synthesizer",
            graph="review",
            stage="review",
            chapter=state.active_chapter,
            summary=f"{report['decision']} / {report['score']}",
            metadata={"json_path": json_path.relative_to(store.project_dir(state.project_id)).as_posix(), "legacy_path": legacy.relative_to(store.project_dir(state.project_id)).as_posix()},
        ),
    )
    state.active_graph = "review"
    state.active_stage = "review"
    state.active_artifact = "review_report"
    state.director_action = normalize_review_action(state.director_action)
    state.director_message = f"第 {state.active_chapter} 章审稿完成：{state.editor_decision}，质量分 {state.quality_score}。报告：{path}"
    state.artifact_registry = [item.to_dict() for item in load_artifacts(store.project_dir(state.project_id))][-20:]
    state.last_agent_reports = append_agent_report(state.last_agent_reports, "review_synthesizer", "saved", {"artifact_id": record.id, "path": record.path})
    store.save_state(state)
    return state.to_dict()


def build_review_prompt(state: NovelState, prompt_name: str) -> str:
    template = load_prompt(prompt_name)
    reports = format_review_reports(state)
    return (
        f"{template.rstrip()}\n\n"
        f"PROJECT_ID: {state.project_id}\n"
        f"TITLE: {state.title}\n"
        f"CHAPTER: {state.active_chapter or state.current_chapter}\n"
        f"REVISION_COUNT: {state.revision_count}\n\n"
        f"## Review Context\n{state.director_task_args.get('review_context') or '暂无'}\n\n"
        f"## Chapter Draft\n{state.chapter_draft or '暂无'}\n\n"
        f"## Editor Reports\n{reports or '暂无'}\n"
    )


def format_review_reports(state: NovelState) -> str:
    fields = [
        ("continuity_review", "连续性审稿"),
        ("structure_review", "结构审稿"),
        ("character_arc_review", "人物弧光审稿"),
        ("style_review", "风格审稿"),
        ("simulated_reader_review", "模拟读者反馈"),
    ]
    parts = []
    for key, label in fields:
        value = str(state.director_task_args.get(key, "")).strip()
        if value:
            parts.append(f"### {label}\n{value}")
    return "\n\n".join(parts)


def load_current_draft(state: NovelState, store: LocalStore) -> str:
    path = store.chapter_draft_path(state.project_id, state.active_chapter, 2 if state.revision_count else 1)
    if path.exists():
        return path.read_text(encoding="utf-8")
    latest = get_latest_artifact(store.project_dir(state.project_id), "chapter_draft", chapter=state.active_chapter)
    if latest:
        return load_artifact_text(store.project_dir(state.project_id), latest)
    legacy = store.chapter_path(state.project_id, state.active_chapter)
    if legacy.exists():
        return legacy.read_text(encoding="utf-8")
    return state.chapter_draft if state.current_chapter == state.active_chapter else ""


def parse_review_json(output: str) -> dict[str, Any]:
    text = output.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            decision, score = parse_editor_review(output)
            return {"decision": decision, "score": score, "blocking_issues": [], "issues": [], "rewrite_tasks": []}
        value = json.loads(text[start : end + 1])
    return value if isinstance(value, dict) else {}


def normalize_review_report(raw: Any, fallback_text: str) -> dict[str, Any]:
    data = dict(raw) if isinstance(raw, dict) else {}
    decision = str(data.get("decision") or data.get("status") or "revise").strip().lower()
    if decision not in {"pass", "revise", "stop"}:
        decision = "revise"
    try:
        score = int(data.get("score") or data.get("quality_score") or 0)
    except (TypeError, ValueError):
        score = 0
    issues = normalize_list(data.get("issues"))
    blocking = normalize_list(data.get("blocking_issues"))
    tasks = normalize_list(data.get("rewrite_tasks"))
    if not issues and fallback_text.strip():
        issues = extract_bullets(fallback_text)[:5]
    return {
        "decision": decision,
        "score": max(0, min(score, 100)),
        "blocking_issues": blocking,
        "issues": issues,
        "rewrite_tasks": tasks,
    }


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def extract_bullets(text: str) -> list[str]:
    return [re.sub(r"^[-*+\d.、\s]+", "", line).strip() for line in text.splitlines() if line.strip().startswith(("-", "*"))]


def render_review_markdown(report: dict[str, Any]) -> str:
    return (
        "# 章节审稿报告\n\n"
        f"STATUS: {report['decision']}\n"
        f"QUALITY_SCORE: {report['score']}\n\n"
        "## 阻塞问题\n"
        f"{format_list(report['blocking_issues'])}\n\n"
        "## 主要问题\n"
        f"{format_list(report['issues'])}\n\n"
        "## 定向改写任务\n"
        f"{format_list(report['rewrite_tasks'])}\n"
    )


def legacy_editor_notes(report: dict[str, Any], markdown: str) -> str:
    return f"STATUS: {report['decision']}\nQUALITY_SCORE: {report['score']}\n\n{markdown}".strip() + "\n"


def format_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- 暂无"


def normalize_review_action(action: str) -> str:
    return "review_chapter" if action in {"", "review", "review_chapter"} else action


def append_agent_report(reports: list[dict], agent: str, status: str, data: dict) -> list[dict]:
    updated = list(reports)
    updated.append({"agent": agent, "status": status, **data})
    return updated[-20:]
