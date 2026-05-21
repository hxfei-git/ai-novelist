from argparse import Namespace

from ai_novelist.cli import make_search_backend, should_use_research_graph, should_use_outline_graph
from ai_novelist.graph_research import build_research_graph, detect_research_need_text
from ai_novelist.graph_outline import build_outline_collaboration_graph
from ai_novelist.config import Settings
from ai_novelist.research import (
    LocalFirstSearchBackend,
    LocalRAGSearchBackend,
    MockSearchBackend,
    SearchBackendError,
    SearchResult,
    WebSearchBackend,
)
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore
from ai_novelist.adapters.base import AgentAdapterError
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
    assert result.retrieval_query == "苟在初圣"
    assert result.retrieval_sources == result.research_sources
    assert "# 检索上下文" in result.retrieval_context
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
    assert outlined["retrieval_context"]
    assert outlined["canon_facts"]


class FailingSearchBackend:
    def search(self, query: str, limit: int = 5):
        raise SearchBackendError("provider failed")


def test_research_graph_records_search_backend_error(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "/research 不存在作品"
    graph = build_research_graph(FailingSearchBackend(), store)

    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    assert result.review_status == "error"
    assert result.error == "provider failed"
    assert result.active_workflow == ""
    assert "参考调研失败" in result.director_message
    assert not store.reference_brief_path("demo").exists()


def test_make_search_backend_uses_mock_when_chat_mock_enabled():
    args = Namespace(mock=True, search_provider="serpapi")
    settings = Settings(search_provider="serpapi", search_api_key="key")

    assert isinstance(make_search_backend(args, settings), MockSearchBackend)


def test_make_search_backend_uses_configured_web_provider():
    args = Namespace(mock=False, search_provider=None)
    settings = Settings(search_provider="tavily", search_api_key="key", search_timeout_seconds=9)

    backend = make_search_backend(args, settings)

    assert isinstance(backend, WebSearchBackend)
    assert backend.provider == "tavily"
    assert backend.timeout_seconds == 9


def test_make_search_backend_wraps_cli_local_corpus_dir(tmp_path):
    args = Namespace(mock=True, search_provider=None, local_corpus_dir=str(tmp_path))
    settings = Settings()

    backend = make_search_backend(args, settings)

    assert isinstance(backend, LocalFirstSearchBackend)


def test_make_search_backend_wraps_env_local_corpus_dir(tmp_path):
    args = Namespace(mock=False, search_provider="mock", local_corpus_dir=None)
    settings = Settings(local_corpus_dir=str(tmp_path))

    backend = make_search_backend(args, settings)

    assert isinstance(backend, LocalFirstSearchBackend)


def test_research_graph_prefers_local_results_without_fallback(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "chapter.md").write_text("月影城主角依靠静默钟塔隐藏身份。", encoding="utf-8")
    store = LocalStore(tmp_path / "projects")
    state = store.create_project("Demo", "demo")
    state.user_request = "/research 月影城"
    fallback = CountingSearchBackend()
    backend = LocalFirstSearchBackend(LocalRAGSearchBackend(corpus), fallback)
    graph = build_research_graph(backend, store)

    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    assert result.research_sources[0]["source"] == "local_corpus"
    assert result.research_sources[0]["metadata"]["relative_path"] == "chapter.md"
    assert fallback.calls == 0


def test_research_graph_falls_back_when_local_misses(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "chapter.md").write_text("这里没有目标关键词。", encoding="utf-8")
    store = LocalStore(tmp_path / "projects")
    state = store.create_project("Demo", "demo")
    state.user_request = "/research 月影城"
    fallback = CountingSearchBackend()
    backend = LocalFirstSearchBackend(LocalRAGSearchBackend(corpus), fallback)
    graph = build_research_graph(backend, store)

    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    assert result.research_sources[0]["source"] == "mock_counting"
    assert fallback.calls == 1


class CountingSearchBackend:
    def __init__(self):
        self.calls = 0

    def search(self, query: str, limit: int = 5):
        self.calls += 1
        return [
            SearchResult(title="fallback", url="mock://fallback", snippet=query, source="mock_counting")
        ]


class RetrievalSummaryAdapter:
    def __init__(self):
        self.prompts = []

    def complete(self, prompt, workspace):
        self.prompts.append(prompt)
        return "# LLM 检索上下文\n\n## 可用事实\n- LLM 提炼后的事实"


class FailingRetrievalSummaryAdapter:
    def complete(self, prompt, workspace):
        raise AgentAdapterError("summary failed")


def test_research_graph_uses_llm_to_synthesize_retrieval_context(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "/research 苟在初圣"
    adapter = RetrievalSummaryAdapter()
    graph = build_research_graph(MockSearchBackend(), store, adapter=adapter)

    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    assert adapter.prompts
    assert "AGENT: retrieval_context_synthesizer" in adapter.prompts[0]
    assert "苟在初圣" in adapter.prompts[0]
    assert result.retrieval_context.startswith("# LLM 检索上下文")
    assert "## 通用检索上下文" in result.reference_brief


def test_research_graph_falls_back_when_llm_summary_fails(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "/research 苟在初圣"
    graph = build_research_graph(MockSearchBackend(), store, adapter=FailingRetrievalSummaryAdapter())

    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    assert result.review_status == "draft"
    assert "# 检索上下文：苟在初圣" in result.retrieval_context
    assert "LLM 检索总结失败" in result.retrieval_context
    assert result.reference_brief
