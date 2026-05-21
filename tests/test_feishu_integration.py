from dataclasses import dataclass, field

import pytest

from ai_novelist.config import Settings
from ai_novelist.director_service import DirectorChoice, DirectorTurnResult
from ai_novelist.feishu import FeishuBotService, FeishuConfigError, extract_text_content, format_turn_result
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


def test_feishu_project_command_shows_current_project(tmp_path):
    store = LocalStore(tmp_path)
    director = FakeDirector()
    bot = FeishuBotService(store, director)  # type: ignore[arg-type]

    response = bot.handle_text("ou_abc", "/project")

    assert "当前项目：feishu-ou_abc" in response
    assert store.state_path("feishu-ou_abc").exists()


def test_feishu_text_calls_director_with_current_project(tmp_path):
    store = LocalStore(tmp_path)
    director = FakeDirector(turn=DirectorTurnResult(final_message="收到"))
    bot = FeishuBotService(store, director)  # type: ignore[arg-type]

    response = bot.handle_text("ou_abc", "查看状态")

    assert response == "收到"
    assert director.calls == [("feishu-ou_abc", "查看状态", "feishu")]


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
