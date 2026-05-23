"""Prompt rendering helpers for outline stages."""

from __future__ import annotations

from ai_novelist.outline.stage_contracts import StageSlot, get_stage_contract
from ai_novelist.state import NovelState


def build_stage_output_rule(stage: str, state: NovelState | None = None) -> str:
    del state
    contract = get_stage_contract(stage)
    base = [
        "请只输出当前阶段产物，不要给 A/B/C 候选菜单。",
        "所有具体设定都必须有来源；来源不足时写“待确认”，不要写成已锁定事实。",
        "不要使用产品规则、游戏机制、编剧理论语言。",
        f"本阶段目的：{contract.purpose}",
        f"确认策略：{contract.confirmation_policy}",
        "",
        "请按以下 Markdown 结构输出：",
    ]
    structure = _stage_structure(stage, contract.slots)
    return "\n".join(base + [structure])


def _stage_structure(stage: str, slots: tuple[StageSlot, ...]) -> str:
    if stage == "direction":
        return (
            "## 方向定位稿\n"
            "- 类型定位：...\n"
            "- 主角姿态：...\n"
            "- 核心看点：...\n"
            "- 核心冲突：...\n"
            "- 情绪边界：...\n"
            "\n## 仍需确认的问题\n"
            "- 最多 1 条；若无写“暂无，当前阶段可继续修改或确认进入下一阶段”。"
        )
    if stage == "worldbuilding":
        return (
            "## 世界观设定稿\n\n"
            "### 世界一句话\n"
            "### 题材核心结构\n"
            "### 主角所在组织或生活圈\n"
            "### 势力、资源与日常压力\n"
            "### 可持续写作素材\n"
            "### 待确认事项\n"
            "### 自检\n"
            "\n## 仍需确认的问题\n"
            "- 最多 3 条；不得给模型自造二选一菜单。"
        )
    if stage == "review_lock":
        return (
            "STATUS: pass|revise|stop\n"
            "## 阶段承接检查\n"
            "## 已锁定 canon 清单\n"
            "## 未解决风险\n"
            "## 需要回改的阶段\n"
            "## 是否可进入章节卡\n"
            "\n## 仍需确认的问题\n"
            "- 仅允许锁定/回改决策问题。"
        )
    lines = [f"## {get_stage_contract(stage).label}稿"]
    for slot in slots:
        suffix = "（可选）" if not slot.required else ""
        lines.append(f"### {slot.label}{suffix}")
    lines.append("")
    lines.append("## 仍需确认的问题")
    lines.append("- 只列真正影响下一步写作的问题。")
    return "\n".join(lines)
