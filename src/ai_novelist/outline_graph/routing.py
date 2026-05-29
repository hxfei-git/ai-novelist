"""Routing helpers for the outline graph runtime."""

from __future__ import annotations

import re

from ai_novelist.outline.stage_contracts import OUTLINE_STAGES
from ai_novelist.state import NovelState


def _parse_compact_numbered_answers(text: str) -> dict[int, str]:
    matches = list(re.finditer(r"(?<!\d)(?P<index>\d+)(?:[.、)]\s*|(?=\D))", text))
    answers: dict[int, str] = {}
    for pos, match in enumerate(matches):
        start = match.end()
        end = matches[pos + 1].start() if pos + 1 < len(matches) else len(text)
        answer = text[start:end].strip(" ：:，,。；;\n\t")
        if answer:
            answers[int(match.group("index"))] = answer
    return answers


def negates_stage_advance(text: str) -> bool:
    return any(marker in text for marker in ("不要进入下一阶段", "不进入下一阶段", "先不进入下一阶段", "暂不进入下一阶段", "别进入下一阶段", "不要推进", "先不推进", "暂不推进"))


def should_run_outline_stage(text: str, state: NovelState) -> bool:
    if state.active_workflow == "outline":
        return True
    markers = ("生成大纲", "写大纲", "大纲", "方向", "概念", "核心冲突", "反转", "世界观", "人物", "故事流程", "主线", "分卷", "章节", "审稿", "锁定", "卖点", "读者", "承诺", "主题", "基调", "篇幅", "一句话梗概")
    return any(marker in text for marker in markers)



def is_final_outline_save_request(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"approve", "save outline", "保存大纲", "确认大纲"} or any(marker in text for marker in ("保存大纲", "确认大纲", "写入大纲"))


def is_lock_request(text: str) -> bool:
    return any(marker in text for marker in ("这个设定别改", "别改", "不要改", "保留", "锁定"))


def is_stage_confirmation(text: str) -> bool:
    lowered = text.strip().lower()
    exact = {"确认", "确定", "继续", "下一阶段", "进入下一阶段", "确认进入下一阶段", "确定进入下一阶段", "锁定", "锁定当前阶段", "通过", "认可", "同意", "ok", "yes", "approve", "confirm"}
    if lowered in exact:
        return True
    return any(marker in text for marker in ("确认进入下一阶段", "确定进入下一阶段", "锁定并进入", "进入下一阶段", "推进到下一阶段"))


def is_short_stage_confirmation(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {
        "下一阶段",
        "进入下一阶段",
        "确认进入下一阶段",
        "确定进入下一阶段",
        "推进到下一阶段",
        "advance",
    }


def delegates_stage_decision(text: str) -> bool:
    markers = ("你决定", "由你决定", "交给你", "系统决定", "系统裁量", "按你建议", "按系统建议", "按当前建议", "默认处理", "你来定", "你看着办")
    wants_advance = any(marker in text for marker in ("下一阶段", "进入", "推进", "继续", "锁定", "确定"))
    return any(marker in text for marker in markers) and wants_advance


def answers_stage_pending_questions(text: str) -> bool:
    if is_short_stage_confirmation(text) or delegates_stage_decision(text):
        return False
    if _parse_compact_numbered_answers(text):
        return True
    if re.search(r"(^|[\s，,；;])\d+[.、)]", text):
        return True
    return any(marker in text for marker in ("回答", "补充", "选择", "选", "采用", "接受", "接收", "同意", "设为", "改成"))


def is_revision_request(text: str) -> bool:
    return any(marker in text for marker in ("修改", "调整", "重做", "重新", "不要", "更", "太", "强化", "补充"))



def is_stage_switch_request(text: str) -> bool:
    return any(marker in text for marker in ("回到", "重做", "重新做", "切换到")) or is_revision_request(text)


def detect_stage_reference(text: str) -> str | None:
    mapping = [
        ("direction", ("方向", "定位", "类型", "卖点", "故事概念", "概念", "一句话故事", "一句话梗概", "核心概念", "核心卖点", "目标读者", "故事承诺", "主题表达", "主角方向", "故事基调", "篇幅结构")),
        ("worldbuilding", ("世界观", "设定", "规则")),
        ("characters", ("人物", "人设", "关系", "反派", "势力")),
        ("story_flow", ("故事流程", "流程", "主线", "节奏", "伏笔")),
        ("volume_outline", ("分卷", "卷纲", "卷内", "卷间", "总大纲", "大纲草案", "草案")),
        ("chapter_outline", ("章节大纲", "章节拆分", "章节钩子", "章节", "细纲")),
        ("review_lock", ("审稿", "锁定", "终审")),
    ]
    for stage, markers in mapping:
        if any(marker in text for marker in markers):
            return stage
    return None


def stage_number(stage: str) -> int:
    return OUTLINE_STAGES.index(stage) + 1 if stage in OUTLINE_STAGES else len(OUTLINE_STAGES)


def next_outline_stage(stage: str) -> str | None:
    if stage == "chapter_outline":
        return None
    if stage not in OUTLINE_STAGES:
        return "direction"
    index = OUTLINE_STAGES.index(stage)
    if index + 1 >= len(OUTLINE_STAGES):
        return None
    return OUTLINE_STAGES[index + 1]


def route_after_human_feedback(data: dict) -> str:
    action = data.get("next_action", "end")
    if action in {"persist_outline", "revise_outline", "propose_directions", "review_outline"}:
        return action
    return "end"
