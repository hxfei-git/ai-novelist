import json

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_drafting import build_drafting_graph
from ai_novelist.graph_review import build_review_graph, build_review_prompt, load_review_context_node
from ai_novelist.graph_writer import build_writer_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def prepared_draft(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    state.current_chapter = 1
    state = NovelState.from_dict(build_drafting_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))
    return store, state


def test_review_generates_markdown_json_and_legacy_notes(tmp_path):
    store, state = prepared_draft(tmp_path)

    result = NovelState.from_dict(build_review_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))

    assert store.review_report_path("demo", 1, 1).exists()
    assert store.review_json_path("demo", 1, 1).exists()
    payload = json.loads(store.review_json_path("demo", 1, 1).read_text(encoding="utf-8"))
    assert {"decision", "score", "blocking_issues", "issues", "rewrite_tasks", "do_not_change"}.issubset(set(payload))
    assert {"blocking_fixes", "pacing_safe_fixes", "backlog_suggestions", "rejected_suggestions"}.issubset(set(payload))
    assert payload["decision"] in {"pass", "revise"}
    assert "STATUS:" in result.editor_notes
    assert "QUALITY_SCORE:" in result.editor_notes
    assert result.editor_decision in {"pass", "revise"}
    assert result.quality_score > 0
    assert any(item["type"] == "review_report" and item["graph"] == "review" for item in result.artifact_registry)


def test_legacy_review_action_is_alias_for_review_chapter(tmp_path):
    store, state = prepared_draft(tmp_path)
    state.director_action = "review"
    store.save_state(state)

    result = build_writer_graph(
        CodexCLIAdapter(mock=True),
        store,
        "review",
        review_func=lambda _state, _task: "approve",
    ).invoke(state.to_dict())

    assert result["director_action"] == "review_chapter"
    assert store.review_json_path("demo", 1, 1).exists()


def test_review_prompt_contains_chapter_draft_once(tmp_path):
    store, state = prepared_draft(tmp_path)
    loaded = NovelState.from_dict(load_review_context_node(state.to_dict(), store))

    prompt = build_review_prompt(loaded, "continuity_editor")

    assert prompt.count("## Chapter Draft") == 1
    assert "## chapter_draft" not in loaded.director_task_args["review_context"]


def test_review_synthesizer_uses_compact_json_not_full_draft(tmp_path):
    store, state = prepared_draft(tmp_path)
    loaded = NovelState.from_dict(load_review_context_node(state.to_dict(), store))
    loaded.director_task_args["continuity_review"] = {"role": "continuity_editor", "verdict": "pass", "top_issues": [], "rewrite_tasks": [], "keep": []}

    prompt = build_review_prompt(loaded, "review_synthesizer")

    assert "## Chapter Draft" not in prompt
    assert "continuity_editor" in prompt
    assert "blocking_issues 最多 3 条" in prompt
    assert "issues 最多 6 条" in prompt
    assert "rewrite_tasks 最多 8 条" in prompt
    assert "不新增问题" in prompt


def test_review_parallel_path_records_all_editor_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    store, state = prepared_draft(tmp_path)

    result = NovelState.from_dict(build_review_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))

    for key in ["continuity_review", "structure_review", "character_arc_review", "style_review", "simulated_reader_review", "pacing_guard_review"]:
        assert isinstance(result.director_task_args[key], dict)
    trace_path = store.project_dir("demo") / "debug" / "agent_runs.jsonl"
    assert trace_path.exists()
    assert "review_synthesizer" in trace_path.read_text(encoding="utf-8")

class AlwaysFailAdapter:
    def complete(self, prompt, workspace, options=None):
        from ai_novelist.adapters.base import AgentAdapterError

        raise AgentAdapterError("review agent failed")


def test_review_agent_failure_does_not_save_empty_report(tmp_path):
    store, state = prepared_draft(tmp_path)

    result = NovelState.from_dict(build_review_graph(AlwaysFailAdapter(), store).invoke(state.to_dict()))

    assert result.review_status == "error"
    assert result.error == "review agent failed"
    assert not store.review_report_path("demo", 1, 1).exists()
    assert not store.review_json_path("demo", 1, 1).exists()
    assert store.load_state("demo").review_status == "error"
