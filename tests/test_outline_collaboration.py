from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_outline import append_message, build_outline_collaboration_graph
from ai_novelist.graph_writer import build_chat_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def run_outline_turn(graph, state, store, text):
    state.user_request = text
    state.last_user_feedback = text
    append_message(state, "user", text)
    store.save_state(state)
    return NovelState.from_dict(graph.invoke(state.to_dict()))


def test_outline_collaboration_approve_persists_outline(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "请生成大纲")
    assert state.outline
    assert state.review_status == "revision_requested"
    assert not store.outline_path("demo").exists()

    state = run_outline_turn(graph, state, store, "保存大纲")
    assert state.review_status == "approved"
    assert store.outline_path("demo").exists()


def test_outline_collaboration_revise_creates_new_version(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "请生成大纲")
    original_version_count = len(state.outline_versions)
    state = run_outline_turn(graph, state, store, "大纲太普通，强化主角罪感，第三幕更黑暗")

    assert state.director_action == "revise_outline"
    assert state.revision_count == 1
    assert len(state.outline_versions) > original_version_count
    assert "修订版总大纲" in state.outline
    assert "主角罪感" in state.revision_instruction
    assert state.editor_decision == "pass"


def test_outline_collaboration_lock_persists_constraints(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "这个设定别改：主角是失忆工程师，世界观规则不要改")

    assert state.director_intent == "lock"
    assert state.locked_constraints
    assert "失忆工程师" in state.locked_constraints[0]


def test_outline_editor_revise_does_not_persist_directly(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "生成大纲")

    assert state.editor_decision == "revise"
    assert state.review_status == "revision_requested"
    assert state.outline
    assert not store.outline_path("demo").exists()


def test_outline_variant_generates_directions_and_waits(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "variant: 给我三个不同方向")

    assert state.director_action == "propose_directions"
    assert state.next_action == "end"
    assert any(version.get("kind") == "directions" for version in state.outline_versions)
    assert not store.outline_path("demo").exists()


def test_old_state_json_missing_new_fields_still_loads():
    state = NovelState.from_dict({"project_id": "old", "title": "Old"})

    assert state.messages == []
    assert state.locked_constraints == []
    assert state.style_preferences == []
    assert state.outline_versions == []
    assert state.selected_outline_version == -1


def test_chat_routes_outline_revision_request(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    state.outline = "# 旧大纲\n主角追查手稿。"
    graph = build_chat_graph(CodexCLIAdapter(mock=True), store)

    state.user_request = "大纲太普通，强化主角罪感"
    state.messages.append({"role": "user", "content": state.user_request})
    result = graph.invoke(state.to_dict())

    assert result["director_action"] == "revise_outline"
    assert "强化主角罪感" in result["revision_instruction"]
    assert "修订版总大纲" in result["outline"]
    assert result["editor_decision"] == "pass"
