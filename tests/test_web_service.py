from __future__ import annotations

from pathlib import Path

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError, AgentCallOptions
from ai_novelist.storage.local_store import LocalStore
from ai_novelist.web import service


class DummyAdapter(AgentAdapter):
    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        if "global_consistency_repair" in prompt:
            return "# repaired chapter\n\n修复后的章节正文，保留原章节事件并补齐连续性。"
        return "{}"


class ModelReviewAdapter(AgentAdapter):
    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        assert "global_consistency_reviewer" in prompt
        assert "Chapter 1" in prompt
        return (
            '{"status":"needs_repair","summary":"模型发现连续性问题。",'
            '"issues":[{"severity":"serious","chapter":1,"category":"timeline",'
            '"message":"第 1 章结尾与第 2 章开场时间线冲突。"}]}'
        )


class FailingReviewAdapter(AgentAdapter):
    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        if "global_consistency_reviewer" in prompt:
            raise AgentAdapterError("model unavailable")
        return "{}"


def test_project_and_outline_stage_file_roundtrip(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = service.create_project(store, "Web Demo", "web-demo", idea="一个显式流程控制的小说项目")

    projects = service.list_projects(store)
    assert [item.project_id for item in projects] == ["web-demo"]
    assert store.load_state(state.project_id).idea == "一个显式流程控制的小说项目"

    saved = service.save_outline_stage_content(store, "web-demo", "worldbuilding", "# 世界观设定\n\n规则清晰。")
    assert saved["status"] == "options_ready"
    assert "规则清晰" in saved["content"]

    reloaded = store.load_state("web-demo")
    assert reloaded.outline_stage_artifacts["worldbuilding"]["status"] == "options_ready"
    assert "规则清晰" in store.load_outline_artifact("web-demo", "worldbuilding")
    assert "规则清晰" in store.worldbuilding_path("web-demo").read_text(encoding="utf-8")


def test_generate_outline_stage_uses_explicit_stage(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    store.create_project("Web Demo", "web-demo")
    captured = {}

    def fake_run(data: dict, adapter: AgentAdapter, local_store: LocalStore, progress=None) -> dict:
        captured.update(data)
        return data

    monkeypatch.setattr(service, "run_outline_stage_node", fake_run)

    state = service.generate_outline_stage(store, DummyAdapter(), "web-demo", "characters", "补强人物关系")

    assert captured["outline_stage"] == "characters"
    assert state.director_action == "run_outline_stage"
    assert state.user_request == "补强人物关系"


def test_chapter_batch_payload_sets_director_task_args(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    store.create_project("Web Demo", "web-demo")
    captured = {}

    class FakeGraph:
        def invoke(self, data: dict) -> dict:
            captured.update(data["director_task_args"])
            return data

    monkeypatch.setattr(service, "build_volume_write_graph", lambda adapter, store, progress=None: FakeGraph())

    service.generate_chapter_batch(store, DummyAdapter(), "web-demo", volume=2, chapters="1-3", max_workers=4)

    assert captured == {"volume": 2, "chapters": "1-3"}


def test_global_review_and_repair_are_explicit_apply(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.active_chapter = 1
    state.current_chapter = 1
    state.chapter_draft = "短"
    store.save_chapter_draft(state, version=1)
    original = store.chapter_draft_path("web-demo", 1, 1).read_text(encoding="utf-8")

    report = service.review_all_chapters(store, DummyAdapter(), "web-demo")
    assert report["status"] == "needs_repair"
    assert store.chapter_draft_path("web-demo", 1, 1).read_text(encoding="utf-8") == original

    proposals = service.generate_repair_proposals(store, DummyAdapter(), "web-demo", report["run_id"])
    assert proposals["proposals"][0]["chapter"] == 1
    proposed_path = store.project_dir("web-demo") / proposals["proposals"][0]["path"]
    assert proposed_path.exists()
    assert not store.chapter_draft_path("web-demo", 1, 2).exists()

    applied = service.apply_repair(store, "web-demo", 1, report["run_id"])
    assert applied["version"] == 2
    assert store.chapter_draft_path("web-demo", 1, 2).exists()


def test_chapter_list_and_detail_prefer_final_then_highest_draft_then_legacy(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")

    state.active_chapter = 1
    state.current_chapter = 1
    state.chapter_draft = "# 第 1 章草稿五\n\n这是第五版草稿正文，用于确认最高版本读取。"
    store.save_chapter_draft(state, version=5)
    state.current_final_chapter = "# 第 1 章定稿\n\n这是定稿正文，应该优先于所有草稿。"
    store.save_final_chapter(state)

    state.active_chapter = 2
    state.current_chapter = 2
    state.chapter_draft = "# 第 2 章草稿一\n\n旧草稿。"
    store.save_chapter_draft(state, version=1)
    state.chapter_draft = "# 第 2 章草稿十二\n\n最高编号草稿，应该被选为最新正文。"
    store.save_chapter_draft(state, version=12)

    state.active_chapter = 3
    state.current_chapter = 3
    state.chapter_draft = "# 第 3 章旧路径\n\n只有 legacy chapter_003.md 时也能读取。"
    store.save_chapter(state)

    chapters = service.list_chapters(store, "web-demo")

    assert [item["chapter"] for item in chapters] == [1, 2, 3]
    assert chapters[0]["source"] == "final"
    assert chapters[0]["version"] is None
    assert chapters[1]["source"] == "draft"
    assert chapters[1]["version"] == 12
    assert chapters[2]["source"] == "legacy"

    first = service.load_chapter_payload(store, "web-demo", 1)
    second = service.load_chapter_payload(store, "web-demo", 2)
    third = service.load_chapter_payload(store, "web-demo", 3)

    assert "定稿正文" in first["content"]
    assert first["path"] == "chapters/chapter_001/final.md"
    assert "最高编号草稿" in second["content"]
    assert second["path"] == "chapters/chapter_002/draft_v12.md"
    assert "旧路径" in third["content"]
    assert third["path"] == "chapters/chapter_003.md"

def test_global_review_uses_model_consistency_report(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    store.save_outline_artifact(state, "chapter_outline", "# 章节大纲\n\n第一章进入雨城，第二章当天夜里继续。")
    state.active_chapter = 1
    state.current_chapter = 1
    state.chapter_draft = "# 第 1 章\n\n" + "雨城的夜色压在港口上，主角追踪线索并在钟楼下确认了同伴留下的暗号。" * 4
    store.save_chapter_draft(state, version=1)

    report = service.review_all_chapters(store, ModelReviewAdapter(), "web-demo")

    assert report["status"] == "needs_repair"
    assert report["review_source"] == "model"
    assert report["summary"] == "模型发现连续性问题。"
    assert any(item["category"] == "timeline" for item in report["issues"])
    saved = service.latest_global_review(store, "web-demo")
    assert saved["run_id"] == report["run_id"]


def test_global_review_falls_back_to_local_scan_on_model_error(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.active_chapter = 1
    state.current_chapter = 1
    state.chapter_draft = "# 第 1 章\n\n" + "TODO：这里待补完整正文。" * 6
    store.save_chapter_draft(state, version=1)

    report = service.review_all_chapters(store, FailingReviewAdapter(), "web-demo")

    assert report["review_source"] == "local"
    assert any(item["category"] == "placeholder" for item in report["issues"])
    assert any(item["category"] == "model_review_error" for item in report["issues"])

