from ai_novelist.outline.stage_contracts import STAGE_CONTRACTS


def test_volume_outline_contract_requires_core_blueprint_slots():
    contract = STAGE_CONTRACTS["volume_outline"]
    labels = [slot.label for slot in contract.slots]

    assert contract.label == "分卷大纲"
    assert "卷级蓝图" in contract.purpose
    assert len([slot for slot in contract.slots if slot.required]) == 14
    assert labels == [
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
    ]


def test_volume_outline_contract_relaxes_hard_locking():
    contract = STAGE_CONTRACTS["volume_outline"]
    allowed = "\n".join(contract.allowed_intents)
    forbidden = "\n".join(contract.forbidden_intents)

    assert "卷级约束与待确认项" in allowed
    assert "只输出卷名和卷目标的短摘要" in forbidden
    assert "逐章细纲" in forbidden
    assert "锁定项、可变项、待确认项" not in allowed
    assert contract.max_questions == 3
    assert contract.max_total_chars == 10000
