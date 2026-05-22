from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_outline import build_outline_stage_synthesizer_prompt, extract_stage_confirmation_questions, format_stage_markdown, append_message, build_outline_collaboration_graph, build_outline_prompt
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


def test_outline_confirmation_advances_one_stage(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "请生成大纲")
    state = run_outline_turn(graph, state, store, "确认进入下一阶段")

    assert state.outline_stage == "worldbuilding"
    assert state.outline_stage_status == "options_ready"
    assert state.outline_stage_artifacts["direction"]["status"] == "locked"
    assert "worldbuilding" in state.outline_stage_artifacts
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


def test_six_stage_confirmation_persists_final_outline(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "生成大纲")
    for _ in range(6):
        state = run_outline_turn(graph, state, store, "确认进入下一阶段")

    assert state.outline_stage == "done"
    assert state.outline_stage_status == "done"
    assert state.review_status == "approved"
    assert "最终锁定总大纲" in state.outline
    assert store.outline_path("demo").exists()


def test_outline_stage_view_can_show_story_flow(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "生成大纲")
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
            "synthesis": "## 一句话方向\n\n重生魔门悬疑智斗。",
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
    assert "整合成一版新的方向控制稿" in prompt
    assert "不要追加、罗列或保留历史修改记录" in prompt
    assert "## 一句话方向" in prompt
    assert "## 方向命令" in prompt
    assert "不写机会/风险/建议" in prompt


def test_non_direction_synthesizer_prompt_avoids_fake_choice_menu():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    prompt = build_outline_stage_synthesizer_prompt(state, "characters", [])

    assert "不要输出让用户误以为必须逐项选择" in prompt
    assert "## 已采用设定" in prompt
    assert "## 仍需确认的问题" in prompt
    assert "候选项或决策" not in prompt


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
