"""Stdlib-only smoke checks for the Director chat workflow."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_writer import append_message, build_chat_graph
from ai_novelist.storage.local_store import LocalStore


def run_turn(graph, store: LocalStore, state, text: str):
    state.user_request = text
    append_message(state, "user", text)
    store.save_state(state)
    return graph.invoke(state.to_dict())


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalStore(Path(tmp))
        state = store.create_project("Demo", "demo")
        graph = build_chat_graph(CodexCLIAdapter(mock=True), store)

        world = run_turn(graph, store, state, "我想写一个月球城市失忆工程师的悬疑科幻")
        assert world["director_action"] == "worldbuild"
        assert world["worldbuilding"]

        state = store.load_state("demo")
        outline = run_turn(graph, store, state, "大纲太普通，增强主角罪感")
        assert outline["director_action"] == "plan_outline"
        assert outline["outline"]

        state = store.load_state("demo")
        chapter = run_turn(graph, store, state, "写第 1 章")
        assert chapter["director_action"] == "write_chapter"
        assert chapter["chapter_draft"]

        state = store.load_state("demo")
        review = run_turn(graph, store, state, "让编辑审稿")
        assert review["director_action"] == "review"
        assert review["editor_notes"]

        state = store.load_state("demo")
        saved = run_turn(graph, store, state, "保存当前结果")
        assert saved["director_action"] == "persist_outputs"
        assert store.worldbuilding_path("demo").exists()
        assert store.outline_path("demo").exists()
        assert store.chapter_path("demo", 1).exists()
        assert store.editor_notes_path("demo", 1).exists()

    print("phase2 chat smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
