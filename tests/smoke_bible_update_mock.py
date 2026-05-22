from pathlib import Path
import shutil

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.bible import load_bible
from ai_novelist.graph_drafting import build_drafting_graph
from ai_novelist.graph_finalize import build_finalize_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def main() -> None:
    root = Path("projects")
    project_id = "smoke-bible-update-mock"
    project_dir = root / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
    store = LocalStore(root)
    adapter = CodexCLIAdapter(mock=True)
    state = store.create_project("Bible 更新 Smoke", project_id)
    state.idea = "月球城市失忆工程师追查纸质手稿预言"
    state = NovelState.from_dict(build_drafting_graph(adapter, store).invoke(state.to_dict()))
    state.director_action = "finalize_chapter"
    state.director_task_args = {"chapter": 1, "explicit_finalize": True}
    state = NovelState.from_dict(build_finalize_graph(adapter, store).invoke(state.to_dict()))

    bible = load_bible(store.project_dir(project_id))
    assert store.final_chapter_path(project_id, 1).exists()
    assert store.chapter_summary_path(project_id, 1).exists()
    assert "1" in bible.chapter_summaries
    assert state.bible_version >= 2
    print("bible update mock smoke passed")


if __name__ == "__main__":
    main()
