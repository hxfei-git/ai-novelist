"""Story flow outline framework and prompt rendering."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoryFlowSection:
    key: str
    heading: str
    purpose: str
    required_points: tuple[str, ...]


STORY_FLOW_SECTIONS: tuple[StoryFlowSection, ...] = (
    StoryFlowSection(
        "mainline_progression",
        "故事主线推进",
        "描述整部小说最核心的因果链。",
        ("故事起点", "引发事件", "主角初始目标", "主线任务 / 主线问题", "阶段性目标变化", "终局目标"),
    ),
    StoryFlowSection(
        "stage_map",
        "故事阶段划分",
        "把整部故事拆成大的流程阶段，而不是直接拆章节。",
        ("开局阶段", "成长阶段", "扩张阶段", "转折阶段", "高潮阶段", "结局阶段"),
    ),
    StoryFlowSection(
        "conflict_escalation",
        "核心冲突升级路径",
        "规划冲突如何越来越大、越来越难、越来越贴近主题。",
        ("初级冲突", "中级冲突", "高级冲突", "终极冲突", "胜利代价", "失败损失", "成长推动"),
    ),
    StoryFlowSection(
        "key_plot_nodes",
        "关键剧情节点",
        "记录全书级别的重要节点。",
        ("开篇钩子", "第一次选择", "第一次胜利", "第一次失败", "中段大转折", "黑暗时刻", "最终觉醒", "终局对决", "结局回响"),
    ),
    StoryFlowSection(
        "character_arc_embedding",
        "人物弧光嵌入流程",
        "说明人物变化如何被剧情事件推动。",
        ("主角起点状态", "成长路径", "关键人物影响", "关系变化流程", "反派镜像", "终局人物状态"),
    ),
    StoryFlowSection(
        "foreshadowing_reveal_cadence",
        "伏笔、悬念与揭示节奏",
        "安排信息释放，避免前期没钩子、后期硬反转。",
        ("核心悬念", "阶段性悬念", "伏笔布置点", "真相揭示顺序", "分层反转", "回收方式"),
    ),
    StoryFlowSection(
        "payoff_promise_cadence",
        "爽点 / 卖点兑现节奏",
        "承接核心卖点和故事承诺，规划持续兑现与升级。",
        ("开局卖点", "阶段性爽点", "升级型爽点", "情绪释放点", "卖点与主线结合"),
    ),
    StoryFlowSection(
        "emotional_pacing",
        "情绪节奏与阅读体验",
        "规划读者情绪，而不只是事件顺序。",
        ("整体情绪曲线", "阶段情绪目标", "高低起伏", "缓冲与爆发", "分卷节奏参考"),
    ),
    StoryFlowSection(
        "worldbuilding_reveal_order",
        "世界观展开顺序",
        "说明静态设定如何逐步进入读者视野。",
        ("开局展示", "中期扩展", "后期揭示", "展示方式", "与主角命运关系"),
    ),
    StoryFlowSection(
        "faction_progression",
        "阵营与势力推进",
        "规划组织、宗门、家族、国家、神明、AI 等势力如何登场和冲突。",
        ("登场顺序", "关系变化", "主角位置变化", "势力冲突推动选择"),
    ),
    StoryFlowSection(
        "cost_failure_mechanism",
        "代价与失败机制",
        "防止主角一路平推，让胜利和成长都有成本。",
        ("能力代价", "选择代价", "关系代价", "世界代价", "失败节点"),
    ),
    StoryFlowSection(
        "reversals_cognition",
        "反转与认知升级",
        "将方向定位中的反转原则落到流程位置。",
        ("反转位置", "身份反转", "阵营反转", "目标反转", "规则反转", "真相反转", "反转后影响", "前文伏笔对应"),
    ),
    StoryFlowSection(
        "volume_bridge_direction",
        "分卷衔接方向",
        "为 volume_outline 提供骨架，而不是替代分卷大纲。",
        ("每卷功能", "每卷核心问题", "阶段性高潮", "卷间钩子"),
    ),
    StoryFlowSection(
        "ending_path",
        "结局路径",
        "提前约束终局，避免中后期发散。",
        ("主线结局", "人物结局", "关系结局", "世界结局", "主题落点", "余味 / 续作空间"),
    ),
)


def story_flow_required_headings() -> tuple[str, ...]:
    return tuple(section.heading for section in STORY_FLOW_SECTIONS)


def full_story_flow_headings() -> list[str]:
    return ["故事流程稿", *story_flow_required_headings()]


def render_story_flow_framework(mode: str = "full") -> str:
    """Return a concise prompt-friendly markdown description of the story flow framework."""
    if mode == "compact":
        return "\n".join(f"- {heading}" for heading in story_flow_required_headings())
    if mode != "full":
        raise ValueError(f"Unsupported story_flow framework mode: {mode}")
    lines: list[str] = [
        "【story_flow 阶段强制框架】",
        "本阶段产物是全书级故事流程蓝图，不是章节大纲，也不是分卷细纲。",
        "必须承接 direction、worldbuilding、characters 已锁定内容；未锁定内容只能写为候选方向、待确认或可选方案。",
        "必须覆盖以下模块：",
    ]
    for index, section in enumerate(STORY_FLOW_SECTIONS, start=1):
        points = "、".join(section.required_points)
        lines.append(f"{index}. {section.heading}：{section.purpose} 必含：{points}。")
    lines.extend(
        [
            "写作边界：",
            "- 不要直接写章节正文。",
            "- 不要生成逐章列表。",
            "- 不要替代 volume_outline 输出完整分卷细纲。",
            "- 不要新增与 worldbuilding 冲突的世界规则。",
            "- 不要新增与 characters 冲突的人物设定或人物终局。",
            "- 每个模块都要说明它如何推动主线、人物、冲突或阅读体验。",
            "- 缺失信息请标为候选方向或待确认问题。",
        ]
    )
    return "\n".join(lines)
