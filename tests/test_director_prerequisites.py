from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.director_service import DirectorService
from ai_novelist.research import MockSearchBackend
from ai_novelist.storage.local_store import LocalStore


def make_service(tmp_path):
    store = LocalStore(tmp_path)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())
    return store, service


def run_confirmed(service: DirectorService, project_id: str, text: str):
    first = service.handle_turn(project_id, text, channel="test")
    assert first.choices
    return service.handle_turn(project_id, "1", channel="test")


def test_director_routes_finalize_and_export(tmp_path):
    store, service = make_service(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    store.save_state(state)

    run_confirmed(service, "demo", "写第 1 章")
    run_confirmed(service, "demo", "审稿第 1 章")
    run_confirmed(service, "demo", "修订第 1 章")
    run_confirmed(service, "demo", "审稿第 1 章")
    finalized = run_confirmed(service, "demo", "定稿第 1 章")

    assert finalized.state.director_action == "finalize_chapter"
    assert store.final_chapter_path("demo", 1).exists()

    exported = run_confirmed(service, "demo", "导出小说")

    assert exported.state.director_action == "export_project"
    assert store.manuscript_export_path("demo").exists()


def test_director_write_chapter_auto_completes_prerequisites(tmp_path):
    store, service = make_service(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    store.save_state(state)

    result = run_confirmed(service, "demo", "写第 1 章")

    assert result.state.director_action == "write_chapter"
    assert store.chapter_card_path("demo", 1).exists()
    assert store.scene_cards_path("demo", 1).exists()
    assert store.chapter_draft_path("demo", 1, 1).exists()
    assert "草稿已生成" in result.state.director_message
