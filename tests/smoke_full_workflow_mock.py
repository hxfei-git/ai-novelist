from pathlib import Path
import shutil

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.director_service import DirectorService
from ai_novelist.research import MockSearchBackend
from ai_novelist.storage.local_store import LocalStore


def main() -> None:
    root = Path("projects")
    project_id = "smoke-full-workflow-mock"
    project_dir = root / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
    store = LocalStore(root)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())
    state = store.create_project("完整闭环 Smoke", project_id)
    state.idea = "月球城市失忆工程师追查纸质手稿预言"
    store.save_state(state)

    run_confirmed_turn(service, project_id, "写第 1 章")
    first_review = run_confirmed_turn(service, project_id, "审稿第 1 章")
    assert first_review.state.editor_decision == "revise"
    run_confirmed_turn(service, project_id, "修订第 1 章")
    second_review = run_confirmed_turn(service, project_id, "审稿第 1 章")
    assert second_review.state.editor_decision == "pass"
    run_confirmed_turn(service, project_id, "定稿第 1 章")
    run_confirmed_turn(service, project_id, "导出小说")

    assert store.chapter_card_path(project_id, 1).exists()
    assert store.scene_cards_path(project_id, 1).exists()
    assert store.chapter_draft_path(project_id, 1, 1).exists()
    assert store.chapter_draft_path(project_id, 1, 2).exists()
    assert store.final_chapter_path(project_id, 1).exists()
    assert store.chapter_summary_path(project_id, 1).exists()
    assert store.manuscript_export_path(project_id).exists()
    assert store.volume_export_path(project_id).exists()
    assert store.bible_export_path(project_id).exists()
    print("full workflow mock smoke passed")



def run_confirmed_turn(service, project_id: str, text: str):
    result = service.handle_turn(project_id, text, channel="test")
    if result.choices:
        result = service.handle_turn(project_id, "1", channel="test")
    return result


if __name__ == "__main__":
    main()
