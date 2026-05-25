"""Volume outline framework and prompt rendering."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VolumeOutlineSection:
    key: str
    heading: str
    purpose: str
    required_points: tuple[str, ...]


VOLUME_OUTLINE_SECTIONS: tuple[VolumeOutlineSection, ...] = (
    VolumeOutlineSection(
        "master_plan",
        "分卷总体规划",
        "说明全书如何切成几卷，以及每卷如何承担不同阶段功能。",
        (
            "分卷数量",
            "每卷名称",
            "每卷大致章节范围",
            "每卷大致字数范围",
            "每卷在全书中的阶段位置",
            "每卷承担的叙事功能",
            "全书分卷推进逻辑",
        ),
    ),
    VolumeOutlineSection(
        "positioning",
        "单卷基础定位",
        "判断每一卷在全书里具体负责什么。",
        (
            "卷序号",
            "卷名",
            "卷副标题",
            "大致章节范围",
            "大致字数范围",
            "所属故事阶段",
            "本卷主叙事功能",
            "可兼具的副功能",
        ),
    ),
    VolumeOutlineSection(
        "logline",
        "本卷一句话概括",
        "用一句话抓住这一卷的剧情承诺和主要看点。",
        (
            "本卷一句话剧情",
            "本卷核心看点",
            "本卷主要问题",
            "本卷读者期待",
            "本卷阶段性承诺",
        ),
    ),
    VolumeOutlineSection(
        "goals",
        "本卷阶段目标",
        "说明主角或主线这一卷要推进到哪里。",
        (
            "主角这一卷想达成什么",
            "主角被迫面对什么",
            "阶段性任务是什么",
            "卷末得到什么",
            "卷末失去什么",
            "成功或失败带来的后果",
        ),
    ),
    VolumeOutlineSection(
        "conflicts",
        "本卷核心冲突",
        "说明这一卷真正驱动剧情的压力来源。",
        (
            "人物冲突",
            "规则冲突",
            "环境冲突",
            "内心冲突",
            "关系冲突",
            "阵营冲突",
            "冲突如何逐步升级",
        ),
    ),
    VolumeOutlineSection(
        "plot_progression",
        "本卷剧情推进",
        "给出卷内过程线和节点推进。",
        (
            "开卷状态",
            "入卷事件",
            "目标建立",
            "前期推进",
            "中段转折",
            "冲突升级",
            "重大选择",
            "低谷或失败",
            "高潮事件",
            "结尾余波",
            "下卷钩子",
        ),
    ),
    VolumeOutlineSection(
        "key_nodes",
        "本卷关键节点",
        "把这一卷的骨架点抓出来。",
        (
            "开卷事件",
            "第一个重要推动事件",
            "第一次明显受挫",
            "中段反转",
            "重大选择",
            "关键揭示",
            "高潮事件",
            "结尾钩子",
        ),
    ),
    VolumeOutlineSection(
        "character_progression",
        "本卷人物推进",
        "说明这一卷里人物认知、关系和命运如何变化。",
        (
            "主角状态变化",
            "主角能力变化",
            "主角信念变化",
            "关键配角作用",
            "重要关系变化",
            "新人物登场",
            "旧人物退场",
            "反派或对手推进",
            "角色秘密揭示进度",
            "人物之间的信息差变化",
        ),
    ),
    VolumeOutlineSection(
        "world_release",
        "本卷世界观释放",
        "控制这一卷要释放哪些世界信息。",
        (
            "新地点",
            "新势力",
            "新规则",
            "历史背景",
            "力量体系推进",
            "社会结构展示",
            "隐藏真相揭示",
            "暂时保留的未知信息",
        ),
    ),
    VolumeOutlineSection(
        "payoffs",
        "本卷爽点与卖点兑现",
        "说明这一卷如何满足读者期待。",
        (
            "主要爽点",
            "高光场面",
            "能力升级点",
            "打脸/逆转点",
            "情感爆点",
            "悬疑揭示点",
            "大场面",
            "最值得期待的桥段",
        ),
    ),
    VolumeOutlineSection(
        "foreshadowing",
        "本卷伏笔、悬念与信息差",
        "控制埋伏、揭示和误导的节奏。",
        (
            "承接前文的伏笔",
            "本卷新增伏笔",
            "本卷揭示的悬念",
            "本卷保留的悬念",
            "本卷制造的误导",
            "人物之间的信息差",
            "读者与主角之间的信息差",
            "为后续卷准备的反转条件",
        ),
    ),
    VolumeOutlineSection(
        "emotional_pacing",
        "本卷情绪节奏",
        "说明这一卷的阅读体验曲线。",
        (
            "开卷情绪",
            "中段情绪",
            "高潮情绪",
            "结尾情绪",
            "本卷整体阅读体验",
            "情绪反差",
            "缓冲段落需求",
        ),
    ),
    VolumeOutlineSection(
        "opening_ending",
        "本卷开头与结尾",
        "说明这一卷如何进入、如何收束、如何引向下一卷。",
        (
            "第一场戏",
            "开头钩子",
            "入卷问题",
            "结尾解决了什么",
            "结尾留下了什么",
            "如何引向下一卷",
        ),
    ),
    VolumeOutlineSection(
        "bridges",
        "与前后卷的衔接",
        "说明这一卷和前后卷之间如何不断线。",
        (
            "继承上一卷的什么问题",
            "延续上一卷的什么后果",
            "本卷解决了哪些阶段问题",
            "本卷制造了哪些新问题",
            "下一卷从哪里接起",
            "本卷在全书主线中的作用",
        ),
    ),
)


def volume_outline_required_headings() -> tuple[str, ...]:
    return tuple(section.heading for section in VOLUME_OUTLINE_SECTIONS)


def full_volume_outline_headings() -> list[str]:
    return [
        "分卷大纲稿",
        *volume_outline_required_headings(),
        "仍需确认的问题",
        "卷级约束与待确认项（可选）",
    ]


def render_volume_outline_framework(mode: str = "full") -> str:
    if mode == "compact":
        return "\n".join(f"- {heading}" for heading in volume_outline_required_headings())
    if mode != "full":
        raise ValueError(f"Unsupported volume_outline framework mode: {mode}")
    lines: list[str] = [
        "【volume_outline 阶段强制框架】",
        "本阶段产物是卷级蓝图，不是章节大纲，也不是逐章细纲。",
        "必须承接 direction、worldbuilding、characters 和 story_flow 的已保存内容；未确认信息写成候选方向、待确认或可选方案。",
        "当用户只给三卷、五卷或只给模糊的卷数时，也要补齐每卷功能、阶段位置和弹性边界。",
        "必须覆盖以下核心模块：",
    ]
    for index, section in enumerate(VOLUME_OUTLINE_SECTIONS, start=1):
        points = "、".join(section.required_points)
        lines.append(f"{index}. {section.heading}：{section.purpose} 必含：{points}。")
    lines.extend(
        [
            "写作边界：",
            "- 不要写逐章细纲。",
            "- 不要替代 chapter_outline。",
            "- 不要把 volume_outline 写成章节正文或场景卡。",
            "- 不要搬运完整 worldbuilding 或 characters 内容。",
            "- 未确认信息统一写成候选方向、待确认或可选方案。",
            "- 可选保留 `### 仍需确认的问题`，但最多 10 条。",
            "- 卷级约束只在确有必要时附加，不要把分卷大纲写死。",
            "- 每个模块都要体现这一卷对主线、人物、世界、冲突或阅读体验的推进作用。",
        ]
    )
    return "\n".join(lines)
