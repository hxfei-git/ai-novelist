import json

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.director_service import DirectorDecision, DirectorService, build_service_director_prompt, parse_service_director_output, update_project_context
from ai_novelist.research import MockSearchBackend
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class JsonDirectorAdapter(CodexCLIAdapter):
    def _mock_director(self, prompt: str) -> str:
        return json.dumps(
            {
                "action": "research",
                "requires_confirmation": True,
                "confidence": 92,
                "user_message": "我会先调研《苟在初圣》的公开资料。",
                "task_args": {
                    "research_query": "苟在初圣",
                    "work_title": "苟在初圣",
                    "author": "初圣",
                },
                "next_steps": ["确认参考事实", "生成同人大纲方向"],
            },
            ensure_ascii=False,
        )


def test_parse_service_director_output_supports_json_research_args():
    state = NovelState(project_id="demo", title="Demo")
    state.user_request = "写苟在初圣同人，作者初圣"
    output = json.dumps(
        {
            "action": "research",
            "requires_confirmation": True,
            "confidence": 91,
            "user_message": "先调研。",
            "task_args": {"work_title": "苟在初圣", "author": "初圣"},
            "next_steps": ["确认事实"],
        },
        ensure_ascii=False,
    )

    decision = parse_service_director_output(output, state)

    assert decision.action == "research"
    assert decision.requires_confirmation is True
    assert decision.task_args["research_query"] == "苟在初圣"
    assert decision.task_args["author"] == "初圣"


def test_parse_service_director_output_enforces_message_and_next_step_budget():
    state = NovelState(project_id="demo", title="Demo")
    long_message = "说明" * 100
    output = json.dumps(
        {
            "action": "ask_user",
            "requires_confirmation": False,
            "confidence": 80,
            "user_message": long_message,
            "next_steps": ["第一步" * 50, "第二步", "第三步", "第四步"],
        },
        ensure_ascii=False,
    )

    decision = parse_service_director_output(output, state)

    assert len(decision.user_message) <= 120
    assert len(decision.next_steps) == 3
    assert all(len(item) <= 80 for item in decision.next_steps)



class ChatDirectorAdapter(CodexCLIAdapter):
    def _mock_director(self, prompt: str) -> str:
        return json.dumps(
            {
                "action": "chat",
                "requires_confirmation": False,
                "confidence": 90,
                "user_message": "可以，我们先聊这个方向。",
                "task_args": {},
                "next_steps": [],
            },
            ensure_ascii=False,
        )


def test_director_service_chat_action_does_not_trigger_workflow(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.active_workflow = "outline"
    state.outline_stage = "characters"
    state.outline_stage_status = "options_ready"
    store.save_state(state)
    service = DirectorService(store, ChatDirectorAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "这个方向感觉怎么样？", channel="cli")

    assert result.decision.action == "chat"
    assert not result.choices
    assert result.final_message == "可以，我们先聊这个方向。"
    assert result.state.director_action == "chat"
    assert result.state.outline_stage == "characters"
    assert not store.load_state("demo").pending_director_decision


def test_cancel_pending_write_action_does_not_execute(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.current_chapter = 1
    store.save_state(state)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    first = service.handle_turn("demo", "写第 1 章", channel="cli")
    cancelled = service.handle_turn("demo", "2", channel="cli")

    assert first.choices[0].id == "confirm"
    assert cancelled.final_message == "已取消上一步计划。你可以重新说明想做什么。"
    state_after = store.load_state("demo")
    assert state_after.chapter_draft == ""
    assert not state_after.pending_director_decision

def test_director_service_confirms_then_reuses_pending_research_decision(tmp_path):
    store = LocalStore(tmp_path)
    store.create_project("Demo", "demo")
    service = DirectorService(store, JsonDirectorAdapter(mock=True), MockSearchBackend())

    first = service.handle_turn("demo", "我想写一本同人小说，苟在初圣的同人，作者是初圣", channel="cli")

    assert first.requires_followup is True
    assert first.choices[0].id == "confirm"
    assert first.choices[0].label == "确认执行"
    assert first.choices[1].id == "cancel"
    pending = store.load_state("demo").pending_director_decision
    assert pending["action"] == "research"
    assert pending["task_args"]["research_query"] == "苟在初圣"

    second = service.handle_turn("demo", "1", channel="cli")

    assert second.state.director_action == "research"
    assert second.state.retrieval_query == "苟在初圣"
    assert second.state.reference_brief
    assert not second.state.pending_director_decision
    assert store.reference_brief_path("demo").exists()
    context = store.load_project_context("demo")
    assert "# Project Context: demo" in context
    assert "最近查询：苟在初圣" in context
    assert "建议下一步" in context


def test_director_service_direct_status_does_not_require_confirmation(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.outline = "# 大纲"
    store.save_state(state)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "查看状态", channel="cli")

    assert result.immediate_message == ""
    assert result.state.director_action == "show_status"
    assert "项目：demo" in result.final_message
    assert not store.load_state("demo").pending_director_decision


def test_director_service_can_cancel_with_choice_number(tmp_path):
    store = LocalStore(tmp_path)
    store.create_project("Demo", "demo")
    service = DirectorService(store, JsonDirectorAdapter(mock=True), MockSearchBackend())

    service.handle_turn("demo", "我想写苟在初圣同人", channel="cli")
    result = service.handle_turn("demo", "2", channel="cli")

    assert "已取消" in result.final_message
    assert not store.load_state("demo").pending_director_decision


def test_pending_decision_executes_on_freeform_non_cancel_reply(tmp_path):
    store = LocalStore(tmp_path)
    store.create_project("Demo", "demo")
    service = DirectorService(store, JsonDirectorAdapter(mock=True), MockSearchBackend())

    service.handle_turn("demo", "我想写苟在初圣同人", channel="cli")
    result = service.handle_turn("demo", "开始调研", channel="cli")

    assert result.state.director_action == "research"
    assert result.state.retrieval_query == "苟在初圣"
    assert not store.load_state("demo").pending_director_decision


class OutlineReviseDirectorAdapter(CodexCLIAdapter):
    def _mock_director(self, prompt: str) -> str:
        return json.dumps(
            {
                "action": "revise_outline",
                "requires_confirmation": True,
                "confidence": 90,
                "user_message": "我会修订当前人物关系。",
                "task_args": {"instruction": "加入魔宗圣女与剑宗天才少女"},
                "next_steps": [],
            },
            ensure_ascii=False,
        )


def test_outline_stage_revision_requires_confirmation_menu(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("重生魔门", "重生魔门")
    state.active_workflow = "outline"
    state.outline_stage = "characters"
    state.outline_stage_status = "options_ready"
    store.save_state(state)
    service = DirectorService(store, OutlineReviseDirectorAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("重生魔门", "加入魔宗圣女与剑宗天才少女", channel="cli")

    assert result.immediate_message == "我会修订当前人物关系。"
    assert result.choices[0].id == "confirm"
    assert store.load_state("重生魔门").pending_director_decision["action"] == "revise_outline"

    confirmed = service.handle_turn("重生魔门", "1", channel="cli")

    assert confirmed.state.director_action == "run_outline_stage"
    assert confirmed.state.outline_stage == "characters"
    assert "characters" in confirmed.state.outline_stage_artifacts
    assert not store.load_state("重生魔门").pending_director_decision


class AskUserDirectorAdapter(CodexCLIAdapter):
    def _mock_director(self, prompt: str) -> str:
        return json.dumps(
            {
                "action": "ask_user",
                "requires_confirmation": False,
                "confidence": 40,
                "user_message": "我需要更多信息。",
                "task_args": {},
                "next_steps": [],
            },
            ensure_ascii=False,
        )


def test_director_service_translates_multi_confirmation_feedback(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.outline = "# 大纲草案"
    state.editor_decision = "revise"
    state.editor_notes = """
建议状态为 revise。

进入下一步前，应先请用户确认：
- “初圣”到底是主角本人、转世、残识、尊号、境界，还是允许自由设定？
- 是否接受“沈砚 = 初圣残识宿主”这一核心设定？
- 是否允许把藏锋诀、避劫草、无名古钟、旧铜钱的性质作为同人原创谜底补完？
""".strip()
    store.save_state(state)
    service = DirectorService(store, AskUserDirectorAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "初圣是穿越而来的人，顶替了初圣本来的灵魂。接收，接收", channel="cli")

    assert result.requires_followup is True
    assert result.decision.action == "revise_outline"
    assert result.decision.requires_confirmation is True
    assert "初圣是穿越而来的人" in result.decision.instruction
    assert "沈砚 = 初圣残识宿主" in result.decision.instruction
    assert "藏锋诀、避劫草、无名古钟、旧铜钱" in result.decision.instruction
    assert len(result.decision.locked_constraints) == 3
    pending = store.load_state("demo").pending_director_decision
    assert pending["action"] == "revise_outline"
    assert "沈砚 = 初圣残识宿主" in pending["task_args"]["instruction"]



def test_update_project_context_syncs_current_outline_stage(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("重生魔门", "demo")
    state.active_workflow = "outline"
    state.outline_stage = "direction"
    state.outline_stage_status = "options_ready"
    state.pending_question = "方向定位当前是控制稿草案；你可以继续修改，或确认进入下一阶段。"
    state.pending_questions = ["旧问题不应优先出现", state.pending_question]
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "label": "方向定位",
        "status": "options_ready",
        "synthesis": "## 一句话方向\n\n追查师傅吞噬气运真相。",
    }

    update_project_context(state, store, DirectorDecision("ask_user"))

    context = store.load_project_context("demo")
    assert "## 当前大纲阶段" in context
    assert "方向定位 (direction)" in context
    assert "追查师傅吞噬气运真相" in context
    assert state.pending_question in context
    assert "旧问题不应优先出现" not in context
    assert "继续提出方向定位修改意见" in context


def test_service_director_prompt_prioritizes_stage_artifact_over_stale_dialogue(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("重生魔门", "demo")
    state.active_workflow = "outline"
    state.outline_stage = "direction"
    state.outline_stage_status = "options_ready"
    state.user_request = "接下来我应该做什么？"
    state.messages = [
        {
            "role": "assistant",
            "content": "之前已确认：主角利用陨落强者气息伪造假面靠山；还剩必须隐藏的生存刚需尚未选定。",
        },
        {"role": "user", "content": "接下来我应该做什么？"},
    ]
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "label": "方向定位",
        "synthesis": "## 一句话方向\n\n追查师傅吞噬气运真相。",
    }
    store.save_state(state)

    prompt = build_service_director_prompt(state, store, "feishu")

    assert "当前大纲阶段产物" in prompt
    assert "追查师傅吞噬气运真相" in prompt
    assert "陨落强者气息" not in prompt
    assert "必须隐藏的生存刚需尚未选定" not in prompt


def test_director_service_shows_named_outline_stage(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("重生魔门", "重生魔门")
    state.active_workflow = "outline"
    state.outline_stage = "direction"
    store.save_state(state)
    store.save_outline_stage(state, "direction", "# 方向定位\n\n这是阶段正文。")
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("重生魔门", "查看方向定位", channel="cli")

    assert result.state.director_action == "show_outline"
    assert "# 方向定位" in result.final_message
    assert "这是阶段正文" in result.final_message
    assert "项目：重生魔门" not in result.final_message




def test_director_service_shows_worldbuilding_by_plain_name(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("重生魔门", "重生魔门")
    state.active_workflow = "outline"
    state.outline_stage = "direction"
    state.worldbuilding = "# 世界观蓝图\n\n气运可以被观测和借贷。"
    store.save_state(state)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("重生魔门", "查看世界观", channel="cli")

    assert result.state.director_action == "show_outline"
    assert "# 世界观设定" in result.final_message
    assert "气运可以被观测和借贷" in result.final_message
    assert "当前还没有参考简报" not in result.final_message



def test_director_service_confirms_existing_worldbuilding_stage(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("重生魔门", "重生魔门")
    state.active_workflow = "outline"
    state.outline_stage = "direction"
    state.outline_stage_status = "options_ready"
    state.worldbuilding = "# 世界观蓝图\n\n气运可以被观测和借贷。"
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "label": "方向定位",
        "status": "options_ready",
        "synthesis": "黑暗魔门悬疑智斗。",
        "role_reviews": [],
    }
    store.save_state(state)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("重生魔门", "确定世界观并进入下一阶段", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.state.outline_stage == "direction"

    confirmed = service.handle_turn("重生魔门", "1", channel="cli")

    assert confirmed.state.outline_stage == "characters"
    assert confirmed.state.outline_stage_artifacts["direction"]["status"] == "locked"
    assert confirmed.state.outline_stage_artifacts["worldbuilding"]["status"] == "locked"
    assert "气运可以被观测和借贷" in confirmed.state.outline_stage_artifacts["worldbuilding"]["synthesis"]
    assert store.outline_stage_path("重生魔门", "worldbuilding").exists()

def test_confirmation_accepts_receive_words():
    from ai_novelist.director_service import is_confirmation

    assert is_confirmation("接收")
    assert is_confirmation("接受")
    assert not is_confirmation("开始修订")

def test_director_service_shows_missing_bible_message(tmp_path):
    store = LocalStore(tmp_path)
    store.create_project("Demo", "demo")
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "查看小说圣经", channel="cli")

    assert result.state.director_action == "show_bible"
    assert "当前还没有小说圣经" in result.final_message


def test_director_service_shows_existing_bible(tmp_path):
    from ai_novelist.bible import NovelBible, save_bible

    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    bible = NovelBible()
    bible.project.title = "月城手稿"
    bible.concept.logline = "失忆工程师追查自己的旧罪。"
    save_bible(store.project_dir("demo"), bible)
    store.save_state(state)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "查看小说圣经", channel="cli")

    assert result.state.director_action == "show_bible"
    assert "当前小说圣经" in result.final_message
    assert "月城手稿" in result.final_message
    assert "失忆工程师" in result.final_message


def test_director_service_update_bible_runs_graph(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.idea = "月球城市失忆工程师"
    state.outline = "# 最终锁定总大纲\n\n失忆工程师追查纸质手稿预言。"
    store.save_state(state)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "更新小说圣经", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.state.director_action == "update_bible"

    confirmed = service.handle_turn("demo", "1", channel="cli")

    assert confirmed.state.director_action == "update_bible"
    assert store.novel_bible_markdown_path("demo").exists()
    assert "小说圣经已更新" in confirmed.final_message

def test_director_service_reports_execution_plan_for_write_chapter(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.current_chapter = 1
    store.save_state(state)
    events = []
    service = DirectorService(
        store,
        CodexCLIAdapter(mock=True),
        MockSearchBackend(),
        progress=lambda stage, message: events.append((stage, message)),
    )

    result = service.handle_turn("demo", "写第 1 章", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.state.director_action == "write_chapter"
    assert ("Plan", "将生成第 1 章正文；缺少章节卡或场景卡时会先自动补齐。") not in events

    confirmed = service.handle_turn("demo", "1", channel="cli")

    assert confirmed.state.director_action == "write_chapter"
    assert ("Plan", "将生成第 1 章正文；缺少章节卡或场景卡时会先自动补齐。") in events
    assert any(stage == "Drafting 1/8" for stage, _message in events)


def make_characters_options_ready_state(store: LocalStore) -> NovelState:
    state = store.create_project("Demo", "demo")
    state.idea = "重生魔门悬疑智斗"
    state.active_workflow = "outline"
    state.outline_stage = "characters"
    state.outline_stage_status = "options_ready"
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "label": "人物关系",
        "status": "options_ready",
        "synthesis": "## Director 汇总\n主角、魔宗圣女、剑宗天才少女构成三角压力。",
        "role_reviews": [],
    }
    state.pending_questions = [
        "魔宗圣女的保守来源是心魔誓约还是派系规则？",
        "剑宗天才少女首次审判是否发生在葬魂谷？",
    ]
    state.pending_question = "\n".join(f"{i}. {q}" for i, q in enumerate(state.pending_questions, 1))
    store.save_state(state)
    return state


def test_outline_stage_delegated_discretion_advances(tmp_path):
    store = LocalStore(tmp_path)
    make_characters_options_ready_state(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "这些由你决定，按当前建议处理并进入下一阶段", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.decision.action == "persist_outputs"
    assert result.state.outline_stage == "characters"

    confirmed = service.handle_turn("demo", "1", channel="cli")

    assert confirmed.state.outline_stage == "story_flow"
    assert confirmed.state.outline_stage_status == "options_ready"
    assert confirmed.state.outline_stage_artifacts["characters"]["status"] == "locked"
    assert "default_discretion_summary" in confirmed.state.outline_stage_artifacts["characters"]
    assert "story_flow" in confirmed.state.outline_stage_artifacts


def test_outline_stage_specific_feedback_reruns_current_stage(tmp_path):
    store = LocalStore(tmp_path)
    make_characters_options_ready_state(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "补充人物设定：魔宗圣女表面诱惑，实际受心魔誓约限制", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.state.director_action == "revise_outline"
    assert result.state.outline_stage == "characters"
    assert result.decision.action == "revise_outline"
    assert "心魔誓约" in result.decision.instruction

    confirmed = service.handle_turn("demo", "1", channel="cli")

    assert confirmed.state.director_action == "run_outline_stage"
    assert confirmed.state.outline_stage_status == "options_ready"


def test_outline_stage_numbered_answers_rerun_current_stage(tmp_path):
    store = LocalStore(tmp_path)
    make_characters_options_ready_state(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "1. 心魔誓约 2. 葬魂谷", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.state.director_action == "revise_outline"
    assert result.state.outline_stage == "characters"
    assert result.decision.intent == "answer_pending_questions"
    assert "心魔誓约" in result.decision.instruction
    assert "葬魂谷" in result.decision.instruction

    confirmed = service.handle_turn("demo", "1", channel="cli")

    assert confirmed.state.director_action == "run_outline_stage"


def test_outline_stage_view_current_does_not_advance(tmp_path):
    store = LocalStore(tmp_path)
    make_characters_options_ready_state(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "查看当前阶段", channel="cli")

    assert result.state.director_action == "show_outline"
    assert result.state.outline_stage == "characters"
    assert result.state.outline_stage_artifacts["characters"]["status"] == "options_ready"
    assert "人物关系" in result.final_message


def test_outline_stage_simple_confirmation_advances(tmp_path):
    store = LocalStore(tmp_path)
    make_characters_options_ready_state(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "进入下一阶段", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.state.outline_stage == "characters"

    confirmed = service.handle_turn("demo", "1", channel="cli")

    assert confirmed.state.outline_stage == "story_flow"
    assert confirmed.state.outline_stage_artifacts["characters"]["status"] == "locked"

def test_director_treats_determine_enter_next_stage_as_approval(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.active_workflow = "outline"
    state.outline_stage = "story_flow"
    state.outline_stage_status = "options_ready"
    state.pending_questions = ["幕一确认习惯如何具象？"]
    state.outline_stage_artifacts["story_flow"] = {
        "stage": "story_flow",
        "label": "故事流程",
        "status": "options_ready",
        "summary": "四幕结构成立。",
        "stage_memory": ["四幕结构成立"],
    }
    store.save_state(state)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "确定进入下一阶段", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.decision.action == "persist_outputs"
    assert result.decision.intent == "approve"
    assert result.state.outline_stage == "story_flow"

    confirmed = service.handle_turn("demo", "1", channel="cli")

    assert confirmed.state.outline_stage == "volume_outline"
    assert confirmed.state.outline_stage_artifacts["story_flow"]["status"] == "locked"
    assert "自行闭环未决问题" in confirmed.state.outline_stage_artifacts["story_flow"]["default_discretion_summary"]

def test_director_does_not_advance_on_bare_determine_detail(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
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
    store.save_state(state)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "确定终局让纪无厌拒绝一次，但不要进入下一阶段", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.state.outline_stage == "story_flow"
    assert result.state.outline_stage_artifacts["story_flow"]["status"] == "options_ready"
    assert result.state.director_action == "revise_outline"



def make_review_lock_options_ready_state(store: LocalStore) -> NovelState:
    state = store.create_project("Demo", "demo")
    state.idea = "重生魔门悬疑智斗"
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
    store.save_state(state)
    return state


def test_outline_next_step_question_reports_status_without_rerun(tmp_path):
    store = LocalStore(tmp_path)
    make_review_lock_options_ready_state(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "接下来我该做什么？", channel="cli")

    assert result.decision.action == "ask_user"
    assert result.decision.intent == "status"
    assert result.state.director_action == "ask_user"
    assert result.state.outline_stage == "review_lock"
    assert result.state.outline_stage_status == "options_ready"
    assert "当前阶段：审稿锁定 options_ready" in result.final_message
    assert "未决问题：2 项" in result.final_message
    assert "可选下一步" in result.final_message
    assert "review_lock" in result.state.outline_stage_artifacts
    assert result.state.outline_stage_artifacts["review_lock"]["status"] == "options_ready"


def test_outline_next_step_variants_do_not_trigger_agent(tmp_path):
    for text in ("下一步呢？", "现在怎么办？"):
        store = LocalStore(tmp_path / text.strip("？"))
        make_review_lock_options_ready_state(store)
        service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

        result = service.handle_turn("demo", text, channel="cli")

        assert result.decision.action == "ask_user"
        assert result.state.outline_stage == "review_lock"
        assert result.state.outline_stage_artifacts["review_lock"]["status"] == "options_ready"
        assert "可选下一步" in result.final_message



def make_story_flow_with_locked_prior_state(store: LocalStore) -> NovelState:
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
    return state


def test_director_service_temporary_revises_locked_direction_then_returns_to_story_flow(tmp_path):
    store = LocalStore(tmp_path)
    make_story_flow_with_locked_prior_state(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn(
        "demo",
        "我希望方向定位阶段的制度框架，感答辩之类的词都很生硬，请按照正常小说去写",
        channel="cli",
    )

    assert result.choices[0].id == "confirm"
    assert result.decision.action == "revise_outline"
    assert result.decision.intent == "revise_previous_stage"
    assert result.decision.task_args["stage"] == "direction"
    assert result.decision.task_args["return_stage"] == "story_flow"
    assert result.state.outline_stage == "story_flow"

    confirmed = service.handle_turn("demo", "1", channel="cli")

    assert confirmed.state.outline_stage == "story_flow"
    assert confirmed.state.outline_stage_status == "options_ready"
    assert confirmed.state.pending_questions == ["第5阶段问题？"]
    assert confirmed.state.outline_stage_artifacts["direction"]["status"] == "locked"
    assert confirmed.state.outline_stage_artifacts["direction"]["pending_questions"] == []
    assert confirmed.state.outline_stage_artifacts["concept"]["status"] == "locked"
    assert confirmed.state.outline_stage_artifacts["worldbuilding"]["status"] == "locked"
    assert "已回到第 5 阶段「故事流程」继续修改" in confirmed.final_message


def test_director_service_stage_number_revision_targets_direction(tmp_path):
    store = LocalStore(tmp_path)
    make_story_flow_with_locked_prior_state(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "回到第1阶段修改，术语太生硬", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.decision.task_args["stage"] == "direction"
    assert result.decision.task_args["return_stage"] == "story_flow"


def test_director_service_chinese_stage_number_revision_targets_direction(tmp_path):
    store = LocalStore(tmp_path)
    make_story_flow_with_locked_prior_state(store)
    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())

    result = service.handle_turn("demo", "重修第一阶段，语感要更像正常小说", channel="cli")

    assert result.choices[0].id == "confirm"
    assert result.decision.task_args["stage"] == "direction"
    assert result.decision.task_args["return_stage"] == "story_flow"
