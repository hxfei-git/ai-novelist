"""Worldbuilding outline framework and structural validation."""

from __future__ import annotations

import re
from typing import Any


WORLD_OUTLINE_FULL_SECTIONS: list[dict[str, Any]] = [
    {
        "heading": "一、世界核心设定",
        "required_points": [
            "世界名称",
            "世界类型",
            "故事发生的时代",
            "世界整体气质",
            "这个世界和现实世界最大的不同",
            "世界最核心的规则",
            "世界最核心的冲突",
            "世界给读者的第一印象",
            "故事主舞台",
            "最吸引人的独特设定",
        ],
    },
    {
        "heading": "二、世界格局",
        "required_points": [
            "世界由哪些区域组成",
            "大陆/国家/城市/星球/位面/维度等空间结构",
            "是否分层",
            "上层世界/下层世界/异世界/平行世界",
            "各区域关系",
            "资源差异",
            "文明程度",
            "危险等级",
            "主线会经过哪些地方",
            "世界边界",
        ],
    },
    {
        "heading": "三、地理与环境",
        "required_points": [
            "地貌",
            "气候",
            "自然灾害",
            "生存难度",
            "生态差异",
            "地理对文明发展的影响",
            "地理对战争/贸易/迁徙的影响",
            "天然屏障",
            "禁区和无人区",
            "地图大致结构",
        ],
    },
    {
        "heading": "四、历史背景",
        "required_points": [
            "世界起源",
            "文明起源",
            "上古时代",
            "旧时代秩序",
            "重大历史事件",
            "战争/灾难/革命/灭世事件",
            "王朝更替/帝国崩塌/文明断层",
            "重要人物的历史影响",
            "失落文明",
            "被篡改或隐藏的历史",
            "当前秩序形成原因",
            "主角出生前的大事",
            "历史遗留问题",
        ],
    },
    {
        "heading": "五、时代背景",
        "required_points": [
            "故事发生在历史哪个阶段",
            "繁荣/战乱/末法/复苏/扩张/衰落/革命前夜/灾后重组",
            "时代紧张感",
            "新旧秩序状态",
        ],
    },
    {
        "heading": "六、世界规则",
        "required_points": [
            "自然规律",
            "超自然力量",
            "神魔鬼灵/AI/外星/高维存在",
            "死亡/灵魂/命运/时间/空间规则",
            "世界边界",
            "管理者",
            "不可违背规则",
            "绝对不可能发生的事",
        ],
    },
    {
        "heading": "七、力量体系",
        "required_points": [
            "力量来源",
            "谁能获得力量",
            "获得条件",
            "能否学习/继承",
            "代价",
            "等级",
            "克制关系",
            "管控方式",
            "对社会/战争/经济/阶级的影响",
        ],
    },
    {
        "heading": "八、成长体系",
        "required_points": [
            "等级划分",
            "成长阶段",
            "晋升条件",
            "突破方式",
            "成长代价",
            "寿命变化",
            "能力变化",
            "战力差距",
            "失败后果",
            "瓶颈",
            "越级挑战",
            "顶级强者尺度",
            "普通人与强者差距",
        ],
    },
    {
        "heading": "九、能力分类体系",
        "required_points": [
            "攻击",
            "防御",
            "治疗",
            "辅助",
            "控制",
            "召唤",
            "精神",
            "空间",
            "时间",
            "诅咒",
            "预知",
            "变身",
            "制造",
            "禁忌",
        ],
    },
    {
        "heading": "十、职业与身份体系",
        "required_points": [
            "普通职业",
            "战斗职业",
            "学术职业",
            "宗教职业",
            "政治职业",
            "军事职业",
            "技术职业",
            "医疗职业",
            "黑暗职业",
            "特殊/稀有职业",
            "职业晋升",
            "社会地位",
            "职业依赖关系",
        ],
    },
    {
        "heading": "十一、资源体系",
        "required_points": [
            "货币",
            "能源",
            "食物",
            "土地",
            "矿产",
            "药材",
            "武器/魔法/科技材料",
            "信息",
            "知识",
            "人才",
            "生命",
            "信仰",
            "权限",
            "传承",
            "生产方式",
            "流通方式",
            "控制者",
            "资源冲突",
        ],
    },
    {
        "heading": "十二、经济体系",
        "required_points": [
            "货币制度",
            "税收制度",
            "贸易方式",
            "商会/公司/黑市/拍卖行",
            "商品流通",
            "资源垄断",
            "贫富差距",
            "主要产业",
            "奴隶或雇佣制度",
            "走私",
            "战争经济",
            "技术或魔法影响",
            "普通人谋生",
            "上层获取财富方式",
        ],
    },
    {
        "heading": "十三、政治与权力体系",
        "required_points": [
            "国家制度",
            "统治者",
            "权力来源",
            "继承方式",
            "官僚系统",
            "军队系统",
            "贵族体系",
            "宗教/公司/家族/种族权力",
            "地方自治",
            "法律执行",
            "权力斗争",
            "政治阴谋",
            "统治合法性",
            "普通人态度",
        ],
    },
    {
        "heading": "十四、势力体系",
        "required_points": [
            "国家/宗门/家族/学院/教会/军队/商会/公司/公会/革命军/黑帮/秘密结社/异族/外来/古老/中立势力",
            "每个势力目标",
            "资源",
            "弱点",
            "联盟和仇恨",
            "与主角关系",
        ],
    },
    {
        "heading": "十五、社会结构",
        "required_points": [
            "阶级制度",
            "普通人与强者关系",
            "贵族和平民关系",
            "城市人与边境人差异",
            "种族地位差异",
            "身份/血统/职业对地位影响",
            "社会流动",
            "教育",
            "婚育继承",
            "家族关系",
            "奴隶/仆从/雇佣兵/流民",
            "犯罪处理",
            "底层生存",
            "上层统治",
        ],
    },
    {
        "heading": "十六、文化体系",
        "required_points": [
            "主流价值观",
            "荣誉观",
            "道德观",
            "禁忌",
            "礼仪",
            "节日",
            "婚丧嫁娶",
            "服饰",
            "饮食",
            "建筑",
            "艺术",
            "音乐",
            "文学",
            "语言",
            "姓名规则",
            "地域/种族/阶级文化差异",
            "官方与民间文化冲突",
        ],
    },
    {
        "heading": "十七、宗教、信仰与神话体系",
        "required_points": [
            "是否有神",
            "神是否真实",
            "神是否干涉",
            "宗教组织",
            "信仰是否产生力量",
            "祭祀",
            "圣地",
            "教义",
            "异端",
            "邪教",
            "先知/圣子/圣女/神使",
            "神话",
            "创世",
            "灭世预言",
            "宗教与政治/主角关系",
        ],
    },
    {
        "heading": "十八、科技、工艺与生产力体系",
        "required_points": [
            "生产力",
            "农业",
            "工业",
            "医疗",
            "交通",
            "通讯",
            "军事技术",
            "建筑",
            "能源",
            "魔法/生物/机械/信息技术",
            "技术垄断",
            "技术与超凡结合",
            "技术发展限制",
        ],
    },
    {
        "heading": "十九、交通与通讯体系",
        "required_points": [
            "普通交通",
            "高级交通",
            "远距离移动",
            "传送",
            "航海/飞行/星际",
            "商路",
            "军用路线",
            "信息传递",
            "通讯即时性",
            "监听",
            "交通控制",
            "偏远隔绝原因",
            "主角移动方式",
        ],
    },
    {
        "heading": "二十、法律与秩序体系",
        "required_points": [
            "法律制定者",
            "法律保护对象",
            "执法权",
            "犯罪定义",
            "审判",
            "监狱",
            "死刑",
            "通缉",
            "私刑",
            "强者受约束程度",
            "贵族特权",
            "超能力监管",
            "禁忌物品管制",
            "黑市",
            "法律与现实秩序矛盾",
        ],
    },
    {
        "heading": "二十一、军事与战争体系",
        "required_points": [
            "军队类型",
            "士兵来源",
            "武器装备",
            "战争规模",
            "指挥体系",
            "防御体系",
            "城防/堡垒/结界/星舰/防护罩",
            "雇佣兵",
            "特种部队",
            "战争规则",
            "禁用武器",
            "战争资源",
            "平民影响",
            "强者或超级武器影响",
            "主要战争史",
            "当前战争边缘",
        ],
    },
    {
        "heading": "二十二、种族、族群与生灵体系",
        "required_points": [
            "主要智慧种族",
            "次要智慧种族",
            "非智慧生物",
            "怪物",
            "神话生物",
            "机械生命/AI/外星/灵体/亡灵/变异体/高维存在",
            "寿命",
            "生理",
            "繁衍",
            "文化",
            "关系",
            "歧视/奴役/战争/同化",
        ],
    },
    {
        "heading": "二十三、重要地点体系",
        "required_points": [
            "主城/王都/首都",
            "宗门/学院/教会/公司总部/军事基地/避难所/黑市/禁地/遗迹/战场/神殿/地下城/监狱/实验室/星舰/空间站/异世界入口/最终决战地点",
            "地点类型",
            "位置",
            "控制势力",
            "资源",
            "危险",
            "历史",
            "秘密",
            "与主角关系",
            "关键剧情",
        ],
    },
    {
        "heading": "二十四、危险体系",
        "required_points": [
            "自然灾害",
            "怪物",
            "疫病",
            "战争",
            "饥荒",
            "诅咒",
            "污染",
            "辐射",
            "魔潮/兽潮/虫族/AI叛乱/神明复苏/异界入侵/精神污染/世界崩坏/时间异常/空间裂缝",
            "社会性危险",
        ],
    },
    {
        "heading": "二十五、知识与教育体系",
        "required_points": [
            "普通教育",
            "贵族教育",
            "宗门/学院/军校/科研机构",
            "师徒传承",
            "家族传承",
            "禁书",
            "图书馆",
            "档案馆",
            "失落知识",
            "知识垄断",
            "错误历史",
            "危险知识",
            "学习代价",
        ],
    },
    {
        "heading": "二十六、日常生活体系",
        "required_points": [
            "吃",
            "穿",
            "住",
            "工作",
            "购物",
            "出行",
            "娱乐",
            "治病",
            "结婚",
            "养老",
            "丧葬",
            "平民恐惧",
            "平民向往",
            "节日",
            "儿童成长",
            "老人生活",
            "普通人与主线关系",
        ],
    },
    {
        "heading": "二十七、信息与舆论体系",
        "required_points": [
            "新闻传播",
            "官方公告",
            "民间传闻",
            "酒馆消息/报纸/广播/网络/数据库/水晶球/神谕/占卜",
            "情报组织",
            "谣言",
            "宣传",
            "信息封锁",
            "历史篡改",
            "公众知道什么",
            "公众不知道什么",
            "主角如何获得关键信息",
        ],
    },
    {
        "heading": "二十八、核心矛盾",
        "required_points": [
            "表面问题",
            "真正问题",
            "维持现状者",
            "推翻现状者",
            "受益者",
            "牺牲者",
            "主角无法置身事外的原因",
        ],
    },
    {
        "heading": "二十九、主角与世界的关系",
        "required_points": [
            "出生地",
            "身份",
            "阶层",
            "拥有资源",
            "缺少资源",
            "制度限制",
            "相关势力",
            "历史秘密",
            "目标",
            "敌人",
            "成长路线",
            "会打破的规则",
            "会改变的秩序",
            "最终成为何种存在",
        ],
    },
    {
        "heading": "三十、主要人物群体",
        "required_points": [
            "统治者",
            "反抗者",
            "普通人",
            "强者",
            "学者",
            "战士",
            "商人",
            "信徒",
            "犯罪者",
            "流浪者",
            "异族",
            "外来者",
            "被压迫者",
            "旧时代遗民",
            "新时代代表",
            "各类诉求",
            "对主角态度",
        ],
    },
    {
        "heading": "三十一、主线时间线",
        "required_points": [
            "远古时期",
            "上古时期",
            "近代时期",
            "主角出生前",
            "主角童年",
            "故事开局",
            "第一阶段/第一卷",
            "第二阶段/第二卷",
            "第三阶段/第三卷",
            "中期转折",
            "世界真相揭露",
            "最终危机",
            "结局后",
        ],
    },
    {
        "heading": "三十二、隐藏真相",
        "required_points": [
            "世界真正起源",
            "被掩盖历史",
            "主角真实身份",
            "反派真实目的",
            "神明真相",
            "世界是否被操控",
            "力量体系代价",
            "资源枯竭原因",
            "灾难来源",
            "势力秘密",
            "普通人不知道的真相",
            "主角最终面对的真相",
        ],
    },
    {
        "heading": "三十三、结局后的世界格局",
        "required_points": [
            "旧秩序是否崩塌",
            "新秩序是否建立",
            "主角是否掌权或离开",
            "世界是否被拯救/毁灭/进入新时代",
            "各势力结局",
            "普通人生活变化",
            "力量体系变化",
            "隐藏真相是否公开",
            "主角选择的后果",
        ],
    },
]


WORLD_OUTLINE_COMPACT_SECTIONS = [
    "一、世界核心设定",
    "二、世界格局",
    "三、地理环境",
    "四、历史背景",
    "五、时代背景",
    "六、世界规则",
    "七、力量体系",
    "八、成长体系",
    "九、职业与身份体系",
    "十、资源与经济体系",
    "十一、政治与势力体系",
    "十二、社会结构",
    "十三、文化与信仰体系",
    "十四、科技与生产力体系",
    "十五、种族与生灵体系",
    "十六、重要地点与危险区域",
    "十七、当前核心矛盾",
    "十八、主角、隐藏真相与最终格局",
]


def full_worldbuilding_headings() -> list[str]:
    return [str(item["heading"]) for item in WORLD_OUTLINE_FULL_SECTIONS]


def compact_worldbuilding_headings() -> list[str]:
    return list(WORLD_OUTLINE_COMPACT_SECTIONS)


def render_worldbuilding_framework(mode: str = "full") -> str:
    """Return a concise prompt-friendly markdown description of the framework."""
    if mode == "compact":
        return "\n".join(f"- {heading}" for heading in WORLD_OUTLINE_COMPACT_SECTIONS)
    if mode != "full":
        raise ValueError(f"Unsupported worldbuilding framework mode: {mode}")
    lines: list[str] = []
    for item in WORLD_OUTLINE_FULL_SECTIONS:
        heading = str(item["heading"])
        required_points = "、".join(str(point) for point in item["required_points"])
        lines.append(f"## {heading}\n- 必须覆盖：{required_points}")
    return "\n\n".join(lines)


def validate_worldbuilding_outline(text: str, mode: str = "full") -> tuple[bool, list[str]]:
    """Return (ok, missing_headings). Headings match Markdown headings from # to ######."""
    headings = _headings_for_mode(mode)
    positions: list[int | None] = [_heading_position(text, heading) for heading in headings]
    missing = [heading for heading, position in zip(headings, positions, strict=True) if position is None]
    if missing:
        return False, missing
    ordered = [position for position in positions if position is not None]
    if ordered != sorted(ordered):
        out_of_order = [
            heading
            for index, heading in enumerate(headings)
            if index > 0 and ordered[index] < ordered[index - 1]
        ]
        return False, out_of_order or headings
    return True, []


def append_missing_worldbuilding_sections(text: str, missing: list[str]) -> str:
    """Last-resort deterministic repair for structurally incomplete worldbuilding output."""
    content = str(text or "").strip()
    if not missing:
        return content

    headings = full_worldbuilding_headings()
    existing = _extract_existing_heading_sections(content, headings)
    lines: list[str] = []
    for index, heading in enumerate(headings):
        lines.append(f"## {heading}")
        body = existing.get(heading, "").strip()
        if body:
            lines.extend(body.splitlines())
        else:
            lines.append(
                "- 待补充：结构兜底占位，本节需要补写与当前小说创意、已锁定方向和主线冲突直接相关的具体设定。"
            )
            if index == 0 and content and not existing:
                lines.append("- 原始草稿摘录：以下内容来自结构修复前输出，需要再归入对应世界组成部分。")
                for raw_line in content.splitlines()[:20]:
                    line = raw_line.strip()
                    if line:
                        lines.append(f"  {line}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _extract_existing_heading_sections(text: str, headings: list[str]) -> dict[str, str]:
    matches: list[tuple[str, int, int]] = []
    for heading in headings:
        pattern = re.compile(rf"^\s*#{{1,6}}\s*{re.escape(heading)}(?:\s|$)", re.MULTILINE)
        match = pattern.search(text or "")
        if match:
            matches.append((heading, match.start(), match.end()))
    matches.sort(key=lambda item: item[1])
    sections: dict[str, str] = {}
    for index, (heading, _start, end) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(text)
        sections[heading] = text[end:next_start].strip()
    return sections


def _headings_for_mode(mode: str) -> list[str]:
    if mode == "full":
        return full_worldbuilding_headings()
    if mode == "compact":
        return compact_worldbuilding_headings()
    raise ValueError(f"Unsupported worldbuilding framework mode: {mode}")


def _heading_position(text: str, heading: str) -> int | None:
    pattern = re.compile(rf"^\s*#{{1,6}}\s*{re.escape(heading)}(?:\s|$)", re.MULTILINE)
    match = pattern.search(text or "")
    return match.start() if match else None
