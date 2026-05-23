from pathlib import Path

from ai_novelist.corpus.craft_extractor import extract_craft_profiles
from ai_novelist.corpus.craft_query_planner import plan_craft_query
from ai_novelist.corpus.craft_retriever import retrieve_craft_context
from ai_novelist.corpus.index import build_corpus_index
from ai_novelist.state import NovelState


def test_retriever_filters_by_stage_and_pacing(tmp_path):
    build_corpus_index(Path("tests/fixtures/corpus"), tmp_path)
    extract_craft_profiles(tmp_path, mock=True)
    state = NovelState(project_id="demo", title="Demo", idea="悬疑科幻")
    state.craft_mode = "assist"
    state.craft_options = {"corpus_index_dir": str(tmp_path)}

    query = plan_craft_query(state, None, "chapter_planning", chapter=1, pacing_target={"function": "setup", "intensity": 2})
    context = retrieve_craft_context(tmp_path, query)

    assert context.selected_notes
    assert all(note.facet != "dialogue" for note in context.selected_notes[:3])
    assert all(not evidence.short_quote for evidence in context.sources)


def test_craft_mode_off_returns_empty(tmp_path):
    state = NovelState(project_id="demo", title="Demo")
    query = plan_craft_query(state, None, "drafting")

    context = retrieve_craft_context(tmp_path, query)

    assert context.selected_notes == []
