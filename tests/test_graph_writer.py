from ai_novelist.adapters.codex_cli import CodexCLIAdapter, CodexCLIError
from ai_novelist.graph_writer import build_chat_graph, build_composer_graph, build_writer_graph, parse_director_output, parse_editor_review
from ai_novelist.storage.local_store import LocalStore


def test_writer_graph_worldbuild_approves_and_persists(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "失忆工程师"

    graph = build_writer_graph(
        CodexCLIAdapter(mock=True),
        store,
        "worldbuild",
        review_func=lambda _state, _task: "approve",
    )
    result = graph.invoke(state.to_dict())

    assert result["review_status"] == "approved"
    assert "月球城市" in result["worldbuilding"]
    assert store.worldbuilding_path("demo").exists()


def test_writer_graph_revise_does_not_persist(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")

    graph = build_writer_graph(
        CodexCLIAdapter(mock=True),
        store,
        "plan_chapters",
        review_func=lambda _state, _task: "revise",
    )
    result = graph.invoke(state.to_dict())

    assert result["review_status"] == "revision_requested"
    assert not store.chapter_plan_path("demo").exists()


def test_writer_graph_write_chapter_and_review(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.current_chapter = 2

    write_graph = build_writer_graph(
        CodexCLIAdapter(mock=True),
        store,
        "write_chapter",
        review_func=lambda _state, _task: "approve",
    )
    written = write_graph.invoke(state.to_dict())

    assert written["review_status"] == "approved"
    assert store.chapter_path("demo", 2).exists()

    review_graph = build_writer_graph(
        CodexCLIAdapter(mock=True),
        store,
        "review",
        review_func=lambda _state, _task: "approve",
    )
    reviewed = review_graph.invoke(written)

    assert reviewed["review_status"] == "approved"
    assert store.editor_notes_path("demo", 2).exists()


def test_writer_graph_plan_outline_persists_outline(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "失忆工程师"
    state.worldbuilding = "# 世界观"

    graph = build_writer_graph(
        CodexCLIAdapter(mock=True),
        store,
        "plan_outline",
        review_func=lambda _state, _task: "approve",
    )
    result = graph.invoke(state.to_dict())

    assert result["review_status"] == "approved"
    assert "总大纲" in result["outline"]
    assert store.outline_path("demo").exists()



def test_parse_editor_review_extracts_status_and_score():
    decision, score = parse_editor_review("STATUS: pass\nQUALITY_SCORE: 88\n")

    assert decision == "pass"
    assert score == 88


def test_composer_graph_runs_full_flow_and_persists_outputs(tmp_path):
    store = LocalStore(tmp_path)
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
    assert result["quality_score"] == 88
    assert store.worldbuilding_path("demo").exists()
    assert store.outline_path("demo").exists()
    assert store.chapter_plan_path("demo").exists()
    assert store.chapter_path("demo", 1).exists()
    assert store.editor_notes_path("demo", 1).exists()


def test_composer_graph_stops_when_revision_is_not_allowed(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "一个失忆工程师在月球城市追查自己的小说手稿"
    state.max_revisions = 0

    graph = build_composer_graph(
        CodexCLIAdapter(mock=True),
        store,
        review_func=lambda _state: "approve",
    )
    result = graph.invoke(state.to_dict())

    assert result["review_status"] == "stopped"
    assert result["editor_decision"] == "revise"
    assert not store.chapter_path("demo", 1).exists()



def test_parse_director_output_extracts_action_message_and_chapter():
    action, message, chapter = parse_director_output("ACTION: write_chapter\nMESSAGE: 写第一章。\nCHAPTER: 1")

    assert action == "write_chapter"
    assert message == "写第一章。"
    assert chapter == 1


def test_chat_graph_routes_worldbuild_and_persist(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    adapter = CodexCLIAdapter(mock=True)
    graph = build_chat_graph(adapter, store)

    state.user_request = "我想写一个月球城市失忆工程师的悬疑科幻"
    state.messages.append({"role": "user", "content": state.user_request})
    result = graph.invoke(state.to_dict())

    assert result["director_action"] == "worldbuild"
    assert "月球城市" in result["worldbuilding"]

    result["user_request"] = "保存当前结果"
    result["messages"].append({"role": "user", "content": "保存当前结果"})
    saved = graph.invoke(result)

    assert saved["director_action"] == "persist_outputs"
    assert store.worldbuilding_path("demo").exists()


class DirectorThenFailingAgentAdapter:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, workspace):
        self.calls += 1
        if self.calls == 1:
            return "ACTION: worldbuild\nMESSAGE: 我先调度世界观 Agent。\nCHAPTER:"
        raise CodexCLIError("Codex CLI timed out after 30s")


def test_chat_graph_reports_selected_agent_error(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    graph = build_chat_graph(DirectorThenFailingAgentAdapter(), store)

    state.user_request = "我想写一本梦境副本升级小说"
    state.messages.append({"role": "user", "content": state.user_request})
    result = graph.invoke(state.to_dict())

    assert result["review_status"] == "error"
    assert result["error"] == "Codex CLI timed out after 30s"
    assert "世界观设定 Agent 执行失败" in result["director_message"]
    assert "已完成" not in result["director_message"]


def test_chat_status_shows_generated_but_unsaved_artifact_path(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.worldbuilding = "# 世界观"
    state.user_request = "生成到哪里了呀"
    state.messages.append({"role": "user", "content": state.user_request})
    graph = build_chat_graph(CodexCLIAdapter(mock=True), store)

    result = graph.invoke(state.to_dict())

    assert result["director_action"] == "show_status"
    assert "世界观：已生成但未保存" in result["director_message"]
    assert str(store.worldbuilding_path("demo")) in result["director_message"]


def test_chat_graph_routes_write_and_review(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    adapter = CodexCLIAdapter(mock=True)
    graph = build_chat_graph(adapter, store)

    state.user_request = "写第 1 章"
    state.messages.append({"role": "user", "content": state.user_request})
    written = graph.invoke(state.to_dict())

    assert written["director_action"] == "write_chapter"
    assert written["current_chapter"] == 1
    assert "空白手稿" in written["chapter_draft"]

    written["user_request"] = "让编辑审稿"
    written["messages"].append({"role": "user", "content": "让编辑审稿"})
    reviewed = graph.invoke(written)

    assert reviewed["director_action"] == "review"
    assert reviewed["editor_decision"] in {"pass", "revise"}
    assert reviewed["quality_score"] > 0
