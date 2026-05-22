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


def test_outline_editor_prompt_keeps_parseable_status_and_review_boundary():
    prompt = load_prompt("outline_editor")

    assert "STATUS: pass|revise|stop" in prompt
    assert "QUALITY_SCORE: 0-100" in prompt
    assert "只审稿，不重写大纲，不新增 canon" in prompt
    assert "修改建议必须指向已有大纲位置" in prompt
    assert "主要问题最多 5 条" in prompt
    assert "修改建议最多 5 条" in prompt
    assert "每条不超过 80 中文字符" in prompt
    assert "不得把建议写成新的稳定设定" in prompt
    for forbidden in ("完整重写大纲", "新增世界观", "人物关系新机制", "章节正文", "长篇分析过程"):
        assert forbidden in prompt


def test_outline_reviser_prompt_defaults_to_minimal_revision():
    prompt = load_prompt("outline_reviser")

    assert "做最小必要修订" in prompt
    assert "默认不要重写完整大纲" in prompt
    assert "只回应 revision_instruction" in prompt
    assert "locked_constraints 必须原样保留" in prompt
    assert "未被修订指令覆盖" in prompt
    assert "不得新增与 revision_instruction 无关的 canon" in prompt
    assert "只有调用方明确要求" in prompt
    assert "变更项最多 8 条" in prompt
    assert "每条不超过 100 中文字符" in prompt
    assert "待确认最多 3 条" in prompt
    assert "修订摘要" in prompt
    assert "保留约束" in prompt
    for forbidden in ("无依据大改", "重写锁定约束", "改动未被要求的世界观/人物关系", "扩写正文"):
        assert forbidden in prompt


def test_chapter_planner_prompt_separates_current_chapter_and_global_modes():
    prompt = load_prompt("chapter_planner")

    assert "当前章节模式" in prompt
    assert "全书章节拆分模式" in prompt
    assert "只输出当前章节写作输入" in prompt
    assert "不建议全书章节数量" in prompt
    assert "不重写全书章节结构" in prompt
    assert "不得新增全局世界观 canon" in prompt
    assert "人物关系机制" in prompt
    assert "不生成场景卡正文" in prompt
    assert "当前章细纲不超过 900 中文字符" in prompt
    assert "场景顺序最多 5 个" in prompt
    assert "全书章节规划 / 拆分全书章节 / 章节总览" in prompt


def test_chapter_goal_agent_prompt_requires_evidence_and_no_new_canon():
    prompt = load_prompt("chapter_goal_agent")

    assert "只输出 JSON" in prompt
    assert "goals" in prompt
    assert "open_questions" in prompt
    assert "evidence" in prompt
    assert "source_hint" in prompt
    assert "每条 goal 必须包含" in prompt
    assert "不能为了补齐目标新增世界观规则" in prompt
    assert "人物关系" in prompt
    assert "依据不足时写入 `open_questions`" in prompt
    assert "不生成完整章节卡" in prompt
    assert "最多 5 条" in prompt
    assert "不超过 80 中文字符" in prompt


def test_chapter_conflict_agent_prompt_requires_source_hints_and_existing_conflicts():
    prompt = load_prompt("chapter_conflict_agent")

    assert "只输出 JSON" in prompt
    assert "conflicts" in prompt
    assert "source_hint" in prompt
    assert "每条 conflict 必须包含" in prompt
    assert "只能识别、提炼和排序已有冲突" in prompt
    assert "不得新增反派" in prompt
    assert "新组织" in prompt
    assert "新世界规则" in prompt
    assert "新长期代价机制" in prompt
    assert "审批/制度机制" in prompt
    assert "minimal_fix_suggestions" in prompt
    assert "最多 5 条" in prompt
    assert "不超过 80 中文字符" in prompt


def test_chapter_hook_agent_prompt_requires_reveal_level_and_existing_foreshadowing():
    prompt = load_prompt("chapter_hook_agent")

    assert "只输出 JSON" in prompt
    assert "hooks" in prompt
    assert "reveal_level" in prompt
    assert "hint" in prompt
    assert "partial" in prompt
    assert "none" in prompt
    assert "每个 hook 必须包含 `source_hint` 和 `reveal_level`" in prompt
    assert "钩子必须来自已有伏笔" in prompt
    assert "当前章节目标" in prompt
    assert "不得提前泄露后续真相" in prompt
    assert "do_not_reveal" in prompt
    for forbidden in ("新增全局真相", "未规划大反转", "新世界规则", "新角色关系", "正文段落"):
        assert forbidden in prompt


def test_chapter_card_synthesizer_prompt_marks_unconfirmed_context_pending():
    prompt = load_prompt("chapter_card_synthesizer")

    assert "只整合当前章节必需信息" in prompt
    assert "不能直接写成 canon" in prompt
    assert "必须标记为“待确认”" in prompt
    assert "场景列表 2-5 个" in prompt
    assert "每节不超过 120 中文字符" in prompt
    assert "整体不超过 1200 中文字符" in prompt
    assert "待确认" in prompt
    assert "确认未新增全局设定" in prompt
    for forbidden in ("新增全局设定", "吸收未确认参考资料", "写正式正文", "扩写无关角色关系", "对白", "细场景动作"):
        assert forbidden in prompt


def test_scene_breakdown_prompt_only_splits_chapter_card():
    prompt = load_prompt("scene_breakdown_agent")

    assert "只基于 Chapter Card" in prompt
    assert "只能拆分 Chapter Card" in prompt
    assert "不能改变章节目标" in prompt
    assert "不写正文、对白" in prompt
    assert "只输出 JSON" in prompt
    assert "scenes" in prompt
    assert "必须是 2-5 个" in prompt
    assert "每个场景字段内容不超过 120 中文字符" in prompt
    for field in ("purpose", "info_delta", "turn", "entry_state", "exit_state"):
        assert field in prompt
    for forbidden in ("新增全局世界观", "新世界规则", "长期人物关系", "章节目标之外的副线"):
        assert forbidden in prompt


def test_scene_conflict_check_prompt_outputs_json_minimal_fixes():
    prompt = load_prompt("scene_conflict_check_agent")

    assert "只输出 JSON，不要 Markdown" in prompt
    assert "issues" in prompt
    assert "最多 5 个" in prompt
    assert "每个建议不超过 80 中文字符" in prompt
    assert "minimal_fix" in prompt
    assert "needs_confirmation" in prompt
    assert "只检查已有场景拆分问题" in prompt
    assert "给最小修正建议" in prompt
    assert "保持场景数量" in prompt
    for forbidden in ("新增场景", "新人物关系", "新世界规则", "新 canon", "大幅重写", "正文"):
        assert forbidden in prompt


def test_scene_synthesizer_prompt_requires_inherited_fields_and_scene_local_details():
    prompt = load_prompt("scene_synthesizer")

    assert "只输出 JSON" in prompt
    assert "scenes" in prompt
    assert "必须是 2-5 个" in prompt
    assert "每场固定 9 个核心字段" in prompt
    assert "每字段不超过 60 中文字符" in prompt
    assert "必须从章节卡、场景拆分报告、冲突检查报告和已有 canon 继承" in prompt
    assert "detail_scope: scene-local" in prompt
    assert "不得写入小说圣经" in prompt
    assert "source_hint" in prompt
    for field in ("location", "characters", "purpose", "character_goal", "conflict_target", "key_information", "emotional_shift", "turn", "exit_state"):
        assert field in prompt
    for forbidden in ("新增全局地点", "组织", "规则", "未规划人物", "无依据感情机制", "正文", "对白"):
        assert forbidden in prompt
