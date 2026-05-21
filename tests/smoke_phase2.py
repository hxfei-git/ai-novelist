"""Stdlib-only smoke checks for phase 2."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_writer import build_writer_graph
from ai_novelist.storage.local_store import LocalStore


def run_task(store: LocalStore, state, task: str):
    graph = build_writer_graph(
        CodexCLIAdapter(mock=True),
        store,
        task,
        review_func=lambda _state, _task: "approve",
    )
    return graph.invoke(state.to_dict() if hasattr(state, "to_dict") else state)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalStore(Path(tmp))
        state = store.create_project("Demo", "demo")
        state.idea = "一个失忆工程师在月球城市追查自己的小说手稿"
        state.outline = "# 小说大纲"
        store.save_state(state)

        world = run_task(store, state, "worldbuild")
        outline = run_task(store, world, "plan_outline")
        plan = run_task(store, outline, "plan_chapters")
        plan["current_chapter"] = 1
        chapter = run_task(store, plan, "write_chapter")
        review = run_task(store, chapter, "review")

        assert review["review_status"] == "approved"
        assert store.worldbuilding_path("demo").exists()
        assert store.chapter_plan_path("demo").exists()
        assert store.chapter_path("demo", 1).exists()
        assert store.editor_notes_path("demo", 1).exists()

    print("phase2 smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
