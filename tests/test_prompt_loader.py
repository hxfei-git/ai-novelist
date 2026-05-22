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


def test_world_builder_prompt_limits_rules_to_conflict_principles():
    prompt = load_prompt("world_builder")

    assert "3-5 条与主线冲突直接相关的运行原则" in prompt
    assert "每条不超过 100 中文字符" in prompt
    assert "如何制造冲突/代价" in prompt
    assert "具体机制必须来自用户原话、锁定大纲或已有小说圣经" in prompt
    assert "不要补造 canon" in prompt
    assert "可复用素材最多 5 个" in prompt
    assert "说明书式规则清单" in prompt
    for forbidden in ("行政流程", "审批", "备案", "绩效", "申请表", "KPI", "考评"):
        assert forbidden in prompt
    assert "至少 5 条" not in prompt
    assert "硬规则" not in prompt


def test_outline_planner_prompt_requires_confirmed_inputs_and_pending_gaps():
    prompt = load_prompt("outline_planner")

    assert "只整合已有创意、世界观和 locked_constraints" in prompt
    assert "不得为了填满三幕/四段结构补造 canon" in prompt
    assert "写“待确认”" in prompt
    assert "整体不超过 1800 中文字符" in prompt
    assert "每幕/每段最多 4 条" in prompt
    assert "伏笔最多 5 个" in prompt
    assert "不输出正文段落或对白" in prompt
    assert "待确认" in prompt
    for forbidden in ("新增世界观大规则", "人物关系机制", "组织流程", "章节正文", "场景动作", "审批", "备案", "绩效", "申请表", "KPI"):
        assert forbidden in prompt
