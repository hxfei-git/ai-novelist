"""Prompt rendering helpers for outline stages."""

from __future__ import annotations

from ai_novelist.characters_framework import full_characters_headings
from ai_novelist.outline.stage_contracts import StageSlot, get_stage_contract
from ai_novelist.state import NovelState
from ai_novelist.worldbuilding_framework import full_worldbuilding_headings


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
        heading_lines = "\n".join(f"- `## {heading}`" for heading in full_worldbuilding_headings())
        return (
            "世界观设定不是题材分类表，也不是规则摘要。必须输出完整小说世界大纲，"
            "并严格使用以下 33 个顶级小节作为 Markdown 二级标题。\n\n"
            "输出格式：\n"
            "- 只输出 Markdown。\n"
            "- 顶部不要写评审报告、分析过程或“以下是”。\n"
            "- 从 `## 一、世界核心设定` 开始，依次写到 `## 三十三、结局后的世界格局`。\n"
            "- 每个小节写 2-5 条 bullet。\n"
            "- 每条 bullet 必须是当前小说世界的具体设定，不要写模板说明。\n"
            "- 信息不足时可以写“暂定：...”，但必须给出合理默认建议；全篇“暂定/待定”小节不得超过 6 个。\n"
            "- 必须继承前序方向和故事概念，不得推翻已锁定设定。\n"
            "- 最后可追加 `## 仍需确认的问题`，最多 5 条，只问会影响后续剧情的大问题。\n"
            "- 不要按题材分类。\n"
            "- 不得只输出“世界运行原则、关键边界、冲突资源、代价红线”。\n\n"
            "必须包含并按顺序输出这些标题：\n"
            f"{heading_lines}"
        )
    if stage == "characters":
        heading_lines = "\n".join(f"- `## {heading}`" for heading in full_characters_headings())
        return (
            "人物关系阶段不是人物小传，也不是静态人设表。必须输出覆盖全文的关系蓝图，"
            "并严格使用以下 14 个顶级小节作为 Markdown 二级标题。\n\n"
            "输出格式：\n"
            "- 只输出 Markdown。\n"
            "- 顶部不要写评审报告、分析过程或“以下是”。\n"
            "- 从 `## 人物关系稿` 开始，依次写到 `## 十三、待确认问题`。\n"
            "- 每个小节写 2-6 条 bullet；关系卡、时间轴和表格可用紧凑 Markdown 表格。\n"
            "- 必须继承 direction 与 worldbuilding，不得凭空新增世界规则、组织或阵营。\n"
            "- 阵营 / 组织关系只能从 worldbuilding 已有设定提取；没有相关设定时写“暂无，不强行生成”。\n"
            "- 核心关系必须写清作者侧真相、角色侧认知、读者侧认知和剧情侧演化。\n"
            "- 重要秘密必须有伏笔、部分揭露、完整揭露和关系后果。\n"
            "- `## 十三、待确认问题` 最多 4 条，只问会影响全文结构的问题；若无写“暂无，当前阶段可继续修改或确认进入下一阶段”。\n"
            "- 不得写章节正文、完整故事流程、场景卡或无主线功能角色堆砌。\n\n"
            "必须包含并按顺序输出这些标题：\n"
            f"{heading_lines}"
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
