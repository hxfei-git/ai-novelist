from pathlib import Path
import shutil

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_drafting import build_drafting_graph
from ai_novelist.graph_review import build_review_graph
from ai_novelist.graph_revision import build_revision_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def main() -> None:
    root = Path("projects")
    project_id = "smoke-chapter-pipeline-mock"
    project_dir = root / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
    store = LocalStore(root)
    adapter = CodexCLIAdapter(mock=True)
    state = store.create_project("章节闭环 Smoke", project_id)
    state.idea = "月球城市失忆工程师追查纸质手稿预言"
    state.current_chapter = 1
    state.max_revisions = 1
    store.save_state(state)

    state = NovelState.from_dict(build_drafting_graph(adapter, store).invoke(state.to_dict()))
    state = NovelState.from_dict(build_review_graph(adapter, store).invoke(state.to_dict()))
    assert state.editor_decision == "revise"
    state = NovelState.from_dict(build_revision_graph(adapter, store).invoke(state.to_dict()))
    state = NovelState.from_dict(build_review_graph(adapter, store).invoke(state.to_dict()))

    assert state.editor_decision == "pass"
    assert store.chapter_card_path(project_id, 1).exists()
    assert store.scene_cards_path(project_id, 1).exists()
    assert store.chapter_draft_path(project_id, 1, 1).exists()
    assert store.review_report_path(project_id, 1, 1).exists()
    assert store.review_json_path(project_id, 1, 1).exists()
    assert store.revision_plan_path(project_id, 1, 1).exists()
    assert store.chapter_draft_path(project_id, 1, 2).exists()
    print("chapter pipeline mock smoke passed")


if __name__ == "__main__":
    main()
