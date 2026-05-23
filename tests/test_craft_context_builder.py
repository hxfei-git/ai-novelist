from pathlib import Path

from ai_novelist.corpus.craft_extractor import extract_craft_profiles
from ai_novelist.corpus.craft_resolver import resolve_author_craft
from ai_novelist.corpus.index import build_corpus_index
from ai_novelist.context_builder import build_context
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def test_context_builder_injects_author_craft_after_locked_constraints(tmp_path):
    index_dir = tmp_path / "index"
    build_corpus_index(Path("tests/fixtures/corpus"), index_dir)
    extract_craft_profiles(index_dir, mock=True)
    store = LocalStore(tmp_path / "projects")
    state = store.create_project("Demo", "demo")
    state.locked_constraints = ["主角不能主动杀人"]
    state.craft_mode = "assist"
    state.craft_options = {"corpus_index_dir": str(index_dir)}
    state = resolve_author_craft(state, store, "chapter_planning", chapter=1)
    store.save_state(state)

    context = build_context(state, store, "chapter_planning", chapter=1)

    assert "## 作者构思参考" in context
    assert context.index("## 锁定约束") < context.index("## 作者构思参考")
    assert "只学习构思方法" in context


def test_context_builder_off_mode_has_no_effective_craft(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.craft_mode = "off"

    context = build_context(state, store, "chapter_planning", chapter=1)

    assert "## 作者构思参考" in context
    assert "只学习构思方法" not in context
