"""Prompt construction helpers for the outline graph."""

from __future__ import annotations

from ai_novelist.outline.chapter_outline_structure import build_chapter_outline_target_context
from ai_novelist.outline.renderers import build_stage_output_rule
from ai_novelist.outline.stage_contracts import OUTLINE_STAGES, STAGE_LABELS, get_stage_contract
from ai_novelist.outline_graph.artifact_io import current_stage_context, previous_stage_context, stage_memory_context
from ai_novelist.state import NovelState


CHAPTER_OUTLINE_FORCE_FULL_KEY = "chapter_outline_force_full_generation"


CHAPTER_OUTLINE_INTERNAL_REQUEST_KEY = "chapter_outline_internal_generation_request"


def chapter_outline_framework_prompt(stage: str, state: NovelState | None = None) -> str:
    if stage != "chapter_outline":
        return ""
    from ai_novelist.chapter_outline_framework import render_chapter_outline_framework

    target_context = "暂无"
    if state is not None:
        raw_metadata = state.director_task_args.get("chapter_outline_metadata")
        if isinstance(raw_metadata, dict):
            target_context = build_chapter_outline_target_context(raw_metadata)
    return (
        "\nCHAPTER_OUTLINE_FRAMEWORK:\n"
        "你必须按下面的章节大纲框架生成。章节大纲按卷渐进推进，当前轮只生成目标卷。\n"
        f"目标卷上下文：\n{target_context}\n"
        f"{render_chapter_outline_framework(mode='full')}\n"
    )


def worldbuilding_framework_prompt(stage: str) -> str:
    if stage != "worldbuilding":
        return ""
    from ai_novelist.worldbuilding_framework import render_worldbuilding_framework

    return (
        "\nWORLD_OUTLINE_FRAMEWORK:\n"
        "你必须按下面的通用世界大纲框架生成，不要按题材分类。"
        "题材只影响每项如何填写。每项都要服务主角生存、冲突制造和后续剧情。\n"
        f"{render_worldbuilding_framework(mode='full')}\n"
    )


def characters_framework_prompt(stage: str) -> str:
    if stage != "characters":
        return ""
    from ai_novelist.characters_framework import render_characters_framework

    return (
        "\nCHARACTERS_RELATIONSHIP_FRAMEWORK:\n"
        "你必须按下面的人物关系蓝图框架生成。人物关系不是人物小传，"
        "而是覆盖全文的关系演化、信息差、秘密揭露、事件种子和锁定约束。\n"
        f"{render_characters_framework(mode='full')}\n"
    )


def story_flow_framework_prompt(stage: str) -> str:
    if stage != "story_flow":
        return ""
    from ai_novelist.story_flow_framework import render_story_flow_framework

    return (
        "\nSTORY_FLOW_FRAMEWORK:\n"
        "你必须按下面的故事流程蓝图框架生成。故事流程不是章节大纲，"
        "而是覆盖全书主线因果、阶段升级、冲突递进、人物弧光、信息释放和终局回收的骨架。\n"
        f"{render_story_flow_framework(mode='full')}\n"
    )


def volume_outline_framework_prompt(stage: str) -> str:
    if stage != "volume_outline":
        return ""
    from ai_novelist.volume_outline_framework import render_volume_outline_framework

    return (
        "\nVOLUME_OUTLINE_FRAMEWORK:\n"
        "你必须按下面的分卷大纲蓝图框架生成。分卷大纲不是章节大纲，也不是逐章细纲，"
        "而是覆盖卷级目标、剧情推进、人物推进、世界观释放、爽点悬念、情绪节奏和前后卷衔接的骨架。\n"
        f"{render_volume_outline_framework(mode='full')}\n"
    )


def chapter_outline_forced_full_generation(state: NovelState, stage: str) -> bool:
    return stage == "chapter_outline" and bool(state.director_task_args.get(CHAPTER_OUTLINE_FORCE_FULL_KEY))


def chapter_outline_internal_generation_request(state: NovelState, stage: str) -> str:
    if stage != "chapter_outline":
        return ""
    return str(state.director_task_args.get(CHAPTER_OUTLINE_INTERNAL_REQUEST_KEY) or "").strip()


def outline_stage_user_request_for_prompt(state: NovelState, stage: str) -> str:
    if chapter_outline_forced_full_generation(state, stage):
        return chapter_outline_internal_generation_request(state, stage) or state.user_request
    return state.user_request


def build_outline_stage_role_prompt(state: NovelState, stage: str, role: str, author_craft: str = "") -> str:
    contract = get_stage_contract(stage)
    user_request = outline_stage_user_request_for_prompt(state, stage)
    return (
        "AGENT: outline_stage_role\n"
        f"ROLE: {role}\n"
        f"STAGE: {stage}\n"
        f"STAGE_LABEL: {STAGE_LABELS[stage]}\n\n"
        "STAGE_CONTRACT:\n"
        f"- 本阶段目的：{contract.purpose}\n"
        f"- 允许新增：{', '.join(contract.allowed_intents)}\n"
        f"- 禁止越权：{', '.join(contract.forbidden_intents)}\n"
        f"- Canon policy：{contract.canon_policy}\n"
        "- 所有具体设定必须说明来源，不能把自造机制写成已锁定事实。\n\n"
        "LANGUAGE_QUALITY:\n"
        "- 不写公式化绝对因果句。\n"
        "- 不写产品规则、游戏机制、编剧理论语言。\n"
        "- 世界观阶段多写角色能看见、听见、触碰、承受的事物。\n\n"
        f"角色专属关注点：\n{role_focus_instruction(stage, role)}\n\n"
        f"用户最新输入：{user_request}\n"
        f"创意：{state.idea or '暂无'}\n"
        f"检索上下文：\n{state.retrieval_context or state.reference_brief or '暂无'}\n\n"
        f"作者构思参考：\n{author_craft or '暂无'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, stage)}\n\n"
        f"当前阶段已有内容：\n{current_stage_context(state, stage)}\n\n"
        f"阶段连续性要求：\n{stage_continuity_requirement(stage)}\n\n"
        f"{worldbuilding_framework_prompt(stage)}\n"
        f"{characters_framework_prompt(stage)}\n"
        f"{story_flow_framework_prompt(stage)}\n"
        f"{volume_outline_framework_prompt(stage)}\n"
        f"{chapter_outline_framework_prompt(stage, state)}\n"
        f"{worldbuilding_overfine_terms_guard(state, stage)}\n"
        f"{characters_relationship_guard(state, stage)}\n"
        f"{outline_stage_boundary_prompt(stage)}\n\n"
        "OUTPUT_BUDGET:\n"
        "- 只输出短 JSON：{role, opportunities, risks, suggestions}。\n"
        "- opportunities/risks/suggestions 各最多 2 条，每条不超过 80 中文字符。\n"
        "- 总输出不超过 500 中文字符。\n"
        "- 不要复述上下文，不要输出分析过程。\n"
        "建议必须基于前序已保存阶段内容和当前阶段已有内容继续创作，"
        "不得把本阶段写成与前序设定割裂的新故事。"
    )


def build_outline_stage_synthesizer_prompt(state: NovelState, stage: str, role_reviews: list[dict[str, str]], author_craft: str = "") -> str:
    contract = get_stage_contract(stage)
    user_request = outline_stage_user_request_for_prompt(state, stage)
    reviews = "\n\n".join(f"## {item['role']}\n{item['content']}" for item in role_reviews)
    return (
        "AGENT: outline_stage_synthesizer\n"
        f"STAGE: {stage}\n"
        f"STAGE_LABEL: {STAGE_LABELS[stage]}\n\n"
        "STAGE_CONTRACT:\n"
        f"- 本阶段目的：{contract.purpose}\n"
        f"- 允许新增：{', '.join(contract.allowed_intents)}\n"
        f"- 禁止越权：{', '.join(contract.forbidden_intents)}\n"
        f"- Canon policy：{contract.canon_policy}\n"
        "- 所有具体设定必须说明来源，不能把自造机制写成已锁定事实。\n\n"
        "LANGUAGE_QUALITY:\n"
        "- 不写公式化绝对因果句。\n"
        "- 不写产品规则、游戏机制、编剧理论语言。\n"
        "- 世界观阶段多写角色能看见、听见、触碰、承受的事物。\n\n"
        f"创意：{state.idea or '暂无'}\n"
        f"用户最新输入：{user_request}\n"
        f"作者构思参考：\n{author_craft or '暂无'}\n\n"
        f"前序已保存阶段内容：\n{previous_stage_context(state, stage)}\n\n"
        f"当前阶段已有内容：\n{current_stage_context(state, stage)}\n\n"
        f"阶段连续性要求：\n{stage_continuity_requirement(stage)}\n\n"
        f"{worldbuilding_framework_prompt(stage)}\n"
        f"{characters_framework_prompt(stage)}\n"
        f"{story_flow_framework_prompt(stage)}\n"
        f"{volume_outline_framework_prompt(stage)}\n"
        f"{chapter_outline_framework_prompt(stage, state)}\n"
        f"{worldbuilding_overfine_terms_guard(state, stage)}\n"
        f"{characters_relationship_guard(state, stage)}\n"
        f"{outline_stage_boundary_prompt(stage)}\n\n"
        f"角色短评：\n{reviews}\n\n"
        f"{outline_stage_synthesizer_output_rule(stage, state)}"
    )


OUTLINE_STAGE_BOUNDARIES = {
    "direction": {
        "allowed": "一句话梗概、核心卖点、类型题材、目标读者、故事承诺、主题表达、主角方向、核心冲突、故事基调、篇幅结构",
        "forbidden": "展开完整世界观规则、编写人物完整档案、制定分卷 / 章节大纲、生成具体剧情桥段、生成复杂组织、境界、势力、地图、制度细则、强行绑定平台、为信息不足处编造确定性设定",
    },
    "concept": {
        "allowed": "故事钩子、一句话概念、主角欲望、核心冲突、主要悬念、叙事承诺、主题问题、反转原则、待后续阶段展开的确认点",
        "forbidden": "具体世界规则、世界规则清单、组织流程、人物关系细则、人物亲密机制、章节列表、第1章/第 1 章、分卷结构、第一卷、专有名词堆砌、行政或制度化细则、申请表、审批、备案、绩效、KPI",
    },
    "worldbuilding": {
        "allowed": "完整小说世界大纲：世界核心设定、世界格局、地理与环境、历史背景、时代背景、世界规则、力量体系、成长体系、能力分类体系、职业与身份体系、资源体系、经济体系、政治与权力体系、势力体系、社会结构、文化体系、宗教信仰神话、科技工艺生产力、交通通讯、法律秩序、军事战争、种族族群生灵、重要地点、危险体系、知识教育、日常生活、信息舆论、核心矛盾、主角与世界关系、主要人物群体、主线时间线、隐藏真相、结局后世界格局",
        "forbidden": "按题材分类替代世界组成部分、只输出世界运行原则/关键边界/冲突资源/代价红线四段摘要、只写抽象口号、只写专有名词清单、空标题模板、过细行政流程、申请表、审批、备案、考评、绩效、KPI、无代价万能规则、完整人物小传、章节正文、分卷章节安排、与主线无关的猎奇机制",
    },
    "characters": {
        "allowed": "全角色总表、角色个人驱动力、主角关系弧光、核心人物关系卡、关系演化时间轴、读者认知进度表、秘密与信息差网络、从世界观提取的阵营/组织关系、关系冲突类型、关系事件种子、角色退场与关系遗产、锁定项与可变项、待确认问题",
        "forbidden": "新世界规则、凭空新增阵营/组织、章节列表、章节正文、完整剧情流程、场景卡、无主线功能人设细节、与主线无关的角色堆砌、未成年性化、非自愿亲密、把人物关系写成审批/绩效/流程表",
    },
    "story_flow": {
        "allowed": "全书主线因果链、故事阶段划分、阶段目标升级、冲突升级路径、关键剧情节点、人物弧光嵌入流程、关系变化流程、伏笔悬念与揭示节奏、爽点/卖点兑现节奏、情绪节奏、世界观展开顺序、阵营与势力推进、代价与失败机制、反转与认知升级、分卷衔接方向、结局路径、待确认问题",
        "forbidden": "直接写章节正文、逐章拆解章节清单、替代 volume_outline 输出完整分卷细纲、新增与 worldbuilding 冲突的世界规则、新增与 characters 冲突的人物设定、无来源地把候选内容写成已锁定正典、只输出模板标题不填充实际内容、行政流程、办理、审批、备案、绩效、申请表、世界百科",
    },
    "volume_outline": {
        "allowed": "分卷总体规划、单卷基础定位、本卷一句话概括、本卷阶段目标、本卷核心冲突、本卷剧情推进、本卷关键节点、本卷人物推进、本卷世界观释放、本卷爽点与卖点兑现、本卷伏笔、悬念与信息差、本卷情绪节奏、本卷开头与结尾、与前后卷的衔接、仍需确认的问题、卷级约束与待确认项（可选）",
        "forbidden": "逐章细纲、第1章、第2章、章节列表、场景列表、细场景动作、正文片段、新世界观规则、新世界规则、新人物系统、过细制度机制、临时改写世界规则、脱离主线的新人物群、只输出卷名和卷目标的短摘要",
    },
    "chapter_outline": {
        "allowed": "按卷生成的卷内章节总体规划、章节列表总表、章级功能 profile、PacingTarget、单章稳定结构、模块状态、章节目标、主要冲突、信息增量、人物状态变化、结尾钩子、连续性提醒、写作执行与审稿检查",
        "forbidden": "正式正文、正文段落、对白、中文引号对白、完整场景卡、场景卡、细场景调度、细场景动作、未确立的新规则、新人物关系、额外世界观机制、审批、制度、亲密机制、临时改写已锁定设定、无关支线扩写",
    },
    "review_lock": {
        "allowed": "阶段承接检查、锁定来源追溯、已锁定 canon 清单、阻塞型结构问题、非阻塞细节问题、需要回改的阶段、章节卡准备度和最终锁定判定",
        "forbidden": "新增世界规则、新增 canon、把候选内容写成已锁定设定、重写人物关系、重写剧情流程、重写前序阶段、生成章节卡、生成正文、章节正文、未标记来源的新 canon、候选菜单、二次创作",
    },
}


def outline_stage_boundary_prompt(stage: str) -> str:
    boundary = OUTLINE_STAGE_BOUNDARIES.get(stage)
    if boundary:
        allowed = str(boundary.get("allowed") or "").strip()
        forbidden = str(boundary.get("forbidden") or "").strip()
    else:
        contract = get_stage_contract(stage)
        allowed = ", ".join(contract.allowed_intents)
        forbidden = ", ".join(contract.forbidden_intents)
    return (
        "STAGE_BOUNDARY:\n"
        f"- 允许输出：{allowed}。\n"
        f"- 禁止输出：{forbidden}。\n"
        "- 只给本阶段短评或产物，不越权生成其他阶段内容，不新增无依据 canon。"
    )


def worldbuilding_overfine_terms_guard(state: NovelState, stage: str) -> str:
    if stage != "worldbuilding":
        return ""
    controlled_terms = ("申请表", "申请", "审批", "备案", "考评", "绩效", "KPI")
    explicit_sources = [state.user_request, state.idea]
    for artifact in state.outline_stage_artifacts.values():
        if not isinstance(artifact, dict) or artifact.get("status") != "locked":
            continue
        explicit_sources.append(str(artifact.get("synthesis") or ""))
        memory = artifact.get("stage_memory")
        if isinstance(memory, list):
            explicit_sources.extend(str(item) for item in memory)
    source_text = "\n".join(item for item in explicit_sources if item)
    explicit_terms = [term for term in controlled_terms if term in source_text]
    if explicit_terms:
        return (
            "\nWORLDBUILDING_OVERFINE_TERMS:\n"
            f"- 用户原始输入或锁定产物已明确包含：{'、'.join(explicit_terms)}。\n"
            "- 可以保留这些词，但只能改写为服务主线冲突的世界运行原则；不得扩写成申请/审批/备案/考评流程或表格制度。"
        )
    return (
        "\nWORLDBUILDING_OVERFINE_TERMS:\n"
        "- 默认不要生成申请表、申请、审批、备案、考评、绩效或 KPI 等行政化机制。\n"
        "- 如果角色短评出现这些词，必须改写为资源压力、代价或阵营冲突原则。"
    )


def characters_relationship_guard(state: NovelState, stage: str) -> str:
    if stage != "characters":
        return ""
    controlled_terms = ("亲密行为", "双修", "道侣", "福利场景", "擦边", "暧昧", "恋爱", "色情", "情色")
    explicit_sources = [state.user_request, state.idea]
    for artifact in state.outline_stage_artifacts.values():
        if not isinstance(artifact, dict) or artifact.get("status") != "locked":
            continue
        explicit_sources.append(str(artifact.get("synthesis") or ""))
        memory = artifact.get("stage_memory")
        if isinstance(memory, list):
            explicit_sources.extend(str(item) for item in memory)
    source_text = "\n".join(item for item in explicit_sources if item)
    explicit_terms = [term for term in controlled_terms if term in source_text]
    if explicit_terms:
        return (
            "\nCHARACTER_RELATIONSHIP_TERMS:\n"
            f"- 用户原始输入或锁定产物已明确包含：{'、'.join(explicit_terms)}。\n"
            "- 可以保留并展开这些成人亲密方向；必须服务目标、动机、权力关系、诱惑、背叛、占有欲或主线冲突，不要改写成行政审批/绩效表格。"
        )
    return (
        "\nCHARACTER_RELATIONSHIP_TERMS:\n"
        "- 默认按全文关系蓝图处理人物：角色必须有叙事职能、关系职能、信息差职能或主线冲突职能。\n"
        "- 成人情感或亲密张力只有在用户输入或已锁定产物明确需要时才展开，并必须服务关系变化或主线冲突。\n"
        "- 禁止未成年性化、非自愿亲密、剥削性内容，禁止把人物关系写成审批/绩效/流程表格。\n"
        "- 无功能人设细节、凭空阵营、静态小传和角色堆砌一律删除或标记为待确认。"
    )


def outline_stage_synthesizer_output_rule(stage: str, state: NovelState | None = None) -> str:
    return build_stage_output_rule(stage, state)


def role_focus_instruction(stage: str, role: str) -> str:
    focus_map = {
        "类型定位 Agent": "从一句话梗概、类型题材、目标读者和篇幅结构判断方向是否清晰；重点检查这本书想讲什么、写给谁看、为什么值得读，以及整体体量是否匹配。",
        "主题卖点 Agent": "从核心卖点、故事承诺、主题表达、主角方向和核心冲突判断方向是否有长线吸引力；重点提炼能驱动后续世界观、人物和剧情的核心卖点。",
        "故事概念 Agent": "专注故事概念本身：主角在什么异常局面中采取什么行动，故事以什么长期问题牵引读者。必须把方向定位转成可连续展开的故事发动机。",
        "世界架构 Agent": "负责世界核心设定、世界格局、地理环境、历史背景和时代背景；必须把主舞台、空间边界、历史遗留问题和时代压力写成后续剧情可复用的世界基座。",
        "规则力量 Agent": "负责世界规则、力量体系、成长体系、能力分类体系和危险体系；必须说明力量来源、获得条件、代价、克制、寿命影响和强者尺度，避免无代价万能规则。",
        "社会权力 Agent": "负责职业身份、资源、经济、政治权力、势力、社会结构、法律秩序、军事战争、文化信仰、科技生产力、交通通讯、信息舆论、知识教育和日常生活；必须写清普通人与强者如何被制度和资源压迫。",
        "剧情服务 Agent": "负责核心矛盾、主角与世界关系、主要人物群体、主线时间线、隐藏真相和结局后的世界格局；必须检查每项设定是否服务后续人物、主线、分卷和章节。",
        "规则架构 Agent": "专注世界规则的因果链：力量、资源、限制和代价如何运转。每条规则都必须能制造剧情选择，而不是只做背景百科。",
        "原作/检索一致性 Agent": "专注参考资料边界：区分已确认事实、用户自创延展和不确定点；不得把缺证据的内容当成原作设定。",
        "主角弧光 Agent": "专注主角如何在关系中被改变：开局关系缺失、信任能力、关键压力源、最终关系观变化；不得写成升级小传。",
        "关系冲突 Agent": "专注核心关系卡、关系演化时间轴、读者认知进度和秘密信息差；每条核心关系必须有起点、变化、终点和主线作用。",
        "反派/势力 Agent": "专注反派、阵营和组织关系：只能从 worldbuilding 已有势力中提取，说明组织如何压迫人物关系、制造背叛和终局选择。",
        "主线结构 Agent": "重点检查故事起点、引发事件、初始目标、主线问题、目标升级、终局目标是否形成清晰因果链。",
        "冲突升级 Agent": "重点检查冲突是否从个人困境升级到组织阵营、制度规则和终极价值矛盾，并记录胜利代价与失败损失。",
        "人物弧光 Agent": "重点检查主角和关键人物的变化如何被剧情推动，关系链如何变化，反派是否形成镜像。",
        "悬念伏笔 Agent": "重点检查核心悬念、阶段悬念、伏笔布置和真相揭示顺序，避免硬反转。",
        "爽点情绪 Agent": "重点检查核心卖点如何在各阶段持续升级兑现，以及紧张、爽感、心疼、燃、满足等情绪节奏。",
        "终局回收 Agent": "重点检查终局是否回答主线问题、回收人物关系与伏笔，并为分卷衔接和结局路径提供稳定骨架。",
        "分卷架构 Agent": "专注分卷数量、卷名、章节/字数范围、阶段位置、主功能和全书推进逻辑；必须先把每卷定位清楚，再谈具体情节。",
        "卷内推进 Agent": "专注单卷的开卷状态、入卷事件、前期推进、中段转折、低谷、高潮、余波和下卷钩子；卷内过程必须自洽。",
        "人物推进 Agent": "专注主角状态、能力、信念、关键配角、重要关系、新登场/退场、反派推进和信息差变化；关系变化要推动卷内剧情。",
        "世界观释放 Agent": "专注每卷的新地点、新势力、新规则、历史背景、力量体系推进和隐藏真相；世界观信息必须服务卷内冲突。",
        "爽点悬念 Agent": "专注这一卷要兑现的爽点、卖点、升级、反转、悬疑、误导和大场面；所有期待都要落到具体桥段。",
        "衔接约束 Agent": "专注前后卷承接、可选约束和不应擅改内容；判断卷末是否留下足够稳定的下一卷入口。",
        "章节拆分 Agent": "专注目标卷的章节数量、章节范围、区间划分、章节列表总表和每章 profile；章节必须能被写手直接转成章节任务，但不得写成场景卡。",
        "章节钩子 Agent": "专注目标卷内钩子分布、伏笔揭示、读者认知进度和追读动力；过渡/日常/收束章允许轻钩子，不制造无关悬念。",
        "连续性编辑 Agent": "专注目标卷内时间、地点、人物状态、道具、能力限制、关系状态、未揭露信息和跨章因果；发现割裂点时优先提出低成本修补方式。",
        "总编辑 Agent": "专注七阶段整体一致性和可写性；逐项核对前序阶段继承链、锁定来源和最终判定是否一致，判断当前大纲是否已经足够进入章节卡和正文生产。",
        "约束审计 Agent": "专注锁定约束、未决问题和设定边界；区分阻塞型结构问题与非阻塞细节问题，检查是否存在互相冲突或尚未闭环的约束。",
        "章节准备 Agent": "专注下一步章节生产准备度；指出章节卡、场景卡和正文写作前还缺哪些最小信息，以及哪些风险必须在章节卡前解决。",
    }
    if role in focus_map:
        return focus_map[role]
    return f"围绕{STAGE_LABELS.get(stage, stage)}阶段，以{role}的专业职责提出短评；必须只处理本角色负责的问题，不复述其他角色的判断。"


def stage_continuity_requirement(stage: str) -> str:
    requirements = {
        "direction": "方向定位是后续所有阶段的源头：只锁定故事的一句话梗概、核心卖点、类型题材、目标读者、故事承诺、主题表达、主角方向、核心冲突、故事基调和篇幅结构等宏观创作原则，具体世界规则、人物细则和剧情桥段留到后续阶段展开。",
        "concept": "故事概念为旧版兼容阶段，新流程不再主动进入。",
        "worldbuilding": "世界观必须承接方向定位提出的一句话梗概、类型题材、目标读者、故事承诺、主题表达、主角方向、核心冲突、故事基调和篇幅结构；按世界组成部分建立完整基座，每项都要影响主角生存、制造冲突或服务后续剧情。",
        "characters": "人物关系必须承接方向定位和世界观规则；本阶段输出全文关系蓝图，区分作者侧真相、角色侧认知、读者侧认知和剧情侧演化；阵营/组织只能从世界观已有设定提取。",
        "story_flow": "故事流程必须承接方向定位、世界观代价和人物关系冲突；这里的流程是全书级主线骨架，必须覆盖主线推进、阶段划分、冲突升级、人物弧光、伏笔揭示、爽点情绪、分卷衔接和结局路径，但不能写成逐章列表或替代分卷大纲。",
        "volume_outline": "分卷大纲必须整合 direction、worldbuilding、characters 和 story_flow。本阶段只做卷级蓝图：分卷数量、卷功能、每卷目标、卷内推进、人物推进、世界观释放、爽点悬念、情绪节奏、开头结尾、前后卷衔接和可选约束备注。可以给大致章节范围和字数范围，但不得拆成逐章细纲，不得替代 chapter_outline。",
        "chapter_outline": "章节大纲必须承接分卷大纲并按卷渐进生成：每次只生成一整卷章节大纲，当前卷确认后再生成下一卷，最后一卷确认后才进入审稿锁定。每章必须先判定章级功能 profile，再按稳定结构灵活详写、简写或标注本章不适用；不写场景卡或正文。",
        "review_lock": "审稿锁定必须沿前序阶段继承链逐项审计：锁定来源要能回指前序阶段或已锁定产物；阻塞型结构问题必须回改，非阻塞细节问题可以先补齐再锁定；不得新增 canon、重写人物关系、重写剧情流程或生成章节卡/正文。",
    }
    return requirements.get(stage, "本阶段必须承接前序已保存阶段内容继续创作。")


def locked_stage_summary(state: NovelState) -> str:
    parts = []
    for stage in OUTLINE_STAGES:
        artifact = state.outline_stage_artifacts.get(stage)
        if artifact and artifact.get("status") == "locked":
            context = stage_memory_context(artifact, 1800)
            if context:
                parts.append(f"## {STAGE_LABELS[stage]}\n{context}")
    return "\n\n".join(parts) or "暂无"
