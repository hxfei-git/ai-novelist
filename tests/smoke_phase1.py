"""Stdlib-only smoke checks for phase 1."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_minimal import build_minimal_graph
from ai_novelist.storage.local_store import LocalStore


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalStore(Path(tmp))
        state = store.create_project("Demo", "demo")
        state.idea = "一个失忆工程师在月球城市追查自己的小说手稿"

        graph = build_minimal_graph(
            CodexCLIAdapter(mock=True),
            store,
            review_func=lambda _: "approve",
        )
        result = graph.invoke(state.to_dict())

        assert result["review_status"] == "approved"
        assert store.outline_path("demo").exists()
        assert "# 小说大纲" in store.outline_path("demo").read_text(encoding="utf-8")

    print("phase1 smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
