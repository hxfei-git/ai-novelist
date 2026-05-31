from importlib import resources

import pytest

from ai_novelist.prompts import PromptNotFoundError, load_prompt
from ai_novelist.prompts.registry import (
    INLINE_AGENT_NAMES,
    PROMPT_REGISTRY,
    validate_prompt_registry,
)
from ai_novelist.outline.renderers import build_stage_output_rule


def prompt_file_names() -> set[str]:
    return {
        path.name.removesuffix(".md")
        for path in resources.files("ai_novelist.prompts").iterdir()
        if path.name.endswith(".md")
    }


def test_prompt_registry_has_no_missing_files():
    problems = validate_prompt_registry()
    assert problems.missing_files == []


def test_prompt_directory_has_no_orphan_files():
    assert sorted(prompt_file_names() - set(PROMPT_REGISTRY)) == []


def test_author_craft_policy_prompt_names_are_registered():
    from ai_novelist.prompts import AUTHOR_CRAFT_POLICY_PROMPTS

    assert sorted(set(AUTHOR_CRAFT_POLICY_PROMPTS) - set(PROMPT_REGISTRY)) == []


def test_inline_agent_names_are_not_prompt_files():
    assert sorted(set(INLINE_AGENT_NAMES) & prompt_file_names()) == []


def test_load_prompt_from_package():
    assert "AGENT: outline_planner" in load_prompt("outline_planner")


def test_missing_world_builder_prompt_is_gone():
    with pytest.raises(PromptNotFoundError):
        load_prompt("world_builder")



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
    assert "高优先级问题" in prompt
    assert "低优先级问题" in prompt
    assert "建议问题" in prompt
    assert "高优先级问题必须尽量一次性列全" in prompt
    assert "不得因为数量超过 10 条而省略真实阻塞项" in prompt
    assert "高优先级问题工程安全上限 50 条" in prompt
    assert "低优先级问题最多 20 条" in prompt
    assert "建议问题最多 10 条" in prompt
    assert "推荐修改意见" in prompt
    assert "必须使用编号列表" in prompt
    assert "主要问题最多 10 条" not in prompt
    assert "修改建议最多 10 条" not in prompt
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
    assert "待确认最多 10 条" in prompt
    assert "修订摘要" in prompt
    assert "保留约束" in prompt
    for forbidden in ("无依据大改", "重写锁定约束", "改动未被要求的世界观/人物关系", "扩写正文"):
        assert forbidden in prompt


def test_outline_stage_pending_prompts_require_concrete_recommendations():
    reviser = load_prompt("outline_stage_reviser")
    stage_rule = build_stage_output_rule("direction")

    assert "推荐方案" in reviser
    assert "不得只写“按当前建议处理”" in reviser
    assert "推荐方案" in stage_rule
    assert "可直接提交的具体处理结论" in stage_rule


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
