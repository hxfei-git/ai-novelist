from ai_novelist.artifacts import save_markdown_artifact
from ai_novelist.bible import NovelBible, save_bible
from ai_novelist.context_builder import build_context
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def test_drafting_context_includes_chapter_and_scene_cards(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "写第 1 章"
    save_markdown_artifact(store.project_dir("demo"), "chapters/chapter_001/chapter_card.md", "# 章节卡", "chapter_card", chapter=1)
    save_markdown_artifact(store.project_dir("demo"), "chapters/chapter_001/scene_cards.md", "# Scene 1", "scene_cards", chapter=1)

    context = build_context(state, store, "drafting", chapter=1)

    assert "# 章节卡" in context
    assert "# Scene 1" in context
    assert "写第 1 章" in context


def test_review_context_includes_draft(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    save_markdown_artifact(store.project_dir("demo"), "chapters/chapter_001/draft_v1.md", "# 草稿正文", "chapter_draft", chapter=1)

    context = build_context(state, store, "review", chapter=1)

    assert "# 草稿正文" in context


def test_locked_constraints_survive_truncation(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.locked_constraints = ["主角不能主动杀人", "结尾必须保留开放疑问"]
    bible = NovelBible()
    bible.project.title = "很长" * 500
    save_bible(store.project_dir("demo"), bible)

    context = build_context(state, store, "drafting", chapter=1, max_chars=260)

    assert "主角不能主动杀人" in context
    assert "结尾必须保留开放疑问" in context
    assert "已截断" in context


def test_max_chars_limit_applies(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.reference_brief = "参考" * 1000

    context = build_context(state, store, "outline_stage", max_chars=500)

    assert len(context) <= 520
    assert "# Task Context" in context


def test_context_includes_previous_chapter_summary(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.chapter_summaries = {"1": "主角发现第一条线索。", "2": "当前章摘要不应作为前文。"}

    context = build_context(state, store, "drafting", chapter=2)

    assert "主角发现第一条线索" in context
    assert "当前章摘要不应作为前文" not in context
