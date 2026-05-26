from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_drafting import build_drafting_graph
from ai_novelist.graph_writer import build_writer_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


CHAPTER_OUTLINE = """## 章节大纲稿

### 第一卷

#### 卷内章节总体规划
- 本卷建立月球城市、失忆工程师和维修站异常。

#### 章节列表总表
| 章节 | 标题 | profile | PacingTarget | 一句话概括 | 结尾状态 |
| --- | --- | --- | --- | --- | --- |
| 第 1 章 | 空白手稿 | 铺垫章 | function=setup, intensity=3, hook=soft | 主角在维修站醒来并发现异常记录。 | 留下审计编号异常。 |
| 第 2 章 | 气闸倒计时 | 推进章 | function=turn, intensity=4, hook=hard | 主角追查东七气闸倒计时。 | 危机升级。 |
"""


def seed_chapter_outline(store: LocalStore, state: NovelState) -> None:
    state.outline_stage_artifacts["chapter_outline"] = {"summary": CHAPTER_OUTLINE}
    store.save_outline_artifact(state, "chapter_outline", CHAPTER_OUTLINE)
    store.save_state(state)


def test_drafting_uses_direct_chapter_outline_without_cards(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    state.current_chapter = 1
    seed_chapter_outline(store, state)

    result = NovelState.from_dict(build_drafting_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))

    assert not store.chapter_card_path("demo", 1).exists()
    assert not store.scene_cards_path("demo", 1).exists()
    assert store.chapter_draft_path("demo", 1, 1).exists()
    assert store.chapter_draft_path("demo", 1, 2).exists()
    assert store.chapter_path("demo", 1).exists()
    assert "修订版" in result.chapter_draft
    assert result.active_graph == "chapter_write"
    assert result.active_stage == "auto_revision"
    assert result.active_chapter == 1
    assert any(item["type"] == "chapter_draft" and item["graph"] == "chapter_write" for item in result.artifact_registry)


def test_legacy_write_chapter_wrapper_uses_direct_graph(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.current_chapter = 2
    seed_chapter_outline(store, state)

    result = build_writer_graph(
        CodexCLIAdapter(mock=True),
        store,
        "write_chapter",
        review_func=lambda _state, _task: "approve",
    ).invoke(state.to_dict())

    assert result["review_status"] == "approved"
    assert result["active_graph"] == "chapter_write"
    assert store.chapter_draft_path("demo", 2, 1).exists()
    assert store.chapter_draft_path("demo", 2, 2).exists()
    assert store.chapter_path("demo", 2).exists()


def test_drafting_reports_simplified_progress_events(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.current_chapter = 1
    seed_chapter_outline(store, state)
    events = []

    result = NovelState.from_dict(
        build_drafting_graph(
            CodexCLIAdapter(mock=True),
            store,
            progress=lambda stage, message: events.append((stage, message)),
        ).invoke(state.to_dict())
    )

    assert result.active_graph == "chapter_write"
    assert any(stage == "ChapterWrite 1/5" for stage, _message in events)
    assert any(stage == "ChapterWrite 5/5" for stage, _message in events)
    assert not any(stage.startswith("ChapterPlan") for stage, _message in events)
    assert not any(stage.startswith("SceneDesign") for stage, _message in events)


class AlwaysFailAdapter:
    def complete(self, prompt, workspace, options=None):
        from ai_novelist.adapters.base import AgentAdapterError

        raise AgentAdapterError("direct draft failed")


def test_drafting_failure_does_not_save_draft_or_cards(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    state.current_chapter = 1
    seed_chapter_outline(store, state)

    result = NovelState.from_dict(build_drafting_graph(AlwaysFailAdapter(), store).invoke(state.to_dict()))

    assert result.review_status == "error"
    assert result.error == "direct draft failed"
    assert not store.chapter_card_path("demo", 1).exists()
    assert not store.chapter_draft_path("demo", 1, 1).exists()
    assert store.load_state("demo").review_status == "error"
