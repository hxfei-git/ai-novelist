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
        purpose="确定整本书的核心故事方向、读者期待、故事承诺、主题命题、主角运动轨道、主要冲突、阅读基调和适合篇幅，为后续世界观、人物、剧情和章节阶段提供约束。",
        canon_policy="no_new_canon",
        allowed_intents=(
            "一句话梗概",
            "核心卖点",
            "类型题材",
            "目标读者",
            "故事承诺",
            "主题表达",
            "主角方向",
            "核心冲突",
            "故事基调",
            "篇幅结构",
        ),
        forbidden_intents=(
            "展开完整世界观规则",
            "编写人物完整档案",
            "制定分卷 / 章节大纲",
            "生成具体剧情桥段",
            "生成复杂组织、境界、势力、地图、制度细则",
            "强行绑定平台",
            "为信息不足处编造确定性设定",
        ),
        slots=(
            StageSlot("logline", "一句话梗概", "主角、处境、目标和故事主要吸引点", True, 1, 120),
            StageSlot("hook", "核心卖点", "最值得读者期待的地方", True, 1, 120),
            StageSlot("genre", "类型题材", "主类型、子类型、题材元素和读者预期", True, 3, 140),
            StageSlot("reader", "目标读者", "主要受众画像与阅读偏好", True, 1, 120),
            StageSlot("promise", "故事承诺", "读者继续读下去会持续看到什么", True, 1, 140),
            StageSlot("theme", "主题表达", "表层主题、深层命题和价值取向", True, 3, 140),
            StageSlot("protagonist", "主角方向", "主角原型、初始处境、外在目标、内在缺口、成长方向和核心冲突", True, 6, 120),
            StageSlot("conflict", "核心冲突", "外部冲突、内部冲突和关系冲突", True, 3, 120),
            StageSlot("tone", "故事基调", "整体基调、情绪比例、可强化情绪和需要避免的情绪", True, 4, 120),
            StageSlot("length", "篇幅结构", "预计体量、叙事结构、节奏特点和展开方式", True, 4, 120),
        ),
        confirmation_policy="只问会影响后续世界观、人物、剧情或篇幅判断的高层缺口；不要要求确认具体世界机制。",
        max_questions=1,
        max_total_chars=2800,
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
        purpose="建立全文人物池、关系演化蓝图和信息差网络，确保角色关系能推动主线、章节和终局。",
        canon_policy="locked_only",
        allowed_intents=(
            "全角色总表",
            "角色个人驱动力",
            "主角关系弧光",
            "核心人物关系卡",
            "关系演化时间轴",
            "读者认知进度表",
            "秘密与信息差网络",
            "阵营 / 组织关系",
            "关系冲突类型",
            "关系事件种子",
            "角色退场与关系遗产",
            "锁定项与可变项",
            "待确认问题",
        ),
        forbidden_intents=(
            "新世界规则",
            "完整剧情流程",
            "章节正文",
            "场景卡",
            "无主线功能角色堆砌",
            "凭空新增阵营/组织",
            "未成年性化",
            "非自愿亲密",
            "把关系写成审批/绩效/流程表",
        ),
        slots=(
            StageSlot("character_pool", "全角色总表", "角色 ID、层级、叙事职能、登场阶段、关系重要性", True, 24, 120),
            StageSlot("character_drives", "角色个人驱动力", "公开身份、真实身份、目标、秘密、关系诉求、行动方式", True, 18, 120),
            StageSlot("protagonist_arc", "主角关系弧光", "主角的关系缺失、压力源、成长变化和终局状态", True, 1, 220),
            StageSlot("relationship_cards", "核心人物关系卡", "核心关系的起点、变化、终点和剧情用途", True, 8, 120),
            StageSlot("evolution_timeline", "关系演化时间轴", "开局、前期、中期、后期和终局的关系变化", True, 8, 120),
            StageSlot("reader_progress", "读者认知进度表", "作者、角色和读者三层认知差", True, 6, 120),
            StageSlot("secret_network", "秘密与信息差网络", "秘密、误解、伏笔、揭露阶段和关系影响", True, 8, 120),
            StageSlot("faction_links", "阵营 / 组织关系", "从 worldbuilding 继承的组织关系和内部张力", False, 6, 120),
            StageSlot("conflict_types", "关系冲突类型", "情感、利益、价值观、身份、信息与历史冲突", True, 8, 100),
            StageSlot("event_seeds", "关系事件种子", "初遇、合作、冲突、背叛、揭秘、救援、和解、决裂", True, 8, 120),
            StageSlot("exit_legacy", "角色退场与关系遗产", "退场变化、留下的秘密、债务、道具和情感影响", True, 6, 120),
            StageSlot("locks", "锁定项与可变项", "必须锁定的关系起点终点、揭露顺序和可变细节", True, 8, 120),
            StageSlot("open_questions", "待确认问题", "只问会影响全文结构的问题", False, 4, 120),
        ),
        confirmation_policy="只问会影响全文关系结构、信息揭露顺序或锁定项的问题；不要把角色当成可自由增删的模板表。",
        max_questions=4,
        max_total_chars=3200,
    ),
    "story_flow": StageContract(
        key="story_flow",
        label="故事流程",
        purpose="建立全书级故事流程蓝图，定义主线因果链、阶段目标升级、冲突递进、人物弧光嵌入、信息释放、爽点情绪、分卷衔接和结局路径，为后续分卷大纲与章节大纲提供骨架。",
        canon_policy="locked_only",
        allowed_intents=(
            "故事起点",
            "引发事件",
            "主线问题",
            "阶段目标",
            "终局目标",
            "阶段划分",
            "冲突升级",
            "关键剧情节点",
            "人物弧光嵌入",
            "关系变化流程",
            "反派镜像",
            "伏笔悬念",
            "揭示节奏",
            "爽点兑现",
            "情绪节奏",
            "世界观展开",
            "阵营推进",
            "失败代价",
            "反转认知",
            "分卷衔接",
            "结局路径",
        ),
        forbidden_intents=(
            "新世界规则",
            "逐章细纲",
            "章节正文",
            "正文片段",
            "完整分卷细纲",
            "新系统名",
            "新增与世界观冲突的 canon",
            "新增与人物关系冲突的人物终局",
            "把候选内容写成已锁定正典",
        ),
        slots=(
            StageSlot("mainline_progression", "故事主线推进", "说明故事起点、引发事件、主角初始目标、主线问题、阶段性目标升级与终局目标。", True, 6, 180),
            StageSlot("stage_map", "故事阶段划分", "按开局、成长、扩张、转折、高潮、结局说明每阶段功能、核心事件类型和阶段出口。", True, 6, 220),
            StageSlot("conflict_escalation", "核心冲突升级路径", "从个人困境升级到组织/阵营、制度/规则、终极价值矛盾，并标注敌人、代价和成长作用。", True, 4, 220),
            StageSlot("key_plot_nodes", "关键剧情节点", "规划开篇钩子、第一次选择、第一次胜利、第一次失败、中段大转折、黑暗时刻、最终觉醒、终局对决、结局回响。", True, 9, 160),
            StageSlot("character_arc_embedding", "人物弧光嵌入流程", "说明主角缺陷与欲望如何被剧情推动变化，关键人物如何影响主角，重要关系如何变化，反派如何镜像主角。", True, 6, 220),
            StageSlot("foreshadowing_reveal_cadence", "伏笔、悬念与揭示节奏", "定义核心悬念、阶段悬念、伏笔布置点、真相分层揭示顺序与回收方向。", True, 6, 220),
            StageSlot("payoff_promise_cadence", "爽点 / 卖点兑现节奏", "承接方向定位的核心卖点和故事承诺，安排开局卖点、阶段爽点、升级爽点、情绪释放点。", True, 5, 200),
            StageSlot("emotional_pacing", "情绪节奏与阅读体验", "规划整体情绪曲线、阶段情绪目标、高低起伏、缓冲与爆发、分卷节奏倾向。", True, 5, 200),
            StageSlot("worldbuilding_reveal_order", "世界观展开顺序", "说明世界规则、地图、历史、力量体系、底层秘密如何随剧情逐步展示。", True, 5, 200),
            StageSlot("faction_progression", "阵营与势力推进", "规划势力登场顺序、关系变化、主角阵营位置变化、势力冲突如何压迫选择。", True, 5, 200),
            StageSlot("cost_failure_mechanism", "代价与失败机制", "规定能力代价、选择代价、关系代价、世界代价、必败节点与后果。", True, 5, 200),
            StageSlot("reversals_cognition", "反转与认知升级", "规划开局、中段、后期、终局的身份/阵营/目标/规则/真相/情感反转，以及反转后的剧情影响。", True, 5, 200),
            StageSlot("volume_bridge_direction", "分卷衔接方向", "为后续 volume_outline 提供骨架：每卷功能、核心问题、阶段高潮、卷尾钩子。不是章节大纲。", True, 5, 180),
            StageSlot("ending_path", "结局路径", "提前规划主线、人物、关系、世界、主题和余味/续作空间的结局方向。", True, 6, 200),
        ),
        confirmation_policy="请确认故事流程中的主线目标升级、核心失败代价、关键反转尺度、终局选择是否符合预期；若有未锁定设定，请标为候选而不是写成正典。",
        max_questions=3,
        max_total_chars=8000,
    ),
    "volume_outline": StageContract(
        key="volume_outline",
        label="分卷大纲",
        purpose="定义卷级蓝图、卷内推进、人物推进、世界观释放、爽点悬念和卷间承接，为后续章节大纲提供稳定骨架。",
        canon_policy="locked_only",
        allowed_intents=(
            "分卷总体规划",
            "单卷基础定位",
            "本卷一句话概括",
            "本卷阶段目标",
            "本卷核心冲突",
            "本卷剧情推进",
            "本卷关键节点",
            "本卷人物推进",
            "本卷世界观释放",
            "本卷爽点与卖点兑现",
            "本卷伏笔、悬念与信息差",
            "本卷情绪节奏",
            "本卷开头与结尾",
            "与前后卷的衔接",
            "仍需确认的问题",
            "卷级约束与待确认项",
            "可选约束备注",
        ),
        forbidden_intents=(
            "逐章细纲",
            "章节正文",
            "正文片段",
            "完整场景卡",
            "替代 chapter_outline",
            "替代 story_flow 重写全书主线",
            "新增无来源 canon",
            "复制完整 worldbuilding 或 characters",
            "只输出卷名和卷目标的短摘要",
        ),
        slots=(
            StageSlot("volume_master_plan", "分卷总体规划", "分卷数量、卷名、章节/字数范围、阶段位置、叙事功能和全书推进逻辑", True, 8, 220),
            StageSlot("volume_positioning", "单卷基础定位", "卷序号、卷名、副标题、范围、所属故事阶段、主功能和副功能", True, 8, 200),
            StageSlot("volume_loglines", "本卷一句话概括", "每卷一句话剧情、核心看点、主要问题、读者期待和阶段性承诺", True, 8, 220),
            StageSlot("volume_goals", "本卷阶段目标", "主角目标、被迫面对、阶段任务、卷末得到/失去和成败后果", True, 8, 220),
            StageSlot("volume_conflicts", "本卷核心冲突", "人物、规则、环境、内心、关系、阵营冲突及升级方式", True, 8, 220),
            StageSlot("volume_plot_progression", "本卷剧情推进", "开卷状态、入卷事件、前期推进、中段转折、低谷、高潮、余波和下卷钩子", True, 8, 260),
            StageSlot("volume_key_nodes", "本卷关键节点", "开卷事件、推动事件、受挫、中段反转、重大选择、关键揭示、高潮和结尾钩子", True, 8, 220),
            StageSlot("volume_character_progression", "本卷人物推进", "主角变化、关键配角、重要关系、新登场/退场、对手推进和信息差变化", True, 8, 220),
            StageSlot("volume_world_reveal", "本卷世界观释放", "新地点、新势力、新规则、历史背景、体系推进、隐藏真相和保留未知", True, 8, 220),
            StageSlot("volume_payoffs", "本卷爽点与卖点兑现", "高光场面、升级、逆转、情感爆点、悬疑揭示、大场面和桥段期待", True, 8, 220),
            StageSlot("volume_foreshadowing", "本卷伏笔、悬念与信息差", "承接伏笔、新增伏笔、揭示、保留、误导、信息差和后续反转条件", True, 8, 220),
            StageSlot("volume_emotional_pacing", "本卷情绪节奏", "开卷、中段、高潮、结尾情绪，整体体验、缓冲和反差", True, 8, 200),
            StageSlot("volume_opening_ending", "本卷开头与结尾", "第一场戏、开头钩子、入卷问题、结尾解决/遗留和下一卷入口", True, 8, 220),
            StageSlot("volume_bridges", "与前后卷的衔接", "继承前卷后果、本卷解决/制造的问题、下一卷接起点和全书作用", True, 8, 220),
        ),
        confirmation_policy="只问会影响分卷数量、卷末大事件、关键人物命运、世界观释放顺序或不可逆设定的问题；不要让用户在模型自造的细枝末节中选择。",
        max_questions=3,
        max_total_chars=10000,
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
