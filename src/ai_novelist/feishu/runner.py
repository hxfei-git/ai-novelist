"""Feishu long-connection runner."""

from __future__ import annotations

import json
from collections.abc import Callable

from ai_novelist.config import Settings


class FeishuConfigError(RuntimeError):
    """Raised when Feishu runtime configuration is incomplete."""


def validate_feishu_settings(settings: Settings) -> None:
    if not settings.feishu_app_id:
        raise FeishuConfigError("缺少 AI_NOVELIST_FEISHU_APP_ID")
    if not settings.feishu_app_secret:
        raise FeishuConfigError("缺少 AI_NOVELIST_FEISHU_APP_SECRET")


def run_feishu_long_connection(settings: Settings, handle_text: Callable[[str, str], str]) -> None:
    validate_feishu_settings(settings)
    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import P2ImMessageReceiveV1, ReplyMessageRequest, ReplyMessageRequestBody
    except ModuleNotFoundError as exc:
        raise FeishuConfigError('缺少 lark-oapi，请先安装：pip install -e ".[feishu]"') from exc

    client = lark.Client.builder().app_id(settings.feishu_app_id).app_secret(settings.feishu_app_secret).build()

    def on_message(data: P2ImMessageReceiveV1) -> None:
        event = data.event
        sender = getattr(event, "sender", None)
        message = getattr(event, "message", None)
        open_id = getattr(getattr(sender, "sender_id", None), "open_id", "") if sender else ""
        message_id = getattr(message, "message_id", "") if message else ""
        message_type = getattr(message, "message_type", "") if message else ""
        content = getattr(message, "content", "") if message else ""
        if message_type != "text":
            reply = "当前只支持文本消息。"
        else:
            reply = handle_text(open_id, extract_text_content(content))
        if message_id:
            request = ReplyMessageRequest.builder().message_id(message_id).request_body(
                ReplyMessageRequestBody.builder().content(json.dumps({"text": reply}, ensure_ascii=False)).msg_type("text").build()
            ).build()
            client.im.v1.message.reply(request)

    event_handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(on_message).build()
    ws_client = lark.ws.Client(settings.feishu_app_id, settings.feishu_app_secret, event_handler=event_handler)
    ws_client.start()


def extract_text_content(content: str) -> str:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return content
    if isinstance(data, dict):
        return str(data.get("text", "")).strip()
    return content
