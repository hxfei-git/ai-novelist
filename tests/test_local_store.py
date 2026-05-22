from ai_novelist.storage.local_store import LocalStore


def test_create_project_and_save_outline(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo Novel", "demo")
    state.outline = "# Outline"

    path = store.save_outline(state)
    loaded = store.load_state("demo")

    assert path.read_text(encoding="utf-8") == "# Outline\n"
    assert loaded.project_id == "demo"
    assert (tmp_path / "demo" / "chapters").is_dir()


def test_project_context_round_trip(tmp_path):
    store = LocalStore(tmp_path)
    store.create_project("Demo", "demo")

    path = store.save_project_context("demo", "# Context\n")

    assert path == store.project_context_path("demo")
    assert store.load_project_context("demo") == "# Context\n"
    assert store.load_project_context("missing") == ""


def test_save_project_memory_skips_unchanged_write(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    path = store.project_memory_path("demo")
    before = path.stat().st_mtime_ns

    store.save_project_memory(state)
    after = path.stat().st_mtime_ns

    assert before == after
    assert path.with_suffix(path.suffix + ".sha256").exists()


def test_lightweight_state_compacts_saved_chapter_draft(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.active_chapter = 1
    state.current_chapter = 1
    state.chapter_draft = "正文" * 1000
    store.save_chapter_draft(state, version=1)
    store.save_state(state)

    raw = store.state_path("demo").read_text(encoding="utf-8")
    assert len(raw) < 3000
