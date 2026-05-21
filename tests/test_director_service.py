import json

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.director_service import DirectorService, parse_service_director_output
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


def test_confirmation_accepts_receive_words():
    from ai_novelist.director_service import is_confirmation

    assert is_confirmation("接收")
    assert is_confirmation("接受")
