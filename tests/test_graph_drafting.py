from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_drafting import build_drafting_graph
from ai_novelist.graph_writer import build_writer_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def test_drafting_auto_completes_chapter_and_scene_cards(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    state.current_chapter = 1
    store.save_state(state)

    result = NovelState.from_dict(build_drafting_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))

    assert store.chapter_card_path("demo", 1).exists()
    assert store.scene_cards_path("demo", 1).exists()
    assert store.chapter_draft_path("demo", 1, 1).exists()
    assert store.chapter_path("demo", 1).exists()
    assert "空白手稿" in result.chapter_draft
    assert result.active_graph == "drafting"
    assert result.active_stage == "draft"
    assert result.active_chapter == 1
    assert any(item["type"] == "chapter_draft" and item["graph"] == "drafting" for item in result.artifact_registry)


def test_legacy_write_chapter_wrapper_uses_drafting_graph(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.current_chapter = 2
    store.save_state(state)

    result = build_writer_graph(
        CodexCLIAdapter(mock=True),
        store,
        "write_chapter",
        review_func=lambda _state, _task: "approve",
    ).invoke(state.to_dict())

    assert result["review_status"] == "approved"
    assert result["active_graph"] == "drafting"
    assert store.chapter_draft_path("demo", 2, 1).exists()
    assert store.chapter_path("demo", 2).exists()
