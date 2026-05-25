"""Prompt rendering helpers for outline stages."""

from __future__ import annotations

import re

from ai_novelist.characters_framework import full_characters_headings
from ai_novelist.chapter_outline_framework import render_chapter_outline_framework
from ai_novelist.outline.stage_contracts import StageSlot, get_stage_contract
from ai_novelist.state import NovelState
from ai_novelist.story_flow_framework import story_flow_required_headings
from ai_novelist.volume_outline_framework import volume_outline_required_headings
from ai_novelist.worldbuilding_framework import full_worldbuilding_headings




def _normalize_direction_key(value: str) -> str:
    return re.sub(r"[\s·•、/()（）【】\[\]{}:：,，.;；]+", "", value).strip().lower()
DIRECTION_SECTION_SPECS = [
    {
        "heading": "一、一句话梗概",
        "aliases": ("一句话梗概", "一句话故事", "一句话概念", "故事一句话"),
        "fields": (("一句话梗概", "暂定：请补充主角、处境、目标和主要吸引点。", ("一句话梗概", "一句话故事", "一句话概念", "故事一句话")),),
    },
    {
        "heading": "二、核心卖点",
        "aliases": ("核心卖点", "核心看点", "核心爽点", "卖点"),
        "fields": (("核心卖点", "暂定：请补充本书最值得读者期待的看点。", ("核心卖点", "核心看点", "核心爽点", "卖点")),),
    },
    {
        "heading": "三、类型题材",
        "aliases": ("类型题材", "类型定位", "题材", "题材定位"),
        "fields": (
            ("主类型", "待确认", ("主类型", "类型定位", "类型", "题材定位")),
            ("子类型 / 题材元素", "待确认", ("子类型 / 题材元素", "子类型/题材元素", "子类型", "题材元素")),
            ("读者预期", "待确认", ("读者预期",)),
        ),
    },
    {
        "heading": "四、目标读者",
        "aliases": ("目标读者", "受众", "读者群", "读者画像"),
        "fields": (("目标读者", "暂定：请明确主要写给谁看。", ("目标读者", "受众", "读者群", "读者画像")),),
    },
    {
        "heading": "五、故事承诺",
        "aliases": ("故事承诺", "阅读承诺", "叙事承诺"),
        "fields": (("故事承诺", "暂定：请补充读者继续读下去会持续看到什么。", ("故事承诺", "阅读承诺", "叙事承诺")),),
    },
    {
        "heading": "六、主题表达",
        "aliases": ("主题表达", "主题", "命题"),
        "fields": (
            ("表层主题", "待确认", ("表层主题", "表层")),
            ("深层命题", "待确认", ("深层命题", "深层")),
            ("价值取向", "待确认", ("价值取向", "价值", "价值观")),
        ),
    },
    {
        "heading": "七、主角方向",
        "aliases": ("主角方向", "主角姿态", "主角行动原则", "主角定位"),
        "fields": (
            ("主角原型", "待确认", ("主角原型", "主角定位")),
            ("初始处境", "待确认", ("初始处境",)),
            ("外在目标", "待确认", ("外在目标",)),
            ("内在缺口", "待确认", ("内在缺口",)),
            ("成长方向", "待确认", ("成长方向", "主角姿态", "主角行动原则")),
            ("核心冲突", "待确认", ("核心冲突",)),
        ),
    },
    {
        "heading": "八、核心冲突",
        "aliases": ("核心冲突", "冲突", "冲突结构"),
        "fields": (
            ("外部冲突", "待确认", ("外部冲突", "外在冲突")),
            ("内部冲突", "待确认", ("内部冲突", "内在冲突")),
            ("关系冲突", "待确认", ("关系冲突",)),
        ),
    },
    {
        "heading": "九、故事基调",
        "aliases": ("故事基调", "情绪边界", "情绪基调", "氛围"),
        "fields": (
            ("整体基调", "待确认", ("整体基调", "故事基调", "情绪边界", "情绪基调", "氛围")),
            ("情绪比例 / 阅读体验", "待确认", ("情绪比例 / 阅读体验", "情绪比例/阅读体验", "阅读体验")),
            ("可以强化的情绪", "待确认", ("可以强化的情绪",)),
            ("需要避免的情绪", "待确认", ("需要避免的情绪",)),
        ),
    },
    {
        "heading": "十、篇幅结构",
        "aliases": ("篇幅结构", "篇幅", "结构", "体量"),
        "fields": (
            ("预计体量", "待确认", ("预计体量", "篇幅", "体量")),
            ("叙事结构", "待确认", ("叙事结构", "结构")),
            ("节奏特点", "待确认", ("节奏特点",)),
            ("展开方式", "待确认", ("展开方式",)),
        ),
    },
]

DIRECTION_SECTION_LOOKUP = {
    _normalize_direction_key(alias): spec["heading"]
    for spec in DIRECTION_SECTION_SPECS
    for alias in (spec["heading"], *spec["aliases"])
}

DIRECTION_FIELD_LOOKUP = {
    _normalize_direction_key(alias): (spec["heading"], field[0])
    for spec in DIRECTION_SECTION_SPECS
    for field in spec["fields"]
    for alias in field[2]
}

DIRECTION_QUESTION_ALIASES = {
    _normalize_direction_key(alias)
    for alias in ("仍需确认的问题", "待确认问题", "待确认的问题")
}


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
        return _direction_stage_structure()
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
            "- 最后可追加 `## 仍需确认的问题`，最多 10 条，只问会影响后续剧情的大问题。\n"
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
            "- `## 十三、待确认问题` 最多 10 条，只问会影响全文结构的问题；若无写“暂无，当前阶段可继续修改或确认进入下一阶段”。\n"
            "- 不得写章节正文、完整故事流程、场景卡或无主线功能角色堆砌。\n\n"
            "必须包含并按顺序输出这些标题：\n"
            f"{heading_lines}"
        )
    if stage == "story_flow":
        heading_lines = "\n".join(f"- `### {heading}`" for heading in story_flow_required_headings())
        return (
            "故事流程阶段不是章节大纲，也不是分卷细纲。必须输出全书级故事流程蓝图，"
            "并严格使用以下 14 个模块作为 Markdown 三级标题。\n\n"
            "输出格式：\n"
            "- 只输出 Markdown。\n"
            "- 顶部不要写评审报告、分析过程或“以下是”。\n"
            "- 必须以 `## 故事流程稿` 开始。\n"
            "- 每个必填标题下必须有具体、可执行的内容，不能只有空泛概念或空标题。\n"
            "- 允许使用简洁表格，但不要输出逐章列表，不要写正文。\n"
            "- 必须承接 direction、worldbuilding、characters 已锁定内容；未锁定信息写成候选或待确认。\n"
            "- `### 仍需确认的问题` 最多 10 条，只问会影响主线阶段、核心代价、关键反转或终局选择的问题；若无写“暂无”。\n"
            "- 不得替代 volume_outline 输出完整分卷细纲。\n\n"
            "必须包含并按顺序输出这些标题：\n"
            f"{heading_lines}"
        )
    if stage == "volume_outline":
        heading_lines = "\n".join(f"- `### {heading}`" for heading in volume_outline_required_headings())
        return (
            "分卷大纲阶段不是章节大纲，也不是逐章细纲。必须输出卷级蓝图，"
            "并严格使用以下 14 个模块作为 Markdown 三级标题。\n\n"
            "输出格式：\n"
            "- 只输出 Markdown。\n"
            "- 顶部不要写评审报告、分析过程或“以下是”。\n"
            "- 必须以 `## 分卷大纲稿` 开始。\n"
            "- 每个必填标题下必须有具体、可执行的内容，不能只有空泛概念或空标题。\n"
            "- 可以用紧凑表格，但不要输出逐章列表，不要写正文或场景卡。\n"
            "- 必须承接 direction、worldbuilding、characters 和 story_flow 的已保存内容；未确认信息写成候选、待确认或可选方案。\n"
            "- 可选保留 `### 仍需确认的问题`，最多 10 条。\n"
            "- 可选保留 `### 卷级约束与待确认项（可选）`，只在确有必要时写。\n"
            "- 不得替代 chapter_outline。\n\n"
            "必须包含并按顺序输出这些标题：\n"
            f"{heading_lines}"
        )
    if stage == "chapter_outline":
        return (
            "章节大纲阶段必须按卷渐进生成，不是一次性生成全书章纲，也不是场景卡或正文。\n\n"
            "输出格式：\n"
            "- 只输出 Markdown。\n"
            "- 顶部不要写评审报告、分析过程或“以下是”。\n"
            "- 必须以 `## 章节大纲稿` 开始，并只生成本轮目标卷。\n"
            "- 目标卷内必须包含 `### 卷内章节总体规划` 和 `### 章节列表总表`。\n"
            "- 每个单章必须明确 profile，并给出 PacingTarget(function/intensity/hook)。\n"
            "- 每章使用稳定结构：基础定位、剧情执行方案、人物/关系/读者认知、伏笔/爽点/情绪/开头结尾、世界观/能力资源/代价/阵营/连续性、写作执行与审稿检查。\n"
            "- 每个单章模块标注状态：详写 / 简写 / 本章不适用。\n"
            "- suggestion.md 的 26 个点是能力池，不是每章硬性全量字段；按 profile 决定详略。\n"
            "- 过渡章、日常章、收束章允许弱冲突、少钩子、低爽点，但必须有明确承接和状态变化。\n"
            "- 高潮章、反转章必须详写冲突、代价、情绪高点和结尾钩子。\n"
            "- 不写完整场景卡、正文段落或对白。\n\n"
            f"{render_chapter_outline_framework(mode='full')}"
        )
    if stage == "review_lock":
        return (
            "STATUS: pass|revise|stop\n"
            "## 阶段承接检查\n"
            "- 必须逐项核对前序阶段继承链：direction -> worldbuilding -> characters -> story_flow -> volume_outline -> chapter_outline。\n"
            "- 只写能回指到前序阶段或已锁定产物的稳定项，不要把候选内容写成 canon。\n"
            "## 已锁定 canon 清单\n"
            "- 每条必须包含：项目 / 来源阶段或锁定产物 / 依据 / 当前用途。\n"
            "- 无法回指来源的内容必须移到风险或回改阶段，不得留在锁定清单。\n"
            "## 风险分级\n"
            "- 阻塞型结构问题：会影响最终锁定或章节卡开工。\n"
            "- 非阻塞细节问题：可先锁定，但需要在章节卡前补齐或继续校准。\n"
            "## 需要回改的阶段\n"
            "- 按最小回改成本排序，说明回改目标与原因。\n"
            "## 是否可进入章节卡\n"
            "- 只写 pass / revise / stop 之一，并给出简短理由。\n\n"
            "## 仍需确认的问题\n"
            "- 只保留仍会影响锁定或回改判断的问题，最多 10 条。"
        )
    lines = [f"## {get_stage_contract(stage).label}稿"]
    for slot in slots:
        suffix = "（可选）" if not slot.required else ""
        lines.append(f"### {slot.label}{suffix}")
    lines.append("")
    lines.append("## 仍需确认的问题")
    lines.append("- 只列真正影响下一步写作的问题。")
    return "\n".join(lines)


def _direction_stage_structure() -> str:
    return (
        "## 方向定位稿\n\n"
        "### 一、一句话梗概\n"
        "- ...\n\n"
        "### 二、核心卖点\n"
        "- ...\n\n"
        "### 三、类型题材\n"
        "- 主类型：...\n"
        "- 子类型 / 题材元素：...\n"
        "- 读者预期：...\n\n"
        "### 四、目标读者\n"
        "- ...\n\n"
        "### 五、故事承诺\n"
        "- ...\n\n"
        "### 六、主题表达\n"
        "- 表层主题：...\n"
        "- 深层命题：...\n"
        "- 价值取向：...\n\n"
        "### 七、主角方向\n"
        "- 主角原型：...\n"
        "- 初始处境：...\n"
        "- 外在目标：...\n"
        "- 内在缺口：...\n"
        "- 成长方向：...\n"
        "- 核心冲突：...\n\n"
        "### 八、核心冲突\n"
        "- 外部冲突：...\n"
        "- 内部冲突：...\n"
        "- 关系冲突：...\n\n"
        "### 九、故事基调\n"
        "- 整体基调：...\n"
        "- 情绪比例 / 阅读体验：...\n"
        "- 可以强化的情绪：...\n"
        "- 需要避免的情绪：...\n\n"
        "### 十、篇幅结构\n"
        "- 预计体量：...\n"
        "- 叙事结构：...\n"
        "- 节奏特点：...\n"
        "- 展开方式：...\n\n"
        "## 仍需确认的问题\n"
        "- 暂无，当前阶段可继续修改或确认进入下一阶段。"
    )


def render_direction_stage_markdown(markdown: str, pending_questions: list[str] | None = None) -> str:
    parsed = _parse_direction_markdown(markdown or "")
    lines = ["## 方向定位稿", ""]
    for spec in DIRECTION_SECTION_SPECS:
        lines.append(f"### {spec['heading']}")
        section = parsed[spec["heading"]]
        generic = [item for item in section["generic"] if item.strip()]
        for index, field in enumerate(spec["fields"]):
            label, placeholder, _aliases = field
            value = section["fields"][label].strip()
            if not value:
                if len(spec["fields"]) == 1 and generic:
                    value = generic[0]
                elif index == 0 and generic:
                    value = generic[0]
                else:
                    value = placeholder
            lines.append(f"- {label}：{value}")
        lines.append("")
    if pending_questions is not None:
        lines.append("## 仍需确认的问题")
        questions = [str(item).strip() for item in pending_questions if str(item).strip()]
        if questions:
            for question in questions:
                lines.append(f"- {question}")
        else:
            lines.append("- 暂无，当前阶段可继续修改或确认进入下一阶段。")
    return "\n".join(lines).rstrip() + "\n"


def summarize_direction_outline(text: str, max_chars: int = 1800) -> str:
    parsed = _parse_direction_markdown(text or "")
    parts = []
    for spec in DIRECTION_SECTION_SPECS:
        section = parsed[spec["heading"]]
        if len(spec["fields"]) == 1:
            field_label, placeholder, _aliases = spec["fields"][0]
            value = _compact_text(section["fields"][field_label]) or _first_generic_value(section["generic"]) or placeholder
            parts.append(f"{field_label}：{value}")
            continue
        field_parts = []
        for field_label, placeholder, _aliases in spec["fields"]:
            value = _compact_text(section["fields"][field_label]) or placeholder
            field_parts.append(f"{field_label}：{value}")
        parts.append(f"{spec['heading']}：{'；'.join(field_parts)}")
    summary = "；".join(parts)
    if len(summary) > max_chars:
        return summary[:max_chars].rstrip() + "..."
    return summary


def extract_direction_memory(text: str, max_items: int = 12, max_chars: int = 1800) -> list[str]:
    parsed = _parse_direction_markdown(text or "")
    result: list[str] = []
    total = 0
    for spec in DIRECTION_SECTION_SPECS:
        section = parsed[spec["heading"]]
        if len(spec["fields"]) == 1:
            field_label, placeholder, _aliases = spec["fields"][0]
            value = _compact_text(section["fields"][field_label]) or _first_generic_value(section["generic"]) or placeholder
            item = f"{field_label}：{value}"
            if item not in result:
                if total + len(item) > max_chars and result:
                    break
                result.append(item)
                total += len(item)
            continue
        for field_label, placeholder, _aliases in spec["fields"]:
            value = _compact_text(section["fields"][field_label]) or placeholder
            item = f"{field_label}：{value}"
            if item in result:
                continue
            if total + len(item) > max_chars and result:
                return result
            result.append(item)
            total += len(item)
            if len(result) >= max_items:
                return result
    return result


def _parse_direction_markdown(text: str) -> dict[str, dict[str, dict[str, str] | list[str]]]:
    parsed: dict[str, dict[str, dict[str, str] | list[str]]] = {}
    for spec in DIRECTION_SECTION_SPECS:
        parsed[spec["heading"]] = {
            "fields": {field[0]: "" for field in spec["fields"]},
            "generic": [],
        }
    current_heading: str | None = None
    in_questions = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^#{1,6}\s*(.+)$", line):
            heading = _resolve_direction_heading(line)
            if heading == "__questions__":
                in_questions = True
                current_heading = None
                continue
            if heading:
                current_heading = heading
                in_questions = False
                continue
            continue
        if in_questions:
            continue
        pair = _split_label_value(line)
        if pair:
            label, value = pair
            mapping = DIRECTION_FIELD_LOOKUP.get(_normalize_direction_key(label))
            if mapping:
                section_heading, field_label = mapping
                parsed[section_heading]["fields"][field_label] = _clean_direction_value(value)
                current_heading = section_heading
                continue
        bullet = _strip_markdown_bullet(line)
        if not bullet:
            continue
        if current_heading and current_heading in parsed:
            parsed[current_heading]["generic"].append(_clean_direction_value(bullet))
        else:
            parsed[DIRECTION_SECTION_SPECS[0]["heading"]]["generic"].append(_clean_direction_value(bullet))
    return parsed


def _resolve_direction_heading(line: str) -> str | None:
    match = re.match(r"^#{1,6}\s*(.+)$", line)
    if not match:
        return None
    title = match.group(1).strip()
    key = _normalize_direction_key(title)
    if key in DIRECTION_SECTION_LOOKUP:
        return DIRECTION_SECTION_LOOKUP[key]
    if key in DIRECTION_QUESTION_ALIASES:
        return "__questions__"
    if key in {
        _normalize_direction_key("方向定位稿"),
        _normalize_direction_key("方向定位"),
        _normalize_direction_key("方向控制稿"),
        _normalize_direction_key("方向控制"),
    }:
        return None
    return None


def _split_label_value(line: str) -> tuple[str, str] | None:
    cleaned = _strip_markdown_bullet(line)
    match = re.match(r"^([^：:]{2,40})[：:]\s*(.+)$", cleaned)
    if not match:
        return None
    label = match.group(1).strip()
    value = match.group(2).strip()
    if not label or not value:
        return None
    return label, value


def _strip_markdown_bullet(line: str) -> str:
    cleaned = re.sub(r"^[-*+•\s]*", "", line)
    cleaned = re.sub(r"^\d+[.、)]\s*", "", cleaned).strip()
    return cleaned


def _clean_direction_value(text: str) -> str:
    value = text.strip()
    value = re.sub(r"[（(]来源[:：].*?[）)]$", "", value)
    value = re.sub(r"(?:\s|。)?来源[:：].*$", "", value).strip()
    return value or "待确认"


def _first_generic_value(values: list[str]) -> str:
    for value in values:
        compact = _compact_text(value)
        if compact and compact not in {"待确认", "暂定：请补充主角、处境、目标和主要吸引点。"}:
            return compact
    return values[0] if values else ""


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _normalize_direction_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z一-鿿]+", "", (value or "").strip()).lower()
