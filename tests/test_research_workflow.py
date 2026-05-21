from ai_novelist.cli import should_use_research_graph, should_use_outline_graph
from ai_novelist.graph_research import build_research_graph, detect_research_need_text
from ai_novelist.graph_outline import build_outline_collaboration_graph
from ai_novelist.research import MockSearchBackend
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore
from ai_novelist.adapters.codex_cli import CodexCLIAdapter


def test_detect_research_need_for_fanfic_and_slash_command():
    assert detect_research_need_text("写苟在初圣同人", has_reference_brief=False)
    assert detect_research_need_text("苟在初圣", has_reference_brief=False)
    assert detect_research_need_text("/research 苟在初圣", has_reference_brief=True)
    assert not detect_research_need_text("写原创月球城市悬疑", has_reference_brief=False)
    assert not detect_research_need_text("写苟在初圣同人", has_reference_brief=True)


def test_research_graph_persists_reference_brief_and_sources(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "写苟在初圣同人"
    events = []
    graph = build_research_graph(MockSearchBackend(), store, progress=lambda stage, message: events.append((stage, message)))

    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    assert result.director_action == "research"
    assert result.active_workflow == "outline"
    assert result.current_stage == "confirm_reference_brief"
    assert "苟在初圣" in result.reference_brief
    assert result.canon_facts
    assert result.research_sources
    assert result.research_uncertainties
    assert store.reference_brief_path("demo").exists()
    assert store.research_sources_path("demo").exists()
    assert events[0] == ("Research", "正在识别需要调研的原作信息...")
    assert events[1][0] == "Search"


def test_chat_routing_prefers_research_before_outline(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "写苟在初圣同人"

    assert should_use_research_graph(state, state.user_request)
    state.reference_brief = "# 参考简报"
    assert not should_use_research_graph(state, state.user_request)


def test_research_then_outline_prompt_contains_reference_brief(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "写苟在初圣同人"
    research_graph = build_research_graph(MockSearchBackend(), store)
    researched = NovelState.from_dict(research_graph.invoke(state.to_dict()))

    assert should_use_outline_graph(researched, "给我三个方向")
    researched.user_request = "给我三个方向"
    outline_graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)
    outlined = outline_graph.invoke(researched.to_dict())

    assert outlined["director_action"] == "propose_directions"
    assert outlined["reference_brief"]
    assert outlined["canon_facts"]
