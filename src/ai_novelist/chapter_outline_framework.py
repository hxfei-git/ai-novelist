"""Chapter outline framework and profile rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterOutlineModule:
    key: str
    heading: str
    purpose: str
    ability_points: tuple[str, ...]


@dataclass(frozen=True)
class ChapterProfile:
    key: str
    label: str
    pacing_function: str
    intensity: int
    hook_strength: str
    focus: str
    minimum_points: tuple[str, ...]


CHAPTER_OUTLINE_STATUSES: tuple[str, ...] = ("详写", "简写", "本章不适用")

CHAPTER_OUTLINE_MODULES: tuple[ChapterOutlineModule, ...] = (
    ChapterOutlineModule(
        "positioning",
        "基础定位",
        "判断这一章是什么章、写到哪里、是否关键，以及和卷级节奏的关系。",
        ("单章基础定位", "本章一句话概括", "本章叙事功能", "本章阶段目标"),
    ),
    ChapterOutlineModule(
        "plot_execution",
        "剧情执行方案",
        "把本章从起因推进到结果，但不细写成场景卡或正文。",
        ("本章核心冲突", "本章剧情推进"),
    ),
    ChapterOutlineModule(
        "character_reader",
        "人物/关系/读者认知",
        "记录人物状态、关系变化和读者知道/不知道/误以为的信息。",
        ("本章人物推进", "本章关系推进", "本章读者认知进度", "本章信息差网络"),
    ),
    ChapterOutlineModule(
        "hooks_emotion",
        "伏笔/爽点/情绪/开头结尾",
        "控制本章的追读动力、情绪曲线、爽点或低谷的真实用途。",
        ("本章伏笔、悬念与揭示", "本章爽点 / 卖点兑现", "本章情绪节奏", "本章开头设计", "本章结尾设计"),
    ),
    ChapterOutlineModule(
        "world_continuity",
        "世界观/能力资源/代价/阵营/连续性",
        "记录设定释放、能力资源变化、代价、阵营推进和跨章连续性。",
        ("本章世界观释放", "本章能力、成长与资源变化", "本章代价与失败机制", "本章阵营与势力推进", "本章连续性检查"),
    ),
    ChapterOutlineModule(
        "execution_review",
        "写作执行与审稿检查",
        "给后续章节卡、正文生成和审稿提供可执行限制。",
        ("本章写作执行要求", "本章正文生成素材", "本章审稿检查项"),
    ),
)


CHAPTER_PROFILES: tuple[ChapterProfile, ...] = (
    ChapterProfile(
        "opening",
        "开篇章",
        "setup",
        3,
        "hard",
        "建立初始处境、主角动机、第一读点和读者继续读下去的理由。",
        ("开头钩子", "主角初始状态", "核心悬念", "结尾状态"),
    ),
    ChapterProfile(
        "setup",
        "铺垫章",
        "setup",
        3,
        "soft",
        "布置后续冲突所需的人物、信息、资源和误导，不抢先爆发。",
        ("铺垫对象", "信息增量", "后续回收位置"),
    ),
    ChapterProfile(
        "transition",
        "过渡章",
        "transition",
        2,
        "none",
        "承接上一段后果，完成位置、目标或状态转换，保留轻钩子。",
        ("承接上一章", "状态变化", "轻钩子"),
    ),
    ChapterProfile(
        "conflict",
        "冲突章",
        "build",
        4,
        "soft",
        "让人物目标和阻力正面摩擦，推进主线或关系压力。",
        ("外部冲突", "选择困境", "结果后果"),
    ),
    ChapterProfile(
        "payoff",
        "爽点章",
        "build",
        4,
        "soft",
        "兑现前文期待，给出压制、反击、收益和余波。",
        ("爽点铺垫", "兑现方式", "余波代价"),
    ),
    ChapterProfile(
        "twist",
        "反转章",
        "twist",
        4,
        "hard",
        "改变读者或主角对局势的判断，并制造新的行动压力。",
        ("误导线索", "认知翻转", "反转后果", "结尾钩子"),
    ),
    ChapterProfile(
        "reveal",
        "揭秘章",
        "twist",
        4,
        "soft",
        "揭开一层真相，同时留下更深问题或新的代价。",
        ("揭示内容", "读者新增认知", "隐藏信息", "后续疑问"),
    ),
    ChapterProfile(
        "relationship",
        "感情推进章",
        "build",
        3,
        "soft",
        "推动信任、误会、亲近、敌意或共同秘密的变化。",
        ("关系开始状态", "关系变化原因", "关系结束状态"),
    ),
    ChapterProfile(
        "world_reveal",
        "世界观释放章",
        "build",
        3,
        "soft",
        "让世界信息通过冲突、交易、代价或行动自然出现。",
        ("信息出现方式", "剧情作用", "代价限制", "连续性"),
    ),
    ChapterProfile(
        "battle",
        "战斗章",
        "build",
        4,
        "soft",
        "用目标、策略、伤势、资源消耗和胜负后果支撑动作段落。",
        ("战斗目标", "能力限制", "胜负代价", "伤势连续性"),
    ),
    ChapterProfile(
        "strategy",
        "谋略章",
        "build",
        4,
        "soft",
        "围绕信息差、误导、布局与反布局推进局势。",
        ("信息差", "布局动作", "对手误判", "后续爆发点"),
    ),
    ChapterProfile(
        "daily",
        "日常章",
        "breather",
        2,
        "none",
        "用低压互动、状态修复或生活细节服务人物和后续铺垫。",
        ("日常功能", "人物状态", "隐藏铺垫"),
    ),
    ChapterProfile(
        "climax",
        "高潮章",
        "climax",
        5,
        "hard",
        "集中爆发卷内主要矛盾，必须明确冲突、代价、情绪高点和结尾承接。",
        ("核心冲突", "胜利代价", "情绪高点", "结尾钩子"),
    ),
    ChapterProfile(
        "aftermath",
        "收束章",
        "aftermath",
        2,
        "none",
        "处理高潮后果、关系余波、资源结算和下一段入口。",
        ("后果处理", "状态结算", "下一章入口"),
    ),
    ChapterProfile(
        "hook",
        "钩子章",
        "build",
        4,
        "hard",
        "以强疑问、新危机或关键人物行动制造翻页动力。",
        ("悬念钩子", "读者追读动机", "下一章承接点"),
    ),
)


PROFILE_BY_LABEL = {profile.label: profile for profile in CHAPTER_PROFILES}


def chapter_profile_labels() -> tuple[str, ...]:
    return tuple(profile.label for profile in CHAPTER_PROFILES)


def normalize_chapter_profile(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "铺垫章"
    for profile in CHAPTER_PROFILES:
        if profile.label in text or profile.key == text:
            return profile.label
    if "低谷" in text or "余波" in text:
        return "收束章"
    return text


def chapter_profile_definition(profile: str) -> ChapterProfile:
    label = normalize_chapter_profile(profile)
    return PROFILE_BY_LABEL.get(label) or PROFILE_BY_LABEL["铺垫章"]


def profile_to_pacing_function(profile: str) -> str:
    return chapter_profile_definition(profile).pacing_function


def profile_intensity(profile: str) -> int:
    return chapter_profile_definition(profile).intensity


def profile_hook_strength(profile: str) -> str:
    return chapter_profile_definition(profile).hook_strength


def profile_required_points(profile: str) -> tuple[str, ...]:
    return chapter_profile_definition(profile).minimum_points


def render_chapter_outline_framework(mode: str = "full") -> str:
    if mode == "compact":
        modules = "、".join(module.heading for module in CHAPTER_OUTLINE_MODULES)
        profiles = "、".join(chapter_profile_labels())
        return f"稳定模块：{modules}\n章级功能 profile：{profiles}"
    if mode != "full":
        raise ValueError(f"Unsupported chapter_outline framework mode: {mode}")

    lines = [
        "【chapter_outline 阶段强制框架】",
        "本阶段按卷渐进生成：每次只生成目标卷的整卷章节大纲，用户确认当前卷后再进入下一卷；全部卷完成后才进入 review_lock。",
        "章节大纲不是场景卡，也不是正文；它要把分卷蓝图拆成可执行的章节任务。",
        "suggestion.md 的 26 个点是能力池，不是每章硬性全量字段；每章先判断章级功能，再决定详写、简写或本章不适用。",
        "",
        "卷级必填：",
        "- 卷内章节总体规划：章节总数、章节区间、高潮/反转/爽点/伏笔/信息揭示/情绪曲线和钩子分布。",
        "- 章节列表总表：章节编号、标题、profile、PacingTarget、本章一句话、核心事件、主要人物、叙事功能、情绪基调、结尾状态和是否关键章。",
        "",
        "单章稳定结构：",
    ]
    for module in CHAPTER_OUTLINE_MODULES:
        points = "、".join(module.ability_points)
        lines.append(f"- {module.heading}：{module.purpose} 可调用能力池：{points}。")
    lines.extend(
        [
            "",
            "模块状态规则：",
            "- 每个单章模块必须显式标注：状态：详写 / 简写 / 本章不适用。",
            "- 高潮、反转、战斗、爽点等强功能章必须详写相关模块。",
            "- 过渡、日常、收束、低谷或余波章可以弱冲突、少钩子、低爽点，但必须写清承接价值和状态变化。",
            "",
            "章级功能 profile：",
        ]
    )
    for profile in CHAPTER_PROFILES:
        minimum = "、".join(profile.minimum_points)
        lines.append(
            f"- {profile.label} -> PacingTarget.function={profile.pacing_function}, intensity={profile.intensity}, "
            f"hook={profile.hook_strength}；侧重：{profile.focus}；最低必填：{minimum}。"
        )
    lines.extend(
        [
            "",
            "输出边界：",
            "- 必须明确当前目标卷，不要重写已确认卷；系统会把当前卷合并进完整 chapter_outline artifact。",
            "- 不允许每章机械填满能力池 26 项；只保留对该 profile 有用的字段。",
            "- 不写场景卡、不写正文段落、不写对白、不新增已锁定阶段没有来源的新规则或新人物关系。",
            "- 每章都必须有 profile、PacingTarget、模块状态、连续性提醒和审稿检查。",
        ]
    )
    return "\n".join(lines)

