from ai_novelist.corpus.project_memory import extract_project_craft_memory, load_project_craft_memory
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def test_extract_project_craft_memory_from_final_chapter(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.active_chapter = 1
    state.current_chapter = 1
    state.current_final_chapter = "门禁权限倒计时，主角在限制中推进信息。\n"
    state.chapter_summaries = {"1": "主角通过门禁压力确认身份疑问。"}
    store.save_final_chapter(state)
    store.save_chapter_summary(state)

    profile = extract_project_craft_memory(state, store, 1)

    assert profile.scope == "project"
    assert profile.notes
    assert store.project_craft_memory_path("demo").exists()
    assert load_project_craft_memory("demo", store).notes
