from ai_novelist.prompts import load_prompt


def test_load_prompt_from_package():
    assert "AGENT: world_builder" in load_prompt("world_builder")


def test_direction_proposer_prompt_marks_directions_as_candidates():
    prompt = load_prompt("direction_proposer")

    assert prompt.count("## 方向 ") == 3
    assert "仅供选择" in prompt
    assert "不是小说圣经、稳定 canon 或锁定设定" in prompt
    assert "未选方案不会进入稳定设定" in prompt
    assert "不得违反 locked_constraints" in prompt
    assert "每个方向固定 6 个字段" in prompt
    assert "每字段不超过 60 中文字符" in prompt
    assert "建议选择不超过 120 中文字符" in prompt
    for forbidden in ("审批", "备案", "绩效", "申请表", "KPI", "章节剧情", "人物亲密制度", "已锁定 canon 口吻"):
        assert forbidden in prompt
