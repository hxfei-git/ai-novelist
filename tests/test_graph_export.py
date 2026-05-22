from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_drafting import build_drafting_graph
from ai_novelist.graph_export import build_export_graph
from ai_novelist.graph_finalize import build_finalize_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def test_export_with_final_chapter_writes_manuscript_volume_and_bible(tmp_path):
    store = LocalStore(tmp_path)
    adapter = CodexCLIAdapter(mock=True)
    state = store.create_project("Demo", "demo")
    state = NovelState.from_dict(build_drafting_graph(adapter, store).invoke(state.to_dict()))
    state.director_action = "finalize_chapter"
    state.director_task_args = {"chapter": 1, "explicit_finalize": True}
    state = NovelState.from_dict(build_finalize_graph(adapter, store).invoke(state.to_dict()))

    result = NovelState.from_dict(build_export_graph(store).invoke(state.to_dict()))

    assert result.review_status == "approved"
    assert store.manuscript_export_path("demo").exists()
    assert store.volume_export_path("demo").exists()
    assert store.bible_export_path("demo").exists()
    assert "空白手稿" in store.manuscript_export_path("demo").read_text(encoding="utf-8")
    assert any(item["type"] == "export" and item["stage"] == "manuscript" for item in result.artifact_registry)


def test_export_sorts_multiple_final_chapters(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    store.final_chapter_path("demo", 2).parent.mkdir(parents=True, exist_ok=True)
    store.final_chapter_path("demo", 2).write_text("# 第 2 章\n\n第二章", encoding="utf-8")
    store.final_chapter_path("demo", 1).parent.mkdir(parents=True, exist_ok=True)
    store.final_chapter_path("demo", 1).write_text("# 第 1 章\n\n第一章", encoding="utf-8")

    result = NovelState.from_dict(build_export_graph(store).invoke(state.to_dict()))

    manuscript = store.manuscript_export_path("demo").read_text(encoding="utf-8")
    assert manuscript.index("第 1 章") < manuscript.index("第 2 章")
    assert result.review_status == "approved"


def test_export_without_final_chapter_returns_prompt(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")

    result = NovelState.from_dict(build_export_graph(store).invoke(state.to_dict()))

    assert result.review_status == "error"
    assert "没有可导出的定稿章节" in result.error
    assert not store.manuscript_export_path("demo").exists()
