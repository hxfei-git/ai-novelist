"""Stdlib-only smoke check for the interactive outline collaboration graph."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_outline import append_message, build_outline_collaboration_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def run_turn(graph, store: LocalStore, state: NovelState, text: str) -> NovelState:
    state.user_request = text
    state.last_user_feedback = text
    append_message(state, "user", text)
    store.save_state(state)
    return NovelState.from_dict(graph.invoke(state.to_dict()))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalStore(Path(tmp))
        state = store.create_project("Demo", "demo")
        state.idea = "一个失忆工程师在月球城市追查自己的小说手稿"
        graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

        state = run_turn(graph, store, state, "生成大纲")
        assert state.outline
        assert state.editor_decision == "revise"
        assert not store.outline_path("demo").exists()

        state = run_turn(graph, store, state, "大纲太普通，强化主角罪感，第三幕更黑暗")
        assert state.editor_decision == "pass"
        assert state.revision_count == 1
        assert "修订版总大纲" in state.outline

        state = run_turn(graph, store, state, "保存大纲")
        assert state.review_status == "approved"
        assert store.outline_path("demo").exists()

    print("outline collaboration smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
