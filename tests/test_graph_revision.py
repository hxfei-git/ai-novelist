import json

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_drafting import build_drafting_graph
from ai_novelist.graph_review import build_review_graph
from ai_novelist.graph_revision import build_revision_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def prepared_review(tmp_path, max_revisions=1):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    state.current_chapter = 1
    state.max_revisions = max_revisions
    state = NovelState.from_dict(build_drafting_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))
    state = NovelState.from_dict(build_review_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))
    return store, state


def test_revision_generates_plan_and_draft_v2(tmp_path):
    store, state = prepared_review(tmp_path)

    result = NovelState.from_dict(build_revision_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))

    assert store.revision_plan_path("demo", 1, 1).exists()
    assert store.chapter_draft_path("demo", 1, 2).exists()
    assert store.chapter_path("demo", 1).exists()
    assert result.revision_count == 1
    assert "revision_plan_v1" in result.current_revision_plan
    plan = json.loads(result.current_revision_plan)["revision_plan_v1"]
    assert 1 <= len(plan["tasks"]) <= 8
    assert all("source" in item for item in plan["tasks"])
    assert all("review_v1.json" in item["source"] for item in plan["tasks"])
    self_check = json.loads(result.director_task_args["revision_self_check"])
    assert set(self_check) == {"tasks_status", "new_risks", "decision"}
    assert self_check["decision"] == "pass"
    assert len(self_check["new_risks"]) <= 5
    assert any(item["type"] == "revision_plan" and item["graph"] == "revision" for item in result.artifact_registry)
    assert any(item["type"] == "chapter_draft" and item["graph"] == "revision" for item in result.artifact_registry)


def test_revision_stops_at_max_revisions(tmp_path):
    store, state = prepared_review(tmp_path, max_revisions=0)

    result = NovelState.from_dict(build_revision_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))

    assert result.review_status == "stopped"
    assert "最大修订次数" in result.director_message
    assert not store.chapter_draft_path("demo", 1, 2).exists()

class AlwaysFailAdapter:
    def complete(self, prompt, workspace, options=None):
        from ai_novelist.adapters.base import AgentAdapterError

        raise AgentAdapterError("revision agent failed")


def test_revision_agent_failure_does_not_save_revised_draft(tmp_path):
    store, state = prepared_review(tmp_path)

    result = NovelState.from_dict(build_revision_graph(AlwaysFailAdapter(), store).invoke(state.to_dict()))

    assert result.review_status == "error"
    assert result.error == "revision agent failed"
    assert not store.revision_plan_path("demo", 1, 1).exists()
    assert not store.chapter_draft_path("demo", 1, 2).exists()
    assert store.load_state("demo").review_status == "error"
