from pathlib import Path

from ai_novelist.corpus.craft_brief import build_stage_craft_brief
from ai_novelist.corpus.craft_extractor import extract_craft_profiles
from ai_novelist.corpus.craft_resolver import resolve_author_craft
from ai_novelist.corpus.craft_schema import CraftContext, CraftEvidence, CraftNote
from ai_novelist.corpus.index import build_corpus_index
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def test_build_stage_craft_brief_has_required_sections():
    note = CraftNote(
        note_id="n1",
        scope="chapter",
        facet="pacing",
        title="节奏",
        pattern="只释放一个问题。",
        why_it_works="让行动承载信息。",
        use_when=["setup"],
        avoid_when=["climax"],
        pacing_functions=["setup"],
        evidence=[CraftEvidence(source_id="c1", work_id="w1", summary="分析摘要")],
    )
    context = CraftContext("chapter_planning", 1, "", ["悬疑"], [note], note.evidence, 3000, ["p1"])

    brief = build_stage_craft_brief(context, {"function": "setup", "intensity": 2}, 3000, "demo")

    assert "## 使用规则" in brief.content
    assert "## 与 Pacing Target 的对齐" in brief.content
    assert "## 不应采纳的方向" in brief.content
    assert "只释放一个问题" in brief.content


def test_resolver_saves_brief_and_sources(tmp_path):
    index_dir = tmp_path / "index"
    build_corpus_index(Path("tests/fixtures/corpus"), index_dir)
    extract_craft_profiles(index_dir, mock=True)
    store = LocalStore(tmp_path / "projects")
    state = store.create_project("Demo", "demo")
    state.craft_mode = "assist"
    state.craft_options = {"corpus_index_dir": str(index_dir), "craft_max_chars": 3000}

    state = resolve_author_craft(state, store, "chapter_planning", chapter=1)
    store.save_state(state)

    assert state.active_craft_brief_path
    assert (store.project_dir("demo") / state.active_craft_brief_path).exists()
    assert state.craft_sources
