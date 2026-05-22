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

        world = run_turn(graph, store, state, "帮我先设计世界观：月球城市失忆工程师的悬疑科幻")
        assert world["director_action"] == "worldbuild"
        assert world["worldbuilding"]

        state = store.load_state("demo")
        outline = run_turn(graph, store, state, "生成大纲")
        assert outline["director_action"] == "run_outline_stage"
        assert outline["outline_stage"] == "direction"
        assert outline["outline_stage_status"] == "options_ready"
        assert not outline["outline"]
        assert not store.outline_path("demo").exists()

        state = store.load_state("demo")
        advanced = run_turn(graph, store, state, "确认进入下一阶段")
        assert advanced["outline_stage"] == "concept"
        assert "concept" in advanced["outline_stage_artifacts"]
        assert not store.outline_path("demo").exists()

        state = store.load_state("demo")
        advanced = run_turn(graph, store, state, "确认进入下一阶段")
        assert advanced["outline_stage"] == "worldbuilding"
        assert "worldbuilding" in advanced["outline_stage_artifacts"]
        assert not store.outline_path("demo").exists()

    print("phase2 chat smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
