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
        purpose="建立可被人物、主线、分卷、章节和小说圣经复用的完整小说世界设定基座。",
        canon_policy="draft_canon_allowed",
        allowed_intents=(
            "完整小说世界大纲",
            "世界核心设定",
            "世界格局",
            "地理与环境",
            "历史背景",
            "时代背景",
            "世界规则",
            "力量体系",
            "成长体系",
            "能力分类体系",
            "职业与身份体系",
            "资源体系",
            "经济体系",
            "政治与权力体系",
            "势力体系",
            "社会结构",
            "文化体系",
            "宗教信仰神话",
            "科技工艺生产力",
            "交通通讯",
            "法律秩序",
            "军事战争",
            "种族族群生灵",
            "重要地点",
            "危险体系",
            "知识教育",
            "日常生活",
            "信息舆论",
            "核心矛盾",
            "主角与世界关系",
            "主要人物群体",
            "主线时间线",
            "隐藏真相",
            "结局后世界格局",
        ),
        forbidden_intents=(
            "按题材分类替代世界组成部分",
            "只输出世界运行原则/关键边界/冲突资源/代价红线四段摘要",
            "只写抽象口号",
            "只写专有名词清单",
            "空标题模板",
            "过细行政流程",
            "申请表",
            "审批",
            "备案",
            "考评",
            "绩效",
            "KPI",
            "无代价万能规则",
            "完整人物小传",
            "章节正文",
            "分卷章节安排",
            "与主线无关的猎奇机制",
        ),
        slots=(
            StageSlot("world_core", "世界核心设定", "世界名称、类型、核心规则、核心冲突、主舞台和独特设定", True, 5, 120),
            StageSlot("world_structure", "格局地理历史时代", "空间结构、地理环境、历史背景和时代张力", True, 5, 120),
            StageSlot("power_growth", "规则力量成长", "世界规则、力量来源、成长代价和能力分类", True, 5, 120),
            StageSlot("society_power", "社会资源权力", "职业、资源经济、政治势力、社会文化和秩序系统", True, 8, 120),
            StageSlot("plot_service", "剧情服务关系", "核心矛盾、主角关系、人物群体、时间线、隐藏真相和终局格局", True, 8, 120),
            StageSlot("open_questions", "待确认", "真正影响后续人物、主线或章节写作的世界缺口", False, 5, 120),
        ),
        confirmation_policy="只问会影响后续人物、主线、分卷或章节写作的世界缺口；不得让用户选择模型自造机制。",
        max_questions=5,
        max_total_chars=None,
    ),
    "characters": StageContract(
        key="characters",
        label="人物关系",
        purpose="定义推动主线冲突的人物目标、关系牵制、成人亲密张力和功能分工。",
        canon_policy="locked_only",
        allowed_intents=("主角目标", "角色秘密", "角色资源", "关系张力", "成人亲密张力", "情色/福利关系功能", "人物主线功能"),
        forbidden_intents=("新世界规则", "完整剧情流程", "无主线功能成人内容", "未成年性化", "非自愿亲密"),
        slots=(
            StageSlot("protagonist", "主角", "目标、缺陷、秘密、资源、底线", True, 1, 220),
            StageSlot("relationships", "关键关系", "帮助、牵制、误解、背叛路径", True, 4, 100),
            StageSlot("opposition", "对立面", "欲望、资源、压迫方式、主线关系", True, 3, 100),
            StageSlot("open_questions", "待确认", "仅限角色功能缺口", False, 2, 120),
        ),
        confirmation_policy="只问角色功能、关系基调或成人亲密尺度缺口。",
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
