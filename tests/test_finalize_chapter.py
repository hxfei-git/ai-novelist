from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.bible import load_bible
from ai_novelist.graph_drafting import build_drafting_graph
from ai_novelist.graph_finalize import build_finalize_graph
from ai_novelist.graph_review import build_review_graph
from ai_novelist.graph_revision import build_revision_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def prepared_passed_chapter(tmp_path):
    store = LocalStore(tmp_path)
    adapter = CodexCLIAdapter(mock=True)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    state.max_revisions = 1
    state = NovelState.from_dict(build_drafting_graph(adapter, store).invoke(state.to_dict()))
    state = NovelState.from_dict(build_review_graph(adapter, store).invoke(state.to_dict()))
    state = NovelState.from_dict(build_revision_graph(adapter, store).invoke(state.to_dict()))
    state = NovelState.from_dict(build_review_graph(adapter, store).invoke(state.to_dict()))
    return store, adapter, state


def test_finalize_chapter_saves_final_summary_and_updates_bible(tmp_path):
    store, adapter, state = prepared_passed_chapter(tmp_path)

    result = NovelState.from_dict(build_finalize_graph(adapter, store).invoke(state.to_dict()))

    assert store.final_chapter_path("demo", 1).exists()
    assert store.chapter_summary_path("demo", 1).exists()
    assert result.current_final_chapter.strip()
    assert result.chapter_summaries["1"]
    assert len(result.chapter_summaries["1"]) <= 180
    assert result.bible_version >= 2
    bible = load_bible(store.project_dir("demo"))
    assert "1" in bible.chapter_summaries
    updates = result.director_task_args["bible_updates"]
    assert "world_rules" not in updates
    assert all("source_hint" in item for item in updates.get("timeline", []))
    assert all("source_hint" in item for item in updates.get("foreshadowing", []))
    assert all("source_hint" in item for item in updates.get("plot_threads", []))
    assert any(item.type == "final_chapter" for item in load_records(result))
    assert any(item.type == "chapter_summary" for item in load_records(result))


def test_finalize_explicit_request_can_bypass_non_pass_review(tmp_path):
    store = LocalStore(tmp_path)
    adapter = CodexCLIAdapter(mock=True)
    state = store.create_project("Demo", "demo")
    state = NovelState.from_dict(build_drafting_graph(adapter, store).invoke(state.to_dict()))
    state.editor_decision = "revise"
    state.director_action = "finalize_chapter"
    state.director_task_args = {"chapter": 1, "explicit_finalize": True}
    store.save_state(state)

    result = NovelState.from_dict(build_finalize_graph(adapter, store).invoke(state.to_dict()))

    assert result.review_status == "approved"
    assert store.final_chapter_path("demo", 1).exists()


def test_finalize_without_draft_returns_error(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.director_action = "finalize_chapter"

    result = NovelState.from_dict(build_finalize_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))

    assert result.review_status == "error"
    assert "缺少第 1 章草稿" in result.error


def load_records(state):
    from ai_novelist.artifacts import ArtifactRecord

    return [ArtifactRecord.from_dict(item) for item in state.artifact_registry]
