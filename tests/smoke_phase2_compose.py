"""Stdlib-only smoke checks for the phase 2 compose workflow."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_writer import build_composer_graph
from ai_novelist.storage.local_store import LocalStore


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalStore(Path(tmp))
        state = store.create_project("Demo", "demo")
        state.idea = "一个失忆工程师在月球城市追查自己的小说手稿"
        state.current_chapter = 1
        state.max_revisions = 1

        graph = build_composer_graph(
            CodexCLIAdapter(mock=True),
            store,
            review_func=lambda _state: "approve",
        )
        result = graph.invoke(state.to_dict())

        assert result["review_status"] == "approved"
        assert result["editor_decision"] == "pass"
        assert result["revision_count"] == 1
        assert store.worldbuilding_path("demo").exists()
        assert store.outline_path("demo").exists()
        assert store.chapter_plan_path("demo").exists()
        assert store.chapter_path("demo", 1).exists()
        assert store.editor_notes_path("demo", 1).exists()

    print("phase2 compose smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
