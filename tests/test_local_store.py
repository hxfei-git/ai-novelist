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
