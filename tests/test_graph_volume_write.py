import json
from pathlib import Path

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_volume_write import build_volume_revision_graph, build_volume_write_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


CHAPTER_OUTLINE = """## 章节大纲稿

### 第一卷：月面醒来

#### 卷内章节总体规划
- 第 1-2 章建立月球城市、维修站异常和东七气闸倒计时。

#### 章节列表总表
| 章节 | 标题 | profile | PacingTarget | 一句话概括 | 结尾状态 |
| --- | --- | --- | --- | --- | --- |
| 第 1 章 | 空白手稿 | 铺垫章 | function=setup, intensity=3, hook=soft | 主角在维修站醒来并发现异常记录。 | 留下审计编号异常。 |
| 第 2 章 | 气闸倒计时 | 推进章 | function=turn, intensity=4, hook=hard | 主角追查东七气闸倒计时。 | 危机升级。 |

### 第二卷：地底档案

#### 章节列表总表
| 第 3 章 | 档案门 | 推进章 | function=turn | 进入地底档案。 | 新问题。 |
"""


def seed_project(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.outline_stage_artifacts["chapter_outline"] = {"summary": CHAPTER_OUTLINE}
    store.save_outline_artifact(state, "chapter_outline", CHAPTER_OUTLINE)
    store.save_state(state)
    return store, state


def test_volume_write_generates_volume_chapters_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    store, state = seed_project(tmp_path)
    state.director_task_args = {"volume": 1}
    store.save_state(state)

    result = NovelState.from_dict(build_volume_write_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))

    assert result.director_action == "write_volume"
    assert result.active_graph == "volume_write"
    assert result.active_stage == "ready_for_human_review"
    assert store.chapter_draft_path("demo", 1, 1).exists()
    assert store.chapter_draft_path("demo", 1, 2).exists()
    assert store.chapter_draft_path("demo", 2, 2).exists()
    assert not store.chapter_draft_path("demo", 3, 1).exists()
    manifest = next((tmp_path / "demo" / "chapters" / "batches" / "volume_001").glob("*/manifest.json"))
    assert manifest.exists()


def test_volume_revision_uses_human_notes_and_saves_new_versions(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    store, state = seed_project(tmp_path)
    state.director_task_args = {"volume": 1}
    state = NovelState.from_dict(build_volume_write_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))
    notes = tmp_path / "notes.md"
    notes.write_text("请强化两章之间的倒计时承接。\n", encoding="utf-8")
    state.director_task_args = {"volume": 1, "notes_path": str(notes)}
    store.save_state(state)

    result = NovelState.from_dict(build_volume_revision_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))

    assert result.director_action == "revise_volume"
    assert result.active_graph == "volume_revision"
    assert result.active_stage == "human_revision_done"
    assert store.chapter_draft_path("demo", 1, 3).exists()
    assert store.chapter_draft_path("demo", 2, 3).exists()
    manifest = next((tmp_path / "demo" / "chapters" / "batches" / "volume_001").glob("*/human_revision_manifest.json"))
    assert manifest.exists()


def test_volume_write_appends_new_draft_versions_on_rerun(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    store, state = seed_project(tmp_path)
    state.director_task_args = {"volume": 1}
    store.save_state(state)

    first = NovelState.from_dict(build_volume_write_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))
    first.director_task_args = {"volume": 1}
    store.save_state(first)

    result = NovelState.from_dict(build_volume_write_graph(CodexCLIAdapter(mock=True), store).invoke(first.to_dict()))

    assert store.chapter_draft_path("demo", 1, 1).exists()
    assert store.chapter_draft_path("demo", 1, 2).exists()
    assert store.chapter_draft_path("demo", 1, 3).exists()
    assert store.chapter_draft_path("demo", 1, 4).exists()
    assert store.chapter_draft_path("demo", 2, 4).exists()
    assert result.director_task_args["batch_latest_drafts"]["1"]["version"] == 4
    assert result.director_task_args["batch_latest_drafts"]["2"]["version"] == 4


def test_volume_write_records_direct_context_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.director_task_args = {"volume": 1, "chapters": "1"}
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "synthesis": "#### 第 1 章：开局\n- 第一章专属大纲。",
    }
    store.save_state(state)

    result = build_volume_write_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict())

    manifest = result["director_task_args"].get("direct_chapter_context_manifest")
    assert isinstance(manifest, list)
    assert any(item.get("section") == "章节大纲切片" for item in manifest)
    assert result["director_task_args"].get("direct_chapter_context_manifest_chapter") == 1
    assert sorted(result["director_task_args"].get("batch_context_manifests", {})) == ["1"]


def test_volume_write_records_per_chapter_context_manifests_without_single_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    store, state = seed_project(tmp_path)
    state.director_task_args = {"volume": 1}
    store.save_state(state)

    result = build_volume_write_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict())

    args = result["director_task_args"]
    batch_context_manifests = args.get("batch_context_manifests")
    assert sorted(batch_context_manifests) == ["1", "2"]
    assert all(any(item.get("section") == "章节大纲切片" for item in manifest) for manifest in batch_context_manifests.values())
    assert "direct_chapter_context_manifest" not in args
    assert "direct_chapter_context_manifest_chapter" not in args


def test_volume_batch_manifest_includes_context_manifests(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    store, state = seed_project(tmp_path)
    state.director_task_args = {"volume": 1}
    store.save_state(state)

    build_volume_write_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict())

    manifest_path = next((tmp_path / "demo" / "chapters" / "batches" / "volume_001").glob("*/manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert sorted(manifest.get("context_manifests", {})) == ["1", "2"]
    assert all(
        any(item.get("section") == "章节大纲切片" for item in chapter_manifest)
        for chapter_manifest in manifest["context_manifests"].values()
    )
