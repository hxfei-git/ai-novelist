from dataclasses import dataclass, field

import pytest

from ai_novelist.config import Settings
from ai_novelist.director_service import DirectorChoice, DirectorTurnResult
from ai_novelist.feishu import FeishuBotService, FeishuConfigError, RecentMessageDeduper, extract_text_content, format_turn_result
from ai_novelist.feishu.runner import validate_feishu_settings
from ai_novelist.feishu.session_store import FeishuSessionStore
from ai_novelist.storage.local_store import LocalStore


@dataclass
class FakeDirector:
    calls: list[tuple[str, str, str]] = field(default_factory=list)
    turn: DirectorTurnResult = field(default_factory=lambda: DirectorTurnResult(final_message="已完成"))

    def handle_turn(self, project_id: str, user_text: str, channel: str = "cli") -> DirectorTurnResult:
        self.calls.append((project_id, user_text, channel))
        return self.turn


def test_feishu_session_store_creates_default_project_mapping(tmp_path):
    store = LocalStore(tmp_path)
    sessions = FeishuSessionStore(store)

    project_id = sessions.current_project("ou_abc")

    assert project_id == "feishu-ou_abc"
    assert sessions.current_project("ou_abc") == "feishu-ou_abc"
    assert (tmp_path / ".feishu_sessions.json").exists()


def test_feishu_project_command_switches_and_creates_project(tmp_path):
    store = LocalStore(tmp_path)
    director = FakeDirector()
    bot = FeishuBotService(store, director)  # type: ignore[arg-type]

    response = bot.handle_text("ou_abc", "/project demo novel")

    assert response == "已切换到项目：demo-novel"
    assert store.state_path("demo-novel").exists()
    assert FeishuSessionStore(store).current_project("ou_abc") == "demo-novel"


def test_feishu_project_command_without_current_project_asks_for_title(tmp_path):
    store = LocalStore(tmp_path)
    director = FakeDirector()
    bot = FeishuBotService(store, director)  # type: ignore[arg-type]

    response = bot.handle_text("ou_abc", "/project")

    assert "请直接发送新小说的名字" in response
    assert FeishuSessionStore(store).needs_new_project_title("ou_abc") is True


def test_feishu_first_text_asks_for_project_title(tmp_path):
    store = LocalStore(tmp_path)
    director = FakeDirector(turn=DirectorTurnResult(final_message="收到"))
    bot = FeishuBotService(store, director)  # type: ignore[arg-type]

    response = bot.handle_text("ou_abc", "查看状态")

    assert "请直接发送新小说的名字" in response
    assert director.calls == []


def test_feishu_pending_title_creates_project(tmp_path):
    store = LocalStore(tmp_path)
    director = FakeDirector(turn=DirectorTurnResult(final_message="收到"))
    bot = FeishuBotService(store, director)  # type: ignore[arg-type]

    bot.handle_text("ou_abc", "换一本")
    response = bot.handle_text("ou_abc", "苟在初圣")

    assert "已创建并切换到新项目：苟在初圣" in response
    assert store.state_path("苟在初圣").exists()
    assert FeishuSessionStore(store).get_current_project("ou_abc") == "苟在初圣"
    assert FeishuSessionStore(store).needs_new_project_title("ou_abc") is False


def test_feishu_text_calls_director_with_current_project(tmp_path):
    store = LocalStore(tmp_path)
    director = FakeDirector(turn=DirectorTurnResult(final_message="收到"))
    sessions = FeishuSessionStore(store)
    sessions.set_current_project("ou_abc", "demo")
    bot = FeishuBotService(store, director, sessions)  # type: ignore[arg-type]

    response = bot.handle_text("ou_abc", "查看状态")

    assert response == "收到"
    assert director.calls == [("demo", "查看状态", "feishu")]


def test_format_turn_result_renders_choices_and_artifacts():
    result = format_turn_result(
        DirectorTurnResult(
            immediate_message="我准备执行。",
            choices=[
                DirectorChoice(id="confirm", label="确认执行", value="1"),
                DirectorChoice(id="cancel", label="取消", value="2"),
            ],
            artifact_paths=["/tmp/project/reference_brief.md"],
        )
    )

    assert "我准备执行。" in result
    assert "1. 确认执行" in result
    assert "2. 取消" in result
    assert "/tmp/project/reference_brief.md" in result


def test_validate_feishu_settings_requires_app_credentials():
    with pytest.raises(FeishuConfigError, match="AI_NOVELIST_FEISHU_APP_ID"):
        validate_feishu_settings(Settings())
    with pytest.raises(FeishuConfigError, match="AI_NOVELIST_FEISHU_APP_SECRET"):
        validate_feishu_settings(Settings(feishu_app_id="cli_x"))


def test_extract_text_content_parses_feishu_text_payload():
    assert extract_text_content('{"text":"查看状态"}') == "查看状态"
    assert extract_text_content("plain text") == "plain text"


def test_recent_message_deduper_rejects_duplicate_message_ids():
    deduper = RecentMessageDeduper(max_size=2)

    assert deduper.first_seen("msg-1") is True
    assert deduper.first_seen("msg-1") is False
    assert deduper.first_seen("msg-2") is True
    assert deduper.first_seen("msg-3") is True
    assert deduper.first_seen("msg-1") is True
