from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.artifacts import load_artifacts
from ai_novelist.director_service import DirectorDecision, DirectorService
from ai_novelist.graph_chapter_plan import CHAPTER_CARD_SECTIONS, build_chapter_plan_graph
from ai_novelist.research import MockSearchBackend
from ai_novelist.storage.local_store import LocalStore


def make_ready_state(store: LocalStore):
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    state.current_chapter = 1
    state.outline = "# 最终大纲\n\n第 1 章发现空白手稿。"
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "label": "章节大纲",
        "synthesis": "第 1 章：空白手稿。林澈发现纸质手稿和失效审计编号。",
    }
    store.save_state(state)
    return state


def test_chapter_plan_graph_generates_chapter_card(tmp_path):
    store = LocalStore(tmp_path)
    state = make_ready_state(store)

    result = build_chapter_plan_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict())

    assert result["active_graph"] == "chapter_plan"
    assert result["active_stage"] == "chapter_card"
    assert result["active_chapter"] == 1
    assert store.chapter_card_path("demo", 1).exists()
    content = store.chapter_card_path("demo", 1).read_text(encoding="utf-8")
    for section in CHAPTER_CARD_SECTIONS:
        assert section in content
    assert result["current_chapter_card"] == content.strip()
    artifacts = load_artifacts(store.project_dir("demo"))
    assert any(item.type == "chapter_card" and item.chapter == 1 and item.graph == "chapter_plan" for item in artifacts)


def test_director_decision_treats_plan_chapters_as_plan_chapter_alias():
    decision = DirectorDecision.from_dict({"action": "plan_chapters", "task_args": {"chapter": 1}})

    assert decision.action == "plan_chapter"
    assert decision.chapter == 1


def test_director_service_routes_chapter_planning(tmp_path):
    store = LocalStore(tmp_path)
    make_ready_state(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    first = service.handle_turn("demo", "规划第 1 章", channel="cli")
    result = service.handle_turn("demo", "1", channel="cli")

    assert first.choices
    assert result.state.director_action == "plan_chapter"
    assert result.state.active_graph == "chapter_plan"
    assert store.chapter_card_path("demo", 1).exists()


def test_chapter_plan_parallel_path_records_three_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    store = LocalStore(tmp_path)
    state = make_ready_state(store)

    result = build_chapter_plan_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict())

    for key in ["chapter_goal_report", "chapter_conflict_report", "chapter_hook_report"]:
        assert result["director_task_args"][key]
    trace_path = store.project_dir("demo") / "debug" / "agent_runs.jsonl"
    assert trace_path.exists()
    text = trace_path.read_text(encoding="utf-8")
    assert "chapter_goal_agent" in text
    assert "chapter_card_synthesizer" in text


def test_chapter_plan_sets_pacing_target(tmp_path):
    store = LocalStore(tmp_path)
    state = make_ready_state(store)

    result = build_chapter_plan_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict())

    pacing = result["director_task_args"].get("pacing_target", {})
    assert pacing.get("chapter") == 1
    assert 1 <= int(pacing.get("intensity", 0)) <= 5
    validation = result["director_task_args"].get("chapter_card_validation", {})
    assert "required_sections" in validation
