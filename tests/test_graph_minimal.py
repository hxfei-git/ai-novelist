from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_minimal import build_minimal_graph
from ai_novelist.storage.local_store import LocalStore


def test_minimal_graph_approves_and_persists_outline(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "失忆工程师"
    adapter = CodexCLIAdapter(mock=True)

    graph = build_minimal_graph(adapter, store, review_func=lambda _: "approve")
    result = graph.invoke(state.to_dict())

    assert result["review_status"] == "approved"
    assert store.outline_path("demo").exists()
