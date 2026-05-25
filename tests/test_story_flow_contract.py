from ai_novelist.outline.stage_contracts import STAGE_CONTRACTS


def test_story_flow_contract_has_full_framework():
    contract = STAGE_CONTRACTS["story_flow"]
    labels = "\n".join(slot.label for slot in contract.slots)

    for heading in [
        "故事主线推进",
        "故事阶段划分",
        "核心冲突升级路径",
        "关键剧情节点",
        "人物弧光嵌入流程",
        "伏笔、悬念与揭示节奏",
        "爽点 / 卖点兑现节奏",
        "情绪节奏与阅读体验",
        "世界观展开顺序",
        "阵营与势力推进",
        "代价与失败机制",
        "反转与认知升级",
        "分卷衔接方向",
        "结局路径",
    ]:
        assert heading in labels

    assert len(contract.slots) >= 14
    assert contract.max_questions == 10
    assert contract.max_total_chars is None or contract.max_total_chars >= 6500


def test_story_flow_allowed_intents_cover_full_story_flow_semantics():
    intents = "\n".join(STAGE_CONTRACTS["story_flow"].allowed_intents)

    for keyword in [
        "故事起点",
        "阶段划分",
        "冲突升级",
        "人物弧光嵌入",
        "伏笔悬念",
        "爽点兑现",
        "情绪节奏",
        "世界观展开",
        "阵营推进",
        "失败代价",
        "反转认知",
        "分卷衔接",
        "结局路径",
    ]:
        assert keyword in intents
