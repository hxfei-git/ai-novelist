from pathlib import Path

from ai_novelist.corpus.craft_extractor import extract_craft_profiles
from ai_novelist.corpus.craft_resolver import resolve_author_craft
from ai_novelist.corpus.index import build_corpus_index
from ai_novelist.context_builder import build_context
from ai_novelist.storage.local_store import LocalStore


def test_author_craft_mock_flow(tmp_path):
    index_dir = tmp_path / "corpus_index"
    build_corpus_index(Path("tests/fixtures/corpus"), index_dir)
    extract_craft_profiles(index_dir, mock=True)

    store = LocalStore(tmp_path / "projects")
    state = store.create_project("Demo", "craft-demo")
    state.idea = "月球城市失忆工程师的悬疑科幻"
    state.user_request = "规划第 1 章"
    state.craft_mode = "assist"
    state.craft_options = {"corpus_index_dir": str(index_dir), "craft_max_chars": 3000}
    state = resolve_author_craft(state, store, "chapter_planning", chapter=1)
    store.save_state(state)

    context = build_context(state, store, "chapter_planning", chapter=1)
    brief_path = store.project_dir("craft-demo") / state.active_craft_brief_path

    assert brief_path.exists()
    assert "作者构思参考" in context
    assert "门禁系统显示他的身份已经死亡" not in brief_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
