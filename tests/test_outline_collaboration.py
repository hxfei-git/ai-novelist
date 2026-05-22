from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.artifacts import load_artifacts
from ai_novelist.graph_outline import build_outline_stage_role_prompt, build_outline_stage_synthesizer_prompt, extract_stage_confirmation_questions, format_stage_markdown, append_message, build_outline_collaboration_graph, build_outline_prompt
from ai_novelist.graph_writer import build_chat_graph
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def run_outline_turn(graph, state, store, text):
    state.user_request = text
    state.last_user_feedback = text
    append_message(state, "user", text)
    store.save_state(state)
    return NovelState.from_dict(graph.invoke(state.to_dict()))


def test_outline_collaboration_generates_only_first_stage(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "请生成大纲")

    assert state.outline_stage == "direction"
    assert state.outline_stage_status == "options_ready"
    assert "direction" in state.outline_stage_artifacts
    assert "黑暗悬疑科幻" in state.outline_stage_artifacts["direction"]["synthesis"]
    assert not state.outline
    assert not store.outline_path("demo").exists()
    assert store.outline_stage_path("demo", "direction").exists()
    assert store.outline_artifact_path("demo", "direction").exists()
    records = load_artifacts(store.project_dir("demo"))
    assert any(item.type == "direction" and item.stage == "direction" and item.path == "outline/direction.md" for item in records)


def test_outline_confirmation_advances_one_stage(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "请生成大纲")
    state = run_outline_turn(graph, state, store, "确认进入下一阶段")

    assert state.outline_stage == "concept"
    assert state.outline_stage_status == "options_ready"
    assert state.outline_stage_artifacts["direction"]["status"] == "locked"
    assert "concept" in state.outline_stage_artifacts
    assert store.outline_artifact_path("demo", "concept").exists()
    assert not store.outline_path("demo").exists()


def test_outline_feedback_stays_on_current_stage(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "请生成大纲")
    state = run_outline_turn(graph, state, store, "方向太普通，强化主角罪感，第三幕更黑暗")

    assert state.director_action == "run_outline_stage"
    assert state.outline_stage == "direction"
    assert state.outline_stage_status == "options_ready"
    assert not state.outline
    assert not store.outline_path("demo").exists()


def test_outline_collaboration_lock_persists_constraints(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "这个设定别改：主角是失忆工程师，世界观规则不要改")

    assert state.director_intent == "lock"
    assert state.locked_constraints
    assert "失忆工程师" in state.locked_constraints[0]


def test_eight_stage_confirmation_persists_final_outline_and_artifacts(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "生成大纲")
    expected_stages = [
        "direction",
        "concept",
        "worldbuilding",
        "characters",
        "story_flow",
        "volume_outline",
        "chapter_outline",
        "review_lock",
    ]
    for _ in range(8):
        state = run_outline_turn(graph, state, store, "确认进入下一阶段")

    assert state.outline_stage == "done"
    assert state.outline_stage_status == "done"
    assert state.review_status == "approved"
    assert "最终锁定总大纲" in state.outline
    assert "故事概念" in state.outline
    assert "分卷大纲" in state.outline
    assert "章节大纲" in state.outline
    assert store.outline_path("demo").exists()
    records = load_artifacts(store.project_dir("demo"))
    for stage in expected_stages:
        assert store.outline_stage_path("demo", stage).exists()
        assert store.outline_artifact_path("demo", stage).exists()
        assert any(item.type == stage and item.stage == stage and item.graph == "outline" for item in records)


def test_outline_stage_view_can_show_story_flow(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "生成大纲")
    state = run_outline_turn(graph, state, store, "确认进入下一阶段")
    state = run_outline_turn(graph, state, store, "确认进入下一阶段")
    state = run_outline_turn(graph, state, store, "确认进入下一阶段")
    state = run_outline_turn(graph, state, store, "确认进入下一阶段")
    state = run_outline_turn(graph, state, store, "查看故事流程")

    assert state.director_action == "show_outline_stage"
    assert "故事流程" in state.director_message


def test_old_state_json_missing_new_fields_still_loads():
    state = NovelState.from_dict({"project_id": "old", "title": "Old"})

    assert state.messages == []
    assert state.locked_constraints == []
    assert state.style_preferences == []
    assert state.outline_versions == []
    assert state.selected_outline_version == -1
    assert state.retrieval_context == ""
    assert state.retrieval_query == ""
    assert state.retrieval_sources == []
    assert state.outline_stage == "direction"
    assert state.outline_stage_status == "collecting"


def test_old_outline_draft_state_loads_as_volume_outline_and_advances(tmp_path):
    store = LocalStore(tmp_path)
    project_dir = store.project_dir("old")
    project_dir.mkdir(parents=True)
    store.chapters_dir("old").mkdir()
    store.outline_stages_dir("old").mkdir()
    store.state_path("old").write_text(
        '{"project_id":"old","title":"Old","outline_stage":"outline_draft","outline_stage_artifacts":{"outline_draft":{"stage":"outline_draft","label":"总大纲草案","status":"options_ready","synthesis":"旧总纲"}}}\n',
        encoding="utf-8",
    )
    state = store.load_state("old")
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    assert state.outline_stage == "volume_outline"
    assert "volume_outline" in state.outline_stage_artifacts

    state = run_outline_turn(graph, state, store, "确认进入下一阶段")

    assert state.outline_stage == "chapter_outline"
    assert state.outline_stage_artifacts["volume_outline"]["status"] == "locked"


def test_chat_routes_outline_request_to_stage_flow(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_chat_graph(CodexCLIAdapter(mock=True), store)

    state.user_request = "生成大纲"
    state.messages.append({"role": "user", "content": state.user_request})
    result = graph.invoke(state.to_dict())

    assert result["director_action"] == "run_outline_stage"
    assert result["outline_stage"] == "direction"
    assert result["outline_stage_status"] == "options_ready"
    assert result["outline"] == ""


def test_outline_prompt_injects_retrieval_context():
    state = NovelState(project_id="demo", title="Demo")
    state.idea = "写同人"
    state.retrieval_query = "苟在初圣"
    state.retrieval_context = "# 检索上下文\n- 低调求生"
    state.retrieval_sources = [{"title": "资料", "url": "https://example.test", "source": "test"}]

    prompt = build_outline_prompt(state, "outline_planner")

    assert "检索查询：苟在初圣" in prompt
    assert "# 检索上下文" in prompt
    assert "资料 (test): https://example.test" in prompt


def test_direction_stage_markdown_hides_role_reviews():
    markdown = format_stage_markdown(
        {
            "stage": "direction",
            "label": "方向定位",
            "user_feedback": "偏悬疑推理线",
            "synthesis": "## 方向定位稿\n\n重生魔门悬疑智斗。",
            "role_reviews": [{"role": "风险编辑 Agent", "content": "机会、风险、建议"}],
        }
    )

    assert "## 方向控制稿" in markdown
    assert "## 角色短评" not in markdown
    assert "风险编辑 Agent" not in markdown


def test_direction_synthesizer_prompt_demands_control_brief():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    prompt = build_outline_stage_synthesizer_prompt(state, "direction", [])

    assert "方向定位不是评审报告" in prompt
    assert "整合成一版新的方向定位稿" in prompt
    assert "不要追加、罗列或保留历史修改记录" in prompt
    assert "## 方向定位稿" in prompt
    assert "全书开篇切入、中期升级、后期终局" in prompt
    assert "不能只写开篇局面" in prompt
    assert "## 一句话方向" not in prompt
    assert "## 方向命令" not in prompt
    assert "## 不许跑偏" not in prompt
    assert "下一阶段输入" not in prompt


def test_non_direction_synthesizer_prompt_avoids_fake_choice_menu():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    prompt = build_outline_stage_synthesizer_prompt(state, "characters", [])

    assert "不要输出让用户误以为必须逐项选择" in prompt
    assert "## 已采用设定" in prompt
    assert "## 仍需确认的问题" in prompt
    assert "候选项或决策" not in prompt


def test_worldbuilding_prompt_uses_saved_direction_context():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "label": "方向定位",
        "status": "options_ready",
        "synthesis": "## 方向定位稿\n\n主角以低调求生方式追查师傅吞噬气运。",
    }

    prompt = build_outline_stage_role_prompt(state, "worldbuilding", "规则架构 Agent")

    assert "前序已保存阶段内容" in prompt
    assert "方向定位（options_ready）" in prompt
    assert "主角以低调求生方式追查师傅吞噬气运" in prompt
    assert "世界观必须承接方向定位和故事概念" in prompt


def test_characters_prompt_uses_direction_and_worldbuilding_context():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "label": "方向定位",
        "status": "locked",
        "synthesis": "黑暗魔门悬疑智斗。",
    }
    state.outline_stage_artifacts["worldbuilding"] = {
        "stage": "worldbuilding",
        "label": "世界观设定",
        "status": "options_ready",
        "synthesis": "气运可以被观测、借贷和吞噬。",
    }

    prompt = build_outline_stage_synthesizer_prompt(state, "characters", [])

    assert "方向定位（locked）" in prompt
    assert "黑暗魔门悬疑智斗" in prompt
    assert "世界观设定（options_ready）" in prompt
    assert "气运可以被观测、借贷和吞噬" in prompt
    assert "人物关系必须承接方向定位、故事概念和世界观规则" in prompt


def test_story_flow_prompt_uses_all_prior_stage_contexts():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")
    state.outline_stage_artifacts["direction"] = {"stage": "direction", "status": "locked", "synthesis": "低调求生追查真相。"}
    state.outline_stage_artifacts["worldbuilding"] = {"stage": "worldbuilding", "status": "locked", "synthesis": "气运规则造成修行代价。"}
    state.outline_stage_artifacts["characters"] = {"stage": "characters", "status": "options_ready", "synthesis": "师徒关系隐藏吞噬冲突。"}

    prompt = build_outline_stage_role_prompt(state, "story_flow", "主线结构 Agent")

    assert "低调求生追查真相" in prompt
    assert "气运规则造成修行代价" in prompt
    assert "师徒关系隐藏吞噬冲突" in prompt
    assert "故事流程必须承接方向定位、故事概念、世界观代价和人物关系冲突" in prompt


def test_current_stage_draft_enters_synthesizer_prompt():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "label": "人物关系",
        "status": "options_ready",
        "synthesis": "魔宗圣女与主角互相试探，剑宗天才少女负责外部审判。",
    }

    prompt = build_outline_stage_synthesizer_prompt(state, "characters", [])

    assert "当前阶段已有内容" in prompt
    assert "人物关系（options_ready）" in prompt
    assert "魔宗圣女与主角互相试探" in prompt
    assert "剑宗天才少女负责外部审判" in prompt


def test_extract_stage_confirmation_questions_from_synthesis():
    markdown = """## Director 汇总
人物关系已整理。

## 已采用设定
魔宗圣女诱惑但保守。

## 仍需确认的问题
1. 魔宗圣女的保守来源是心魔誓约还是派系规则？
2. 剑宗圣女事件是否发生在葬魂谷？
"""

    questions = extract_stage_confirmation_questions(markdown)

    assert questions == [
        "魔宗圣女的保守来源是心魔誓约还是派系规则？",
        "剑宗圣女事件是否发生在葬魂谷？",
    ]


def test_direction_stage_markdown_integrates_without_feedback_dump():
    markdown = format_stage_markdown(
        {
            "stage": "direction",
            "label": "方向定位",
            "user_feedback": "师傅暗中吞噬主角气运",
            "synthesis": "整理后的方向定位",
        }
    )

    assert "## 用户本轮反馈" not in markdown
    assert "师傅暗中吞噬主角气运" not in markdown
    assert "整理后的方向定位" in markdown
