"""Contracts for active outline collaboration stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CanonPolicy = Literal[
    "no_new_canon",
    "draft_canon_allowed",
    "locked_only",
    "audit_only",
]


@dataclass(frozen=True)
class StageSlot:
    key: str
    label: str
    description: str
    required: bool = True
    max_items: int | None = None
    max_chars_per_item: int | None = None


@dataclass(frozen=True)
class StageContract:
    key: str
    label: str
    purpose: str
    canon_policy: CanonPolicy
    allowed_intents: tuple[str, ...]
    forbidden_intents: tuple[str, ...]
    slots: tuple[StageSlot, ...]
    confirmation_policy: str
    max_questions: int = 1
    max_total_chars: int | None = None


ACTIVE_OUTLINE_STAGES = [
    "direction",
    "worldbuilding",
    "characters",
    "story_flow",
    "volume_outline",
    "chapter_outline",
    "review_lock",
]
OUTLINE_STAGES = list(ACTIVE_OUTLINE_STAGES)
LEGACY_OUTLINE_STAGES = {"concept", "outline_draft"}

STAGE_LABELS = {
    "direction": "方向定位",
    "concept": "故事概念（旧版）",
    "worldbuilding": "世界观设定",
    "characters": "人物关系",
    "story_flow": "故事流程",
    "volume_outline": "分卷大纲",
    "chapter_outline": "章节大纲",
    "review_lock": "审稿锁定",
    "done": "已锁定",
}


STAGE_CONTRACTS = {
    "direction": StageContract(
        key="direction",
        label="方向定位",
        purpose="确定故事类型、主角姿态、读者期待、冲突方向和情绪边界。",
        canon_policy="no_new_canon",
        allowed_intents=("故事类型", "主角行动姿态", "核心看点", "核心冲突方向", "情绪边界", "创作禁区"),
        forbidden_intents=("具体代价形式", "修炼体系", "门派制度", "专有名词清单", "章节桥段", "人物小传"),
        slots=(
            StageSlot("genre", "类型定位", "这是什么类型的故事", True, 1, 60),
            StageSlot("protagonist_stance", "主角姿态", "主角主要如何行动", True, 1, 60),
            StageSlot("reader_payoff", "核心看点", "读者期待的爽点或张力", True, 1, 70),
            StageSlot("central_conflict", "核心冲突", "长期冲突方向", True, 1, 70),
            StageSlot("emotional_boundary", "情绪边界", "作品气质与禁区", True, 1, 70),
        ),
        confirmation_policy="只问方向偏好；不要求确认具体世界机制。",
        max_questions=1,
        max_total_chars=420,
    ),
    "worldbuilding": StageContract(
        key="worldbuilding",
        label="世界观设定",
        purpose="建立支撑故事长期写作的世界内部结构。",
        canon_policy="draft_canon_allowed",
        allowed_intents=("力量或修炼体系", "门派/组织生态", "势力格局与理念", "资源与场景素材", "可持续冲突来源"),
        forbidden_intents=("抽象剧情算法", "代价红线式标题", "人物小传", "章节流程", "结局安排", "产品规则语言"),
        slots=(
            StageSlot("power_system", "力量体系", "修炼/技术/能力如何存在并限制角色", True, 3, 120),
            StageSlot("home_institution", "本门或核心组织", "主角所在门派/组织/城市生态", True, 3, 120),
            StageSlot("factions", "势力与理念", "外部势力、阵营理念或利益冲突", False, 3, 120),
            StageSlot("daily_scenes", "日常场景与素材", "可反复进入章节的地点、任务、仪式、物件", True, 5, 80),
            StageSlot("open_questions", "待确认", "真正影响后续写作的世界缺口", False, 3, 120),
        ),
        confirmation_policy="只问会影响长期写作的世界缺口；不得让用户选择模型自造机制。",
        max_questions=3,
        max_total_chars=1200,
    ),
    "characters": StageContract(
        key="characters",
        label="人物关系",
        purpose="定义推动主线冲突的人物目标、关系牵制和功能分工。",
        canon_policy="locked_only",
        allowed_intents=("主角目标", "角色秘密", "角色资源", "关系张力", "人物主线功能"),
        forbidden_intents=("新世界规则", "完整剧情流程", "福利机制", "亲密行为规则"),
        slots=(
            StageSlot("protagonist", "主角", "目标、缺陷、秘密、资源、底线", True, 1, 220),
            StageSlot("relationships", "关键关系", "帮助、牵制、误解、背叛路径", True, 4, 100),
            StageSlot("opposition", "对立面", "欲望、资源、压迫方式、主线关系", True, 3, 100),
            StageSlot("open_questions", "待确认", "仅限角色功能缺口", False, 2, 120),
        ),
        confirmation_policy="只问角色功能缺口或关系基调。",
        max_questions=2,
        max_total_chars=1100,
    ),
    "story_flow": StageContract(
        key="story_flow",
        label="故事流程",
        purpose="定义主线推进、转折升级、信息释放和终局方向。",
        canon_policy="locked_only",
        allowed_intents=("开局压力", "阶段目标", "失败风险", "中段反转", "终局方向", "伏笔回收方向"),
        forbidden_intents=("新世界规则", "逐章细纲", "正文片段", "新系统名"),
        slots=(
            StageSlot("opening_pressure", "开局压力", "故事如何启动", True, 3, 100),
            StageSlot("mid_escalation", "中段升级", "升级与反转", True, 4, 100),
            StageSlot("late_conflict", "后段冲突显形", "主线冲突显形方式", True, 3, 100),
            StageSlot("ending_direction", "终局方向", "终局目标与代价", True, 2, 100),
            StageSlot("foreshadowing", "伏笔布置与回收方向", "主要伏笔链路", True, 4, 90),
        ),
        confirmation_policy="只问主线走向或终局方向缺口。",
        max_questions=2,
        max_total_chars=1200,
    ),
    "volume_outline": StageContract(
        key="volume_outline",
        label="分卷大纲",
        purpose="定义卷级结构、卷内矛盾、高潮与卷间承接。",
        canon_policy="locked_only",
        allowed_intents=("卷目标", "卷矛盾", "卷高潮", "主角变化", "卷间钩子"),
        forbidden_intents=("逐章细节", "正文场景", "临时新 canon"),
        slots=(
            StageSlot("volumes", "分卷结构", "卷名或卷功能", True, 5, 90),
            StageSlot("goals", "卷目标", "每卷必须完成的变化", True, 5, 100),
            StageSlot("conflicts", "卷内主要矛盾", "卷级冲突", True, 5, 100),
            StageSlot("climaxes", "卷级高潮", "卷收束事件", True, 5, 90),
            StageSlot("bridges", "卷间钩子", "下一卷启动条件", True, 5, 90),
        ),
        confirmation_policy="只问分卷规模或高潮方向缺口。",
        max_questions=2,
        max_total_chars=1400,
    ),
    "chapter_outline": StageContract(
        key="chapter_outline",
        label="章节大纲",
        purpose="给出前若干章可直接执行的章节规划。",
        canon_policy="locked_only",
        allowed_intents=("章节目标", "主要冲突", "信息增量", "人物状态变化", "结尾钩子", "连续性提醒"),
        forbidden_intents=("正文对白", "完整场景卡", "新世界规则"),
        slots=(
            StageSlot("chapter_ids", "章节编号", "仅限首批章节", True, 12, 16),
            StageSlot("chapter_goals", "章节目标", "每章目标", True, 12, 80),
            StageSlot("chapter_conflicts", "主要冲突", "每章冲突", True, 12, 80),
            StageSlot("info_gain", "信息增量", "每章新增信息", True, 12, 80),
            StageSlot("state_change", "人物状态变化", "每章状态变化", True, 12, 80),
            StageSlot("hooks", "结尾钩子", "每章钩子", True, 12, 80),
        ),
        confirmation_policy="只问首批章节范围或开篇策略。",
        max_questions=2,
        max_total_chars=1600,
    ),
    "review_lock": StageContract(
        key="review_lock",
        label="审稿锁定",
        purpose="审计前序阶段一致性，给出锁定建议与风险。",
        canon_policy="audit_only",
        allowed_intents=("一致性检查", "锁定建议", "未解决风险", "回改阶段", "章节卡准备度"),
        forbidden_intents=("新设定", "新人物", "新剧情重写"),
        slots=(
            StageSlot("consistency", "阶段承接检查", "阶段之间是否冲突", True, 8, 90),
            StageSlot("locked_canon", "已锁定 canon 清单", "可进入写作的稳定项", True, 12, 80),
            StageSlot("risks", "未解决风险", "风险项与影响", True, 8, 90),
            StageSlot("fix_stages", "需要回改的阶段", "回改建议", False, 4, 90),
            StageSlot("ready", "是否可进入章节卡", "pass/revise/stop", True, 1, 40),
        ),
        confirmation_policy="不问创意题，只问是否锁定或回改。",
        max_questions=1,
        max_total_chars=1200,
    ),
}

LEGACY_STAGE_ALIAS = {
    "concept": "direction",
    "outline_draft": "volume_outline",
}


def get_stage_contract(stage: str) -> StageContract:
    stage_key = LEGACY_STAGE_ALIAS.get(stage, stage)
    if stage_key not in STAGE_CONTRACTS:
        raise KeyError(stage)
    return STAGE_CONTRACTS[stage_key]


def stage_order_index(stage: str) -> int:
    stage_key = LEGACY_STAGE_ALIAS.get(stage, stage)
    if stage_key not in OUTLINE_STAGES:
        return len(OUTLINE_STAGES)
    return OUTLINE_STAGES.index(stage_key)
