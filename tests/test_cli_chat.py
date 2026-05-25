from ai_novelist.cli import build_parser, run_chat_command
from ai_novelist.config import Settings
from ai_novelist.director_service import DirectorDecision, DirectorTurnResult
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class FakeDirectorService:
    seen_inputs = []

    def __init__(self, **kwargs):
        self.store = kwargs["store"]

    def handle_turn(self, project_id: str, user_text: str, channel: str = "cli") -> DirectorTurnResult:
        self.seen_inputs.append(user_text)
        state = self.store.load_state(project_id)
        if user_text == "boom":
            state.director_action = "write_chapter"
            state.director_message = "写作失败，但会话仍在。"
            state.error = "Codex CLI timed out after 30s"
            self.store.save_state(state)
            return DirectorTurnResult(final_message=state.director_message, state=state, decision=DirectorDecision(action="write_chapter"))
        if user_text == "exit":
            state.director_action = "stop"
            state.director_message = "已结束本次创作对话。"
            state.error = ""
            self.store.save_state(state)
            return DirectorTurnResult(final_message=state.director_message, state=state, decision=DirectorDecision(action="stop"))
        state.director_action = "chat"
        state.director_message = "继续。"
        state.error = ""
        self.store.save_state(state)
        return DirectorTurnResult(final_message=state.director_message, state=state, decision=DirectorDecision(action="chat"))


def test_run_chat_command_prints_turn_error_and_continues(monkeypatch, tmp_path, capsys):
    store = LocalStore(tmp_path)
    parser = build_parser()
    args = parser.parse_args(["chat", "--project", "demo", "--mock"])
    settings = Settings(projects_dir=tmp_path)
    inputs = iter(["boom", "exit"])
    FakeDirectorService.seen_inputs = []

    monkeypatch.setattr("ai_novelist.cli.DirectorService", FakeDirectorService)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    assert run_chat_command(args, store, settings) == 0

    captured = capsys.readouterr()
    assert "错误：Codex CLI timed out after 30s" in captured.err
    assert "Director> 写作失败，但会话仍在。" in captured.out
    assert "Director> 已结束本次创作对话。" in captured.out
    assert FakeDirectorService.seen_inputs == ["boom", "exit"]
