import json

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.artifacts import load_artifacts
from ai_novelist.graph_outline import OUTLINE_STAGES, build_outline_stage_role_prompt, build_outline_stage_synthesizer_prompt, extract_stage_confirmation_questions, format_stage_markdown, sanitize_direction_stage_output, append_message, build_outline_collaboration_graph, build_outline_prompt
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
    assert any(item.type == "direction_role_reviews" and item.stage == "direction" and item.path == "outline/debug/direction_role_reviews.md" for item in records)


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


def test_outline_collaboration_lock_stays_stage_local(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "这个设定别改：主角是失忆工程师，世界观规则不要改")

    assert state.director_intent == "lock"
    assert state.locked_constraints == []
    assert "失忆工程师" in state.revision_instruction


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
    assert store.novel_bible_json_path("demo").exists()
    assert store.novel_bible_markdown_path("demo").exists()
    records = load_artifacts(store.project_dir("demo"))
    for stage in expected_stages:
        assert store.outline_stage_path("demo", stage).exists()
        assert store.outline_artifact_path("demo", stage).exists()
        assert any(item.type == stage and item.stage == stage and item.graph == "outline" for item in records)
    assert any(item.type == "novel_bible" and item.graph == "bible" for item in records)


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

    assert state.director_action == "show_outline"
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

    assert markdown.count("## 方向定位稿") == 1
    assert "## 方向控制稿" not in markdown
    assert "# 方向定位" not in markdown.splitlines()
    assert "## 角色短评" not in markdown
    assert "风险编辑 Agent" not in markdown


def test_direction_synthesizer_prompt_demands_control_brief():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    prompt = build_outline_stage_synthesizer_prompt(state, "direction", [])

    assert "方向定位不是评审报告" in prompt
    assert "整合成一版新的方向定位稿" in prompt
    assert "不要追加、罗列或保留历史修改记录" in prompt
    assert "## 方向定位稿" in prompt
    assert "只写 6-8 条" in prompt
    assert "每条不超过 80 个中文字符" in prompt
    assert "类型定位、主角行动原则、核心爽点、核心冲突" in prompt
    for forbidden in ("申请表", "审批", "考评", "备案", "绩效", "KPI"):
        assert forbidden in prompt
    assert "不能只写开篇局面" in prompt
    assert "## 一句话方向" not in prompt
    assert "## 方向命令" not in prompt
    assert "## 不许跑偏" not in prompt
    assert "下一阶段输入" not in prompt


def test_non_direction_synthesizer_prompt_avoids_fake_choice_menu():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    prompt = build_outline_stage_synthesizer_prompt(state, "characters", [])

    assert "不输出候选菜单式 A/B/C" in prompt
    assert "## 人物关系稿" in prompt
    assert "与主线冲突的功能" in prompt
    assert "## 仍需确认的问题" in prompt
    assert "候选项或决策" not in prompt


def test_outline_role_prompts_include_stage_boundaries_for_all_stages():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    for stage in OUTLINE_STAGES:
        prompt = build_outline_stage_role_prompt(state, stage, "阶段 Agent")
        assert "STAGE_BOUNDARY" in prompt
        assert "允许输出" in prompt
        assert "禁止输出" in prompt
        assert "不越权生成其他阶段内容" in prompt
        assert "opportunities/risks/suggestions 各最多 2 条" in prompt
        assert "总输出不超过 500 中文字符" in prompt


def test_outline_synthesizer_prompts_use_stage_specific_structures():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    concept_prompt = build_outline_stage_synthesizer_prompt(state, "concept", [])
    world_prompt = build_outline_stage_synthesizer_prompt(state, "worldbuilding", [])
    chapter_prompt = build_outline_stage_synthesizer_prompt(state, "chapter_outline", [])

    assert "## 故事概念稿" in concept_prompt
    assert "## 世界运行原则" in world_prompt
    assert "## 章节大纲稿" in chapter_prompt
    assert "具体世界规则" in concept_prompt
    assert "完整人物小传" in world_prompt
    assert "正式正文" in chapter_prompt
    assert "完整场景卡" in chapter_prompt
    assert len({concept_prompt, world_prompt, chapter_prompt}) == 3


def test_concept_stage_prompt_limits_output_to_core_concept():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    role_prompt = build_outline_stage_role_prompt(state, "concept", "故事概念 Agent")
    synth_prompt = build_outline_stage_synthesizer_prompt(state, "concept", [])

    assert "故事钩子" in role_prompt
    assert "主角欲望" in role_prompt
    assert "核心冲突" in role_prompt
    assert "反转原则" in synth_prompt
    assert "待后续展开" in synth_prompt
    assert "只写 5-7 条短句" in synth_prompt
    assert "每条不超过 90 中文字符" in synth_prompt
    for forbidden in ("章节列表", "第1章", "第一卷", "世界规则清单", "组织流程", "人物亲密机制", "申请表", "审批", "备案", "绩效", "KPI"):
        assert forbidden in role_prompt or forbidden in synth_prompt
    assert "## 待后续展开" not in synth_prompt


def test_non_direction_formatter_does_not_duplicate_synthesis_heading():
    markdown = format_stage_markdown(
        {
            "stage": "characters",
            "label": "人物关系",
            "synthesis": "## 人物关系稿\n主角与圣女互相试探。",
        }
    )

    assert markdown.count("## 人物关系稿") == 1
    assert "## Director 汇总\n## 人物关系稿" not in markdown
    assert markdown.startswith("# 人物关系")


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


def test_worldbuilding_prompt_blocks_default_administrative_mechanisms():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    role_prompt = build_outline_stage_role_prompt(state, "worldbuilding", "规则架构 Agent")
    synth_prompt = build_outline_stage_synthesizer_prompt(state, "worldbuilding", [])

    assert "世界运行原则" in role_prompt
    assert "力量/技术边界" in role_prompt
    assert "资源与代价" in role_prompt
    assert "冲突来源" in role_prompt
    assert "默认不要生成申请表、申请、审批、备案、考评、绩效或 KPI" in role_prompt
    assert "## 世界运行原则" in synth_prompt
    assert "## 关键边界" in synth_prompt
    assert "## 冲突资源" in synth_prompt
    assert "## 代价红线" in synth_prompt
    assert "6-8 条" in synth_prompt
    assert "每条不超过 100 中文字符" in synth_prompt
    assert "最多列 3 个阵营或资源冲突点" in synth_prompt
    for forbidden in ("申请表", "审批", "备案", "考评", "绩效", "KPI", "表格制度"):
        assert forbidden in role_prompt or forbidden in synth_prompt


def test_worldbuilding_prompt_preserves_user_requested_controlled_terms_as_principles():
    state = NovelState(project_id="demo", title="Demo", idea="职场绩效修仙")
    state.user_request = "世界观保留职场绩效修仙，但不要写成流水线表格。"

    prompt = build_outline_stage_synthesizer_prompt(state, "worldbuilding", [])

    assert "用户原始输入或锁定产物已明确包含：绩效" in prompt
    assert "可以保留这些词" in prompt
    assert "只能改写为服务主线冲突的世界运行原则" in prompt
    assert "不得扩写成申请/审批/备案/考评流程或表格制度" in prompt


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


def test_characters_prompt_requires_mainline_conflict_function():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    role_prompt = build_outline_stage_role_prompt(state, "characters", "关系冲突 Agent")
    synth_prompt = build_outline_stage_synthesizer_prompt(state, "characters", [])

    assert "主角缺陷与欲望" in role_prompt
    assert "关键人物目标" in role_prompt
    assert "阵营位置" in role_prompt
    assert "背叛/信任风险" in role_prompt
    assert "人物 / 目标 / 与主线冲突的功能 / 关系张力 / 弧光风险" in synth_prompt
    assert "主要人物 3-5 个" in synth_prompt
    assert "每字段不超过 60 中文字符" in synth_prompt
    assert "每个角色都必须有主线功能或冲突功能" in synth_prompt
    for forbidden in ("亲密行为", "双修审批", "道侣绩效", "道侣流程", "暧昧规则", "福利场景", "恋爱系统表格"):
        assert forbidden in role_prompt or forbidden in synth_prompt


def test_characters_prompt_preserves_user_requested_terms_as_conflict_function():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")
    state.user_request = "人物关系里保留道侣绩效这个黑色幽默方向，但别写福利场景。"

    prompt = build_outline_stage_synthesizer_prompt(state, "characters", [])

    assert "用户原始输入或锁定产物已明确包含：道侣绩效、福利场景" in prompt
    assert "可以保留这些词的方向" in prompt
    assert "必须改写为目标、动机、阵营位置或主线冲突功能" in prompt
    assert "不得生成亲密行为规则、道侣流程或福利场景" in prompt


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


def test_story_flow_prompt_limits_flow_to_narrative_structure():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    role_prompt = build_outline_stage_role_prompt(state, "story_flow", "主线结构 Agent")
    synth_prompt = build_outline_stage_synthesizer_prompt(state, "story_flow", [])

    assert "流程只表示叙事流程" in role_prompt
    assert "这里的“流程”只指叙事流程" in synth_prompt
    assert "阶段目标" in synth_prompt
    assert "关键转折" in synth_prompt
    assert "伏笔布置/回收方向" in synth_prompt
    assert "失败代价" in synth_prompt
    assert "三幕或四段结构" in synth_prompt
    assert "每段最多 4 个要点" in synth_prompt
    assert "每点不超过 90 中文字符" in synth_prompt
    for forbidden in ("完整章节正文", "细场景动作", "未确立新规则", "新增世界观 canon", "突然新增人物关系", "行政流程", "办理", "审批", "备案", "绩效", "申请表"):
        assert forbidden in role_prompt or forbidden in synth_prompt


def test_volume_outline_prompt_limits_output_to_volume_level():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    role_prompt = build_outline_stage_role_prompt(state, "volume_outline", "分卷策划 Agent")
    synth_prompt = build_outline_stage_synthesizer_prompt(state, "volume_outline", [])

    assert "只做卷级目标、卷内高潮、代价和卷间钩子" in role_prompt
    assert "只输出卷级结构，不拆具体章节" in synth_prompt
    assert "规划 3-5 卷" in synth_prompt
    assert "卷名 / 卷目标 / 卷内主要矛盾 / 高潮事件 / 失败或胜利代价 / 卷间钩子" in synth_prompt
    assert "每字段不超过 80 中文字符" in synth_prompt
    assert "每卷必须包含目标、高潮、代价和卷间钩子" in synth_prompt
    assert "主角能力或认知变化" in synth_prompt
    for forbidden in ("逐章细纲", "第1章", "第2章", "章节列表", "场景列表", "正文片段", "新世界观规则", "新人物系统", "过细制度机制"):
        assert forbidden in role_prompt or forbidden in synth_prompt


def test_chapter_outline_prompt_limits_output_to_chapter_level_plan():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")

    role_prompt = build_outline_stage_role_prompt(state, "chapter_outline", "章节拆分 Agent")
    synth_prompt = build_outline_stage_synthesizer_prompt(state, "chapter_outline", [])

    assert "只做章节目标、冲突、信息增量、人物变化、钩子和连续性提醒" in role_prompt
    assert "只做章节级规划" in synth_prompt
    assert "首批输出 8-12 章" in synth_prompt
    assert "章节编号 / 章节目标 / 主要冲突 / 信息增量 / 人物状态变化 / 结尾钩子 / 连续性提醒" in synth_prompt
    assert "每字段不超过 60 中文字符" in synth_prompt
    assert "每章必须包含目标、冲突、信息增量和钩子" in synth_prompt
    assert "信息增量只能来自前序已确立设定" in synth_prompt
    for forbidden in ("正式正文", "对白", "中文引号对白", "细场景调度", "完整场景卡", "未确立新规则", "新人物关系", "审批", "制度", "亲密机制"):
        assert forbidden in role_prompt or forbidden in synth_prompt


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


def test_direction_sanitizer_removes_nested_titles_and_institutional_terms():
    markdown = sanitize_direction_stage_output(
        "# 方向定位\n\n## 方向控制稿\n"
        "1. 类型定位：重生魔门悬疑智斗，以低调求生追查真相。\n"
        "2. 主角行动原则：利用宗门流程求生，不正面硬刚。\n"
        "3. 核心爽点：用亲密行为申请表和道侣绩效考评制造反差。\n"
        "4. 核心冲突：师傅暗中吞噬气运，主角必须破局。\n"
        "5. 情绪基调：压抑、克制、步步反击。\n"
        "6. 禁区：不要写成审批备案驱动的制度条款。"
    )

    assert markdown.count("## 方向定位稿") == 1
    assert "## 方向控制稿" not in markdown
    assert "# 方向定位" not in markdown.splitlines()
    for forbidden in ("申请表", "审批", "考评", "备案", "绩效", "项目审批", "亲密行为申请表"):
        assert forbidden not in markdown
    for marker in ("类型定位", "主角行动原则", "核心冲突", "情绪基调", "禁区"):
        assert marker in markdown


def test_outline_stage_generation_emits_progress_events(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    events = []
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store, progress=lambda stage, message: events.append((stage, message)))

    state = run_outline_turn(graph, state, store, "生成大纲")

    assert state.outline_stage == "direction"
    assert any(stage == "OutlineStage" and "准备" in message for stage, message in events)
    assert any(stage == "类型定位 Agent" for stage, _message in events)
    assert any(stage == "主题卖点 Agent" for stage, _message in events)
    assert any(stage == "风险编辑 Agent" for stage, _message in events)
    assert any(stage == "大纲汇总 Agent" for stage, _message in events)
    assert any(stage == "OutlineStage" and "保存" in message for stage, message in events)


def test_outline_stage_advance_emits_progress_events(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    events = []
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store, progress=lambda stage, message: events.append((stage, message)))

    state = run_outline_turn(graph, state, store, "生成大纲")
    events.clear()
    state = run_outline_turn(graph, state, store, "确认进入下一阶段")

    assert state.outline_stage == "concept"
    assert any(stage == "OutlineStage" and "锁定" in message for stage, message in events)
    assert any(stage == "OutlineStage" and "进入" in message for stage, message in events)
    assert any(stage == "故事概念 Agent" for stage, _message in events)
    assert any(stage == "大纲汇总 Agent" for stage, _message in events)


def test_save_state_slims_outline_artifacts_and_writes_memory(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "重生魔门，低调求生"
    state.locked_constraints.append("师傅暗中吞噬主角气运")
    long_synthesis = "## 方向定位稿\n\n" + "主角以低调求生追查真相。" * 200
    state.messages = [{"role": "assistant", "content": "长回复" * 400} for _ in range(20)]
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "label": "方向定位",
        "status": "options_ready",
        "synthesis": long_synthesis,
        "role_reviews": [{"role": "风险编辑 Agent", "content": "内部短评"}],
        "stage_memory": ["低调求生追查真相", "师傅吞噬主角气运"],
    }

    store.save_state(state)

    saved = json.loads(store.state_path("demo").read_text(encoding="utf-8"))
    artifact = saved["outline_stage_artifacts"]["direction"]
    assert "synthesis" not in artifact
    assert "role_reviews" not in artifact
    assert artifact["path"] == "outline/direction.md"
    assert artifact["stage_memory"] == ["低调求生追查真相", "师傅吞噬主角气运"]
    assert len(saved["messages"]) == 12
    assert all(len(item["content"]) <= 503 for item in saved["messages"])
    assert store.outline_artifact_path("demo", "direction").exists()
    memory = store.project_memory_path("demo").read_text(encoding="utf-8")
    assert "不可压缩种子设定" in memory
    assert "原始创意：重生魔门，低调求生" in memory
    assert "锁定约束：师傅暗中吞噬主角气运" in memory
    assert "低调求生追查真相" in memory


def test_concept_role_prompts_have_role_specific_context():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "label": "方向定位",
        "status": "locked",
        "stage_memory": ["主角低调求生", "师傅吞噬气运是核心谜团"],
    }

    concept_prompt = build_outline_stage_role_prompt(state, "concept", "故事概念 Agent")
    conflict_prompt = build_outline_stage_role_prompt(state, "concept", "核心冲突 Agent")
    twist_prompt = build_outline_stage_role_prompt(state, "concept", "反转机制 Agent")

    assert "角色专属关注点" in concept_prompt
    assert "故事发动机" in concept_prompt
    assert "中期升级" in conflict_prompt
    assert "认知差" in twist_prompt
    assert len({concept_prompt, conflict_prompt, twist_prompt}) == 3
    assert len({len(concept_prompt), len(conflict_prompt), len(twist_prompt)}) == 3


def test_stage_prompt_prefers_stage_memory_over_full_synthesis():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门")
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "label": "方向定位",
        "status": "locked",
        "summary": "很短摘要",
        "stage_memory": ["主角低调求生", "师傅吞噬气运是核心谜团"],
        "synthesis": "完整长文不应进入 prompt。" + "污染" * 200,
    }

    prompt = build_outline_stage_role_prompt(state, "concept", "故事概念 Agent")

    assert "主角低调求生" in prompt
    assert "师傅吞噬气运是核心谜团" in prompt
    assert "完整长文不应进入 prompt" not in prompt


def test_non_direction_stage_markdown_hides_role_reviews_by_default():
    markdown = format_stage_markdown(
        {
            "stage": "characters",
            "label": "人物关系",
            "synthesis": "主角与圣女互相试探。",
            "role_reviews": [{"role": "关系冲突 Agent", "content": "内部建议"}],
        }
    )

    assert "主角与圣女互相试探" in markdown
    assert "角色短评" not in markdown
    assert "内部建议" not in markdown


def test_compact_numbered_pending_answers_are_absorbed(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "重生魔门"
    state.active_workflow = "outline"
    state.outline_stage = "characters"
    state.outline_stage_status = "options_ready"
    state.pending_questions = ["圣女保守来源？", "伏笔如何安排？", "结局阶段是否再设计？"]
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "label": "人物关系",
        "status": "options_ready",
        "summary": "主角与圣女互相试探。",
        "stage_memory": ["主角与圣女互相试探"],
    }
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "1可以2伏笔3结局阶段再设计")

    assert state.director_intent == "answer_pending_questions"
    assert "圣女保守来源？ -> 可以" in state.revision_instruction
    assert "伏笔如何安排？ -> 伏笔" in state.revision_instruction
    assert "结局阶段是否再设计？ -> 结局阶段再设计" in state.revision_instruction

def test_determine_advance_closes_pending_questions_before_next_stage(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "重生魔门"
    state.active_workflow = "outline"
    state.outline_stage = "story_flow"
    state.outline_stage_status = "options_ready"
    state.pending_questions = ["幕一确认习惯如何具象？", "终局让渡之择如何回应？"]
    state.pending_question = "\n".join(f"{i}. {q}" for i, q in enumerate(state.pending_questions, 1))
    state.outline_stage_artifacts["story_flow"] = {
        "stage": "story_flow",
        "label": "故事流程",
        "status": "options_ready",
        "synthesis": "## Director 汇总\n故事四幕已经成立。",
        "pending_questions": list(state.pending_questions),
        "stage_memory": ["四幕结构成立"],
    }
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "确定进入下一阶段")

    locked = state.outline_stage_artifacts["story_flow"]
    assert state.outline_stage == "volume_outline"
    assert locked["status"] == "locked"
    assert locked["pending_questions"] == []
    assert "自行闭环未决问题" in locked["default_discretion_summary"]
    assert "幕一确认习惯如何具象" in locked["default_discretion_summary"]
    assert state.locked_constraints == []


def test_outline_progress_prints_agent_model_metadata(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    events = []
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store, progress=lambda stage, message: events.append((stage, message)))

    state = run_outline_turn(graph, state, store, "生成大纲")

    assert state.outline_stage == "direction"
    assert any(stage == "类型定位 Agent" and "mock | n/a" in message for stage, message in events)
    assert any(stage == "类型定位 Agent" and "mock | n/a | " in message for stage, message in events)
    assert any(stage == "大纲汇总 Agent" and "mock | n/a" in message for stage, message in events)
    assert any(stage == "大纲汇总 Agent" and "mock | n/a | " in message for stage, message in events)

def test_outline_direct_entry_does_not_advance_on_bare_determine_detail(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "重生魔门"
    state.active_workflow = "outline"
    state.outline_stage = "story_flow"
    state.outline_stage_status = "options_ready"
    state.pending_questions = ["终局让渡之择如何回应？"]
    state.outline_stage_artifacts["story_flow"] = {
        "stage": "story_flow",
        "label": "故事流程",
        "status": "options_ready",
        "summary": "四幕结构成立。",
        "stage_memory": ["四幕结构成立"],
    }
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "确定终局让纪无厌拒绝一次，但不要进入下一阶段")

    assert state.outline_stage == "story_flow"
    assert state.outline_stage_artifacts["story_flow"]["status"] == "options_ready"
    assert state.director_action == "run_outline_stage"



def test_outline_direct_entry_next_step_question_uses_director_status(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "重生魔门"
    state.active_workflow = "outline"
    state.outline_stage = "review_lock"
    state.outline_stage_status = "options_ready"
    state.pending_questions = ["是否需要补一个失败代价？", "终局拒绝是否保留一次？"]
    state.pending_question = "\n".join(f"{i}. {q}" for i, q in enumerate(state.pending_questions, 1))
    state.outline_stage_artifacts["review_lock"] = {
        "stage": "review_lock",
        "label": "审稿锁定",
        "status": "options_ready",
        "synthesis": "## Director 汇总\n当前总纲已接近锁定。",
        "pending_questions": list(state.pending_questions),
    }
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "接下来我该做什么？")

    assert state.director_action == "ask_user"
    assert state.director_intent == "status"
    assert state.outline_stage == "review_lock"
    assert state.outline_stage_artifacts["review_lock"]["status"] == "options_ready"
    assert "当前阶段：审稿锁定 options_ready" in state.director_message
    assert "可选下一步" in state.director_message



def test_outline_direct_entry_temporary_revises_locked_direction_then_returns_to_story_flow(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "重生魔门悬疑智斗"
    state.active_workflow = "outline"
    state.outline_stage = "story_flow"
    state.outline_stage_status = "options_ready"
    for stage, label in [
        ("direction", "方向定位"),
        ("concept", "故事概念"),
        ("worldbuilding", "世界观设定"),
        ("characters", "人物关系"),
    ]:
        state.outline_stage_artifacts[stage] = {
            "stage": stage,
            "label": label,
            "status": "locked",
            "summary": f"{label}旧稿",
            "stage_memory": [f"{label}旧稿"],
        }
    state.outline_stage_artifacts["story_flow"] = {
        "stage": "story_flow",
        "label": "故事流程",
        "status": "options_ready",
        "summary": "第5阶段旧稿",
        "stage_memory": ["第5阶段旧稿"],
        "pending_questions": ["第5阶段问题？"],
    }
    state.pending_questions = ["第5阶段问题？"]
    state.pending_question = "1. 第5阶段问题？"
    store.save_state(state)
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "方向定位阶段的制度词太生硬，按正常小说去写")

    assert state.outline_stage == "story_flow"
    assert state.outline_stage_status == "options_ready"
    assert state.pending_questions == ["第5阶段问题？"]
    assert state.outline_stage_artifacts["direction"]["status"] == "locked"
    assert state.outline_stage_artifacts["direction"]["pending_questions"] == []
    assert "已回到第 5 阶段「故事流程」继续修改" in state.director_message


def test_outline_stage_parallel_path_preserves_role_order(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_NOVELIST_PARALLEL_AGENTS", "1")
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    graph = build_outline_collaboration_graph(CodexCLIAdapter(mock=True), store)

    state = run_outline_turn(graph, state, store, "请生成大纲")

    reviews = state.outline_stage_artifacts["direction"]["role_reviews"]
    assert [item["role"] for item in reviews] == ["类型定位 Agent", "主题卖点 Agent", "风险编辑 Agent"]
    trace_path = store.project_dir("demo") / "debug" / "agent_runs.jsonl"
    assert trace_path.exists()
    assert "outline_stage_role" in trace_path.read_text(encoding="utf-8")
