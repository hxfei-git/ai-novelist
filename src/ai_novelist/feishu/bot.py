"""Feishu message handling without SDK-specific dependencies."""

from __future__ import annotations

from ai_novelist.director_service import DirectorService, DirectorTurnResult
from ai_novelist.feishu.session_store import FeishuSessionStore, normalize_project_id
from ai_novelist.storage.local_store import LocalStore


class FeishuBotService:
    def __init__(self, store: LocalStore, director: DirectorService, sessions: FeishuSessionStore | None = None) -> None:
        self.store = store
        self.director = director
        self.sessions = sessions or FeishuSessionStore(store)

    def handle_text(self, open_id: str, text: str) -> str:
        user_text = text.strip()
        if not open_id.strip():
            return "无法识别飞书用户。"
        if not user_text:
            return "请输入你的需求，或发送 /project 查看当前项目。"
        if user_text.startswith("/project"):
            return self._handle_project_command(open_id, user_text)

        project_id = self.sessions.current_project(open_id)
        self.store.create_project(project_id, project_id)
        turn = self.director.handle_turn(project_id, user_text, channel="feishu")
        return format_turn_result(turn)

    def _handle_project_command(self, open_id: str, text: str) -> str:
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            project_id = self.sessions.current_project(open_id)
            self.store.create_project(project_id, project_id)
            return f"当前项目：{project_id}\n发送 /project <project_id> 可切换或创建项目。"

        try:
            project_id = normalize_project_id(parts[1])
        except ValueError as exc:
            return f"项目切换失败：{exc}"
        self.store.create_project(project_id, project_id)
        self.sessions.set_current_project(open_id, project_id)
        return f"已切换到项目：{project_id}"


def format_turn_result(turn: DirectorTurnResult) -> str:
    lines: list[str] = []
    message = turn.immediate_message or turn.final_message
    if not message and turn.state is not None:
        message = turn.state.director_message
    lines.append(message.strip() if message else "已处理。")

    if turn.choices:
        lines.append("")
        lines.append("请选择：")
        for choice in turn.choices:
            lines.append(f"{choice.value}. {choice.label}")

    if turn.artifact_paths:
        lines.append("")
        lines.append("产物路径：")
        for path in turn.artifact_paths:
            lines.append(f"- {path}")
    return "\n".join(lines).strip()
