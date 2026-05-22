from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.director_service import DirectorService
from ai_novelist.research import MockSearchBackend
from ai_novelist.storage.local_store import LocalStore


def make_service(tmp_path):
    store = LocalStore(tmp_path)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())
    return store, service


def test_director_routes_finalize_and_export(tmp_path):
    store, service = make_service(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    store.save_state(state)

    service.handle_turn("demo", "写第 1 章", channel="test")
    service.handle_turn("demo", "审稿第 1 章", channel="test")
    service.handle_turn("demo", "修订第 1 章", channel="test")
    service.handle_turn("demo", "审稿第 1 章", channel="test")
    finalized = service.handle_turn("demo", "定稿第 1 章", channel="test")

    assert finalized.state.director_action == "finalize_chapter"
    assert store.final_chapter_path("demo", 1).exists()

    exported = service.handle_turn("demo", "导出小说", channel="test")

    assert exported.state.director_action == "export_project"
    assert store.manuscript_export_path("demo").exists()


def test_director_write_chapter_auto_completes_prerequisites(tmp_path):
    store, service = make_service(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    store.save_state(state)

    result = service.handle_turn("demo", "写第 1 章", channel="test")

    assert result.state.director_action == "write_chapter"
    assert store.chapter_card_path("demo", 1).exists()
    assert store.scene_cards_path("demo", 1).exists()
    assert store.chapter_draft_path("demo", 1, 1).exists()
    assert "草稿已生成" in result.state.director_message
