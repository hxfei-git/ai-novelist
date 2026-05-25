from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.artifacts import load_artifacts
from ai_novelist.director_service import DirectorService
from ai_novelist.graph_chapter_plan import build_chapter_plan_graph
from ai_novelist.graph_scene import SCENE_FIELDS, build_scene_graph
from ai_novelist.research import MockSearchBackend
from ai_novelist.storage.local_store import LocalStore


def make_state_with_chapter_card(store: LocalStore):
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    state.current_chapter = 1
    state.outline = "# 最终大纲\n\n第 1 章发现空白手稿。"
    store.save_state(state)
    result = build_chapter_plan_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict())
    return result


def test_scene_graph_generates_scene_cards(tmp_path):
    store = LocalStore(tmp_path)
    state_data = make_state_with_chapter_card(store)

    result = build_scene_graph(CodexCLIAdapter(mock=True), store).invoke(state_data)

    assert result["active_graph"] == "scene"
    assert result["active_stage"] == "scene_cards"
    assert result["active_chapter"] == 1
    assert store.scene_cards_path("demo", 1).exists()
    content = store.scene_cards_path("demo", 1).read_text(encoding="utf-8")
    assert content.count("## 场景") >= 2
    for field in SCENE_FIELDS:
        assert field in content
    assert result["current_scene_cards"] == content.strip()
    artifacts = load_artifacts(store.project_dir("demo"))
    assert any(item.type == "scene_cards" and item.chapter == 1 and item.graph == "scene" for item in artifacts)


def test_scene_graph_missing_chapter_card_returns_readable_message(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")

    result = build_scene_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict())

    assert result["review_status"] == "error"
    assert "缺少第 1 章章节卡" in result["director_message"]
    assert not store.scene_cards_path("demo", 1).exists()


def test_director_service_routes_scene_planning(tmp_path):
    store = LocalStore(tmp_path)
    make_state_with_chapter_card(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    first = service.handle_turn("demo", "规划第 1 章场景", channel="cli")
    result = service.handle_turn("demo", "1", channel="cli")

    assert first.choices
    assert result.state.director_action == "plan_scenes"
    assert result.state.active_graph == "scene"
    assert store.scene_cards_path("demo", 1).exists()

class AlwaysFailAdapter:
    def complete(self, prompt, workspace, options=None):
        from ai_novelist.adapters.base import AgentAdapterError

        raise AgentAdapterError("scene agent failed")


def test_scene_agent_failure_does_not_save_empty_scene_cards(tmp_path):
    store = LocalStore(tmp_path)
    state_data = make_state_with_chapter_card(store)

    result = build_scene_graph(AlwaysFailAdapter(), store).invoke(state_data)

    assert result["review_status"] == "error"
    assert result["error"] == "scene agent failed"
    assert not store.scene_cards_path("demo", 1).exists()
    assert store.load_state("demo").review_status == "error"
