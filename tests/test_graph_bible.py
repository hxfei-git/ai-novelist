from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.artifacts import load_artifacts, save_markdown_artifact
from ai_novelist.bible import CharacterCard, NovelBible, WorldRule, load_bible, save_bible
from ai_novelist.graph_bible import build_bible_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def add_outline_artifacts(store: LocalStore, state: NovelState) -> None:
    stages = {
        "direction": "# 方向定位\n\n黑暗悬疑科幻，失忆工程师追查旧罪。",
        "concept": "# 故事概念\n\n纸质手稿预言事故，核心冲突是求生与公开旧罪。",
        "worldbuilding": "# 世界观\n\n记忆审计、纸质手稿、月背冷库。",
        "characters": "# 人物\n\n林澈、许岚、沈博士。",
        "story_flow": "# 故事流程\n\n异常手稿、冷库追查、公开自证。",
        "volume_outline": "# 分卷大纲\n\n三卷结构。",
        "chapter_outline": "# 章节大纲\n\n12 章结构。",
        "review_lock": "# 审稿锁定\n\n八阶段连续。",
    }
    for stage, content in stages.items():
        state.outline_stage_artifacts[stage] = {
            "stage": stage,
            "label": stage,
            "status": "locked",
            "synthesis": content,
        }
        save_markdown_artifact(
            store.project_dir(state.project_id),
            f"outline/{stage}.md",
            content,
            stage,
            stage=stage,
            graph="outline",
            source_agent="outline_stage_synthesizer",
        )
    state.outline = "# 最终锁定总大纲\n\n" + "\n\n".join(stages.values())
    state.outline_stage = "done"
    state.outline_stage_status = "done"
    store.save_state(state)


def test_bible_graph_initializes_from_outline_artifacts(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    add_outline_artifacts(store, state)
    graph = build_bible_graph(CodexCLIAdapter(mock=True), store)

    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    bible = load_bible(store.project_dir("demo"))
    assert store.novel_bible_json_path("demo").exists()
    assert store.novel_bible_markdown_path("demo").exists()
    assert bible.project.genre == "科幻悬疑"
    assert bible.concept.logline
    assert any(item.name == "林澈" for item in bible.characters)
    assert result.bible_version == bible.version
    assert result.bible_updated_at


def test_bible_graph_registers_artifact(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    add_outline_artifacts(store, state)

    result = NovelState.from_dict(build_bible_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))

    records = load_artifacts(store.project_dir("demo"))
    assert any(
        item.type == "novel_bible"
        and item.path == "novel_bible.md"
        and item.graph == "bible"
        and item.stage == "bible_update"
        and item.source_agent == "bible_update_synthesizer"
        for item in records
    )
    assert any(item.get("type") == "novel_bible" for item in result.artifact_registry)


def test_bible_graph_conflicts_do_not_block_mock_flow(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    add_outline_artifacts(store, state)
    bible = NovelBible()
    bible.characters.append(CharacterCard(name="林澈", role="反派"))
    bible.world_rules.append(WorldRule(name="记忆审计", description="记忆可以随意重写。"))
    save_bible(store.project_dir("demo"), bible)

    result = NovelState.from_dict(build_bible_graph(CodexCLIAdapter(mock=True), store).invoke(state.to_dict()))
    updated = load_bible(store.project_dir("demo"))

    assert result.director_message.startswith("小说圣经已更新")
    assert updated.open_questions
    assert any(report.get("agent") == "bible_conflict_checker" for report in result.last_agent_reports)
